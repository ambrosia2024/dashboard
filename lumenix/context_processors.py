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
