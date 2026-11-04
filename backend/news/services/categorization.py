"""Assign a display category and an ML prediction to an incoming article.

Publisher sections are trusted when specific (e.g. Business or Sports). Broad
"World" / top-stories feeds are treated as a fallback and can be refined by
strong topic rules so Indian domestic affairs are not displayed as World News.
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache

from news.ml.classifier import classify_article
from news.models import Category

logger = logging.getLogger("newshub.categorization")

_WORD = re.compile(r"[a-z0-9]+")

# High-precision phrase rules for stories commonly misfiled in generic feeds.
# Scores are additive but require multiple signals before overriding a broad
# provider section. Keep phrases specific to avoid classifying every mention
# of a public institution as politics.
STRONG_CATEGORY_RULES = {
    "politics": {
        "supreme court": 3,
        "high court": 3,
        "election commission": 3,
        "local body polls": 3,
        "municipal corporation": 2,
        "civic body": 2,
        "chief minister": 2,
        "prime minister": 2,
        "state assembly": 2,
        "lok sabha": 2,
        "rajya sabha": 2,
        "political party": 2,
        "model code of conduct": 2,
        "brihanmumbai municipal corporation": 2,
        "bmc": 2,
        "tdp": 2,
        "ysrcp": 2,
        "bjp": 1,
        "congress": 1,
        "parliament": 2,
        "minister": 1,
        "commissioner": 1,
        "encroachment": 1,
        "encroachments": 1,
        "polling": 1,
        "vote count": 2,
        "councillor": 1,
        "mayor": 1,
    },
    "business": {
        "quarterly results": 3,
        "stock market": 3,
        "share price": 2,
        "market shares": 2,
        "revenue growth": 2,
        "net profit": 2,
        "central bank": 1,
        "interest rates": 2,
        "inflation rate": 2,
        "merger agreement": 3,
        "acquisition deal": 2,
    },
    "technology": {
        "software update": 2,
        "cybersecurity": 3,
        "data breach": 2,
        "smartphone launch": 2,
        "artificial intelligence": 3,
        "machine learning": 3,
        "chip maker": 2,
        "cloud computing": 2,
    },
    "sports": {
        "cricket match": 3,
        "test match": 3,
        "ipl": 2,
        "world cup": 2,
        "premier league": 2,
        "football match": 3,
        "champions league": 2,
        "olympic games": 2,
    },
    "entertainment": {
        "box office": 3,
        "film festival": 2,
        "movie release": 2,
        "streaming series": 2,
        "music album": 2,
    },
    "health": {
        "public health": 2,
        "clinical trial": 3,
        "health ministry": 2,
        "medical treatment": 2,
        "disease outbreak": 3,
    },
    "education": {
        "board examination": 3,
        "entrance examination": 3,
        "university admission": 2,
        "school education": 2,
        "exam results": 2,
    },
    "science": {
        "scientific study": 2,
        "space mission": 2,
        "research paper": 2,
        "climate research": 2,
        "nasa mission": 2,
    },
}


@lru_cache(maxsize=1)
def _category_cache() -> dict:
    """Slug -> (id, name, keywords) mapping, cleared by `invalidate_cache`."""
    return {
        category.slug: {
            "id": category.id,
            "name": category.name,
            "keywords": [
                keyword.strip().lower()
                for keyword in (category.keywords or "").split(",")
                if keyword.strip()
            ],
        }
        for category in Category.objects.all()
    }


def invalidate_cache() -> None:
    _category_cache.cache_clear()


def _keyword_scores(text: str) -> dict[str, int]:
    lowered = (text or "").lower()
    words = set(_WORD.findall(lowered))
    scores: dict[str, int] = {}
    for slug, data in _category_cache().items():
        score = 0
        for keyword in data["keywords"]:
            if " " in keyword:
                if keyword in lowered:
                    score += 2
            elif keyword in words:
                score += 1
        for phrase, weight in STRONG_CATEGORY_RULES.get(slug, {}).items():
            if phrase in lowered:
                score += weight
        if score:
            scores[slug] = score
    return scores


def keyword_category(text: str) -> tuple[str | None, int]:
    scores = _keyword_scores(text)
    if not scores:
        return None, 0
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    slug, score = ranked[0]
    if len(ranked) > 1 and score == ranked[1][1]:
        return None, score
    return slug, score


def resolve_category(
    title: str,
    description: str = "",
    feed_slug: str = "",
    use_ml: bool = True,
) -> dict:
    """Return display category, its source, and the ML prediction.

    Specific provider sections remain authoritative. Broad ``world`` feeds are
    refined when multiple high-precision topic signals identify a domestic or
    specialist subject. A low-confidence ML prediction never overrides a
    provider section on its own.
    """
    text = f"{title} {description}".strip()
    ml_label, ml_confidence = (None, 0.0)
    if use_ml:
        result = classify_article(title, description)
        ml_label, ml_confidence = result["category"], result["confidence"]

    categories = _category_cache()
    feed_valid = feed_slug if feed_slug in categories else ""
    predicted = ml_label if ml_label in categories else ""
    rule_slug, rule_score = keyword_category(text)

    # Keep explicit/specialist publisher sections. The generic World News
    # section is not specific enough to override strong article-level signals.
    if feed_valid and feed_valid != "world":
        chosen_slug, source = feed_valid, "feed"
    elif rule_slug and rule_score >= 3:
        chosen_slug, source = rule_slug, "rule"
    elif predicted and ml_confidence >= 0.45:
        chosen_slug, source = predicted, "ml"
    elif feed_valid:
        chosen_slug, source = feed_valid, "feed"
    elif rule_slug and rule_score >= 2:
        chosen_slug, source = rule_slug, "rule"
    elif predicted and ml_confidence >= 0.25:
        chosen_slug, source = predicted, "ml"
    else:
        chosen_slug = "world" if "world" in categories else ""
        source = "rule"

    return {
        "category_slug": chosen_slug,
        "category_source": source,
        "ml_category_slug": predicted or "",
        "ml_confidence": round(ml_confidence, 4),
    }
