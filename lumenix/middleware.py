# lumenix/middleware.py

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import quote

from lumenix.security import is_locked, record_failure, record_success, register_attempt


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


class AdminLoginProtectionMiddleware:
    """
    Hardens /admin/login against brute-force attempts.
    Uses independent counters from frontend account login.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.scope = "admin"

    def __call__(self, request):
        maybe_block = self.process_request(request)
        if maybe_block:
            return maybe_block
        response = self.get_response(request)
        return self.process_response(request, response)

    def _is_admin_login(self, request):
        return request.path.rstrip("/") == "/admin/login" and request.method == "POST"

    def process_request(self, request):
        if not self._is_admin_login(request):
            return None

        identifier = (request.POST.get("username") or "").strip().lower()
        attempts = register_attempt(request, scope=self.scope)
        if attempts > getattr(settings, "LOGIN_BURST_LIMIT_PER_MINUTE", 20):
            messages.error(request, "Too many admin login attempts. Please wait and try again.")
            next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
            if next_url:
                return redirect(f"/admin/login/?next={quote(next_url, safe='/%?=&')}")
            return redirect("/admin/login/")

        if is_locked(request, identifier, scope=self.scope):
            messages.error(request, "Too many admin login attempts. Please wait and try again.")
            next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
            if next_url:
                return redirect(f"/admin/login/?next={quote(next_url, safe='/%?=&')}")
            return redirect("/admin/login/")

        return None

    def process_response(self, request, response):
        if not self._is_admin_login(request):
            return response

        identifier = (request.POST.get("username") or "").strip().lower()
        if request.user.is_authenticated and response.status_code in (301, 302):
            record_success(request, identifier, scope=self.scope)
        elif response.status_code == 200:
            record_failure(request, identifier, scope=self.scope)

        return response
