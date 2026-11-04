"""News aggregation pipeline.

External providers -> normalization -> duplicate removal -> categorization ->
sentiment -> SQLite. All network access happens here (server side only).
"""
from __future__ import annotations

import html
import logging
import re
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

from news.feeds import BALANCED_FEEDS, CATEGORY_METADATA, FEEDS_BY_KEY, FEED_KEYS
from news.ml.sentiment import analyze_sentiment
from news.models import Article, Category
from news.providers import NormalizedArticle, fetch_feeds, search_external
from news.services.categorization import invalidate_cache, resolve_category
from news.services.dedupe import (
    build_dedupe_key,
    clean_text,
    clean_title,
    is_near_duplicate,
    is_valid_article_url,
)

logger = logging.getLogger("newshub.aggregator")

LAST_FETCH_KEY = "newshub:last_fetch:{scope}"
SEARCH_MARKER_KEY = "newshub:search_fetch:{key}"


def _cache_key(value: str) -> str:
    import hashlib

    return hashlib.sha1(" ".join(value.lower().split()).encode("utf-8")).hexdigest()


def ensure_categories() -> None:
    """Create the standard category rows if they do not exist yet."""
    created = False
    existing = set(Category.objects.values_list("slug", flat=True))
    for slug, meta in CATEGORY_METADATA.items():
        if slug in existing:
            continue
        Category.objects.update_or_create(
            slug=slug,
            defaults={
                "name": meta["name"],
                "description": meta["description"],
                "keywords": meta["keywords"],
                "display_order": meta["order"],
            },
        )
        created = True
    if created:
        invalidate_cache()


def _recent_titles(days: int = 5) -> list[tuple[str, str, str]]:
    """Return (headline, URL, publisher) triples for publisher-local dedupe."""
    cutoff = timezone.now() - timedelta(days=days)
    return list(
        Article.objects.filter(published_at__gte=cutoff)
        .order_by("-published_at")
        .values_list("title", "source_url", "source_name")[:2000]
    )


def _publisher_host(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
        return host[4:] if host.startswith("www.") else host
    except ValueError:
        return ""


def _publisher_identity(url: str, source_name: str = "") -> str:
    """Use Google News' publisher metadata when its wrapper URL hides the host."""
    host = _publisher_host(url)
    if host in {"news.google.com", "news.googleusercontent.com"}:
        normalized_name = re.sub(r"\s*\(via google news\)\s*", " ", (source_name or "").lower())
        name = re.sub(r"[^a-z0-9]+", " ", normalized_name).strip()
        return f"google-news:{name}" if name else host
    return host


def _apply_article(
    item: NormalizedArticle,
    existing: Article | None,
    known_titles: list[tuple[str, str, str]],
) -> Article | None:
    title = clean_title(item.title, item.source_name)
    if len(title) < 10:
        return None
    description = clean_text(item.description, 1200)
    content = html.unescape(str(item.content or "")).replace("\r\n", "\n").replace("\r", "\n")
    content = re.sub(r"[ \t]+", " ", content)
    content = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", content).strip()
    if len(content) > 20000:
        content = content[:19999].rstrip() + "…"

    resolution = resolve_category(
        title, description, feed_slug=item.category_slug or ""
    )
    categories = {
        category.slug: category
        for category in Category.objects.filter(
            slug__in={
                resolution["category_slug"],
                resolution["ml_category_slug"],
            }
        )
    }

    sentiment = analyze_sentiment(f"{title}. {description}")
    published = item.published_at or timezone.now()
    if timezone.is_naive(published):
        published = timezone.make_aware(published)
    # Some feeds publish future-dated items (scheduled coverage); clamp them so
    # "latest" ordering stays truthful.
    if published > timezone.now() + timedelta(hours=2):
        published = timezone.now()

    defaults = {
        "title": title,
        "description": description,
        "image_url": item.image_url if item.image_url.startswith("http") else "",
        "source_name": clean_text(item.source_name, 190),
        "source_url": item.source_url,
        "author": clean_text(item.author, 250),
        "published_at": published,
        "category": categories.get(resolution["category_slug"]),
        "ml_category": categories.get(resolution["ml_category_slug"] or ""),
        "ml_confidence": resolution["ml_confidence"] or None,
        "category_source": resolution["category_source"],
        "sentiment_label": sentiment["label"],
        "sentiment_score": sentiment["score"],
        "is_breaking": item.is_breaking,
        "provider": item.provider or "rss",
        "retrieved_at": timezone.now(),
    }
    if content:
        defaults["content"] = content
    if item.search_query:
        defaults["search_query"] = clean_text(item.search_query, 290)

    if existing:
        # Preserve editorial overrides and view history on refresh.
        if existing.category_source == Article.CategorySource.MANUAL:
            defaults.pop("category", None)
            defaults.pop("category_source", None)
        for key, value in defaults.items():
            if key == "retrieved_at":
                continue
            if value in (None, "", []) and getattr(existing, key, None):
                continue
            setattr(existing, key, value)
        existing.retrieved_at = timezone.now()
        existing.save()
        return existing

    known_titles.append((title, item.source_url, item.source_name))
    return Article.objects.create(dedupe_key=build_dedupe_key(item.source_url, title), **defaults)


def persist_articles(
    items: list[NormalizedArticle],
    search_query: str = "",
) -> dict:
    """Deduplicate and store normalized articles. Returns ingestion statistics."""
    ensure_categories()
    known_titles = _recent_titles()
    created = updated = skipped = 0
    seen_in_batch: list[tuple[str, str, str]] = []

    for item in items:
        if not is_valid_article_url(item.source_url):
            skipped += 1
            continue
        title = clean_title(item.title, item.source_name)
        if len(title) < 10:
            skipped += 1
            continue

        key = build_dedupe_key(item.source_url, title)
        existing = Article.objects.filter(dedupe_key=key).first()
        # Existing rows are refreshes, not duplicates; only new headlines are
        # compared against the recent corpus.
        # Keep the same event from different publishers. Only suppress repeated
        # copies from the same publisher/domain; cross-publisher copies are
        # valuable input for NewsLens and must remain independently addressable.
        publisher = _publisher_identity(item.source_url, item.source_name)
        recent_same_publisher = [
            old_title for old_title, old_url, old_source in known_titles[-1200:]
            if publisher and _publisher_identity(old_url, old_source) == publisher
        ]
        batch_same_publisher = [
            old_title for old_title, old_url, old_source in seen_in_batch
            if publisher and _publisher_identity(old_url, old_source) == publisher
        ]
        if existing is None and (
            any(is_near_duplicate(title, other) for other in recent_same_publisher)
            or any(is_near_duplicate(title, other) for other in batch_same_publisher)
        ):
            skipped += 1
            continue
        if search_query:
            item.search_query = search_query
        try:
            article = _apply_article(item, existing, known_titles)
        except Exception as exc:  # noqa: BLE001 - one bad item must not stop the batch
            logger.warning("Could not store article %r: %s", title[:80], exc)
            skipped += 1
            continue
        if article is None:
            skipped += 1
            continue
        if existing:
            updated += 1
        else:
            created += 1
            seen_in_batch.append((article.title, article.source_url, article.source_name))

    return {
        "received": len(items),
        "created": created,
        "updated": updated,
        "duplicates_skipped": skipped,
    }


def refresh_feed(
    feed_keys: list[str] | None = None,
    force: bool = False,
    scope: str = "general",
) -> dict:
    """Fetch feeds (throttled by a cache marker) and persist new articles."""
    config = settings.NEWSHUB
    marker = LAST_FETCH_KEY.format(scope=scope)
    if not config["LIVE_FETCH_ENABLED"]:
        return {"skipped": True, "reason": "live_fetch_disabled", "fetched": 0}
    if not force and cache.get(marker):
        return {"skipped": True, "reason": "fresh", "fetched": 0}

    keys = feed_keys or BALANCED_FEEDS
    result = fetch_feeds(keys[: config["MAX_FEEDS"]])
    stats = persist_articles(result.articles)
    cache.set(marker, timezone.now().isoformat(), 60 * config["FRESHNESS_WINDOW_MINUTES"])
    stats.update(
        {
            "skipped": False,
            "providers_attempted": result.providers_attempted,
            "providers_succeeded": result.providers_succeeded,
            "errors": result.errors,
        }
    )
    logger.info(
        "Feed refresh %s: +%s new, %s updated, %s duplicates (%s/%s providers)",
        scope,
        stats["created"],
        stats["updated"],
        stats["duplicates_skipped"],
        result.providers_succeeded,
        result.providers_attempted,
    )
    return stats


def ensure_fresh_content(minimum: int = 15) -> dict | None:
    """Called by public feed endpoints so the home page is never empty."""
    published = Article.objects.published().count()
    marker = cache.get(LAST_FETCH_KEY.format(scope="general"))
    if published >= minimum and marker:
        return None
    try:
        return refresh_feed(force=not marker or published < minimum, scope="general")
    except Exception as exc:  # noqa: BLE001 - never break reading the cached feed
        logger.warning("Background refresh failed: %s", exc)
        return {"skipped": True, "reason": "provider_error", "error": str(exc)}


def ingest_all_feeds() -> dict:
    """Full refresh used by the management command / cron job."""
    return refresh_feed(feed_keys=FEED_KEYS, force=True, scope="all")


def search_news(query: str, limit: int = 30) -> dict:
    """Search external providers for a topic and store the results."""
    marker = SEARCH_MARKER_KEY.format(key=_cache_key(query))
    cached = cache.get(marker)
    result = search_external(query, limit=limit)
    stats = persist_articles(result.articles, search_query=query)
    cache.set(marker, timezone.now().isoformat(), settings.NEWSHUB["CACHE_TTL"])
    stats.update(
        {
            "providers_attempted": result.providers_attempted,
            "providers_succeeded": result.providers_succeeded,
            "errors": result.errors,
            "cached": bool(cached),
        }
    )
    logger.info(
        "Search %r: %s received, %s stored, providers %s/%s",
        query,
        stats["received"],
        stats["created"],
        result.providers_succeeded,
        result.providers_attempted,
    )
    return stats


def source_breakdown() -> list[dict]:
    rows = (
        Article.objects.published()
        .exclude(source_name="")
        .values("source_name")
        .annotate(total=Count("id"))
        .order_by("-total")[:40]
    )
    return [{"source": row["source_name"], "article_count": row["total"]} for row in rows]


def feed_status() -> list[dict]:
    """Configured feeds grouped by publisher. Counts of *stored* articles live in
    ``source_breakdown`` because aggregated items carry the original publisher's
    name (e.g. "BBC News") rather than the feed's name.
    """
    configured = {}
    for key in FEED_KEYS:
        feed = FEEDS_BY_KEY[key]
        configured.setdefault(feed.name, {"name": feed.name, "feeds": [], "categories": set()})
        configured[feed.name]["feeds"].append(feed.key)
        configured[feed.name]["categories"].add(feed.category)
    return [
        {
            "name": name,
            "feed_keys": data["feeds"],
            "categories": sorted(data["categories"]),
            "type": "rss",
        }
        for name, data in configured.items()
    ]
