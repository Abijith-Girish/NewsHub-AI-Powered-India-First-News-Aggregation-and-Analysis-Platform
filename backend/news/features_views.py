"""Additional NewsHub insights: translation, briefings, analytics, NewsLens and TruthTrace."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
import requests
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from rest_framework.views import APIView

from news.ml.story_matching import find_claim_matches, find_story_matches
from news.models import (
    Article,
    ArticleInteraction,
    ClaimEvidence,
    TrackedClaim,
)
from news.serializers import ArticleSerializer
from news.services.article_extraction import extract_article_content
from news.services.llm import chat_completion, is_llm_enabled, llm_provider_label, reset_llm_provider_trace

logger = logging.getLogger("newshub.features")

LANGUAGES = {
    "en": "English",
    "ml": "Malayalam",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
}

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "have", "has", "was",
    "were", "are", "will", "would", "could", "about", "after", "before", "into",
    "over", "under", "said", "says", "their", "they", "them", "than", "then",
    "its", "his", "her", "our", "you", "your", "who", "what", "when", "where",
    "why", "how", "not", "but", "also", "more", "been", "being", "according",
}


def _article_payload(article: Article, request) -> dict:
    return ArticleSerializer(article, context={"request": request}).data


def _split_translation_chunks(text: str, max_chars: int = 3000) -> list[str]:
    chunks = []
    current = ""
    for paragraph in (part.strip() for part in text.split("\n") if part.strip()):
        while len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(paragraph[:max_chars])
            paragraph = paragraph[max_chars:]
        candidate = f"{current}\n{paragraph}".strip() if current else paragraph
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


def _translate_with_libre(text: str, target: str, endpoint: str, api_key: str, timeout: float) -> str:
    translated_parts = []
    for chunk in _split_translation_chunks(text):
        payload = {"q": chunk, "source": "en", "target": target, "format": "text"}
        if api_key:
            payload["api_key"] = api_key
        response = requests.post(endpoint, json=payload, timeout=timeout)
        response.raise_for_status()
        translated = response.json().get("translatedText", "").strip()
        if not translated:
            raise ValueError("The translation provider returned empty text.")
        translated_parts.append(translated)
    return "\n\n".join(translated_parts)


SARVAM_LANGUAGE_CODES = {
    "hi": "hi-IN", "ml": "ml-IN", "ta": "ta-IN",
    "te": "te-IN", "kn": "kn-IN",
}


def _translate_with_sarvam(text: str, target: str, api_key: str, endpoint: str, timeout: float) -> str:
    """Translate through Sarvam's Indian-language API (2,000 chars/request)."""
    translated_parts = []
    for chunk in _split_translation_chunks(text, max_chars=1800):
        response = requests.post(
            endpoint,
            json={
                "input": chunk,
                "source_language_code": "en-IN",
                "target_language_code": SARVAM_LANGUAGE_CODES[target],
                "model": "sarvam-translate:v1",
                "numerals_format": "international",
            },
            headers={"api-subscription-key": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
        translated = (response.json().get("translated_text") or "").strip()
        if not translated:
            raise ValueError("Sarvam returned an empty translation.")
        translated_parts.append(translated)
    return "\n\n".join(translated_parts)


class TranslateArticleView(APIView):
    """Translate publisher/editor-supplied text through LibreTranslate or the configured LLM."""
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"

    def post(self, request):
        article_id = request.data.get("article_id")
        target = str(request.data.get("target_language") or "").lower().strip()
        if target not in LANGUAGES:
            return Response(
                {"detail": f"Choose one of these languages: {', '.join(LANGUAGES.values())}.", "supported_languages": LANGUAGES},
                status=status.HTTP_400_BAD_REQUEST,
            )

        extraction = None
        if article_id:
            article = get_object_or_404(Article.objects.published(), pk=article_id)
            title = article.title
            extraction = extract_article_content(article)
            text = extraction.text
        else:
            title = str(request.data.get("title") or "")[:500]
            text = str(request.data.get("text") or "")[:12000]

        if not (title.strip() or text.strip()):
            return Response({"detail": "There is no article text available to translate."}, status=400)

        # English is already the source language used by the default NewsHub feed.
        if target == "en":
            return Response({
                "target_language": target, "target_language_name": LANGUAGES[target],
                "title": title, "translated_text": text or title,
                "method": "original_text", "content_status": extraction.content_status if extraction else "provided_text",
                "content_note": extraction.note if extraction else "",
                "note": "This is the original English text." + (f" {extraction.note}" if extraction else ""),
            })

        config = settings.NEWSHUB
        libre_url = config.get("TRANSLATION_API_URL")
        libre_key = config.get("TRANSLATION_API_KEY")
        sarvam_key = config.get("SARVAM_API_KEY")
        sarvam_url = config.get("SARVAM_TRANSLATE_API_URL", "https://api.sarvam.ai/translate")
        language = LANGUAGES[target]
        full_text = "\n\n".join(part for part in [title, text] if part).strip()
        cache_digest = hashlib.sha256(full_text.encode("utf-8")).hexdigest()[:24]
        cache_key = f"newshub:translation:{target}:{cache_digest}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        provider_error = None
        translated = ""
        method = ""
        if sarvam_key and target in SARVAM_LANGUAGE_CODES:
            try:
                translated = _translate_with_sarvam(
                    full_text, target, sarvam_key, sarvam_url,
                    config.get("TRANSLATION_TIMEOUT", 25),
                )
                method = "sarvam-translate:v1"
            except Exception as exc:  # noqa: BLE001 - try another configured provider
                provider_error = exc
                logger.warning("Sarvam translation failed: %s", exc)

        if not translated and libre_url:
            try:
                translated = _translate_with_libre(
                    full_text, target, libre_url, libre_key,
                    config.get("TRANSLATION_TIMEOUT", 25),
                )
                method = "libretranslate"
            except Exception as exc:  # noqa: BLE001 - try configured LLM as a fallback
                provider_error = exc
                logger.warning("LibreTranslate failed: %s", exc)

        if not translated and is_llm_enabled():
            try:
                reset_llm_provider_trace()
                chunks = _split_translation_chunks(full_text, max_chars=4200)
                translated_parts = []
                for chunk in chunks:
                    translated_parts.append(chat_completion(
                        [
                            {"role": "system", "content": (
                                f"Translate the supplied news text into {language}. Preserve names, dates, "
                                "numbers, quotations, attribution and uncertainty. Do not add or remove facts. "
                                "Return only the translation and preserve paragraph breaks."
                            )},
                            {"role": "user", "content": chunk},
                        ],
                        max_tokens=1600,
                        temperature=0.0,
                    ))
                translated = "\n\n".join(part.strip() for part in translated_parts if part.strip())
                method = f"llm:{llm_provider_label()}"
            except Exception as exc:  # noqa: BLE001
                provider_error = exc
                logger.warning("LLM translation failed: %s", exc)

        if not translated:
            if not sarvam_key and not libre_url and not is_llm_enabled():
                return Response(
                    {
                        "detail": "Translation requires a provider. Configure SARVAM_API_KEY (recommended for Hindi, Malayalam, Tamil, Telugu and Kannada), TRANSLATION_API_URL for LibreTranslate, or GEMINI_API_KEY/GROQ_API_KEY in backend/.env.",
                        "code": "translation_not_configured",
                    }, status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(
                {"detail": "The configured translation provider could not complete this request. Check the service URL, installed language pair, credentials and backend logs.", "code": "translation_provider_error"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        limited_note = f" {extraction.note}" if extraction and extraction.content_status != "full" else ""
        payload = {
            "target_language": target,
            "target_language_name": language,
            "title": title,
            "translated_text": translated,
            "method": method,
            "content_status": extraction.content_status if extraction else "provided_text",
            "content_note": extraction.note if extraction else "",
            "note": "Machine translation can contain errors. Consult the original publisher for authoritative wording." + limited_note,
        }
        cache.set(cache_key, payload, 60 * 60 * 24)
        return Response(payload)


class ArticleContentView(APIView):
    """Retrieve the best publisher text available for the article reader."""
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "article_content"

    def get(self, request, pk):
        article = get_object_or_404(Article.objects.published(), pk=pk)
        result = extract_article_content(article)
        return Response({
            "article_id": article.id,
            "title": article.title,
            "content": result.text,
            "content_status": result.content_status,
            "content_source": result.content_source,
            "extraction_method": result.method,
            "note": result.note,
            "word_count": result.word_count,
            "source_url": article.source_url,
        })


class DailyBriefingView(APIView):
    """A reproducible daily briefing from the most recent stored reporting."""
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"

    def get(self, request):
        now = timezone.now()
        cutoff = now - timedelta(hours=24)
        queryset = Article.objects.published().with_relations().filter(published_at__gte=cutoff)
        preference_note = "Latest published reporting from NewsHub's stored sources."
        if request.user.is_authenticated:
            try:
                preference = request.user.preference
                if preference.personalize_feed:
                    category_ids = list(preference.preferred_categories.values_list("id", flat=True))
                    if category_ids:
                        queryset = queryset.filter(category_id__in=category_ids) | Article.objects.published().with_relations().filter(published_at__gte=cutoff, is_breaking=True)
                        preference_note = "Prioritizes your selected interests while retaining breaking coverage."
            except Exception:  # user may not yet have a preference row
                pass

        articles = list(queryset.order_by("-is_breaking", "-published_at").distinct()[:10])
        if not articles:
            articles = list(
                Article.objects.published().with_relations()
                .filter(published_at__gte=now - timedelta(days=7))
                .order_by("-published_at")[:8]
            )
            preference_note = "No articles were stored in the last 24 hours; showing the latest available stories from the last seven days."

        if not articles:
            return Response({"generated_at": now.isoformat(), "intro": "No news is available yet. Refresh the news feed and try again.", "stories": [], "note": preference_note})

        topic_count = len({a.category_id for a in articles if a.category_id})
        headline_roundup = "; ".join(article.title.rstrip(". ") for article in articles[:4])
        intro = (
            f"Today's coverage spans {topic_count} topic areas. Key headlines: {headline_roundup}."
            if headline_roundup
            else f"Your briefing contains {len(articles)} recent stories."
        )
        ai_generated = False
        if is_llm_enabled():
            context = "\n".join(
                f"[{a.source_name or 'Publisher'}] {a.title}. {a.description[:500]}"
                for a in articles
            )
            try:
                intro = chat_completion(
                    [
                        {"role": "system", "content": "Write a concise 3-4 sentence daily news briefing using only the supplied headlines and descriptions. Do not infer facts not present. Mention uncertainty and avoid sensational language."},
                        {"role": "user", "content": context[:9000]},
                    ],
                    max_tokens=250,
                    temperature=0.2,
                )
                ai_generated = True
            except Exception as exc:
                logger.info("Daily briefing uses deterministic fallback: %s", exc)

        return Response(
            {
                "generated_at": now.isoformat(),
                "intro": intro,
                "stories": [_article_payload(article, request) for article in articles],
                "note": preference_note,
                "ai_generated": ai_generated,
                "window": "24 hours (seven-day fallback when empty)",
            }
        )


class ReadingEventView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "reading"

    def post(self, request):
        try:
            article_id = int(request.data.get("article_id"))
            seconds = int(request.data.get("duration_seconds", 0))
        except (TypeError, ValueError):
            return Response({"detail": "A valid article_id and duration_seconds are required."}, status=400)
        if seconds < 1 or seconds > 1800:
            return Response({"detail": "Reading duration must be between 1 and 1800 seconds."}, status=400)
        article = get_object_or_404(Article.objects.published(), pk=article_id)
        ArticleInteraction.objects.create(
            user=request.user,
            article=article,
            interaction_type=ArticleInteraction.InteractionType.READ_TIME,
            duration_seconds=seconds,
        )
        return Response({"recorded": True, "duration_seconds": seconds}, status=201)


class ReadingAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        since = timezone.now() - timedelta(days=30)
        base = ArticleInteraction.objects.filter(user=request.user, timestamp__gte=since)
        views = base.filter(interaction_type=ArticleInteraction.InteractionType.VIEW)
        read_events = base.filter(interaction_type=ArticleInteraction.InteractionType.READ_TIME)
        read_seconds = read_events.aggregate(total=Sum("duration_seconds"))["total"] or 0

        category_rows = list(
            views.exclude(article__category__isnull=True)
            .values("article__category__name")
            .annotate(count=Count("id"))
            .order_by("-count")[:8]
        )
        publisher_rows = list(
            views.exclude(article__source_name="")
            .values("article__source_name")
            .annotate(count=Count("id"))
            .order_by("-count")[:8]
        )
        daily_rows = list(
            views.annotate(day=TruncDate("timestamp"))
            .values("day").annotate(count=Count("id"))
            .order_by("day")
        )
        top_rows = list(
            views.values("article_id").annotate(count=Count("id"))
            .order_by("-count")[:5]
        )
        top_ids = [row["article_id"] for row in top_rows]
        view_counts = {row["article_id"]: row["count"] for row in top_rows}
        top_articles = Article.objects.filter(id__in=top_ids).select_related("category", "ml_category")
        top_map = {article.id: article for article in top_articles}
        top_payload = [
            {**_article_payload(top_map[article_id], request), "view_events": view_counts[article_id]}
            for article_id in top_ids if article_id in top_map
        ]
        return Response(
            {
                "period_days": 30,
                "total_article_views": views.count(),
                "unique_articles_read": views.values("article_id").distinct().count(),
                "reading_minutes": round(read_seconds / 60, 1),
                "reading_sessions": read_events.count(),
                "saved_articles": request.user.saved_articles.count(),
                "categories": [{"name": row["article__category__name"], "count": row["count"]} for row in category_rows],
                "publishers": [{"name": row["article__source_name"], "count": row["count"]} for row in publisher_rows],
                "daily_activity": [{"date": row["day"].isoformat(), "views": row["count"]} for row in daily_rows],
                "top_articles": top_payload,
            }
        )


def _keywords(text: str, limit: int = 8) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", (text or "").lower())
    counts = Counter(word for word in words if word not in STOPWORDS)
    return [word for word, _ in counts.most_common(limit)]


class NewsLensView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"

    def get(self, request, pk: int):
        article = get_object_or_404(Article.objects.published().with_relations(), pk=pk)
        matches = find_story_matches(article, limit=10, candidate_limit=600)
        comparisons = []
        for match in matches:
            candidate = match["article"]
            terms = _keywords(f"{candidate.title} {candidate.description}", 12)
            comparisons.append(
                {
                    "article": _article_payload(candidate, request),
                    "similarity": match["similarity"],
                    "tfidf_similarity": match["tfidf_similarity"],
                    "shared_topics": match["shared_topics"][:6],
                    "distinctive_terms": [term for term in terms if term not in match["shared_topics"]][:5],
                    "shared_entities": match["shared_entities"],
                    "shared_event_terms": match.get("shared_event_terms", []),
                    "match_reason": match["match_reason"],
                    "tone": candidate.sentiment_label or "not assessed",
                }
            )
        return Response(
            {
                "anchor": _article_payload(article, request),
                "comparison_count": len(comparisons),
                "publisher_count": len({item["article"]["source"] for item in comparisons if item["article"].get("source")}),
                "comparisons": comparisons,
                "note": (
                    "NewsLens ranks likely same-event coverage using normalized event terms, article text, "
                    "headline overlap, named entities and publication timing. Broad category matches "
                    "alone are excluded. Scores are "
                    "retrieval estimates, not proof that reports describe an identical event or that a "
                    "publisher is biased. Open each source to inspect its reporting."
                ),
            }
        )


def _llm_classify_evidence(claim: str, matches: list[dict]) -> dict[int, tuple[str, str]]:
    """Optionally classify evidence passages; conservative context fallback is used."""
    if not is_llm_enabled() or not matches:
        return {}
    records = []
    for index, match in enumerate(matches[:6]):
        article = match["article"]
        records.append({
            "id": index,
            "title": article.title,
            "publisher": article.source_name,
            "text": (article.content or article.description or article.title)[:1200],
        })
    prompt = (
        "For each news report, determine whether its supplied text directly SUPPORTS, "
        "CONTRADICTS, or only provides CONTEXT for the exact claim. Treat quoted claims, "
        "hypotheticals, denials, and reports about allegations carefully. If it is not explicit, "
        "choose context. Do not infer truth from publisher reputation. Return only valid JSON: "
        '{"items":[{"id":0,"stance":"context|support|contradict","reason":"brief reason"}]}\n\n'
        f"Claim: {claim}\nReports: {json.dumps(records, ensure_ascii=False)}"
    )
    try:
        raw = chat_completion(
            [{"role": "system", "content": "You are a conservative evidence classification assistant."},
             {"role": "user", "content": prompt}],
            max_tokens=700,
            temperature=0.0,
        )
        payload = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
        classified = {}
        for item in payload.get("items", []):
            idx = int(item.get("id"))
            stance = item.get("stance")
            if 0 <= idx < len(records) and stance in {"support", "contradict", "context"}:
                classified[idx] = (stance, str(item.get("reason") or "")[:300])
        return classified
    except Exception as exc:
        logger.info("TruthTrace evidence classification unavailable: %s", exc)
        return {}


def _refresh_claim_evidence(tracked: TrackedClaim) -> None:
    """Attach claim-specific reports and prune stale false positives in the evaluated window."""
    candidates = list(
        Article.objects.published().with_relations()
        .exclude(pk=tracked.article_id)
        .order_by("-published_at")[:900]
    )
    # A linked source article is context, not corroborating evidence. Match the
    # actual user-entered claim against other stored reports to avoid attaching
    # unrelated stories merely because they share a broad topic.
    matches = find_claim_matches(tracked.claim, candidates, limit=15)
    matched_ids = {item["article"].id for item in matches}
    candidate_ids = {item.id for item in candidates}
    # Remove previous low-quality associations only when that article is still
    # inside the candidate window and has failed the stricter current matcher.
    # Older timeline entries outside the window are retained as history.
    tracked.evidence.filter(article_id__in=candidate_ids).exclude(article_id__in=matched_ids).delete()
    existing = set(tracked.evidence.values_list("article_id", flat=True))
    new_matches = [item for item in matches if item["article"].id not in existing]
    stance_map = _llm_classify_evidence(tracked.claim, new_matches)
    for index, match in enumerate(new_matches):
        article = match["article"]
        stance, _reason = stance_map.get(index, ("context", ""))
        evidence_type = {
            "support": ClaimEvidence.EvidenceType.SUPPORT,
            "contradict": ClaimEvidence.EvidenceType.CONTRADICT,
        }.get(stance, ClaimEvidence.EvidenceType.CONTEXT)
        ClaimEvidence.objects.get_or_create(
            tracked_claim=tracked,
            article=article,
            defaults={
                "evidence_type": evidence_type,
                "relevance_score": round(float(match.get("similarity", 0.0)), 3),
            },
        )


def _claim_payload(tracked: TrackedClaim, request) -> dict:
    evidence = tracked.evidence.select_related("article", "article__category").order_by("article__published_at")
    return {
        "id": str(tracked.id),
        "claim": tracked.claim,
        "status": tracked.status,
        "created_at": tracked.created_at.isoformat(),
        "updated_at": tracked.updated_at.isoformat(),
        "source_article": _article_payload(tracked.article, request) if tracked.article_id else None,
        "evidence": [
            {
                "id": item.id,
                "evidence_type": item.evidence_type,
                "relevance_score": item.relevance_score,
                "added_at": item.created_at.isoformat(),
                "article": _article_payload(item.article, request),
            }
            for item in evidence
        ],
        "note": "Related reports are collected as context. They are not automatically labelled as proof for or against the claim.",
    }


class TrackedClaimsView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"

    def get(self, request):
        claims = TrackedClaim.objects.filter(user=request.user).select_related("article").order_by("-updated_at")[:50]
        return Response({"results": [_claim_payload(item, request) for item in claims]})

    def post(self, request):
        article = None
        if request.data.get("article_id"):
            article = get_object_or_404(Article.objects.published(), pk=request.data.get("article_id"))
        claim = str(request.data.get("claim") or (article.title if article else "")).strip()
        if len(claim) < 12 or len(claim) > 2000:
            return Response({"detail": "Enter a claim between 12 and 2000 characters."}, status=400)
        tracked = TrackedClaim.objects.create(user=request.user, article=article, claim=claim)
        _refresh_claim_evidence(tracked)
        return Response(_claim_payload(tracked, request), status=201)


class TrackedClaimDetailView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"

    def get(self, request, claim_id):
        tracked = get_object_or_404(TrackedClaim.objects.select_related("article"), pk=claim_id, user=request.user)
        _refresh_claim_evidence(tracked)
        return Response(_claim_payload(tracked, request))

    def delete(self, request, claim_id):
        tracked = get_object_or_404(TrackedClaim, pk=claim_id, user=request.user)
        tracked.delete()
        return Response({"deleted": True})
