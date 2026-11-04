from django.test import SimpleTestCase

from news.feeds import BALANCED_FEEDS, FEEDS, FEEDS_BY_KEY, GOOGLE_REGION


class IndiaFirstFeedConfigurationTests(SimpleTestCase):
    def test_google_news_uses_india_edition(self):
        self.assertIn("hl=en-IN", GOOGLE_REGION)
        self.assertIn("gl=IN", GOOGLE_REGION)
        self.assertIn("ceid=IN:en", GOOGLE_REGION)

    def test_indian_publishers_are_in_configured_sources(self):
        expected = {
            "the_hindu", "the_hindu_national", "ndtv", "hindustan_times",
            "indian_express", "india_today", "mint", "business_standard",
            "economic_times", "google_toi", "google_wion", "google_news18",
            "google_deccan_herald", "google_firstpost", "google_scroll", "google_the_print",
        }
        self.assertTrue(expected.issubset(FEEDS_BY_KEY.keys()))

    def test_normal_refresh_includes_indian_and_global_publishers(self):
        self.assertIn("the_hindu", BALANCED_FEEDS)
        self.assertIn("ndtv", BALANCED_FEEDS)
        self.assertIn("bbc_world", BALANCED_FEEDS)
        self.assertIn("guardian_world", BALANCED_FEEDS)


    def test_india_first_feed_collection_has_global_sources_and_capacity(self):
        self.assertEqual(len(FEEDS), 47)
        self.assertEqual(len(BALANCED_FEEDS), 31)
        self.assertIn("google_top", BALANCED_FEEDS)
        self.assertIn("bbc_world", BALANCED_FEEDS)

    def test_feed_keys_are_unique(self):
        keys = [feed.key for feed in FEEDS]
        self.assertEqual(len(keys), len(set(keys)))
