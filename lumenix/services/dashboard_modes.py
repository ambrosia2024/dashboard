# lumenix/services/dashboard_modes.py
"""Shared dashboard view-mode resolution + per-view chart emphasis lookup.

Used by the dashboard/risk views (via DashboardModeMixin) and by the sidebar
template tag so the active view is resolved the same way everywhere.
"""

from django.core.exceptions import ObjectDoesNotExist

from lumenix.models import DashboardViewMode, DashboardViewChart


def _get_user_profile(request):
    try:
        return request.user.profile
    except (ObjectDoesNotExist, AttributeError):
        return None


def is_mode_locked(request):
    """True when the user has an admin-assigned mode that overrides the selector."""
    profile = _get_user_profile(request)
    return bool(profile and profile.dashboard_mode_id)


def get_active_mode(request):
    """Resolve the active view mode: profile > ?view=/?mode= > cookie > default > first."""
    qs = DashboardViewMode.active_objects.all()

    profile = _get_user_profile(request)
    if profile and profile.dashboard_mode_id:
        mode = qs.filter(pk=profile.dashboard_mode_id).first()
        if mode:
            return mode

    code = request.GET.get("view") or request.GET.get("mode")
    if code:
        mode = qs.filter(code=code).first()
        if mode:
            return mode

    cookie_code = request.COOKIES.get("dashboard_mode")
    if cookie_code:
        mode = qs.filter(code=cookie_code).first()
        if mode:
            return mode

    mode = qs.filter(is_default=True).order_by("id").first()
    return mode or qs.order_by("id").first()


def chart_emphasis_map(mode):
    """{chart_identifier: emphasis} for the given mode (empty when mode is None)."""
    if not mode:
        return {}
    rows = (
        DashboardViewChart.active_objects
        .select_related("chart")
        .filter(mode=mode)
    )
    return {row.chart.identifier: row.emphasis for row in rows}
