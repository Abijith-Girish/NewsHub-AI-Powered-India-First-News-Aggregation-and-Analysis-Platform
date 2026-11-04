"""RSS/Atom providers, including Google News topic and search feeds."""
from __future__ import annotations

import calendar
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup
from django.conf import settings

from news.feeds import FeedConfig
from news.providers.base import NormalizedArticle
from news.services.dedupe import clean_text, clean_title, is_valid_article_url

logger = logging.getLogger("newshub.providers")

USER_AGENT = settings.NEWSHUB["USER_AGENT"]


def _published(entry) -> datetime | None:
    for attribute in ("published_parsed", "updated_parsed", "created_parsed"):
        value = getattr(entry, attribute, None)
        if value:
            try:
                return datetime.fromtimestamp(calendar.timegm(value), tz=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                continue
    return None


def _plain_summary(entry, title: str) -> str:
    """Convert an RSS summary to readable text and drop link-only dumps."""
    raw = entry.get("summary") or entry.get("description") or ""
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    text = clean_text(soup.get_text(" ", strip=True))
    # Google News descriptions are just a list of links repeating the headline.
    if "news.google.com/rss/articles" in raw or raw.count("<a ") > 2:
        return ""
    if text.lower().startswith(title.lower()[:60].lower()):
        return ""
    return text[:1200]



def _full_content(entry) -> str:
    """Extract full text only when an RSS/Atom provider supplies it inline."""
    candidates = []
    for item in entry.get("content", []) or []:
        if isinstance(item, dict) and item.get("value"):
            candidates.append(item["value"])
    encoded = entry.get("content_encoded") or entry.get("content:encoded")
    if encoded:
        candidates.append(encoded)
    for raw in candidates:
        soup = BeautifulSoup(str(raw), "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text("\n\n", strip=True)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text).strip()
        if len(text) > 20000:
            text = text[:19999].rstrip() + "…"
        if len(text) > 250:
            return text
    return ""


def _first_image(entry) -> str:
    for field in ("media_content", "media_thumbnail"):
        for item in entry.get(field, []) or []:
            url = item.get("url")
            if url and url.startswith("http"):
                return url
    for enclosure in entry.get("enclosures", []) or []:
        url = enclosure.get("href") or enclosure.get("url")
        media_type = enclosure.get("type", "")
        if url and (media_type.startswith("image") or media_type == ""):
            if url.startswith("http"):
                return url
    image = entry.get("image")
    if isinstance(image, dict) and image.get("href"):
        return image["href"]
    raw = entry.get("summary") or ""
    if "<img" in raw:
        soup = BeautifulSoup(raw, "html.parser")
        tag = soup.find("img")
        if tag and tag.get("src", "").startswith("http"):
            return tag["src"]
    return ""


def _entry_source_name(entry, feed: FeedConfig) -> str:
    source = entry.get("source")
    if isinstance(source, dict) and source.get("title"):
        return clean_text(source["title"], 150)
    return feed.name


def fetch_feed(feed: FeedConfig, max_items: int, timeout: float) -> list[NormalizedArticle]:
    """Fetch and normalize one RSS feed. Raises requests.RequestException on failure."""
    response = requests.get(
        feed.url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml"},
    )
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"Malformed feed: {feed.name}")

    articles: list[NormalizedArticle] = []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
    for entry in parsed.entries[:max_items]:
        link = clean_text(entry.get("link", ""))
        if not is_valid_article_url(link):
            continue
        title = clean_title(entry.get("title", ""), feed.name)
        if not title:
            continue
        published = _published(entry) or datetime.now(tz=timezone.utc)
        if published < cutoff:
            continue
        source_name = _entry_source_name(entry, feed)
        is_breaking = bool(
            feed.breaking_source
            and datetime.now(tz=timezone.utc) - published <= timedelta(hours=3)
        )
        articles.append(
            NormalizedArticle(
                title=title,
                description=_plain_summary(entry, title),
                content=_full_content(entry),
                source_url=link,
                source_name=source_name,
                image_url=_first_image(entry),
                author=clean_text(entry.get("author", ""), 250),
                published_at=published,
                provider="rss",
                feed_key=feed.key,
                category_slug=feed.category,
                is_breaking=is_breaking,
            )
        )
    return articles


def google_news_search(query: str, max_items: int = 25, timeout: float = 8) -> list[NormalizedArticle]:
    """Search Google News RSS. No API key is required."""
    url = (
        "https://news.google.com/rss/search?q="
        f"{quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"
    )
    feed = FeedConfig(
        key=f"google_search:{query}",
        name="Google News",
        url=url,
        category="",
    )
    articles = fetch_feed(feed, max_items=max_items, timeout=timeout)
    for article in articles:
        article.search_query = query
        article.provider = "google_news_search"
        article.is_breaking = False
    return articles
