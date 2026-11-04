"""Serializers for articles, categories, fact checks and admin writes."""
from __future__ import annotations

from rest_framework import serializers

from news.models import Article, Category, FactCheck, SavedArticle
from news.services.dedupe import build_dedupe_key, is_valid_article_url


class CategorySerializer(serializers.ModelSerializer):
    article_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description", "article_count")


class ArticleSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    source = serializers.CharField(source="source_name", read_only=True)
    sentiment = serializers.SerializerMethodField()
    saved = serializers.SerializerMethodField()
    publisher_domain = serializers.CharField(read_only=True)
    match_score = serializers.SerializerMethodField()
    match_reason = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = (
            "id",
            "title",
            "description",
            "image_url",
            "source",
            "source_url",
            "author",
            "published_at",
            "category",
            "sentiment",
            "is_breaking",
            "publisher_domain",
            "saved",
            "match_score",
            "match_reason",
        )

    def get_sentiment(self, obj):
        if not obj.sentiment_label:
            return None
        return {
            "label": obj.sentiment_label,
            "score": obj.sentiment_score,
            "note": "Tone of the wording; not a measure of accuracy.",
        }

    def _saved_ids(self):
        return self.context.get("saved_ids")

    def get_saved(self, obj) -> bool:
        if self._saved_ids() is not None:
            return obj.id in self._saved_ids()
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return SavedArticle.objects.filter(user=request.user, article=obj).exists()

    def get_match_score(self, obj):
        score = getattr(obj, "match_score", None)
        return score

    def get_match_reason(self, obj):
        return getattr(obj, "match_reason", None)


class ArticleDetailSerializer(ArticleSerializer):
    ml_category = CategorySerializer(read_only=True)

    class Meta(ArticleSerializer.Meta):
        fields = ArticleSerializer.Meta.fields + (
            "content",
            "status",
            "category_source",
            "ml_category",
            "ml_confidence",
        )


class FactCheckRequestSerializer(serializers.Serializer):
    claim = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    article_title = serializers.CharField(required=False, allow_blank=True, max_length=500)
    source_url = serializers.URLField(required=False, allow_blank=True, max_length=1000)
    content = serializers.CharField(required=False, allow_blank=True, max_length=8000)

    def validate_source_url(self, value):
        if value and not is_valid_article_url(value):
            raise serializers.ValidationError("Enter a valid http(s) article URL.")
        return value

    def validate(self, attrs):
        if not any(
            (attrs.get(field) or "").strip()
            for field in ("claim", "article_title", "source_url", "content")
        ):
            raise serializers.ValidationError(
                "Provide a claim, a headline, an article URL or a paragraph of text."
            )
        return attrs


class FactCheckSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="reference", read_only=True)
    verdict_label = serializers.CharField(source="get_verdict_display", read_only=True)

    class Meta:
        model = FactCheck
        fields = (
            "id",
            "claim",
            "article_title",
            "source_url",
            "verdict",
            "verdict_label",
            "confidence",
            "explanation",
            "evidence",
            "related_articles",
            "analysis_notes",
            "engine",
            "created_at",
        )


class SummarizeRequestSerializer(serializers.Serializer):
    article_id = serializers.IntegerField(required=False)
    title = serializers.CharField(required=False, allow_blank=True, max_length=500)
    text = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    length = serializers.ChoiceField(choices=["short", "detailed"], default="short")

    def validate(self, attrs):
        if not attrs.get("article_id") and not (
            (attrs.get("title") or "").strip() or (attrs.get("text") or "").strip()
        ):
            raise serializers.ValidationError("Provide an article_id or title/text to summarize.")
        return attrs


class SentimentRequestSerializer(serializers.Serializer):
    article_id = serializers.IntegerField(required=False)
    text = serializers.CharField(required=False, allow_blank=True, max_length=20000)

    def validate(self, attrs):
        if not attrs.get("article_id") and not (attrs.get("text") or "").strip():
            raise serializers.ValidationError("Provide an article_id or text to analyze.")
        return attrs


class CategorizeRequestSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True, max_length=500)
    description = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    content = serializers.CharField(required=False, allow_blank=True, max_length=20000)

    def validate(self, attrs):
        text = " ".join(
            attrs.get(field) or "" for field in ("title", "description", "content")
        ).strip()
        if len(text) < 15:
            raise serializers.ValidationError(
                "Provide at least a headline or a short description to classify."
            )
        return attrs


class AdminArticleSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Article
        fields = (
            "id",
            "title",
            "description",
            "content",
            "image_url",
            "source_name",
            "source_url",
            "author",
            "published_at",
            "category",
            "status",
            "is_breaking",
            "category_source",
            "ml_category",
            "ml_confidence",
            "view_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "category_source",
            "ml_category",
            "ml_confidence",
            "view_count",
            "created_at",
            "updated_at",
        )

    def validate_title(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError("The title is too short.")
        return value

    def validate_source_url(self, value):
        value = (value or "").strip()
        if not is_valid_article_url(value):
            raise serializers.ValidationError("Enter a valid http(s) article URL.")
        return value

    def validate(self, attrs):
        instance = self.instance
        url = attrs.get("source_url", getattr(instance, "source_url", ""))
        title = attrs.get("title", getattr(instance, "title", ""))
        key = build_dedupe_key(url, title)
        existing = Article.objects.filter(dedupe_key=key)
        if instance:
            existing = existing.exclude(pk=instance.pk)
        if existing.exists():
            raise serializers.ValidationError(
                {"source_url": "Another article with this URL or headline already exists."}
            )
        return attrs

    def _finalize(self, article: Article, validated_data: dict) -> Article:
        if "category" in validated_data:
            article.category = validated_data["category"]
            article.category_source = Article.CategorySource.MANUAL
        article.dedupe_key = build_dedupe_key(article.source_url, article.title)
        article.save()
        return article

    def create(self, validated_data):
        article = Article(**validated_data)
        article.category_source = Article.CategorySource.MANUAL
        article.save()
        return self._finalize(article, validated_data)

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        return self._finalize(instance, validated_data)


class AdminUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    is_staff = serializers.BooleanField()
    is_active = serializers.BooleanField()
    date_joined = serializers.DateTimeField()
    saved_count = serializers.IntegerField()
    fact_check_count = serializers.IntegerField()
