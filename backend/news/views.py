"""Public news API: feeds, search, detail, recommendations, saves, metadata."""
from __future__ import annotations

import hashlib
import logging
from datetime import timedelta
from django.utils.dateparse import parse_date

from django.core.cache import cache
from django.db.models import Count, F, Q, Window
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models.functions import RowNumber
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from news.exceptions import ProviderUnavailable
from news.ml.recommend import popular_articles, recommend_for_article, recommend_for_user
from news.models import Article, ArticleInteraction, Category, SavedArticle
from news.pagination import StandardPagination
from news.serializers import (
    ArticleDetailSerializer,
    ArticleSerializer,
    CategorySerializer,
)
from news.services import aggregator
from news.services.dedupe import clean_text
from news.services.trending import trending_stories, trending_topics

logger = logging.getLogger("newshub.views")

VALID_SORTS = {"latest", "oldest", "relevance"}
SEARCH_CACHE_KEY = "newshub:search_run:{key}"
SEARCH_MIN_LENGTH = 2


def _ensure_fresh() -> None:
    try:
        aggregator.ensure_fresh_content()
    except Exception as exc:  # noqa: BLE001 - cached content is still served
        logger.warning("Freshness check failed: %s", exc)


def _saved_ids(request) -> set[int]:
    if not request.user.is_authenticated:
        return set()
    return set(
        SavedArticle.objects.filter(user=request.user).values_list("article_id", flat=True)
    )


def _context(request, **extra) -> dict:
    context = {"request": request, "saved_ids": _saved_ids(request)}
    context.update(extra)
    return context


def _query_tokens(query: str) -> list[str]:
    from news.services.factcheck import STOPWORDS, _tokens

    tokens = sorted(_tokens(query), key=len, reverse=True)
    return tokens or [query.strip()]


def _validated_date_range(params):
    """Parse and validate advanced date inputs against India local date."""
    from_raw = (params.get("from_date") or "").strip()
    to_raw = (params.get("to_date") or "").strip()
    try:
        from_date = parse_date(from_raw[:10]) if from_raw else None
    except (TypeError, ValueError):
        from_date = None
    try:
        to_date = parse_date(to_raw[:10]) if to_raw else None
    except (TypeError, ValueError):
        to_date = None
    today = timezone.localdate()
    if from_raw and from_date is None:
        raise ValidationError({"from_date": "Use a valid date in YYYY-MM-DD format."})
    if to_raw and to_date is None:
        raise ValidationError({"to_date": "Use a valid date in YYYY-MM-DD format."})
    if from_date and from_date > today:
        raise ValidationError({"from_date": "From date cannot be in the future (India local date)."})
    if to_date and to_date > today:
        raise ValidationError({"to_date": "To date cannot be in the future (India local date)."})
    if from_date and to_date and from_date > to_date:
        raise ValidationError({"date_range": "From date must be on or before To date."})
    return from_date, to_date


def _filter_articles(queryset, params, query: str = ""):
    from_date, to_date = _validated_date_range(params)
    q = (query or params.get("q") or "").strip()
    if q:
        condition = Q()
        for token in _query_tokens(q)[:8]:
            condition |= (
                Q(title__icontains=token)
                | Q(description__icontains=token)
                | Q(content__icontains=token)
                | Q(search_query__icontains=token)
                | Q(author__icontains=token)
            )
        queryset = queryset.filter(condition)

    exact_phrase = (params.get("exact") or "").strip()[:200]
    if exact_phrase:
        queryset = queryset.filter(
            Q(title__icontains=exact_phrase)
            | Q(description__icontains=exact_phrase)
            | Q(content__icontains=exact_phrase)
        )

    exclude_query = (params.get("exclude") or "")[:200].strip()
    if exclude_query:
        for token in _query_tokens(exclude_query)[:8]:
            queryset = queryset.exclude(
                Q(title__icontains=token)
                | Q(description__icontains=token)
                | Q(content__icontains=token)
            )

    author = (params.get("author") or "").strip()[:100]
    if author:
        queryset = queryset.filter(author__icontains=author)

    has_image = (params.get("has_image") or "").lower()
    if has_image in {"1", "true", "yes"}:
        queryset = queryset.exclude(image_url="")
    elif has_image in {"0", "false", "no"}:
        queryset = queryset.filter(image_url="")

    if from_date:
        queryset = queryset.filter(published_at__date__gte=from_date)
    if to_date:
        queryset = queryset.filter(published_at__date__lte=to_date)

    category = (params.get("category") or "").strip()
    if category and category.lower() != "all":
        queryset = queryset.filter(category__slug=category)

    source = (params.get("source") or "").strip()
    if source and source.lower() != "all":
        queryset = queryset.filter(source_name__iexact=source)

    if params.get("breaking") in {"1", "true", "yes"}:
        queryset = queryset.filter(is_breaking=True)

    date_filter = (params.get("date") or "all").lower()
    now = timezone.now()
    if date_filter == "today":
        queryset = queryset.filter(published_at__gte=now - timedelta(hours=24))
    elif date_filter == "week":
        queryset = queryset.filter(published_at__gte=now - timedelta(days=7))
    elif date_filter == "month":
        queryset = queryset.filter(published_at__gte=now - timedelta(days=30))

    return queryset


def _rank_by_relevance(query: str, articles: list[Article]) -> list[Article]:
    """Rank a candidate list against the query with TF-IDF cosine similarity."""
    if not articles:
        return []
    documents = [query] + [
        f"{article.title} {article.title} {article.description or ''} {(article.content or '')[:500]} {article.category.name if article.category else ''}"
        for article in articles
    ]
    try:
        matrix = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2), sublinear_tf=True
        ).fit_transform(documents)
        similarities = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    except ValueError:
        return sorted(articles, key=lambda item: item.published_at, reverse=True)

    scores = {article.id: float(similarities[index]) for index, article in enumerate(articles)}
    for article in articles:
        article.match_score = round(scores[article.id], 4)
    return sorted(
        articles,
        key=lambda article: (scores[article.id], article.published_at.timestamp()),
        reverse=True,
    )


def _diversified_queryset(queryset):
    """Interleave publisher ranks so one high-volume outlet cannot fill the page."""
    return queryset.annotate(
        _publisher_rank=Window(
            expression=RowNumber(),
            partition_by=[F("source_name")],
            order_by=F("published_at").desc(),
        )
    ).order_by("_publisher_rank", "-published_at")


def _interleave_publishers(articles: list[Article]) -> list[Article]:
    from collections import defaultdict, deque

    buckets = defaultdict(deque)
    for article in articles:
        key = (article.source_name or article.publisher_domain or "Unknown").lower()
        buckets[key].append(article)
    result = []
    while buckets:
        for key in list(buckets):
            result.append(buckets[key].popleft())
            if not buckets[key]:
                del buckets[key]
    return result


def _paginated(request, items, serializer_class, context, meta: dict | None = None):
    paginator = StandardPagination()
    page = paginator.paginate_queryset(items, request)
    serializer = serializer_class(page, many=True, context=context)
    response = paginator.get_paginated_response(serializer.data)
    if meta is not None:
        response.data["meta"] = meta
    return response


def _recommendation_payload(items: list[dict], context: dict) -> list[dict]:
    payload = []
    for item in items:
        article = item["article"]
        article.match_score = item["score"]
        article.match_reason = item.get("reason", "")
        data = ArticleSerializer(article, context=context).data
        data["match_similarity"] = item.get("similarity", 0.0)
        payload.append(data)
    return payload


class NewsListView(APIView):
    """General article feed with filtering, sorting and pagination."""

    def get(self, request):
        _ensure_fresh()
        queryset = _filter_articles(
            Article.objects.published().with_relations(), request.query_params
        )
        sort = (request.query_params.get("sort") or "latest").lower()
        if sort not in VALID_SORTS:
            sort = "latest"

        context = _context(request)
        query = (request.query_params.get("q") or "").strip()
        meta = {"sort": sort, "query": query or None}

        if sort == "relevance" and query:
            candidates = _rank_by_relevance(
                query, list(queryset.order_by("-published_at")[:300])
            )
            return _paginated(request, candidates, ArticleSerializer, context, meta)

        if sort == "oldest":
            ordered = queryset.order_by("published_at")
        else:
            ordered = _diversified_queryset(queryset)
        return _paginated(request, ordered, ArticleSerializer, context, meta)


class LatestNewsView(APIView):
    def get(self, request):
        _ensure_fresh()
        queryset = _diversified_queryset(_filter_articles(
            Article.objects.published().with_relations(), request.query_params
        ))
        return _paginated(
            request, queryset, ArticleSerializer, _context(request), {"sort": "latest"}
        )


class BreakingNewsView(APIView):
    """Breaking items come only from provider metadata (top-stories feeds)."""

    def get(self, request):
        _ensure_fresh()
        cutoff = timezone.now() - timedelta(hours=24)
        articles = list(
            Article.objects.published()
            .with_relations()
            .filter(is_breaking=True, published_at__gte=cutoff)
            .order_by("-published_at")[:6]
        )
        fallback = False
        note = ""
        if not articles:
            fallback = True
            note = (
                "No article is currently flagged as breaking by a provider, so the "
                "most recent headlines are shown instead."
            )
            articles = list(
                Article.objects.published()
                .with_relations()
                .order_by("-published_at")[:4]
            )
        serializer = ArticleSerializer(articles, many=True, context=_context(request))
        return Response(
            {"fallback": fallback, "note": note, "results": serializer.data}
        )


class TrendingView(APIView):
    def get(self, request):
        _ensure_fresh()
        topics = trending_topics(limit=10, hours=48)
        stories = trending_stories(limit=6, hours=72)
        serializer = ArticleSerializer(stories, many=True, context=_context(request))
        return Response(
            {
                "topics": topics,
                "stories": serializer.data,
                "window_hours": 48,
                "note": (
                    "Topics and counts are derived from stored articles published in the "
                    "last 48 hours; they are not invented trend scores."
                ),
                "generated_at": timezone.now().isoformat(),
            }
        )


class SearchView(APIView):
    """Topic search across multiple providers, then deduplicated in the database."""

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        if len(query) < SEARCH_MIN_LENGTH:
            return Response(
                {"detail": "Enter at least two characters to search.", "code": "invalid_query"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(query) > 200:
            return Response(
                {"detail": "Search queries must be 200 characters or fewer.", "code": "invalid_query"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reject invalid or future date ranges before contacting external providers.
        _validated_date_range(request.query_params)
        refresh = request.query_params.get("refresh") in {"1", "true"}
        marker = SEARCH_CACHE_KEY.format(
            key=hashlib.sha1(" ".join(query.lower().split()).encode("utf-8")).hexdigest()
        )
        live_stats = None
        if refresh or not cache.get(marker):
            try:
                live_stats = aggregator.search_news(query)
                cache.set(marker, True, 600)
            except Exception as exc:  # noqa: BLE001 - stored results still serve
                logger.warning("Live search failed for %r: %s", query, exc)
                live_stats = {"errors": ["Search providers unavailable"], "providers_succeeded": 0}
            if request.user.is_authenticated:
                ArticleInteraction.objects.create(
                    user=request.user,
                    interaction_type=ArticleInteraction.InteractionType.SEARCH,
                    query=query[:290],
                )

        queryset = _filter_articles(
            Article.objects.published().with_relations(),
            request.query_params,
            query=query,
        )
        sort = (request.query_params.get("sort") or "relevance").lower()
        if sort not in VALID_SORTS:
            sort = "relevance"

        candidates = list(queryset.order_by("-published_at")[:300])
        if sort == "relevance":
            candidates = _rank_by_relevance(query, candidates)
        elif sort == "oldest":
            candidates.sort(key=lambda article: article.published_at)
        else:
            candidates.sort(key=lambda article: article.published_at, reverse=True)
            candidates = _interleave_publishers(candidates)

        meta = {
            "query": query,
            "sort": sort,
            "matched_stored_articles": len(candidates),
            "live_search": live_stats,
            "count_note": (
                "The count reflects matching articles stored by NewsHub after "
                "deduplication. Providers do not expose a reliable total, so no "
                "provider-wide total is claimed."
            ),
            "available_filters": _filter_options(),
        }

        if not candidates:
            if live_stats and not live_stats.get("providers_succeeded"):
                raise ProviderUnavailable(
                    "News providers could not be reached and no stored articles match "
                    "this search. Please try again shortly."
                )
            return _paginated(
                request, [], ArticleSerializer, _context(request), meta
            )

        return _paginated(
            request, candidates, ArticleSerializer, _context(request), meta
        )


def _filter_options() -> dict:
    sources = list(
        Article.objects.published()
        .exclude(source_name="")
        .values_list("source_name", flat=True)
        .distinct()
        .order_by("source_name")[:60]
    )
    categories = list(
        Category.objects.annotate(
            article_count=Count(
                "articles", filter=Q(articles__status=Article.Status.PUBLISHED)
            )
        ).values("name", "slug", "article_count")
    )
    return {"sources": sources, "categories": categories}


class ArticleDetailView(APIView):
    def get(self, request, pk: int):
        article = get_object_or_404(
            Article.objects.with_relations().select_related("category", "ml_category"), pk=pk
        )
        if article.status != Article.Status.PUBLISHED and not request.user.is_staff:
            return Response({"detail": "Article not found."}, status=status.HTTP_404_NOT_FOUND)

        Article.objects.filter(pk=article.pk).update(view_count=F("view_count") + 1)
        if request.user.is_authenticated:
            ArticleInteraction.objects.create(
                user=request.user,
                article=article,
                interaction_type=ArticleInteraction.InteractionType.VIEW,
            )

        related = recommend_for_article(article, limit=6)
        context = _context(request)
        serializer = ArticleDetailSerializer(article, context=context)
        return Response(
            {
                "article": serializer.data,
                "recommendations": _recommendation_payload(related, context),
            }
        )


class ArticleRecommendationsView(APIView):
    def get(self, request, pk: int):
        article = get_object_or_404(Article.objects.published(), pk=pk)
        limit = max(1, min(int(request.query_params.get("limit", 6) or 6), 20))
        items = recommend_for_article(article, limit=limit)
        context = _context(request)
        return Response(
            {
                "article_id": article.id,
                "mode": "content_based_tfidf_cosine",
                "results": _recommendation_payload(items, context),
                "method_note": (
                    "Scores blend TF-IDF cosine similarity with a recency weight. "
                    "Scores are exposed for evaluation."
                ),
            }
        )


class RecommendedFeedView(APIView):
    def get(self, request):
        _ensure_fresh()
        limit = max(1, min(int(request.query_params.get("limit", 12) or 12), 24))
        context = _context(request)
        if request.user.is_authenticated:
            items = recommend_for_user(request.user, limit=limit)
            mode = "personalized"
            note = (
                "Ranked by your category interests, saved articles and recent reading. "
                "Other important news is still available in the main feed."
            )
        else:
            items = popular_articles(limit=limit)
            mode = "popularity"
            note = (
                "Sign in and choose interests to get personalized recommendations. "
                "These picks use recency and reader engagement."
            )
        return Response(
            {
                "mode": mode,
                "note": note,
                "results": _recommendation_payload(items, context),
            }
        )


class SaveArticleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        article = get_object_or_404(Article.objects.published(), pk=pk)
        saved, created = SavedArticle.objects.get_or_create(user=request.user, article=article)
        if created:
            ArticleInteraction.objects.create(
                user=request.user,
                article=article,
                interaction_type=ArticleInteraction.InteractionType.SAVE,
            )
        return Response(
            {"saved": True, "created": created, "article_id": article.id},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, pk: int):
        article = get_object_or_404(Article, pk=pk)
        deleted, _ = SavedArticle.objects.filter(user=request.user, article=article).delete()
        return Response({"saved": False, "removed": bool(deleted)})


class SavedNewsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        saved = SavedArticle.objects.filter(user=request.user).select_related(
            "article", "article__category"
        )
        articles = [item.article for item in saved if item.article.status == Article.Status.PUBLISHED]
        for article in articles:
            article.saved_at = next(
                (item.saved_at for item in saved if item.article_id == article.id), None
            )
        context = _context(request)
        data = ArticleSerializer(articles, many=True, context=context).data
        for item, article in zip(data, articles):
            item["saved_at"] = article.saved_at
        return Response({"count": len(data), "results": data})


class CategoriesView(APIView):
    def get(self, request):
        categories = Category.objects.annotate(
            article_count=Count(
                "articles", filter=Q(articles__status=Article.Status.PUBLISHED)
            )
        )
        return Response({"results": CategorySerializer(categories, many=True).data})


class CategoryNewsView(APIView):
    def get(self, request, slug: str):
        _ensure_fresh()
        category = get_object_or_404(Category, slug=slug)
        queryset = _diversified_queryset(
            Article.objects.published().with_relations().filter(category=category)
        )
        queryset = _filter_articles(queryset, request.query_params, query="") if request.query_params.get("q") else queryset
        context = _context(request)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = ArticleSerializer(page, many=True, context=context)
        response = paginator.get_paginated_response(serializer.data)
        response.data["category"] = CategorySerializer(category).data
        return response


class SourcesView(APIView):
    def get(self, request):
        from django.conf import settings

        config = settings.NEWSHUB
        return Response(
            {
                "sources": aggregator.feed_status(),
                "stored_sources": aggregator.source_breakdown(),
                "api_providers": [
                    {"name": "NewsAPI", "configured": bool(config["NEWSAPI_KEY"])},
                    {"name": "GNews", "configured": bool(config["GNEWS_API_KEY"])},
                    {"name": "Google News RSS", "configured": True},
                ],
                "note": (
                    "Aggregation uses public RSS feeds by default. Optional JSON APIs "
                    "activate automatically when their keys are configured."
                ),
            }
        )


class HealthView(APIView):
    def get(self, request):
        return Response(
            {
                "status": "ok",
                "time": timezone.now().isoformat(),
                "published_articles": Article.objects.published().count(),
                "live_fetch_enabled": self._live_fetch_enabled(),
            }
        )

    @staticmethod
    def _live_fetch_enabled() -> bool:
        from django.conf import settings

        return bool(settings.NEWSHUB["LIVE_FETCH_ENABLED"])
