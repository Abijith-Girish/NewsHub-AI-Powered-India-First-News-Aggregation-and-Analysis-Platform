"""Trending topics computed from stored article headlines.

No synthetic statistics: every count reported here is the number of stored
articles in the current window whose headline contains the term.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone
from sklearn.feature_extraction.text import TfidfVectorizer

from news.models import Article

logger = logging.getLogger("newshub.trending")

GENERIC_TERMS = {
    "news", "update", "updates", "report", "reports", "live", "latest", "today",
    "week", "year", "says", "said", "new", "first", "last", "more", "after",
    "amid", "over", "into", "from", "with", "that", "this", "will", "could",
    "would", "may", "why", "how", "what", "who", "when", "where", "here",
}


def _titles(hours: int, limit: int) -> list[str]:
    cutoff = timezone.now() - timedelta(hours=hours)
    titles = list(
        Article.objects.published()
        .filter(published_at__gte=cutoff)
        .order_by("-published_at")
        .values_list("title", flat=True)[:limit]
    )
    if len(titles) < 8:
        titles = list(
            Article.objects.published()
            .order_by("-published_at")
            .values_list("title", flat=True)[:limit]
        )
    return [title for title in titles if title]


def trending_topics(limit: int = 10, hours: int = 48) -> list[dict]:
    titles = _titles(hours, 500)
    if len(titles) < 3:
        return []

    try:
        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            min_df=2,
            max_features=600,
            sublinear_tf=True,
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b",
        )
        matrix = vectorizer.fit_transform(titles)
    except ValueError:
        return []

    terms = vectorizer.get_feature_names_out()
    weights = matrix.sum(axis=0).A1
    document_counts = (matrix > 0).sum(axis=0).A1

    candidates = []
    for index, term in enumerate(terms):
        tokens = term.split()
        if any(token in GENERIC_TERMS for token in tokens):
            continue
        if any(token.isdigit() or len(token) < 3 for token in tokens):
            continue
        count = int(document_counts[index])
        if count < 2:
            continue
        candidates.append(
            {
                "topic": term.title() if len(term) > 4 else term.upper(),
                "normalized": term,
                "article_count": count,
                "score": round(float(weights[index]), 3),
            }
        )

    # Prefer meaningful two-word phrases (e.g. "artificial intelligence") over
    # their individual words, then rank by TF-IDF weight.
    candidates.sort(
        key=lambda item: (
            len(item["normalized"].split()),
            item["score"],
            item["article_count"],
        ),
        reverse=True,
    )

    selected: list[dict] = []
    used_phrases: list[set[str]] = []
    for candidate in candidates:
        tokens = set(candidate["normalized"].split())
        if any(tokens <= phrase or phrase <= tokens for phrase in used_phrases):
            continue
        selected.append(candidate)
        used_phrases.append(tokens)
        if len(selected) >= limit:
            break
    return selected


def trending_stories(limit: int = 6, hours: int = 72) -> list[Article]:
    cutoff = timezone.now() - timedelta(hours=hours)
    queryset = (
        Article.objects.published()
        .with_relations()
        .filter(published_at__gte=cutoff)
        .order_by("-published_at")[:200]
    )
    articles = list(queryset)
    if not articles:
        articles = list(Article.objects.published().with_relations().order_by("-published_at")[:200])
    for article in articles:
        article.engagement = article.saves.count() * 3 + article.view_count
    articles.sort(
        key=lambda item: (item.engagement, item.published_at.timestamp()), reverse=True
    )
    return articles[:limit]
