from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from accounts.models import UserPreference
from news.tests.factories import PASSWORD, make_user

User = get_user_model()


class AuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def register(self, **overrides):
        payload = {
            "username": "newreader",
            "email": "newreader@example.com",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        }
        payload.update(overrides)
        return self.client.post("/api/auth/register/", payload, format="json")

    def test_register_returns_token_and_creates_preferences(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data["token"])
        self.assertEqual(data["user"]["username"], "newreader")
        self.assertTrue(UserPreference.objects.filter(user__username="newreader").exists())

    def test_register_rejects_mismatched_passwords(self):
        response = self.register(password_confirm="DifferentPass!2026")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password_confirm", response.json())

    def test_register_rejects_duplicate_username_and_email(self):
        make_user("taken")
        self.assertEqual(self.register(username="taken").status_code, 400)
        self.assertEqual(self.register(email="taken@example.com").status_code, 400)

    def test_register_rejects_weak_password(self):
        response = self.register(password="12345678", password_confirm="12345678")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())

    def test_login_with_username_and_email(self):
        make_user("loginuser")
        by_name = self.client.post(
            "/api/auth/login/",
            {"identifier": "loginuser", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(by_name.status_code, 200)
        by_email = self.client.post(
            "/api/auth/login/",
            {"identifier": "loginuser@example.com", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(by_email.status_code, 200)

    def test_login_with_bad_password_fails(self):
        make_user("loginuser")
        response = self.client.post(
            "/api/auth/login/",
            {"identifier": "loginuser", "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())

    def test_profile_requires_auth_and_can_be_updated(self):
        self.assertEqual(self.client.get("/api/auth/profile/").status_code, 401)
        user = make_user("profileuser")
        self.client.force_authenticate(user=user)
        response = self.client.patch(
            "/api/auth/profile/", {"first_name": "Ada"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["first_name"], "Ada")

    def test_logout_invalidates_token(self):
        user = make_user("logoutuser")
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.assertEqual(self.client.get("/api/auth/profile/").status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 200)
        self.assertFalse(Token.objects.filter(user=user).exists())
        self.assertEqual(self.client.get("/api/auth/profile/").status_code, 401)

    def test_preferences_round_trip(self):
        user = make_user("prefuser")
        self.client.force_authenticate(user=user)
        response = self.client.put(
            "/api/user/preferences/",
            {"preferred_categories": ["technology", "science"], "personalize_feed": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = self.client.get("/api/user/preferences/").json()
        self.assertEqual(sorted(data["preferred_categories"]), ["science", "technology"])

    def test_preferences_reject_unknown_category(self):
        user = make_user("prefuser")
        self.client.force_authenticate(user=user)
        response = self.client.put(
            "/api/user/preferences/",
            {"preferred_categories": ["not-a-category"]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_preferences_require_auth(self):
        self.assertEqual(self.client.get("/api/user/preferences/").status_code, 401)
