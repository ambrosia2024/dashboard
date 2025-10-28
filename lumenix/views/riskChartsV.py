# lumenix/views/riskChartsV.py

from django.views.generic import TemplateView

class RiskChartsView(TemplateView):
    template_name = "lumenix/risk_charts.html"

