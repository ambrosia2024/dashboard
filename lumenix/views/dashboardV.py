# lumenix/views/dashboardV.py

from django.utils.translation import get_language
from django.views.generic import TemplateView

from lumenix.models import PlantConcept, PathogenConcept


class DashboardView(TemplateView):
    template_name = "lumenix/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        lang = get_language() or "en"

        def pick_label(d):
            # d is the JSONField dict of labels; pick lang -> en -> any
            if isinstance(d, dict):
                return d.get(lang) or d.get("en") or next(iter(d.values()), "")
            return ""

        crops_qs = (
            PlantConcept.objects
            .filter(ambrosia_supported=True)
            .only("id", "pref_label")
            .order_by("id")
        )
        paths_qs = (
            PathogenConcept.objects
            .filter(ambrosia_supported=True)
            .only("id", "pref_label")
            .order_by("id")
        )

        context["crops"] = [{"id": c.id, "label": pick_label(c.pref_label)} for c in crops_qs]
        context["pathogens"] = [{"id": p.id, "label": pick_label(p.pref_label)} for p in paths_qs]

        return context

