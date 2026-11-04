"""Serializers for registration, login and user preferences."""
from __future__ import annotations

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import UserPreference
from news.models import Category

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "date_joined",
        )
        read_only_fields = ("id", "username", "is_staff", "date_joined")


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, max_length=128)
    password_confirm = serializers.CharField(write_only=True, max_length=128)

    def validate_username(self, value: str) -> str:
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is already taken.")
        if not value.replace("_", "").replace(".", "").isalnum():
            raise serializers.ValidationError(
                "Use letters, numbers, dots or underscores only."
            )
        return value

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with that email already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        try:
            validate_password(attrs["password"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        UserPreference.objects.get_or_create(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(
        help_text="Username or email address.", max_length=254
    )
    password = serializers.CharField(write_only=True, max_length=128)

    def validate(self, attrs):
        identifier = attrs["identifier"].strip()
        password = attrs["password"]
        username = identifier
        if "@" in identifier:
            match = User.objects.filter(email__iexact=identifier).first()
            username = match.username if match else identifier
        user = authenticate(request=self.context.get("request"), username=username, password=password)
        if user is None:
            raise serializers.ValidationError(
                {"detail": "Invalid credentials. Check your username/email and password."}
            )
        if not user.is_active:
            raise serializers.ValidationError({"detail": "This account is disabled."})
        attrs["user"] = user
        return attrs


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description")


class PreferencesSerializer(serializers.Serializer):
    preferred_categories = serializers.ListField(
        child=serializers.SlugField(), required=False, default=list
    )
    personalize_feed = serializers.BooleanField(required=False, default=True)

    def validate_preferred_categories(self, value):
        slugs = list(dict.fromkeys(value))
        existing = set(Category.objects.filter(slug__in=slugs).values_list("slug", flat=True))
        missing = [slug for slug in slugs if slug not in existing]
        if missing:
            raise serializers.ValidationError(f"Unknown categories: {', '.join(missing)}")
        return slugs

    def to_representation(self, instance: UserPreference):
        return {
            "preferred_categories": list(
                instance.preferred_categories.values_list("slug", flat=True)
            ),
            "personalize_feed": instance.personalize_feed,
            "updated_at": instance.updated_at,
        }
