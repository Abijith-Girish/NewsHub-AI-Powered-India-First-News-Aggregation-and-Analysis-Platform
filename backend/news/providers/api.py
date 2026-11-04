"""Optional JSON news API providers.

Both are disabled automatically when their API key is not configured, so the
application works with RSS only. Keys are read from backend environment
variables and never exposed to the browser.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests
from django.conf import settings

from news.providers.base import NormalizedArticle
from news.services.dedupe import clean_text, is_valid_article_url

logger = logging.getLogger("newshub.providers")

USER_AGENT = settings.NEWSHUB["USER_AGENT"]


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_newsapi(query: str, max_items: int = 20, timeout: float = 8) -> list[NormalizedArticle]:
    key = settings.NEWSHUB["NEWSAPI_KEY"]
    if not key:
        return []
    response = requests.get(
        "https://newsapi.org/v2/everything",
        params={
            "q": query,
            "pageSize": min(max_items, 100),
            "sortBy": "publishedAt",
            "language": "en",
        },
        headers={"X-Api-Key": key, "User-Agent": USER_AGENT},
        timeout=timeout,
    )
    if response.status_code == 401:
        raise ValueError("NewsAPI rejected the configured API key.")
    response.raise_for_status()
    articles = []
    for item in response.json().get("articles", [])[:max_items]:
        url = item.get("url") or ""
        if not is_valid_article_url(url) or not item.get("title"):
            continue
        articles.append(
            NormalizedArticle(
                title=clean_text(item["title"], 490),
                description=clean_text(item.get("description") or "", 1200),
                content=clean_text(item.get("content") or "", 8000),
                source_url=url,
                source_name=clean_text((item.get("source") or {}).get("name", ""), 150),
                image_url=item.get("urlToImage") or "",
                author=clean_text(item.get("author") or "", 250),
                published_at=_parse_iso(item.get("publishedAt")) or datetime.now(tz=timezone.utc),
                provider="newsapi",
                search_query=query,
            )
        )
    return articles


def fetch_gnews(query: str, max_items: int = 20, timeout: float = 8) -> list[NormalizedArticle]:
    key = settings.NEWSHUB["GNEWS_API_KEY"]
    if not key:
        return []
    response = requests.get(
        "https://gnews.io/api/v4/search",
        params={
            "q": query,
            "lang": "en",
            "max": min(max_items, 100),
            "apikey": key,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    if response.status_code in {401, 403}:
        raise ValueError("GNews rejected the configured API key.")
    response.raise_for_status()
    articles = []
    for item in response.json().get("articles", [])[:max_items]:
        url = item.get("url") or ""
        if not is_valid_article_url(url) or not item.get("title"):
            continue
        articles.append(
            NormalizedArticle(
                title=clean_text(item["title"], 490),
                description=clean_text(item.get("description") or "", 1200),
                content=clean_text(item.get("content") or "", 8000),
                source_url=url,
                source_name=clean_text((item.get("source") or {}).get("name", ""), 150),
                image_url=item.get("image") or "",
                author="",
                published_at=_parse_iso(item.get("publishedAt")) or datetime.now(tz=timezone.utc),
                provider="gnews",
                search_query=query,
            )
        )
    return articles
