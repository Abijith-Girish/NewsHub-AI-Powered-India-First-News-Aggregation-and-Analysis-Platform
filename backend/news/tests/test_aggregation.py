from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from news.models import Article, Category
from news.providers.base import NormalizedArticle, ProviderResult
from news.services import aggregator


def normalized(**overrides):
    defaults = {
        "title": "Quantum chip startup raises new funding round",
        "description": "The company said the investment will fund a larger research team.",
        "source_url": "https://example.com/quantum-chip-funding",
        "source_name": "Example Wire",
        "published_at": timezone.now().astimezone(dt_timezone.utc),
        "provider": "rss",
        "feed_key": "test_feed",
        "category_slug": "technology",
    }
    defaults.update(overrides)
    return NormalizedArticle(**defaults)


class AggregationTests(TestCase):
    def setUp(self):
        cache.clear()
        aggregator.ensure_categories()

    def test_categories_are_created(self):
        self.assertEqual(Category.objects.count(), 10)
        self.assertTrue(Category.objects.filter(slug="artificial-intelligence").exists())

    @patch("news.services.aggregator.fetch_feeds")
    def test_refresh_stores_articles_and_sets_category(self, fetch_feeds):
        fetch_feeds.return_value = ProviderResult(
            articles=[normalized(), normalized(
                title="Parliament debates the new budget",
                source_url="https://example.com/budget-debate",
                category_slug="politics",
            )],
            providers_attempted=1,
            providers_succeeded=1,
        )
        stats = aggregator.refresh_feed(force=True)
        self.assertEqual(stats["created"], 2)
        self.assertEqual(Article.objects.count(), 2)
        article = Article.objects.get(source_url="https://example.com/quantum-chip-funding")
        self.assertEqual(article.category.slug, "technology")
        self.assertEqual(article.category_source, Article.CategorySource.FEED)
        self.assertIsNotNone(article.ml_confidence)
        self.assertTrue(article.dedupe_key)
        self.assertIn(article.sentiment_label, {"positive", "neutral", "negative"})

    @patch("news.services.aggregator.fetch_feeds")
    def test_repeat_ingest_updates_instead_of_duplicating(self, fetch_feeds):
        fetch_feeds.return_value = ProviderResult(
            articles=[normalized()], providers_attempted=1, providers_succeeded=1
        )
        aggregator.refresh_feed(force=True)
        stats = aggregator.refresh_feed(force=True)
        self.assertEqual(Article.objects.count(), 1)
        self.assertEqual(stats["created"], 0)
        self.assertEqual(stats["updated"], 1)

    @patch("news.services.aggregator.fetch_feeds")
    def test_same_story_from_different_publishers_is_preserved(self, fetch_feeds):
        fetch_feeds.return_value = ProviderResult(
            articles=[
                normalized(title="Global markets rally after rate decision"),
                normalized(
                    title="Global markets rally after the rate decision",
                    source_url="https://other.example.com/markets-rally",
                    source_name="Other Wire",
                ),
            ],
            providers_attempted=2,
            providers_succeeded=2,
        )
        stats = aggregator.refresh_feed(force=True)
        self.assertEqual(stats["created"], 2)
        self.assertEqual(stats["duplicates_skipped"], 0)

    @patch("news.services.aggregator.fetch_feeds")
    def test_google_news_wrapper_uses_publisher_metadata_for_dedupe(self, fetch_feeds):
        fetch_feeds.return_value = ProviderResult(
            articles=[
                normalized(
                    title="India announces new Earth observation satellite mission",
                    source_url="https://news.google.com/rss/articles/AAA?oc=5",
                    source_name="The Hindu",
                ),
                normalized(
                    title="India announces new Earth observation satellite mission",
                    source_url="https://news.google.com/rss/articles/BBB?oc=5",
                    source_name="WION",
                ),
            ],
            providers_attempted=2,
            providers_succeeded=2,
        )
        stats = aggregator.refresh_feed(force=True)
        self.assertEqual(stats["created"], 2)
        self.assertEqual(stats["duplicates_skipped"], 0)

    @patch("news.services.aggregator.fetch_feeds")
    def test_same_publisher_near_duplicate_is_deduplicated(self, fetch_feeds):
        fetch_feeds.return_value = ProviderResult(
            articles=[
                normalized(title="Global markets rally after rate decision"),
                normalized(
                    title="Global markets rally after the rate decision",
                    source_url="https://www.example.com/markets-rally-updated",
                    source_name="Example Wire",
                ),
            ],
            providers_attempted=1,
            providers_succeeded=1,
        )
        stats = aggregator.refresh_feed(force=True)
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["duplicates_skipped"], 1)

    @patch("news.services.aggregator.fetch_feeds")
    def test_invalid_urls_and_short_titles_are_dropped(self, fetch_feeds):
        fetch_feeds.return_value = ProviderResult(
            articles=[
                normalized(source_url="javascript:alert(1)"),
                normalized(title="Short", source_url="https://example.com/short"),
            ],
            providers_attempted=1,
            providers_succeeded=1,
        )
        stats = aggregator.refresh_feed(force=True)
        self.assertEqual(stats["created"], 0)
        self.assertEqual(Article.objects.count(), 0)

    @patch("news.services.aggregator.search_external")
    def test_topic_search_persists_results(self, search_external):
        search_external.return_value = ProviderResult(
            articles=[
                normalized(
                    title="Artificial intelligence rules debated by regulators",
                    source_url="https://example.com/ai-rules",
                    category_slug="",
                )
            ],
            providers_attempted=2,
            providers_succeeded=1,
        )
        stats = aggregator.search_news("artificial intelligence")
        self.assertEqual(stats["created"], 1)
        article = Article.objects.first()
        self.assertEqual(article.search_query, "artificial intelligence")
        self.assertIsNotNone(article.category)

    @patch("news.services.aggregator.fetch_feeds")
    def test_editor_override_survives_refresh(self, fetch_feeds):
        fetch_feeds.return_value = ProviderResult(
            articles=[normalized()], providers_attempted=1, providers_succeeded=1
        )
        aggregator.refresh_feed(force=True)
        article = Article.objects.first()
        article.category = Category.objects.get(slug="business")
        article.category_source = Article.CategorySource.MANUAL
        article.save()

        aggregator.refresh_feed(force=True)
        article.refresh_from_db()
        self.assertEqual(article.category.slug, "business")
        self.assertEqual(article.category_source, Article.CategorySource.MANUAL)
