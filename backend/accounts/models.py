"""Account-level personalization settings."""
from django.conf import settings
from django.db import models


class UserPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preference"
    )
    preferred_categories = models.ManyToManyField(
        "news.Category", blank=True, related_name="preferred_by"
    )
    personalize_feed = models.BooleanField(
        default=True,
        help_text="When enabled, the home feed is ranked using preferred categories and reading history.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Preferences for {self.user}"
