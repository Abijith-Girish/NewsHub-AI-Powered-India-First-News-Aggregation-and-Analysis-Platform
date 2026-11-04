from django.test import TestCase

from news.services.aggregator import ensure_categories
from news.services.categorization import invalidate_cache, resolve_category


class CategoryResolutionTests(TestCase):
    def setUp(self):
        ensure_categories()
        invalidate_cache()

    def test_domestic_civic_court_story_overrides_generic_world_feed(self):
        result = resolve_category(
            "Supreme Court Pauses Mumbai Civic Body Chief's Salary Over Encroachments",
            "The Mumbai municipal corporation commissioner was directed to remove illegal encroachments.",
            feed_slug="world",
            use_ml=False,
        )
        self.assertEqual(result["category_slug"], "politics")
        self.assertEqual(result["category_source"], "rule")

    def test_specific_publisher_category_is_preserved(self):
        result = resolve_category(
            "Supreme Court pauses Mumbai civic body chief's salary",
            "The court issued directions to the municipal corporation.",
            feed_slug="business",
            use_ml=False,
        )
        self.assertEqual(result["category_slug"], "business")
        self.assertEqual(result["category_source"], "feed")

    def test_generic_world_story_without_strong_topic_signal_stays_world(self):
        result = resolve_category(
            "A community festival draws visitors to a coastal town",
            "Residents welcomed visitors during the annual cultural event.",
            feed_slug="world",
            use_ml=False,
        )
        self.assertEqual(result["category_slug"], "world")
        self.assertEqual(result["category_source"], "feed")
