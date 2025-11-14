# lumenix/account_adapter.py

from allauth.account.adapter import DefaultAccountAdapter


class NoSignupAccountAdapter(DefaultAccountAdapter):
    """Disallow public registration (signup)."""

    def is_open_for_signup(self, request):
        # Always return False - /accounts/signup/ is effectively disabled
        return True
