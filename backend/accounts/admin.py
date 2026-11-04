from django.contrib import admin

from accounts.models import UserPreference


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "personalize_feed", "updated_at")
    filter_horizontal = ("preferred_categories",)
    search_fields = ("user__username", "user__email")
