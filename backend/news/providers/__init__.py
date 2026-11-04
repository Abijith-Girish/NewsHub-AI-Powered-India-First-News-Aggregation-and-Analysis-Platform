"""Provider registry: parallel RSS fetching plus optional JSON APIs."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.conf import settings

from news.feeds import FEEDS_BY_KEY, FeedConfig
from news.providers.api import fetch_gnews, fetch_newsapi
from news.providers.base import NormalizedArticle, ProviderResult
from news.providers.rss import fetch_feed, google_news_search

logger = logging.getLogger("newshub.providers")


def fetch_feeds(feed_keys: list[str], max_workers: int = 8) -> ProviderResult:
    """Fetch several RSS feeds in parallel with per-feed timeouts."""
    config = settings.NEWSHUB
    feeds: list[FeedConfig] = [FEEDS_BY_KEY[key] for key in feed_keys if key in FEEDS_BY_KEY]
    result = ProviderResult(providers_attempted=len(feeds))
    if not feeds:
        return result

    with ThreadPoolExecutor(max_workers=min(max_workers, len(feeds))) as pool:
        futures = {
            pool.submit(
                fetch_feed,
                feed,
                config["FEED_MAX_ITEMS"],
                config["FETCH_TIMEOUT"],
            ): feed
            for feed in feeds
        }
        for future in as_completed(futures):
            feed = futures[future]
            try:
                articles = future.result()
                result.articles.extend(articles)
                result.providers_succeeded += 1
            except Exception as exc:  # network errors must not break the feed
                logger.warning("Feed %s failed: %s", feed.key, exc)
                result.errors.append(f"{feed.name}: unavailable")
    return result


def search_external(query: str, limit: int = 30) -> ProviderResult:
    """Search Google News RSS plus any configured JSON API providers."""
    config = settings.NEWSHUB
    result = ProviderResult(providers_attempted=1)

    try:
        result.articles.extend(
            google_news_search(query, max_items=limit, timeout=config["FETCH_TIMEOUT"])
        )
        result.providers_succeeded += 1
    except Exception as exc:
        logger.warning("Google News search failed for %r: %s", query, exc)
        result.errors.append("Google News search: unavailable")

    optional = []
    if config["NEWSAPI_KEY"]:
        optional.append(("NewsAPI", fetch_newsapi))
    if config["GNEWS_API_KEY"]:
        optional.append(("GNews", fetch_gnews))

    for name, fetcher in optional:
        result.providers_attempted += 1
        try:
            result.articles.extend(fetcher(query, max_items=limit, timeout=config["FETCH_TIMEOUT"]))
            result.providers_succeeded += 1
        except Exception as exc:
            logger.warning("%s failed for %r: %s", name, query, exc)
            result.errors.append(f"{name}: unavailable")

    return result


__all__ = [
    "fetch_feeds",
    "search_external",
    "NormalizedArticle",
    "ProviderResult",
]
