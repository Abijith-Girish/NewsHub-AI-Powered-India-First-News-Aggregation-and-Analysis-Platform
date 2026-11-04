from django.urls import path

from accounts import views

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="auth-register"),
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/profile/", views.ProfileView.as_view(), name="auth-profile"),
    path("user/preferences/", views.PreferencesView.as_view(), name="user-preferences"),
    path("users/<str:username>/", views.PublicProfileView.as_view(), name="public-profile"),
]
