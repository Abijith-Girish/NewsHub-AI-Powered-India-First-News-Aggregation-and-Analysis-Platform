"""Authentication and preference endpoints."""
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import UserPreference
from accounts.serializers import (
    LoginSerializer,
    PreferencesSerializer,
    RegisterSerializer,
    UserSerializer,
)
from news.models import Category

User = get_user_model()


def _auth_payload(user) -> dict:
    token, _ = Token.objects.get_or_create(user=user)
    return {"token": token.key, "user": UserSerializer(user).data}


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(_auth_payload(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(_auth_payload(serializer.validated_data["user"]))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({"detail": "You have been logged out."})


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    def _preference(self, user) -> UserPreference:
        preference, _ = UserPreference.objects.get_or_create(user=user)
        return preference

    def get(self, request):
        preference = self._preference(request.user)
        return Response(PreferencesSerializer(preference).to_representation(preference))

    def put(self, request):
        preference = self._preference(request.user)
        serializer = PreferencesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        slugs = serializer.validated_data.get("preferred_categories", [])
        categories = Category.objects.filter(slug__in=slugs)
        preference.preferred_categories.set(categories)
        if "personalize_feed" in serializer.validated_data:
            preference.personalize_feed = serializer.validated_data["personalize_feed"]
        preference.save()
        return Response(PreferencesSerializer(preference).to_representation(preference))


class PublicProfileView(APIView):
    """Small public badge used by the profile header (no email exposure)."""

    permission_classes = [AllowAny]

    def get(self, request, username):
        user = User.objects.filter(username__iexact=username).first()
        if not user:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                "username": user.username,
                "display_name": user.get_full_name() or user.username,
                "joined": user.date_joined,
            }
        )
