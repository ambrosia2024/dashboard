# lumenix/middleware.py

from django.shortcuts import redirect
from django.urls import reverse


class EnforceProfileCompletionMiddleware:
    """
    If a logged-in user has no first_name or last_name, redirect them to the profile completion page, unless they are
    already there or on an allowed path (login, logout, static, etc.).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.process_request(request)
        if response:
            return response
        return self.get_response(request)

    def process_request(self, request):
        user = request.user
        path = request.path

        if path.startswith("/static/"):
            return None

        # Resolve exempt paths once per request (cheap enough)
        try:
            complete_profile_url = reverse("account_complete_profile")
            login_url = reverse("account_login")
            signup_url = reverse("account_signup")
            reset_url = reverse("account_reset_password")
        except Exception:
            return None

        exempt_paths = {
            complete_profile_url,
            login_url,
            signup_url,
            reset_url,
            "/admin/login/",
        }

        if user.is_authenticated:
            missing_names = not user.first_name or not user.last_name
            if missing_names and path not in exempt_paths:
                return redirect("account_complete_profile")

        return None
