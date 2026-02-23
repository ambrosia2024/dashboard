# lumenix/views/riskChartsV.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from lumenix.models import DashboardViewMode, DashboardViewChart


class RiskChartsView(LoginRequiredMixin, TemplateView):
    template_name = "lumenix/risk_charts.html"  # default fallback

    def get_template_names(self):
        name = self.request.resolver_match.url_name

        if name == "risk-charts-all":
            return ["lumenix/risk_charts.html"]
        if name == "risk-charts-toxin":
            return ["lumenix/risk_charts_new.html"]

        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        mode = self._get_active_mode()
        ctx["current_mode"] = mode
        ctx["available_modes"] = DashboardViewMode.active_objects.order_by("id")

        view_charts = (
            DashboardViewChart.active_objects
            .select_related("chart", "mode")
            .filter(mode=mode, chart__page_code="risk")
            .order_by("order")
        )

        charts = [{
            "identifier": vc.chart.identifier,
            "label": vc.chart.label,
            "template_name": vc.chart.template_name,
            "config": vc.effective_config,
        } for vc in view_charts]

        ctx["charts"] = charts

        # default selection
        requested = self.request.GET.get("chart")
        selected = next((c for c in charts if c["identifier"] == requested), None) if requested else None
        ctx["selected_chart"] = selected or (charts[0] if charts else None)

        # If this is the toxin-only page, force it to toxin chart (by identifier)
        if self.request.resolver_match.url_name == "risk-charts-toxin":
            toxin = next(
                (c for c in charts if c["identifier"] in ("toxins_over_time", "toxin_over_time", "toxinsChart")), None)
            if toxin:
                ctx["selected_chart"] = toxin

        return ctx

    def _get_active_mode(self):
        qs = DashboardViewMode.active_objects.all()

        # prefer ?view= over anything else
        code = self.request.GET.get("view") or self.request.GET.get("mode")
        if code:
            mode = qs.filter(code=code).first()
            if mode:
                return mode

        # cookie fallback
        cookie_code = self.request.COOKIES.get("dashboard_mode")
        if cookie_code:
            mode = qs.filter(code=cookie_code).first()
            if mode:
                return mode

        mode = qs.filter(is_default=True).order_by("id").first()
        return mode or qs.order_by("id").first()

