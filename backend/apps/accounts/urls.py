from django.urls import path
from .views import LoginView, LogoutView, MeView, RefreshView, SetPasswordView

urlpatterns = [
    path("me/", MeView.as_view(), name="auth-me"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("set-password/", SetPasswordView.as_view(), name="auth-set-password"),
]
