"""Refresh ML predictions and rule-based display categories for stored articles.

Manual/editor overrides and specific publisher sections remain untouched.
Generic ``world`` feed assignments are re-evaluated because broad top-story
feeds often contain domestic politics, business, technology and sports items.
"""
from django.core.management.base import BaseCommand

from news.models import Article, Category
from news.services.categorization import invalidate_cache, resolve_category


class Command(BaseCommand):
    help = "Refresh category predictions and refine generic World News assignments."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=2000)

    def handle(self, *args, **options):
        invalidate_cache()
        categories = {category.slug: category for category in Category.objects.all()}
        queryset = Article.objects.select_related("category", "ml_category").order_by("-published_at")[: options["limit"]]
        changed = 0
        for article in queryset:
            feed_slug = article.category.slug if article.category_id else ""
            resolution = resolve_category(
                article.title,
                article.description,
                feed_slug=feed_slug,
            )
            article.ml_confidence = resolution["ml_confidence"] or None
            article.ml_category = categories.get(resolution["ml_category_slug"] or "")

            # Never overwrite editorial decisions. Preserve an explicit
            # publisher section unless it was the generic World News bucket.
            is_manual = article.category_source == Article.CategorySource.MANUAL
            is_specific_feed = (
                article.category_source == Article.CategorySource.FEED
                and feed_slug
                and feed_slug != "world"
            )
            if not is_manual and not is_specific_feed:
                article.category = categories.get(resolution["category_slug"] or "")
                article.category_source = resolution["category_source"]

            article.save(update_fields=[
                "ml_category",
                "ml_confidence",
                "category",
                "category_source",
                "updated_at",
            ])
            changed += 1
        self.stdout.write(self.style.SUCCESS(f"Reclassified {changed} articles."))
