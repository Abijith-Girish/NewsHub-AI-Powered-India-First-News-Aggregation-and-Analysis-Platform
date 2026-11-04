from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from news.models import Article, ArticleInteraction, Category, ClaimEvidence, FactCheck, SavedArticle, TrackedClaim


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "display_order", "article_total")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("display_order",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_count=Count("articles"))

    @admin.display(description="Articles", ordering="_count")
    def article_total(self, obj):
        return obj._count


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "source_name",
        "category",
        "status",
        "is_breaking",
        "published_at",
        "category_source",
    )
    list_filter = ("status", "category", "category_source", "is_breaking", "source_name")
    search_fields = ("title", "description", "source_name", "author")
    date_hierarchy = "published_at"
    autocomplete_fields = ("category", "ml_category")
    readonly_fields = (
        "dedupe_key",
        "provider",
        "retrieved_at",
        "created_at",
        "updated_at",
        "view_count",
        "ml_confidence",
        "sentiment_label",
        "sentiment_score",
        "source_link",
    )
    actions = ("mark_published", "mark_archived", "flag_breaking")
    list_per_page = 30

    fieldsets = (
        ("Content", {"fields": ("title", "description", "content", "image_url", "author")}),
        ("Source", {"fields": ("source_name", "source_url", "source_link", "provider")}),
        (
            "Classification",
            {
                "fields": (
                    "category",
                    "category_source",
                    "ml_category",
                    "ml_confidence",
                    "sentiment_label",
                    "sentiment_score",
                )
            },
        ),
        ("Publishing", {"fields": ("status", "is_breaking", "published_at")}),
        (
            "Internal",
            {
                "classes": ("collapse",),
                "fields": (
                    "dedupe_key",
                    "search_query",
                    "view_count",
                    "retrieved_at",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(description="Original article")
    def source_link(self, obj):
        if not obj.source_url:
            return "—"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">Open publisher page</a>',
            obj.source_url,
        )

    @admin.action(description="Publish selected articles")
    def mark_published(self, request, queryset):
        queryset.update(status=Article.Status.PUBLISHED)

    @admin.action(description="Archive selected articles")
    def mark_archived(self, request, queryset):
        queryset.update(status=Article.Status.ARCHIVED)

    @admin.action(description="Flag selected articles as breaking")
    def flag_breaking(self, request, queryset):
        queryset.update(is_breaking=True)


@admin.register(SavedArticle)
class SavedArticleAdmin(admin.ModelAdmin):
    list_display = ("user", "article", "saved_at")
    search_fields = ("user__username", "article__title")
    raw_id_fields = ("user", "article")


@admin.register(ArticleInteraction)
class ArticleInteractionAdmin(admin.ModelAdmin):
    list_display = ("user", "interaction_type", "article", "query", "duration_seconds", "timestamp")
    list_filter = ("interaction_type",)
    search_fields = ("user__username", "query")
    raw_id_fields = ("user", "article")


@admin.register(FactCheck)
class FactCheckAdmin(admin.ModelAdmin):
    list_display = ("claim_excerpt", "verdict", "confidence", "user", "created_at")
    list_filter = ("verdict", "engine")
    search_fields = ("claim", "article_title")
    readonly_fields = (
        "reference",
        "claim",
        "article_title",
        "source_url",
        "verdict",
        "confidence",
        "explanation",
        "evidence",
        "related_articles",
        "analysis_notes",
        "engine",
        "created_at",
        "user",
    )

    @admin.display(description="Claim")
    def claim_excerpt(self, obj):
        return obj.claim[:80]


@admin.register(TrackedClaim)
class TrackedClaimAdmin(admin.ModelAdmin):
    list_display = ("claim_excerpt", "user", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at")
    search_fields = ("claim", "user__username")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Claim")
    def claim_excerpt(self, obj):
        return obj.claim[:100]


@admin.register(ClaimEvidence)
class ClaimEvidenceAdmin(admin.ModelAdmin):
    list_display = ("tracked_claim", "article", "evidence_type", "relevance_score", "created_at")
    list_filter = ("evidence_type", "created_at")
    search_fields = ("tracked_claim__claim", "article__title")
