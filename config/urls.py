# config/urls.py

from django.contrib import admin
from django.urls import path, include

from .views import status_view

from lumenix.views.account import SignupView
from lumenix.views.profile import CompleteProfileView

urlpatterns = [
    path("status", status_view),

    path('admin/', admin.site.urls),

    # Must precede allauth's include: shows the registration form read-only while signup is closed.
    path('accounts/signup/', SignupView.as_view(), name="account_signup"),
    path('accounts/', include('allauth.urls')),

    path('accounts/complete-profile/', CompleteProfileView.as_view(), name="account_complete_profile"),

    path('', include('lumenix.urls')),
]
