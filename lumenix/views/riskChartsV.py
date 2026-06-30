# lumenix/views/riskChartsV.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from lumenix.models import DashboardViewMode, DashboardViewChart, DashboardChart
from lumenix.services.dashboard_modes import chart_emphasis_map
from lumenix.views.mixins import DashboardModeMixin


class RiskChartsView(DashboardModeMixin, LoginRequiredMixin, TemplateView):
    template_name = "lumenix/risk_charts.html"  # default fallback

    def get_template_names(self):
        name = self.request.resolver_match.url_name

        if name == "risk-charts-all":
            return ["lumenix/risk_charts.html"]
        if name == "risk-charts-item":
            return ["lumenix/risk_charts_new.html"]
        if name == "risk-charts-toxin":
            return ["lumenix/risk_charts_new.html"]
        if name == "risk-charts-pathogen":
            return ["lumenix/risk_charts_new.html"]

        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        mode = self.get_active_mode()
        ctx["current_mode"] = mode
        ctx["mode_locked"] = self.is_mode_locked()
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
            "emphasis": vc.emphasis,
        } for vc in view_charts]

        ctx["charts"] = charts

        def first_enabled(items):
            return next((c for c in items if c["emphasis"] != "disabled"), items[0] if items else None)

        # default selection: honour ?chart=, else the first non-disabled chart
        requested = self.request.GET.get("chart")
        selected = next((c for c in charts if c["identifier"] == requested), None) if requested else None
        ctx["selected_chart"] = selected or first_enabled(charts)

        # If a specific chart identifier is in path, force that selection.
        chart_identifier = self.kwargs.get("chart_identifier")
        if chart_identifier:
            linked = next((c for c in charts if c["identifier"] == chart_identifier), None)
            if linked:
                ctx["selected_chart"] = linked
            else:
                # Allow sidebar-driven direct links even when the chart is not in the current mode mapping.
                standalone = (
                    DashboardChart.active_objects
                    .filter(identifier=chart_identifier, page_code="risk")
                    .first()
                )
                if standalone:
                    ctx["selected_chart"] = {
                        "identifier": standalone.identifier,
                        "label": standalone.label,
                        "template_name": standalone.template_name,
                        "config": standalone.default_config or {},
                    }

        # If this is the toxin-only page, force it to toxin chart (by identifier)
        if self.request.resolver_match.url_name == "risk-charts-toxin":
            toxin = next(
                (c for c in charts if c["identifier"] in ("toxin_over_time")), None)
            if toxin:
                ctx["selected_chart"] = toxin

        # If this is the pathogen-only page, force it to pathogen chart (by identifier)
        if self.request.resolver_match.url_name == "risk-charts-pathogen":
            pathogen = next(
                (c for c in charts if c["identifier"] in ("pathogen_concentration_over_time")), None)
            if pathogen:
                ctx["selected_chart"] = pathogen

        # Guard: if the selected chart is greyed-out (disabled) for the active view,
        # the template shows a "not available in this view" notice instead of the chart.
        selected = ctx.get("selected_chart")
        emphasis = chart_emphasis_map(mode).get(selected["identifier"]) if selected else None
        ctx["chart_unavailable"] = emphasis == "disabled"
        ctx["current_mode_label"] = mode.label if mode else ""

        return ctx
