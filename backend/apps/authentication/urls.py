from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import LoginView, SignUpView, SignUpOptionsView, LogoutView, ProfileView, ChangePasswordView, UpdateFCMTokenView

urlpatterns = [
    path("login/",          LoginView.as_view(),         name="auth-login"),
    path("signup/",         SignUpView.as_view(),         name="auth-signup"),
    path("signup/options/", SignUpOptionsView.as_view(),  name="auth-signup-options"),
    path("logout/",         LogoutView.as_view(),        name="auth-logout"),
    path("token/refresh/",  TokenRefreshView.as_view(),  name="token-refresh"),
    path("profile/",        ProfileView.as_view(),       name="auth-profile"),
    path("change-password/",ChangePasswordView.as_view(),name="auth-change-password"),
    path("fcm-token/",      UpdateFCMTokenView.as_view(),name="auth-fcm-token"),
]
