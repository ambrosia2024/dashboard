# lumenix/views/dashboardV.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import get_language
from django.views.generic import TemplateView

from lumenix.models import PlantConcept, PathogenConcept, DashboardViewMode, DashboardViewChart


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "lumenix/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        lang = get_language() or "en"

        def pick_label(d):
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

        mode = self._get_active_mode()
        context["current_mode"] = mode
        context["available_modes"] = DashboardViewMode.active_objects.order_by("id")

        if mode:
            view_charts = (
                DashboardViewChart.active_objects
                .select_related("chart", "mode")
                .filter(mode=mode)
                .order_by("order")
            )
            context["charts"] = [
                {
                    "identifier": vc.chart.identifier,
                    "label": vc.chart.label,
                    "template_name": vc.chart.template_name,
                    "config": vc.effective_config,
                }
                for vc in view_charts
            ]
        else:
            context["charts"] = []

        return context

    def _get_active_mode(self):
        qs = DashboardViewMode.active_objects.all()

        # 1) Query param (shareable links)
        mode_code = self.request.GET.get("view") or self.request.GET.get("mode")
        if mode_code:
            mode = qs.filter(code=mode_code).first()
            if mode:
                return mode

        # 2) Cookie (no-login persistence)
        cookie_code = self.request.COOKIES.get("dashboard_mode")
        if cookie_code:
            mode = qs.filter(code=cookie_code).first()
            if mode:
                return mode

        # 3) Default mode
        mode = qs.filter(is_default=True).order_by("id").first()
        if mode:
            return mode

        # 4) Last resort
        return qs.order_by("id").first()

