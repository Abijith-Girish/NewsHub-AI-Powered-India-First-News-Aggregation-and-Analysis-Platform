"""Article summarization with a local extractive engine and optional LLM.

Guarantees:
* Never adds facts that are not in the supplied text.
* Clearly reports which fields the summary was based on.
* Falls back to extractive summarization when no AI key is configured.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone

from django.core.cache import cache
from sklearn.feature_extraction.text import TfidfVectorizer

from news.exceptions import AIServiceError
from news.services.article_extraction import clean_article_text, extract_article_content
from news.services.llm import (
    chat_completion,
    is_llm_enabled,
    llm_cache_identity,
    llm_provider_label,
    reset_llm_provider_trace,
)

logger = logging.getLogger("newshub.ml")

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
LENGTHS = {
    "short": {"sentences": 2, "words": 70, "label": "Short summary"},
    "detailed": {"sentences": 5, "words": 170, "label": "Detailed summary"},
}


def _sentences(text: str) -> list[str]:
    candidates = [part.strip() for part in SENTENCE_SPLIT.split(text or "") if part.strip()]
    return [sentence for sentence in candidates if len(sentence.split()) >= 5]


def _truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(",;:") + "…"


def _extractive(text: str, title: str, sentence_count: int, max_words: int) -> str:
    sentences = _sentences(text)
    if not sentences:
        return _truncate_words(text.strip(), max_words) if text.strip() else ""

    if len(sentences) <= sentence_count:
        return _truncate_words(" ".join(sentences), max_words)

    try:
        vectorizer = TfidfVectorizer(stop_words="english", sublinear_tf=True)
        matrix = vectorizer.fit_transform(sentences + [title or ""])
    except ValueError:
        return _truncate_words(" ".join(sentences[:sentence_count]), max_words)

    title_vector = matrix[-1]
    scores = []
    for index in range(len(sentences)):
        row = matrix[index]
        title_overlap = 0.0
        if row.nnz and title_vector.nnz:
            title_overlap = float(row.multiply(title_vector).sum())
        length_penalty = 0.0 if 8 <= len(sentences[index].split()) <= 40 else -0.15
        position_bonus = 0.25 if index == 0 else 0.0
        scores.append((float(row.sum()) + title_overlap * 2.0 + position_bonus + length_penalty, index))

    chosen = sorted(index for _, index in sorted(scores, reverse=True)[:sentence_count])
    return _truncate_words(" ".join(sentences[index] for index in chosen), max_words)


def _clean_source_text(value: str) -> str:
    """Use the same boilerplate and duplicate cleanup for all summary inputs."""
    return clean_article_text(value)


def _source_text(article, extraction=None) -> tuple[str, list[str], bool, str, str]:
    """Choose the best available text and preserve its completeness metadata."""
    extraction = extraction or extract_article_content(article)
    text = _clean_source_text(extraction.text or "")
    fields = [extraction.content_source] if text else []
    status = extraction.content_status

    if not text and article.title:
        text = _clean_source_text(article.title)
        fields = ["title"]
        status = "headline_only"

    limited = status != "full"
    return text, fields, limited, status, extraction.note


def _split_chunks(text: str, max_chars: int = 10000) -> list[str]:
    """Split long article text on paragraph/sentence boundaries."""
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text or "") if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs or [text]:
        if len(paragraph) <= max_chars:
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                chunks.append(current)
            current = paragraph
            continue
        # A single very long paragraph is broken at sentence boundaries.
        for sentence in SENTENCE_SPLIT.split(paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            candidate = f"{current} {sentence}".strip() if current else sentence
            if len(candidate) > max_chars and current:
                chunks.append(current)
                current = sentence
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def _llm_summary(article, text: str, length: str) -> str:
    """Summarize full source text, using map/reduce for long articles."""
    spec = LENGTHS[length]
    system = (
        "You are a careful news editor. Summarize ONLY the supplied source text. "
        "Do not add facts, dates, numbers, quotes or opinions that are not present. "
        "Preserve attribution and uncertainty. Return plain text only."
    )
    chunks = _split_chunks(text)
    if len(chunks) <= 1:
        user = (
            f"Article title: {article.title}\nPublisher: {article.source_name or 'unknown'}\n"
            f"Requested format: {spec['label']}, at most {spec['words']} words.\n\n{text}"
        )
        result = chat_completion(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=350 if length == "short" else 650,
            temperature=0.0,
        )
    else:
        partials = []
        for index, chunk in enumerate(chunks, start=1):
            partial = chat_completion(
                [
                    {"role": "system", "content": system + " Summarize this section in 2-3 factual bullet points."},
                    {"role": "user", "content": f"Article: {article.title}\nSection {index}/{len(chunks)}:\n{chunk}"},
                ],
                max_tokens=260,
                temperature=0.0,
            )
            partials.append(partial)
        result = chat_completion(
            [
                {"role": "system", "content": system + " Combine the section notes into one coherent summary without repeating points."},
                {"role": "user", "content": (
                    f"Article: {article.title}\nFormat: {spec['label']}; maximum {spec['words']} words.\n"
                    + "\n\n".join(partials)
                )},
            ],
            max_tokens=350 if length == "short" else 650,
            temperature=0.0,
        )
    result = result.strip()
    if not result:
        raise AIServiceError("The AI service returned an empty summary.")
    return _truncate_words(result, spec["words"])


def summarize_article(article, length: str = "short") -> dict:
    if length not in LENGTHS:
        raise ValueError("length must be 'short' or 'detailed'")
    spec = LENGTHS[length]

    # Extraction runs before cache lookup so a previously cached snippet-only
    # response cannot hide newly available publisher text. The extractor itself
    # caches both successful fetches and short-lived failures.
    extraction = extract_article_content(article)
    text, fields, limited, content_status, extraction_note = _source_text(article, extraction)
    if not text.strip():
        raise ValueError("This article has no text available to summarize.")

    source_fingerprint = hashlib.sha256(
        f"{article.title}\n{text}\n{content_status}".encode("utf-8", errors="ignore")
    ).hexdigest()[:20]
    cache_key = (
        f"newshub:summary:v5:{article.id}:{length}:{llm_cache_identity()}:{source_fingerprint}"
    )
    cached = cache.get(cache_key)
    if cached:
        return cached

    method = "extractive_tfidf"
    warning = ""
    # AI summaries require enough actual body text. Headlines and very short
    # snippets stay local so the UI does not imply a full-article analysis.
    body_word_count = len(text.split())
    has_usable_body = content_status in {"full", "partial"} and body_word_count >= 45
    if is_llm_enabled() and has_usable_body:
        try:
            reset_llm_provider_trace()
            summary = _llm_summary(article, text, length)
            method = f"llm:{llm_provider_label()}"
        except Exception as exc:  # noqa: BLE001 - preserve the local fallback
            logger.warning(
                "LLM summary failed: article_id=%s provider=%s error=%s",
                article.id, llm_provider_label(), exc,
            )
            summary = _extractive(text, article.title, spec["sentences"], spec["words"])
            warning = f"AI summary unavailable: {exc} A local extractive summary is shown."
    else:
        summary = _extractive(text, article.title, spec["sentences"], spec["words"])
        if not is_llm_enabled():
            warning = "AI summarization is not configured. A local extractive summary is shown."
        elif not has_usable_body:
            warning = "There is not enough article body text for a reliable AI summary. " + extraction_note

    if limited and extraction_note and extraction_note not in warning:
        warning = (warning + " " if warning else "") + extraction_note

    if not summary:
        raise ValueError("A summary could not be produced from the available text.")

    result = {
        "article_id": article.id,
        "title": article.title,
        "length": length,
        "summary": summary,
        "method": method,
        "based_on": fields,
        "limited_content": limited,
        "content_status": content_status,
        "content_source": extraction.content_source,
        "extraction_method": extraction.method,
        "extraction_note": extraction_note,
        "extracted_word_count": extraction.word_count,
        "word_count": len(summary.split()),
        "ai_generated": method.startswith("llm:"),
        "warning": warning,
        "source_url": article.source_url,
        "source_name": article.source_name,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "disclaimer": (
            "Automatically generated from the text available to NewsHub. Always check the original "
            "publisher article before relying on details."
        ),
    }
    # AI summaries can be cached longer; local fallback summaries are brief-lived
    # so a retry can use newly available publisher content or provider availability.
    cache.set(cache_key, result, 60 * 60 * 6 if result["ai_generated"] else 30)
    return result


def summarize_text(title: str, text: str, length: str = "short") -> dict:
    """Ad-hoc summary used by the standalone AI endpoint."""
    if length not in LENGTHS:
        raise ValueError("length must be 'short' or 'detailed'")
    spec = LENGTHS[length]
    combined = " ".join(part for part in [text or ""] if part).strip()
    if not combined and not title:
        raise ValueError("Provide article text to summarize.")

    method = "extractive_tfidf"
    warning = ""
    if is_llm_enabled() and len(combined.split()) >= 15:
        try:
            reset_llm_provider_trace()
            system = (
                "You summarize news text. Use only the supplied text; never invent facts. "
                f"Write at most {spec['sentences']} sentences and {spec['words']} words."
            )
            summary = chat_completion(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"Title: {title}\n\nText:\n{combined[:6000]}"},
                ],
                max_tokens=300 if length == "short" else 500,
                temperature=0.1,
            )
            method = f"llm:{llm_provider_label()}"
        except Exception as exc:  # noqa: BLE001 - local summary remains available
            logger.info("LLM text summary failed: %s", exc)
            summary = _extractive(combined or title, title, spec["sentences"], spec["words"])
            warning = f"AI summary unavailable: {exc} A local extractive summary is shown."
    else:
        summary = _extractive(combined or title, title, spec["sentences"], spec["words"])

    return {
        "length": length,
        "summary": summary,
        "method": method,
        "based_on": ["text"] if combined else ["title"],
        "limited_content": not combined,
        "word_count": len(summary.split()),
        "ai_generated": method.startswith("llm:"),
        "warning": warning,
        "disclaimer": (
            "Automatically generated from the supplied text; verify against the source."
        ),
    }
