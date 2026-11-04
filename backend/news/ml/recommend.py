"""Content-based recommendations using TF-IDF and cosine similarity."""
from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from news.models import Article, ArticleInteraction, SavedArticle

logger = logging.getLogger("newshub.ml")

MAX_CANDIDATES = 400
CANDIDATE_DAYS = 30


def _document(article: Article) -> str:
    category = article.category.name if article.category else ""
    return " ".join(
        [
            article.title,
            article.title,  # headline carries the most signal
            article.description or "",
            (article.content or "")[:600],
            category,
        ]
    ).strip()


def _recency_weight(published_at, half_life_days: float = 7.0) -> float:
    if not published_at:
        return 0.0
    age_days = max((timezone.now() - published_at).total_seconds() / 86400, 0.0)
    return 0.5 ** (age_days / half_life_days)


def _fetch_candidates(exclude_ids: set[int], limit: int = MAX_CANDIDATES) -> list[Article]:
    cutoff = timezone.now() - timedelta(days=CANDIDATE_DAYS)
    base = (
        Article.objects.published()
        .with_relations()
        .exclude(id__in=exclude_ids or [0])
    )
    candidates = list(base.filter(published_at__gte=cutoff).order_by("-published_at")[:limit])
    if len(candidates) < 10:
        candidates = list(base.order_by("-published_at")[:limit])
    return candidates


def _score_articles(
    profile_text: str,
    candidates: list[Article],
    preferred_ids: set[int] | None = None,
    history_ids: set[int] | None = None,
    limit: int = 8,
) -> list[dict]:
    if not candidates or not profile_text.strip():
        return []
    documents = [profile_text] + [_document(article) for article in candidates]
    try:
        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
            max_features=30000,
        )
        matrix = vectorizer.fit_transform(documents)
    except ValueError:  # empty vocabulary
        return []

    similarities = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    preferred_ids = preferred_ids or set()
    history_ids = history_ids or set()
    scored = []
    for index, article in enumerate(candidates):
        similarity = float(similarities[index])
        recency = _recency_weight(article.published_at)
        # Explicit interests outweigh a single saved/read item so one sports
        # article cannot drown out a technology preference.
        boost = 0.0
        if article.category_id in preferred_ids:
            boost += 0.3
        elif article.category_id in history_ids:
            boost += 0.08
        score = 0.78 * similarity + 0.16 * recency + boost
        if similarity <= 0.0 and boost == 0.0:
            continue
        scored.append(
            {
                "article": article,
                "score": round(score, 4),
                "similarity": round(similarity, 4),
                "recency": round(recency, 4),
                "reason": "Related content",
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def recommend_for_article(article: Article, limit: int = 6) -> list[dict]:
    """Similar articles to the one currently being read (same article excluded)."""
    candidates = _fetch_candidates({article.id})
    profile = _document(article)
    boost = {article.category_id} if article.category_id else set()
    recommendations = _score_articles(
        profile, candidates, preferred_ids=boost, limit=limit
    )
    for item in recommendations:
        item["reason"] = (
            f"Similar to this article in {article.category.name}"
            if article.category and item["article"].category_id == article.category_id
            else "Similar topic and wording"
        )
    return recommendations


def _user_profile(user) -> dict:
    """Build a weighted text profile from explicit interests and reading history."""
    parts: list[str] = []
    preferred_ids: set[int] = set()
    history_ids: set[int] = set()

    preference = getattr(user, "preference", None)
    if preference is None:
        from accounts.models import UserPreference

        preference, _ = UserPreference.objects.get_or_create(user=user)
    if preference and preference.personalize_feed:
        for category in preference.preferred_categories.all():
            # Explicit interests carry the strongest weight in the profile text.
            parts.extend([category.name] * 5)
            if category.keywords:
                parts.extend([category.keywords] * 2)
            preferred_ids.add(category.id)

    saved = SavedArticle.objects.filter(user=user).select_related("article")[:20]
    for item in saved:
        parts.append(_document(item.article))
        if item.article.category_id and item.article.category_id not in preferred_ids:
            history_ids.add(item.article.category_id)

    recent = (
        ArticleInteraction.objects.filter(user=user, article__isnull=False)
        .select_related("article")
        .order_by("-timestamp")[:25]
    )
    for interaction in recent:
        parts.append(_document(interaction.article))
        category_id = interaction.article.category_id
        if category_id and category_id not in preferred_ids:
            history_ids.add(category_id)

    return {
        "text": " ".join(parts),
        "preferred_ids": preferred_ids,
        "history_ids": history_ids,
        "personalize": bool(preference and preference.personalize_feed),
    }


def recommend_for_user(user, limit: int = 12) -> list[dict]:
    """Personalized recommendations, with a popularity/recency fallback."""
    saved_ids = set(
        SavedArticle.objects.filter(user=user).values_list("article_id", flat=True)
    )
    seen_ids = set(
        ArticleInteraction.objects.filter(user=user, article__isnull=False)
        .values_list("article_id", flat=True)[:200]
    )
    exclude = saved_ids | seen_ids

    profile = _user_profile(user)
    candidates = _fetch_candidates(exclude)
    if profile["personalize"] and profile["text"].strip():
        recommendations = _score_articles(
            profile["text"],
            candidates,
            preferred_ids=profile["preferred_ids"],
            history_ids=profile["history_ids"],
            limit=limit,
        )
        if recommendations:
            for item in recommendations:
                article = item["article"]
                if article.category_id in profile["preferred_ids"] and article.category:
                    item["reason"] = f"Because you follow {article.category.name}"
                elif article.category_id in profile["history_ids"]:
                    item["reason"] = "Related to articles you read"
                else:
                    item["reason"] = "Similar to your reading interests"
            return recommendations

    return popular_articles(limit=limit, exclude_ids=exclude)


def popular_articles(limit: int = 12, exclude_ids: set[int] | None = None) -> list[dict]:
    """Fallback ranking for new or anonymous visitors: engagement then recency."""
    exclude_ids = exclude_ids or set()
    cutoff = timezone.now() - timedelta(days=7)
    articles = list(
        Article.objects.published()
        .with_relations()
        .exclude(id__in=exclude_ids or [0])
        .filter(published_at__gte=cutoff)
        .order_by("-published_at")[:250]
    )
    if len(articles) < 5:
        articles = list(
            Article.objects.published()
            .with_relations()
            .exclude(id__in=exclude_ids or [0])
            .order_by("-published_at")[:250]
        )

    scored = []
    for article in articles:
        saves = getattr(article, "save_count", None)
        if saves is None:
            saves = article.saves.count()
        score = (
            0.55 * _recency_weight(article.published_at, 3.0)
            + 0.25 * min(saves / 5.0, 1.0)
            + 0.20 * min(article.view_count / 25.0, 1.0)
        )
        scored.append(
            {
                "article": article,
                "score": round(score, 4),
                "similarity": 0.0,
                "recency": round(_recency_weight(article.published_at, 3.0), 4),
                "reason": "Popular with readers" if saves or article.view_count else "Recent coverage",
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def recommendation_debug(user=None, article=None, limit: int = 6) -> dict:
    """Explainable payload used by tests and the admin dashboard."""
    if article:
        items = recommend_for_article(article, limit)
        mode = "article_similarity"
    elif user and user.is_authenticated:
        items = recommend_for_user(user, limit)
        mode = "user_profile"
    else:
        items = popular_articles(limit)
        mode = "popularity_fallback"
    return {
        "mode": mode,
        "items": [
            {
                "article_id": item["article"].id,
                "title": item["article"].title,
                "score": item["score"],
                "similarity": item["similarity"],
                "recency": item["recency"],
                "reason": item["reason"],
            }
            for item in items
        ],
    }
