from django.urls import path

from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.views.auth_views import (
    RegisterView,
    LoginView,
    LogoutView,
    GoogleAuthView,
    TokenRefresh,
)

urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("login/", LoginView.as_view()),
    path("logout/", LogoutView.as_view()),
    path("google/", GoogleAuthView.as_view()),

    path("token/", TokenObtainPairView.as_view()),
    path("token/refresh/", TokenRefresh.as_view()),
]