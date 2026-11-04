from django.urls import path

from news import admin_views, ai_views, features_views, views

urlpatterns = [
    # Public news
    path("health/", views.HealthView.as_view(), name="health"),
    path("news/", views.NewsListView.as_view(), name="news-list"),
    path("news/latest/", views.LatestNewsView.as_view(), name="news-latest"),
    path("news/breaking/", views.BreakingNewsView.as_view(), name="news-breaking"),
    path("news/trending/", views.TrendingView.as_view(), name="news-trending"),
    path("news/search/", views.SearchView.as_view(), name="news-search"),
    path("news/recommended/", views.RecommendedFeedView.as_view(), name="news-recommended"),
    path("news/sources/", views.SourcesView.as_view(), name="news-sources"),
    path("news/category/<slug:slug>/", views.CategoryNewsView.as_view(), name="news-category"),
    path("news/<int:pk>/", views.ArticleDetailView.as_view(), name="news-detail"),
    path("news/<int:pk>/content/", features_views.ArticleContentView.as_view(), name="news-article-content"),
    path(
        "news/<int:pk>/recommendations/",
        views.ArticleRecommendationsView.as_view(),
        name="news-recommendations",
    ),
    path("news/<int:pk>/save/", views.SaveArticleView.as_view(), name="news-save"),
    path("categories/", views.CategoriesView.as_view(), name="categories"),
    path("user/saved-news/", views.SavedNewsView.as_view(), name="saved-news"),

    # AI / ML
    path("ai/summarize/", ai_views.SummarizeView.as_view(), name="ai-summarize"),
    path("ai/sentiment/", ai_views.SentimentView.as_view(), name="ai-sentiment"),
    path("ai/translate/", features_views.TranslateArticleView.as_view(), name="ai-translate"),
    path("ai/daily-briefing/", features_views.DailyBriefingView.as_view(), name="ai-daily-briefing"),
    path("analytics/reading-event/", features_views.ReadingEventView.as_view(), name="reading-event"),
    path("analytics/reading/", features_views.ReadingAnalyticsView.as_view(), name="reading-analytics"),
    path("news/<int:pk>/newslens/", features_views.NewsLensView.as_view(), name="news-newslens"),
    path("truth-trace/", features_views.TrackedClaimsView.as_view(), name="truth-trace-list-create"),
    path("truth-trace/<int:claim_id>/", features_views.TrackedClaimDetailView.as_view(), name="truth-trace-detail"),
    path("ml/categorize/", ai_views.CategorizeView.as_view(), name="ml-categorize"),
    path("ml/metrics/", ai_views.MLMetricsView.as_view(), name="ml-metrics"),
    path("fact-check/", ai_views.FactCheckView.as_view(), name="fact-check"),
    path(
        "fact-check/history/",
        ai_views.FactCheckHistoryView.as_view(),
        name="fact-check-history",
    ),
    path(
        "fact-check/<uuid:reference>/",
        ai_views.FactCheckDetailView.as_view(),
        name="fact-check-detail",
    ),

    # Admin
    path("admin/news/", admin_views.AdminArticleListCreateView.as_view(), name="admin-news"),
    path(
        "admin/news/<int:pk>/",
        admin_views.AdminArticleDetailView.as_view(),
        name="admin-news-detail",
    ),
    path(
        "admin/news/<int:pk>/category/",
        admin_views.AdminCategoryReviewView.as_view(),
        name="admin-news-category",
    ),
    path(
        "admin/review-queue/",
        admin_views.AdminReviewQueueView.as_view(),
        name="admin-review-queue",
    ),
    path(
        "admin/categories/",
        admin_views.AdminCategoriesView.as_view(),
        name="admin-categories",
    ),
    path(
        "admin/categories/<int:pk>/",
        admin_views.AdminCategoryDetailView.as_view(),
        name="admin-category-detail",
    ),
    path("admin/users/", admin_views.AdminUsersView.as_view(), name="admin-users"),
    path(
        "admin/fact-checks/",
        admin_views.AdminFactChecksView.as_view(),
        name="admin-fact-checks",
    ),
    path("admin/dashboard/", admin_views.AdminDashboardView.as_view(), name="admin-dashboard"),
    path("admin/ingest/", admin_views.AdminIngestView.as_view(), name="admin-ingest"),
]
