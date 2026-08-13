from django.urls import path, include

urlpatterns = [
    path("auth/", include("accounts.api.v1.auth.urls")),
    path("profile/", include("accounts.api.v1.profile.urls")),
    path("password/", include("accounts.api.v1.password.urls")),
]