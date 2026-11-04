from django.test import SimpleTestCase

from news.services.dedupe import (
    build_dedupe_key,
    clean_title,
    is_near_duplicate,
    is_valid_article_url,
    normalize_url,
)


class NormalizationTests(SimpleTestCase):
    def test_tracking_parameters_are_removed(self):
        url = "https://Example.com/story/?utm_source=x&utm_medium=y&id=42#top"
        self.assertEqual(normalize_url(url), "https://example.com/story?id=42")
        self.assertEqual(
            normalize_url("https://example.com/story?utm_source=x"),
            normalize_url("https://example.com/story/"),
        )

    def test_invalid_urls_are_rejected(self):
        self.assertEqual(normalize_url("javascript:alert(1)"), "")
        self.assertFalse(is_valid_article_url("ftp://example.com/a"))
        self.assertFalse(is_valid_article_url("not a url"))
        self.assertTrue(is_valid_article_url("https://example.com/a"))

    def test_publisher_suffix_removed(self):
        self.assertEqual(
            clean_title("Mars mission delayed again - BBC News", "BBC News"),
            "Mars mission delayed again",
        )
        self.assertEqual(
            clean_title(
                "A very long real headline that should stay intact - The Verge",
                "The Verge",
            ),
            "A very long real headline that should stay intact",
        )
        # A dash inside a genuine headline is preserved when no suffix matches.
        self.assertEqual(
            clean_title("Trump - Biden debate draws record audience"),
            "Trump - Biden debate draws record audience",
        )

    def test_dedupe_key_is_stable_across_tracking_params(self):
        left = build_dedupe_key("https://example.com/a?utm_source=newsletter", "Headline")
        right = build_dedupe_key("https://example.com/a/", "Different headline")
        self.assertEqual(left, right)

    def test_near_duplicate_detection(self):
        self.assertTrue(
            is_near_duplicate(
                "OpenAI launches a new reasoning model for developers",
                "OpenAI launches new reasoning model for developers",
            )
        )
        self.assertFalse(
            is_near_duplicate(
                "OpenAI launches a new reasoning model for developers",
                "Parliament passes the annual budget after a long debate",
            )
        )
