# config/urls.py

from django.contrib import admin
from django.urls import path, include, re_path

from .views import status_view, disabled_auth_view

from lumenix.views.profile import CompleteProfileView

urlpatterns = [
    path("status", status_view),
    re_path(r"^accounts/password/reset(?:/.*)?$", disabled_auth_view, name="account_reset_password"),

    path('admin/', admin.site.urls),

    path('accounts/', include('allauth.urls')),

    path('accounts/complete-profile/', CompleteProfileView.as_view(), name="account_complete_profile"),

    path('', include('lumenix.urls')),
]
