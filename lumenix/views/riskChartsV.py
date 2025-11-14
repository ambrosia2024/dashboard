# lumenix/views/riskChartsV.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

class RiskChartsView(LoginRequiredMixin, TemplateView):
    template_name = "lumenix/risk_charts.html"

