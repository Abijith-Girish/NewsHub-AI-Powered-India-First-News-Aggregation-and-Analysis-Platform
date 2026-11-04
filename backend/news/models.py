"""Database models for aggregated news, saved articles and fact checks."""
from __future__ import annotations

import hashlib
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    keywords = models.TextField(
        blank=True,
        help_text="Comma separated keywords used by the rule-based category fallback.",
    )
    display_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ArticleQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=Article.Status.PUBLISHED)

    def with_relations(self):
        return self.select_related("category", "ml_category")


class Article(models.Model):
    """A normalized article from an external provider or created by an admin.

    Aggregated items store publisher-supplied feed metadata and, when the
    provider supplies inline full text, that feed content. NewsHub does not
    scrape publisher webpages or bypass paywalls; every item retains its source link.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class CategorySource(models.TextChoices):
        FEED = "feed", "Provider category"
        ML = "ml", "ML classifier"
        RULE = "rule", "Keyword rules"
        MANUAL = "manual", "Editor override"

    class Sentiment(models.TextChoices):
        POSITIVE = "positive", "Positive"
        NEUTRAL = "neutral", "Neutral"
        NEGATIVE = "negative", "Negative"

    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    content = models.TextField(
        blank=True, help_text="Only stored when the provider or editor supplies it."
    )
    image_url = models.URLField(max_length=1000, blank=True)
    source_name = models.CharField(max_length=200, blank=True)
    source_url = models.URLField(max_length=1000, db_index=True)
    author = models.CharField(max_length=300, blank=True)
    published_at = models.DateTimeField(default=timezone.now, db_index=True)
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="articles"
    )
    ml_category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="ml_articles",
    )
    ml_confidence = models.FloatField(null=True, blank=True)
    category_source = models.CharField(
        max_length=10, choices=CategorySource.choices, blank=True
    )
    sentiment_label = models.CharField(
        max_length=10, choices=Sentiment.choices, blank=True
    )
    sentiment_score = models.FloatField(null=True, blank=True)
    is_breaking = models.BooleanField(default=False, db_index=True)
    provider = models.CharField(max_length=80, blank=True)
    search_query = models.CharField(max_length=300, blank=True, db_index=True)
    dedupe_key = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PUBLISHED, db_index=True
    )
    view_count = models.PositiveIntegerField(default=0)
    retrieved_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ArticleQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["-published_at", "status"]),
            models.Index(fields=["category", "-published_at"]),
            models.Index(fields=["source_name"]),
        ]

    def __str__(self) -> str:
        return self.title[:90]

    @property
    def publisher_domain(self) -> str:
        from urllib.parse import urlparse

        try:
            return urlparse(self.source_url).netloc.replace("www.", "")
        except ValueError:  # pragma: no cover - defensive
            return ""

    def related_articles(self, limit: int = 6):
        from news.ml.recommend import recommend_for_article

        return recommend_for_article(self, limit=limit)


class SavedArticle(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_articles"
    )
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="saves")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-saved_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "article"], name="unique_saved_article")
        ]

    def __str__(self) -> str:
        return f"{self.user} saved {self.article_id}"


class ArticleInteraction(models.Model):
    """Lightweight interaction log used to personalize recommendations."""

    class InteractionType(models.TextChoices):
        VIEW = "view", "View"
        SAVE = "save", "Save"
        CLICK = "click", "Outbound click"
        SEARCH = "search", "Search"
        READ_TIME = "read_time", "Reading time"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interactions"
    )
    article = models.ForeignKey(
        Article, null=True, blank=True, on_delete=models.CASCADE, related_name="interactions"
    )
    interaction_type = models.CharField(max_length=10, choices=InteractionType.choices)
    query = models.CharField(max_length=300, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["user", "-timestamp"])]

    def __str__(self) -> str:
        return f"{self.user} {self.interaction_type} {self.article_id or self.query}"


class FactCheck(models.Model):
    """Store the evidence-based credibility analysis of a submitted claim."""

    class Verdict(models.TextChoices):
        SUPPORTED = "supported", "Supported by available evidence"
        CONTRADICTED = "contradicted", "Contradicted by available evidence"
        MIXED = "mixed", "Mixed evidence"
        INSUFFICIENT = "insufficient", "Insufficient evidence"

    reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="fact_checks",
    )
    claim = models.TextField()
    article_title = models.CharField(max_length=500, blank=True)
    source_url = models.URLField(max_length=1000, blank=True)
    verdict = models.CharField(max_length=15, choices=Verdict.choices)
    confidence = models.FloatField(default=0.0)
    explanation = models.TextField(blank=True)
    evidence = models.JSONField(default=list, blank=True)
    related_articles = models.JSONField(default=list, blank=True)
    analysis_notes = models.JSONField(default=dict, blank=True)
    engine = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.verdict}: {self.claim[:60]}"

    @staticmethod
    def fingerprint(claim: str) -> str:
        normalized = " ".join(claim.lower().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


class TrackedClaim(models.Model):
    """A user-followed claim with a chronological set of related reports."""

    class Status(models.TextChoices):
        TRACKING = "tracking", "Tracking"
        PAUSED = "paused", "Paused"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tracked_claims"
    )
    article = models.ForeignKey(
        Article, null=True, blank=True, on_delete=models.SET_NULL, related_name="tracked_claims"
    )
    claim = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.TRACKING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["user", "-updated_at"], name="news_tracked_user_updated")]

    def __str__(self) -> str:
        return self.claim[:90]


class ClaimEvidence(models.Model):
    """Related articles collected for a tracked claim; association is not a verdict."""

    class EvidenceType(models.TextChoices):
        SUPPORT = "support", "Potentially supporting"
        CONTRADICT = "contradict", "Potentially contradicting"
        CONTEXT = "context", "Related context"

    tracked_claim = models.ForeignKey(
        TrackedClaim, on_delete=models.CASCADE, related_name="evidence"
    )
    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="claim_evidence"
    )
    evidence_type = models.CharField(
        max_length=12, choices=EvidenceType.choices, default=EvidenceType.CONTEXT
    )
    relevance_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tracked_claim", "article"], name="unique_claim_article_evidence"
            )
        ]

    def __str__(self) -> str:
        return f"{self.tracked_claim_id}: {self.article_id}"
