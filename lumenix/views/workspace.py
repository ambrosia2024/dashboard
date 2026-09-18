# lumenix/views/workspace.py
"""
V2 journey entry pages:

- PreferencesView  (design 01-profile): self-declared role + technical-details
  preference, stored on UserProfile. Shown after login until a role is saved.
- WorkspaceView    (design 02-workspace): the landing page once preferences
  are saved. Saved situations and assessment history are not implemented yet,
  so their sections render the empty states from the implementation handoff.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView

from lumenix.models import ROLE_TO_VIEW_MODE, AssessmentRun, DashboardViewMode, SavedSituation, UserProfile, UserRole

# Feather icon per role, purely decorative.
ROLE_ICONS = {
    UserRole.FARMER: "sun",
    UserRole.FORESTER: "feather",
    UserRole.ADVISOR: "users",
    UserRole.PRODUCER: "package",
    UserRole.DISTRIBUTOR: "truck",
    UserRole.POLICY_MAKER: "briefcase",
    UserRole.TECHNICIAN: "tool",
    UserRole.OTHER: "compass",
}

SKIP_SESSION_KEY = "preferences_skipped"


def get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


class PreferencesView(LoginRequiredMixin, TemplateView):
    template_name = "lumenix/preferences.html"

    def _safe_next(self):
        candidate = self.request.POST.get("next") or self.request.GET.get("next") or ""
        if candidate and url_has_allowed_host_and_scheme(candidate, allowed_hosts={self.request.get_host()}):
            return candidate
        return reverse("overview")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = get_or_create_profile(self.request.user)
        if self.request.method == "POST":
            selected = self.request.POST.get("role", profile.role)
        else:
            requested = self.request.GET.get("role", "")
            selected = requested if requested in UserRole.values else profile.role
        ctx.update({
            "profile": profile,
            "roles": [
                {
                    "value": value,
                    "label": label,
                    "icon": ROLE_ICONS.get(value, "circle"),
                    "selected": value == selected,
                }
                for value, label in UserRole.choices
            ],
            "role_other": (
                self.request.POST.get("role_other", "") if self.request.method == "POST" else profile.role_other
            ),
            "show_technical_details": (
                self.request.POST.get("show_technical_details") == "on"
                if self.request.method == "POST" else profile.show_technical_details
            ),
            "role_error": kwargs.get("role_error", ""),
            "role_other_error": kwargs.get("role_other_error", ""),
            "next": self._safe_next(),
            "first_time": not profile.role,
        })
        return ctx

    def post(self, request, *args, **kwargs):
        profile = get_or_create_profile(request.user)

        if request.POST.get("action") == "technical":
            profile.show_technical_details = request.POST.get("show_technical_details") == "on"
            profile.save(update_fields=["show_technical_details"])
            return redirect(self._safe_next())

        if request.POST.get("action") == "skip":
            # Skipping is per sign-in: the page comes back on the next login
            # until a role has actually been saved.
            request.session[SKIP_SESSION_KEY] = True
            return redirect(self._safe_next())

        role = (request.POST.get("role") or "").strip()
        quick = request.POST.get("action") == "quick_role"   # header selector: role only
        if role not in UserRole.values or (quick and role == UserRole.OTHER):
            if quick:
                return redirect(f"{reverse('account_preferences')}?role=other&next={self._safe_next()}")
            return self.render_to_response(self.get_context_data(role_error="Choose a role to continue."))

        role_other = (request.POST.get("role_other") or "").strip()[:100]
        if role == UserRole.OTHER and not role_other:
            return self.render_to_response(self.get_context_data(role_other_error="Tell us your role to continue."))
        if role != UserRole.OTHER:
            role_other = ""

        profile.role = role
        profile.role_other = role_other
        # Technical details is toggled on the outcome page (action="technical"), not here.
        profile.preferences_saved_at = timezone.now()
        # The dashboard view follows the role, so the header "View" and the
        # chosen role can never disagree.
        mode = DashboardViewMode.active_objects.filter(code=ROLE_TO_VIEW_MODE.get(role, "default")).first()
        profile.dashboard_mode = mode
        profile.save(update_fields=["role", "role_other", "preferences_saved_at", "dashboard_mode"])
        request.session.pop(SKIP_SESSION_KEY, None)
        messages.success(request, "Preferences saved.")

        response = redirect(self._safe_next())
        if mode:
            response.set_cookie("dashboard_mode", mode.code, max_age=60 * 60 * 24 * 90, samesite="Lax")
        return response


class WorkspaceView(LoginRequiredMixin, TemplateView):
    template_name = "lumenix/overview.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = get_or_create_profile(self.request.user)
        ctx.update({
            "profile": profile,
            # Not implemented yet: both lists are intentionally empty so the
            # page shows the handoff's empty states rather than sample data.
            "saved_situations": SavedSituation.active_objects.filter(user=self.request.user).select_related("crop", "hazard")[:6],
            "recent_requests": AssessmentRun.active_objects.filter(user=self.request.user)[:8],
            "explorations": [
                {
                    "title": "Explore climate history",
                    "text": "Review past trends and events for a region.",
                    "icon": "clock",
                    "url": "",
                },
                {
                    "title": "Explore future climate",
                    "text": "See projections and scenarios for a location.",
                    "icon": "thermometer",
                    "url": "",
                },
                {
                    "title": "Assess my situation",
                    "text": "Combine crop, hazard and location for specific risks.",
                    "icon": "target",
                    "url": reverse("assessment-new"),
                },
            ],
        })
        return ctx
