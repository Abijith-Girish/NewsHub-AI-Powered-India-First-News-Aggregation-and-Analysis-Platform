from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from news.models import Article, ArticleInteraction, SavedArticle
from news.tests.factories import make_article, make_old_article, make_user
from news.services import aggregator


@patch("news.views._ensure_fresh", lambda: None)
class PublicNewsApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.tech = make_article(
            "New artificial intelligence model runs on laptops",
            category_slug="technology",
            description="A compact model for local inference.",
            source_name="Tech Wire",
        )
        self.politics = make_article(
            "Parliament approves the annual budget",
            category_slug="politics",
            source_name="City Press",
            description="Lawmakers voted after a long debate.",
        )
        self.old = make_old_article(
            days=20,
            title="Older science discovery announced last month",
            category_slug="science",
            source_name="Science Wire",
        )
        self.breaking = make_article(
            "Breaking: major earthquake strikes coastal region",
            category_slug="world",
            is_breaking=True,
            source_name="Wire Service",
        )

    def test_news_list_is_paginated_and_ordered(self):
        response = self.client.get("/api/news/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 4)
        self.assertEqual(data["results"][0]["title"], self.breaking.title)
        self.assertIn("meta", data)
        self.assertEqual(data["results"][0]["source"], "Wire Service")

    def test_filter_by_category_and_source(self):
        by_category = self.client.get("/api/news/?category=technology").json()
        self.assertEqual(by_category["count"], 1)
        self.assertEqual(by_category["results"][0]["id"], self.tech.id)

        by_source = self.client.get("/api/news/?source=City%20Press").json()
        self.assertEqual(by_source["count"], 1)
        self.assertEqual(by_source["results"][0]["id"], self.politics.id)

    def test_advanced_search_filters_and_empty_exclusions(self):
        # An empty `exclude` parameter must not generate an icontains="" filter.
        all_articles = self.client.get("/api/news/?exclude=").json()
        self.assertEqual(all_articles["count"], 4)

        exact = self.client.get("/api/news/?exact=annual%20budget&author=Unknown").json()
        self.assertEqual(exact["count"], 0)

        filtered = self.client.get("/api/news/?exact=annual%20budget&exclude=rumour").json()
        self.assertEqual(filtered["count"], 1)
        self.assertEqual(filtered["results"][0]["id"], self.politics.id)

    def test_date_filter_and_oldest_sort(self):
        today = self.client.get("/api/news/?date=today").json()
        self.assertEqual(today["count"], 3)
        oldest = self.client.get("/api/news/?sort=oldest").json()
        self.assertEqual(oldest["results"][0]["id"], self.old.id)

    def test_advanced_date_filters_reject_invalid_future_and_reversed_ranges(self):
        future = (timezone.localdate() + timedelta(days=1)).isoformat()
        invalid = self.client.get("/api/news/?from_date=2026-02-30")
        self.assertEqual(invalid.status_code, 400)
        future_response = self.client.get(f"/api/news/?to_date={future}")
        self.assertEqual(future_response.status_code, 400)
        reversed_response = self.client.get("/api/news/?from_date=2026-10-20&to_date=2026-10-01")
        self.assertEqual(reversed_response.status_code, 400)

    @patch("news.views.aggregator.search_news")
    def test_search_rejects_future_date_before_provider_call(self, search_news):
        future = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.client.get(f"/api/news/search/?q=india&to_date={future}")
        self.assertEqual(response.status_code, 400)
        search_news.assert_not_called()

    def test_breaking_endpoint(self):
        data = self.client.get("/api/news/breaking/").json()
        self.assertFalse(data["fallback"])
        self.assertEqual(len(data["results"]), 1)
        self.assertTrue(data["results"][0]["is_breaking"])

    def test_breaking_endpoint_fallback_is_honest(self):
        Article.objects.update(is_breaking=False)
        data = self.client.get("/api/news/breaking/").json()
        self.assertTrue(data["fallback"])
        self.assertTrue(data["note"])
        self.assertFalse(any(item["is_breaking"] for item in data["results"]))

    def test_trending_returns_real_counts(self):
        data = self.client.get("/api/news/trending/").json()
        self.assertIn("topics", data)
        self.assertIn("stories", data)
        for topic in data["topics"]:
            self.assertGreaterEqual(topic["article_count"], 2)

    def test_article_detail_and_view_tracking(self):
        user = make_user()
        self.client.force_authenticate(user=user)
        response = self.client.get(f"/api/news/{self.tech.id}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("article", data)
        self.assertIn("recommendations", data)
        self.assertIn("content", data["article"])
        self.tech.refresh_from_db()
        self.assertEqual(self.tech.view_count, 1)
        self.assertTrue(
            ArticleInteraction.objects.filter(user=user, article=self.tech).exists()
        )
        ids = [item["id"] for item in data["recommendations"]]
        self.assertNotIn(self.tech.id, ids)

    def test_unpublished_article_is_hidden_from_public(self):
        draft = make_article("Secret draft headline about mergers", status=Article.Status.DRAFT)
        response = self.client.get(f"/api/news/{draft.id}/")
        self.assertEqual(response.status_code, 404)

    def test_recommendations_are_scored_and_exclude_current(self):
        make_article(
            "Machine learning tool improves laptop inference",
            category_slug="technology",
            description="Local artificial intelligence inference on a laptop.",
        )
        response = self.client.get(f"/api/news/{self.tech.id}/recommendations/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["mode"], "content_based_tfidf_cosine")
        ids = [item["id"] for item in data["results"]]
        self.assertNotIn(self.tech.id, ids)
        self.assertTrue(all("match_score" in item for item in data["results"]))

    def test_recommended_feed_for_anonymous(self):
        data = self.client.get("/api/news/recommended/").json()
        self.assertEqual(data["mode"], "popularity")
        self.assertTrue(data["results"])

    def test_preferences_drive_personalized_feed(self):
        user = make_user()
        self.client.force_authenticate(user=user)
        self.client.put(
            "/api/user/preferences/",
            {"preferred_categories": ["politics"], "personalize_feed": True},
            format="json",
        )
        data = self.client.get("/api/news/recommended/").json()
        self.assertEqual(data["mode"], "personalized")
        self.assertTrue(data["results"])

    def test_save_and_unsave_article(self):
        user = make_user()
        self.client.force_authenticate(user=user)
        response = self.client.post(f"/api/news/{self.tech.id}/save/")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(SavedArticle.objects.filter(user=user, article=self.tech).exists())

        repeat = self.client.post(f"/api/news/{self.tech.id}/save/")
        self.assertEqual(repeat.status_code, 200)

        saved = self.client.get("/api/user/saved-news/").json()
        self.assertEqual(saved["count"], 1)
        self.assertEqual(saved["results"][0]["id"], self.tech.id)

        delete = self.client.delete(f"/api/news/{self.tech.id}/save/")
        self.assertEqual(delete.status_code, 200)
        self.assertFalse(SavedArticle.objects.filter(user=user).exists())

    def test_save_requires_authentication(self):
        response = self.client.post(f"/api/news/{self.tech.id}/save/")
        self.assertEqual(response.status_code, 401)

    def test_categories_include_counts(self):
        data = self.client.get("/api/categories/").json()
        tech = next(item for item in data["results"] if item["slug"] == "technology")
        self.assertEqual(tech["article_count"], 1)

    def test_category_feed_endpoint(self):
        response = self.client.get("/api/news/category/technology/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["category"]["slug"], "technology")

    @patch("news.views.aggregator.search_news")
    def test_search_returns_ranked_results(self, search_news):
        search_news.return_value = {
            "received": 0, "created": 0, "updated": 0, "skipped": 0,
            "providers_succeeded": 1, "providers_attempted": 1, "errors": [],
        }
        data = self.client.get("/api/news/search/?q=laptop").json()
        self.assertGreaterEqual(data["count"], 1)
        self.assertEqual(data["meta"]["query"], "laptop")
        self.assertIn("matched_stored_articles", data["meta"])

    @patch("news.views.aggregator.search_news")
    def test_search_impossible_query_returns_empty_state(self, search_news):
        search_news.return_value = {
            "received": 0, "created": 0, "updated": 0, "skipped": 0,
            "providers_succeeded": 1, "providers_attempted": 1, "errors": [],
        }
        data = self.client.get("/api/news/search/?q=zzzzqqqq").json()
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["results"], [])

    def test_search_rejects_short_query(self):
        response = self.client.get("/api/news/search/?q=a")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_query")

    @patch("news.views.aggregator.search_news")
    def test_search_reports_provider_outage(self, search_news):
        search_news.return_value = {
            "received": 0, "created": 0, "updated": 0, "skipped": 0,
            "providers_succeeded": 0, "providers_attempted": 1,
            "errors": ["Google News search: unavailable"],
        }
        response = self.client.get("/api/news/search/?q=unfindabletopicxyz")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "provider_unavailable")

    def test_health_endpoint(self):
        data = self.client.get("/api/health/").json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["published_articles"], 4)
