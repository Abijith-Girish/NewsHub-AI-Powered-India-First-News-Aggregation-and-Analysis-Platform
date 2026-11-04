"""Administrator-only API endpoints. Every view requires is_staff."""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from news.ml.classifier import model_status
from news.models import Article, ArticleInteraction, Category, FactCheck, SavedArticle
from news.pagination import StandardPagination
from news.serializers import (
    AdminArticleSerializer,
    AdminUserSerializer,
    CategorySerializer,
    FactCheckSerializer,
)
from news.services import aggregator
from news.services.categorization import invalidate_cache

User = get_user_model()


def review_queue_queryset():
    """Articles whose *display* category came from the model or rules and still
    needs an editor's confirmation. Provider-labelled articles are excluded:
    the publisher's own section is authoritative.
    """
    return (
        Article.objects.with_relations()
        .published()
        .filter(
            category_source__in=[
                Article.CategorySource.ML,
                Article.CategorySource.RULE,
                "",
            ]
        )
        .filter(
            Q(category__isnull=True)
            | Q(ml_confidence__lt=0.5)
            | Q(ml_category__isnull=False, category__isnull=False)
            & ~Q(category=F("ml_category"))
        )
        .order_by("-published_at")
    )


class AdminArticleListCreateView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        queryset = Article.objects.with_relations().order_by("-created_at")
        query = (request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(source_name__icontains=query)
            )
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        category = request.query_params.get("category")
        if category:
            queryset = queryset.filter(category__slug=category)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = AdminArticleSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = AdminArticleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        article = serializer.save()
        return Response(AdminArticleSerializer(article).data, status=status.HTTP_201_CREATED)


class AdminArticleDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk: int):
        article = get_object_or_404(Article, pk=pk)
        return Response(AdminArticleSerializer(article).data)

    def put(self, request, pk: int):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk: int):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk: int, partial: bool):
        article = get_object_or_404(Article, pk=pk)
        serializer = AdminArticleSerializer(article, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        article = serializer.save()
        return Response(AdminArticleSerializer(article).data)

    def delete(self, request, pk: int):
        article = get_object_or_404(Article, pk=pk)
        title = article.title
        article.delete()
        return Response({"deleted": True, "title": title})


class AdminCategoryReviewView(APIView):
    """Apply the ML suggestion or an editor override to an article category."""

    permission_classes = [IsAdminUser]

    def post(self, request, pk: int):
        article = get_object_or_404(Article.objects.with_relations(), pk=pk)
        accept_ml = bool(request.data.get("accept_ml"))
        if accept_ml:
            if not article.ml_category:
                return Response(
                    {"detail": "No ML prediction is stored for this article."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            article.category = article.ml_category
            article.category_source = Article.CategorySource.ML
        else:
            slug = (request.data.get("category_slug") or "").strip()
            category = Category.objects.filter(slug=slug).first()
            if not category:
                return Response(
                    {"detail": "Provide a valid category_slug or accept_ml."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            article.category = category
            article.category_source = Article.CategorySource.MANUAL
        article.save(update_fields=["category", "category_source", "updated_at"])
        return Response(AdminArticleSerializer(article).data)


class AdminReviewQueueView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        queryset = review_queue_queryset()[:60]
        data = []
        for article in queryset:
            data.append(
                {
                    "id": article.id,
                    "title": article.title,
                    "source": article.source_name,
                    "source_url": article.source_url,
                    "published_at": article.published_at,
                    "category": CategorySerializer(article.category).data
                    if article.category
                    else None,
                    "ml_category": CategorySerializer(article.ml_category).data
                    if article.ml_category
                    else None,
                    "ml_confidence": article.ml_confidence,
                    "category_source": article.category_source,
                }
            )
        return Response({"count": len(data), "results": data})


class AdminCategoriesView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        categories = Category.objects.annotate(
            article_count=Count("articles")
        ).order_by("display_order", "name")
        return Response({"results": CategorySerializer(categories, many=True).data})

    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        invalidate_cache()
        return Response(CategorySerializer(category).data, status=status.HTTP_201_CREATED)


class AdminCategoryDetailView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, pk: int):
        category = get_object_or_404(Category, pk=pk)
        serializer = CategorySerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        invalidate_cache()
        return Response(serializer.data)

    def delete(self, request, pk: int):
        category = get_object_or_404(Category, pk=pk)
        if category.articles.exists():
            return Response(
                {
                    "detail": (
                        "This category still has articles. Move or delete them first "
                        "so content is not orphaned."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        category.delete()
        invalidate_cache()
        return Response({"deleted": True})


class AdminUsersView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        users = (
            User.objects.annotate(
                saved_count=Count("saved_articles", distinct=True),
                fact_check_count=Count("fact_checks", distinct=True),
            )
            .order_by("-date_joined")[:200]
        )
        return Response(
            {"count": users.count(), "results": AdminUserSerializer(users, many=True).data}
        )


class AdminFactChecksView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        records = FactCheck.objects.select_related("user")[:50]
        data = FactCheckSerializer(records, many=True).data
        return Response({"count": records.count(), "results": data})


class AdminDashboardView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()
        articles = Article.objects.all()
        published = articles.filter(status=Article.Status.PUBLISHED)
        users = User.objects.all()

        categories = (
            Category.objects.annotate(
                article_count=Count(
                    "articles", filter=Q(articles__status=Article.Status.PUBLISHED)
                )
            ).order_by("display_order")
        )
        sources = (
            published.exclude(source_name="")
            .values("source_name")
            .annotate(count=Count("id"))
            .order_by("-count")[:12]
        )
        review_queue = review_queue_queryset().count()
        recent = articles.with_relations().order_by("-created_at")[:8]
        recent_fact_checks = FactCheck.objects.order_by("-created_at")[:5]

        return Response(
            {
                "articles": {
                    "total": articles.count(),
                    "published": published.count(),
                    "drafts": articles.filter(status=Article.Status.DRAFT).count(),
                    "archived": articles.filter(status=Article.Status.ARCHIVED).count(),
                    "breaking": published.filter(is_breaking=True).count(),
                    "last_24h": published.filter(
                        published_at__gte=now - timedelta(hours=24)
                    ).count(),
                },
                "users": {
                    "total": users.count(),
                    "staff": users.filter(is_staff=True).count(),
                    "new_7d": users.filter(date_joined__gte=now - timedelta(days=7)).count(),
                },
                "engagement": {
                    "saved_articles": SavedArticle.objects.count(),
                    "interactions": ArticleInteraction.objects.count(),
                    "fact_checks": FactCheck.objects.count(),
                    "views": int(published.aggregate(total=Sum("view_count"))["total"] or 0),
                },
                "categories": [
                    {
                        "name": category.name,
                        "slug": category.slug,
                        "article_count": category.article_count,
                    }
                    for category in categories
                ],
                "sources": [
                    {"source": row["source_name"], "article_count": row["count"]}
                    for row in sources
                ],
                "model": model_status(),
                "review_queue": review_queue,
                "providers": aggregator.feed_status(),
                "last_feeds_refresh": cache.get("newshub:last_fetch:general"),
                "config": {
                    "live_fetch_enabled": settings.NEWSHUB["LIVE_FETCH_ENABLED"],
                    "llm_configured": bool(
                        settings.NEWSHUB.get("GEMINI_API_KEY")
                        or settings.NEWSHUB.get("GROQ_API_KEY")
                        or settings.NEWSHUB.get("LLM_API_KEY")
                    ),
                    "gemini_configured": bool(settings.NEWSHUB.get("GEMINI_API_KEY")),
                    "groq_configured": bool(settings.NEWSHUB.get("GROQ_API_KEY")),
                    "newsapi_configured": bool(settings.NEWSHUB["NEWSAPI_KEY"]),
                    "gnews_configured": bool(settings.NEWSHUB["GNEWS_API_KEY"]),
                },
                "recent_articles": AdminArticleSerializer(recent, many=True).data,
                "recent_fact_checks": FactCheckSerializer(
                    recent_fact_checks, many=True
                ).data,
            }
        )


class AdminIngestView(APIView):
    """Trigger a feed refresh manually (never exposes provider credentials)."""

    permission_classes = [IsAdminUser]

    def post(self, request):
        scope = (request.data.get("scope") or "general").lower()
        try:
            if scope == "all":
                stats = aggregator.ingest_all_feeds()
            else:
                stats = aggregator.refresh_feed(force=True, scope="general")
        except Exception as exc:  # noqa: BLE001
            return Response(
                {"detail": f"Ingestion failed: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(stats)
