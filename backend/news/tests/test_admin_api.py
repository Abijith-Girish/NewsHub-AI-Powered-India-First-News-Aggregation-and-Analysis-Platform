from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from news.models import Article, Category
from news.tests.factories import category, make_article, make_user

PAYLOAD = {
    "title": "Editor written announcement about new services",
    "description": "A manually written article used to test admin content management.",
    "source_name": "NewsHub Editorial",
    "source_url": "https://newshub.example.com/editorial/announcement",
    "status": "published",
}


class AdminPermissionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.reader = make_user("reader")
        self.staff = make_user("editor", staff=True)

    def test_anonymous_and_regular_users_are_blocked(self):
        self.assertIn(self.client.get("/api/admin/dashboard/").status_code, (401, 403))
        self.client.force_authenticate(user=self.reader)
        self.assertEqual(self.client.get("/api/admin/dashboard/").status_code, 403)
        self.assertEqual(self.client.post("/api/admin/news/", PAYLOAD, format="json").status_code, 403)

    def test_staff_can_create_update_and_delete_articles(self):
        self.client.force_authenticate(user=self.staff)
        created = self.client.post(
            "/api/admin/news/", {**PAYLOAD, "category": category("business").id}, format="json"
        )
        self.assertEqual(created.status_code, 201)
        article = Article.objects.get(pk=created.json()["id"])
        self.assertEqual(article.category_source, Article.CategorySource.MANUAL)
        self.assertEqual(article.status, Article.Status.PUBLISHED)

        patched = self.client.patch(
            f"/api/admin/news/{article.id}/",
            {"title": "Updated editorial announcement headline"},
            format="json",
        )
        self.assertEqual(patched.status_code, 200)
        article.refresh_from_db()
        self.assertEqual(article.title, "Updated editorial announcement headline")

        deleted = self.client.delete(f"/api/admin/news/{article.id}/")
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(Article.objects.filter(pk=article.id).exists())

    def test_duplicate_source_url_is_rejected(self):
        self.client.force_authenticate(user=self.staff)
        existing = make_article("Original editorial headline about markets")
        response = self.client.post(
            "/api/admin/news/",
            {**PAYLOAD, "source_url": existing.source_url},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("source_url", response.json())

    def test_invalid_url_is_rejected(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            "/api/admin/news/", {**PAYLOAD, "source_url": "not-a-url"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_dashboard_shape(self):
        make_article("Dashboard article about artificial intelligence")
        self.client.force_authenticate(user=self.staff)
        data = self.client.get("/api/admin/dashboard/").json()
        for key in ("articles", "users", "engagement", "categories", "model", "providers"):
            self.assertIn(key, data)
        self.assertEqual(data["articles"]["published"], 1)
        self.assertEqual(data["users"]["total"], 2)
        self.assertTrue(data["model"]["available"])

    def test_review_queue_and_accept_ml_category(self):
        article = make_article(
            "Quantum startup releases new chip for data centres",
            category_slug="business",
        )
        article.ml_category = category("technology")
        article.ml_confidence = 0.35
        article.category_source = Article.CategorySource.ML
        article.save()

        self.client.force_authenticate(user=self.staff)
        queue = self.client.get("/api/admin/review-queue/").json()
        self.assertGreaterEqual(queue["count"], 1)

        response = self.client.post(
            f"/api/admin/news/{article.id}/category/", {"accept_ml": True}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        article.refresh_from_db()
        self.assertEqual(article.category.slug, "technology")
        self.assertEqual(article.category_source, Article.CategorySource.ML)

    def test_manual_category_override(self):
        article = make_article("Sports report about the championship final")
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            f"/api/admin/news/{article.id}/category/",
            {"category_slug": "entertainment"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        article.refresh_from_db()
        self.assertEqual(article.category.slug, "entertainment")
        self.assertEqual(article.category_source, Article.CategorySource.MANUAL)

    def test_category_management(self):
        self.client.force_authenticate(user=self.staff)
        created = self.client.post(
            "/api/admin/categories/",
            {"name": "Climate", "slug": "climate", "description": "Climate coverage"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        category_id = created.json()["id"]

        linked = make_article("Climate article for deletion guard", category_slug="technology")
        linked.category = Category.objects.get(pk=category_id)
        linked.save()

        blocked = self.client.delete(f"/api/admin/categories/{category_id}/")
        self.assertEqual(blocked.status_code, 400)

        linked.category = category("technology")
        linked.save()
        deleted = self.client.delete(f"/api/admin/categories/{category_id}/")
        self.assertEqual(deleted.status_code, 200)

    def test_users_endpoint_lists_activity(self):
        self.client.force_authenticate(user=self.staff)
        data = self.client.get("/api/admin/users/").json()
        usernames = {item["username"] for item in data["results"]}
        self.assertEqual(usernames, {"reader", "editor"})
        self.assertIn("saved_count", data["results"][0])
