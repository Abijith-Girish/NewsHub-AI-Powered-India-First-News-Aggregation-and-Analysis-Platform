from unittest.mock import Mock, patch

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from news.models import ArticleInteraction, ClaimEvidence, TrackedClaim
from news.tests.factories import make_article, make_user


class ReaderInsightApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user("insights_reader")
        self.article = make_article(
            "New technology research changes local computing",
            description="Researchers reported a new computing method.",
            content="The publisher supplied the full article text.",
            source_name="Research Wire",
        )

    @patch("news.features_views.extract_article_content")
    def test_article_content_endpoint_returns_extraction_status(self, extract):
        extract.return_value = type("Result", (), {
            "text": "A full publisher article body with several paragraphs.",
            "content_status": "full",
            "content_source": "publisher_page",
            "method": "beautifulsoup_fallback",
            "note": "Full article text was available from the publisher page.",
            "word_count": 180,
            "source_url": self.article.source_url,
        })()
        response = self.client.get(f"/api/news/{self.article.id}/content/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content_status"], "full")
        self.assertEqual(response.json()["content_source"], "publisher_page")
        self.assertEqual(response.json()["word_count"], 180)

    def test_daily_briefing_returns_stored_articles_without_llm(self):
        with patch("news.features_views.is_llm_enabled", return_value=False):
            response = self.client.get("/api/ai/daily-briefing/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["stories"])
        self.assertFalse(response.json()["ai_generated"])

    def test_news_lens_returns_honest_empty_state(self):
        response = self.client.get(f"/api/news/{self.article.id}/newslens/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["comparison_count"], 0)
        self.assertIn("not proof", response.json()["note"])

    def test_news_lens_matches_same_event_from_a_different_publisher(self):
        related = make_article(
            "ISRO launches new Earth observation satellite from Sriharikota",
            description="The Indian space agency launched an Earth observation satellite on its latest mission.",
            content="ISRO launched the Earth observation satellite from Sriharikota on Tuesday. The mission will provide updated remote sensing data.",
            source_name="India News Network",
            source_url="https://indianews.example.org/isro-earth-observation-launch",
            category_slug="science",
        )
        unrelated = make_article(
            "New smartphone launches with improved camera features",
            description="A technology company announced a new mobile phone.",
            source_name="Gadget Daily",
            source_url="https://gadget.example.org/new-smartphone-launch",
            category_slug="technology",
        )
        self.article.title = "ISRO launches Earth observation satellite from Sriharikota"
        self.article.description = "The Indian space agency launched a new Earth observation satellite."
        self.article.content = "ISRO launched an Earth observation satellite from Sriharikota on Tuesday. The new satellite is designed to provide remote sensing data."
        self.article.source_url = "https://science.example.com/isro-launch"
        self.article.source_name = "Science News"
        self.article.save()

        response = self.client.get(f"/api/news/{self.article.id}/newslens/")
        self.assertEqual(response.status_code, 200)
        comparison_ids = [row["article"]["id"] for row in response.json()["comparisons"]]
        self.assertIn(related.id, comparison_ids)
        self.assertNotIn(unrelated.id, comparison_ids)

    def test_reading_event_requires_authentication(self):
        response = self.client.post(
            "/api/analytics/reading-event/",
            {"article_id": self.article.id, "duration_seconds": 20},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_reading_event_and_analytics(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/analytics/reading-event/",
            {"article_id": self.article.id, "duration_seconds": 45},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        analytics = self.client.get("/api/analytics/reading/")
        self.assertEqual(analytics.status_code, 200)
        self.assertEqual(analytics.json()["reading_minutes"], 0.8)

    def test_truth_trace_can_be_created_and_listed(self):
        self.client.force_authenticate(user=self.user)
        created = self.client.post(
            "/api/truth-trace/",
            {"article_id": self.article.id, "claim": self.article.title},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(TrackedClaim.objects.filter(user=self.user).count(), 1)
        self.assertEqual(ClaimEvidence.objects.count(), 0)
        listed = self.client.get("/api/truth-trace/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()["results"]), 1)

    def test_translation_fails_clearly_without_configured_service(self):
        with patch("news.features_views.is_llm_enabled", return_value=False):
            response = self.client.post(
                "/api/ai/translate/",
                {"article_id": self.article.id, "target_language": "ml"},
                format="json",
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "translation_not_configured")

    @patch("news.features_views.requests.post")
    @patch("news.features_views.is_llm_enabled", return_value=False)
    def test_translation_uses_sarvam_for_indian_languages(self, _llm_enabled, post):
        post.return_value = Mock(
            status_code=200,
            json=lambda: {"translated_text": "ഇത് ഒരു പരിശോധനയാണ്."},
        )
        config = {
            **settings.NEWSHUB,
            "SARVAM_API_KEY": "test-key",
            "SARVAM_TRANSLATE_API_URL": "https://api.sarvam.ai/translate",
        }
        with patch("news.features_views.settings.NEWSHUB", config):
            response = self.client.post(
                "/api/ai/translate/",
                {"article_id": self.article.id, "target_language": "ml"},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["method"], "sarvam-translate:v1")
        self.assertIn("translated_text", response.json())
        request_kwargs = post.call_args.kwargs
        self.assertEqual(request_kwargs["headers"]["api-subscription-key"], "test-key")
        self.assertEqual(request_kwargs["json"]["target_language_code"], "ml-IN")
