# lumenix/account_adapter.py

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class NoSignupAccountAdapter(DefaultAccountAdapter):
    """Allow or block public signup via settings flag."""

    def is_open_for_signup(self, request):
        return bool(getattr(settings, "PUBLIC_SIGNUP_ENABLED", False))
