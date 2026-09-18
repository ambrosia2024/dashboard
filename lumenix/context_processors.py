# lumenix/context_processors.py

from django.utils.translation import get_language

from lumenix.models import PlantConcept, PathogenConcept


def _pick_label(payload, lang):
    if isinstance(payload, dict):
        return payload.get(lang) or payload.get("en") or next(iter(payload.values()), "")
    return ""


def risk_context_data(request):
    """
    Global crop/hazard lists for compact cross-page context controls.
    """
    lang = get_language() or "en"

    crops = (
        PlantConcept.objects
        .filter(ambrosia_supported=True)
        .only("id", "pref_label")
        .order_by("id")
    )
    hazards = (
        PathogenConcept.objects
        .filter(ambrosia_supported=True)
        .only("id", "pref_label")
        .order_by("id")
    )

    return {
        "global_risk_crops": [{"id": c.id, "label": _pick_label(c.pref_label, lang)} for c in crops],
        "global_risk_hazards": [{"id": h.id, "label": _pick_label(h.pref_label, lang)} for h in hazards],
    }


def auth_flags(request):
    """
    Flags the authentication templates need, e.g. whether the login page may
    advertise account creation. Mirrors the account adapter's decision.
    """
    from allauth.account.adapter import get_adapter

    try:
        signup_open = bool(get_adapter(request).is_open_for_signup(request))
    except Exception:  # pragma: no cover - never break page rendering over a flag
        signup_open = False
    return {"signup_open": signup_open}


def user_preferences(request):
    """
    The signed-in user's V2 preferences (role label, technical-details flag)
    for the app shell, e.g. the role chip in the header.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    try:
        profile = user.profile
    except Exception:
        return {"user_role": "", "user_role_label": "", "show_technical_details": False}
    return {
        "user_role": profile.role,
        "user_role_label": profile.role_label,
        "show_technical_details": profile.show_technical_details,
    }
