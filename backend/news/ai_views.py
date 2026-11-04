"""AI / ML endpoints: summaries, sentiment, classification and fact checks."""
from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from news.ml.classifier import classify_article, get_metrics, model_status
from news.ml.sentiment import analyze_sentiment, sentiment_for_article
from news.ml.summarizer import summarize_article, summarize_text
from news.models import Article, Category, FactCheck
from news.serializers import (
    CategorizeRequestSerializer,
    CategorySerializer,
    FactCheckRequestSerializer,
    FactCheckSerializer,
    SentimentRequestSerializer,
    SummarizeRequestSerializer,
)
from news.services.factcheck import (
    DISCLAIMER,
    analyze_claim,
    persist_fact_check,
)

logger = logging.getLogger("newshub.ai")


class SummarizeView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"

    def post(self, request):
        serializer = SummarizeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data.get("article_id"):
            article = get_object_or_404(
                Article.objects.published(), pk=data["article_id"]
            )
            try:
                result = summarize_article(article, data["length"])
            except ValueError as exc:
                return Response(
                    {"detail": str(exc), "code": "no_content"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            try:
                result = summarize_text(
                    data.get("title", ""), data.get("text", ""), data["length"]
                )
            except ValueError as exc:
                return Response(
                    {"detail": str(exc), "code": "no_content"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return Response(result)


class SentimentView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"

    def post(self, request):
        serializer = SentimentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        article_meta = None
        if data.get("article_id"):
            article = get_object_or_404(
                Article.objects.published(), pk=data["article_id"]
            )
            result = sentiment_for_article(article)
            article_meta = {
                "id": article.id,
                "title": article.title,
                "source": article.source_name,
                "source_url": article.source_url,
            }
        else:
            result = analyze_sentiment(data.get("text", ""))

        return Response(
            {
                **result,
                "article": article_meta,
                "disclaimer": (
                    "Sentiment describes the tone of the language used. It does not "
                    "indicate whether an article is accurate, biased or trustworthy."
                ),
            }
        )


class CategorizeView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"

    def post(self, request):
        serializer = CategorizeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        prediction = classify_article(
            data.get("title", ""), data.get("description", ""), data.get("content", "")
        )
        category = None
        if prediction["category"]:
            category = Category.objects.filter(slug=prediction["category"]).first()
        return Response(
            {
                **prediction,
                "category_detail": CategorySerializer(category).data if category else None,
                "model": model_status(),
                "note": (
                    "This is a statistical prediction from a locally trained model. "
                    "Editors can correct it in the admin dashboard."
                ),
            }
        )


class MLMetricsView(APIView):
    def get(self, request):
        metrics = get_metrics()
        return Response(
            {
                "model": model_status(),
                "metrics": metrics if metrics.get("available") else None,
                "note": (
                    "Metrics are computed on a held-out split of the curated seed "
                    "corpus; they are not a real-world benchmark."
                ),
            }
        )


class FactCheckView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "fact_check"

    def post(self, request):
        serializer = FactCheckRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = analyze_claim(
                claim=data.get("claim", ""),
                article_title=data.get("article_title", ""),
                source_url=data.get("source_url", ""),
                content=data.get("content", ""),
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc), "code": "invalid_claim"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        record = persist_fact_check(result, user=request.user)
        response_data = FactCheckSerializer(record).data
        response_data.update(
            {
                "disclaimer": DISCLAIMER,
                "engine_note": (
                    "The verdict is produced by conservative claim-specific evidence scoring. "
                    "Directional results require independent established-publisher sources or "
                    "dedicated fact-check reporting; conflicting relevant reports are shown as "
                    "Mixed. An LLM, when configured, only writes the explanation and cannot "
                    "change the verdict."
                ),
            }
        )
        return Response(response_data, status=status.HTTP_201_CREATED)


class FactCheckDetailView(APIView):
    def get(self, request, reference):
        record = get_object_or_404(FactCheck, reference=reference)
        if record.user_id and request.user != record.user and not request.user.is_staff:
            return Response(
                {"detail": "Fact check not found."}, status=status.HTTP_404_NOT_FOUND
            )
        response_data = FactCheckSerializer(record).data
        response_data["disclaimer"] = DISCLAIMER
        return Response(response_data)


class FactCheckHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        records = FactCheck.objects.filter(user=request.user)[:20]
        return Response(
            {"count": records.count(), "results": FactCheckSerializer(records, many=True).data}
        )
