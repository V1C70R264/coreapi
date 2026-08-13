from django.urls import path
from accounts.views.profile_views import ChangePasswordView, ProfileView, EmailTestView

urlpatterns = [
    path("", ProfileView.as_view()),
    path("change-password/", ChangePasswordView.as_view()),
    path("email-test/", EmailTestView.as_view()),
]