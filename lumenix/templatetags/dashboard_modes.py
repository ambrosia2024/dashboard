# lumenix/templatetags/dashboard_modes.py

from django import template
from lumenix.models import DashboardViewMode

register = template.Library()

@register.inclusion_tag("lumenix/partials/dashboard_mode_select.html", takes_context=True)
def dashboard_mode_select(context):
    """
    Provides available dashboard modes for the header.
    Does not decide the active mode (your view does that); it just renders options.
    If current_mode is missing from context, it will render without a selected value.
    """
    return {
        "available_modes": DashboardViewMode.active_objects.order_by("id"),
        "current_mode": context.get("current_mode"),
    }
