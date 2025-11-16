# config/urls.py

from django.contrib import admin
from django.urls import path, include

from .views import status_view

from lumenix.views.profile import CompleteProfileView

urlpatterns = [
    path("status", status_view),

    path('admin/', admin.site.urls),

    path('accounts/', include('allauth.urls')),

    path('accounts/complete-profile/', CompleteProfileView.as_view(), name="account_complete_profile"),

    path('', include('lumenix.urls')),
]
