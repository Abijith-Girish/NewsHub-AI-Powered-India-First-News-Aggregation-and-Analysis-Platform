"""Small helpers for building deterministic test data."""
from __future__ import annotations

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from news.models import Article, Category
from news.services.aggregator import ensure_categories
from news.services.dedupe import build_dedupe_key

User = get_user_model()

PASSWORD = "Str0ngPass!2026"


def make_user(username: str = "reader", staff: bool = False, email: str | None = None):
    ensure_categories()
    return User.objects.create_user(
        username=username,
        email=email or f"{username}@example.com",
        password=PASSWORD,
        is_staff=staff,
        is_superuser=staff,
    )


def category(slug: str) -> Category:
    ensure_categories()
    return Category.objects.get(slug=slug)


def make_article(
    title: str = "Test headline about technology",
    *,
    category_slug: str | None = "technology",
    description: str = "A description with enough words to look like news copy.",
    content: str = "",
    source_name: str = "Test Wire",
    source_url: str | None = None,
    published_at=None,
    is_breaking: bool = False,
    status: str = Article.Status.PUBLISHED,
    ml_confidence: float | None = 0.8,
    sentiment_label: str = "neutral",
):
    url = source_url or f"https://example.com/{uuid.uuid4().hex}"
    return Article.objects.create(
        title=title,
        description=description,
        content=content,
        source_name=source_name,
        source_url=url,
        published_at=published_at or timezone.now(),
        category=category(category_slug) if category_slug else None,
        ml_category=category(category_slug) if category_slug else None,
        ml_confidence=ml_confidence,
        category_source=Article.CategorySource.ML if category_slug else "",
        status=status,
        is_breaking=is_breaking,
        sentiment_label=sentiment_label,
        sentiment_score=0.0,
        dedupe_key=build_dedupe_key(url, title),
    )


def make_old_article(days: int = 10, **kwargs):
    return make_article(published_at=timezone.now() - timedelta(days=days), **kwargs)
