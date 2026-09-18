# lumenix/templatetags/dashboard_modes.py

from django import template
from django.core.exceptions import ObjectDoesNotExist

from lumenix.models import UserRole

register = template.Library()


@register.inclusion_tag("lumenix/partials/dashboard_mode_select.html", takes_context=True)
def dashboard_mode_select(context):
    """
    Header role selector (replaces the old View selector). The dashboard view
    follows the selected role, so the two can never disagree. Options are the
    same eight roles as the preferences page.
    """
    request = context.get("request")
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"roles": [], "current_role": "", "current_label": ""}
    try:
        profile = user.profile
        current_role, current_label = profile.role, profile.role_label
    except ObjectDoesNotExist:
        current_role, current_label = "", ""
    return {
        "roles": [
            {
                "value": value,
                "label": (current_label if value == UserRole.OTHER and current_role == UserRole.OTHER and current_label else label),
            }
            for value, label in UserRole.choices
        ],
        "current_role": current_role,
        "current_label": current_label,
        "next": request.get_full_path() if request else "/",
    }
