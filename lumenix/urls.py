# lumenix/urls.py

from django.urls import path
from .views import DashboardView, ClimateDataGeoJSONView, RiskChartsView
from .views.chart_ai import chart_qa_stream
from .views.pathogen_api import pathogen_concentration_meta, pathogen_concentration_query

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path("api/climate-data/", ClimateDataGeoJSONView.as_view(), name="climate_data_geojson"),

    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("risk-charts/", RiskChartsView.as_view(), name="risk-charts-all"),
    path("risk-charts/chart/<slug:chart_identifier>/", RiskChartsView.as_view(), name="risk-charts-item"),
    path("risk-charts/toxin/", RiskChartsView.as_view(), name="risk-charts-toxin"),
    path("risk-charts/pathogen/", RiskChartsView.as_view(), name="risk-charts-pathogen"),
    path("api/risk-charts/<slug:chart_identifier>/qa-stream/", chart_qa_stream, name="risk-chart-qa-stream"),
    path("api/risk-charts/pathogen-concentration/meta/", pathogen_concentration_meta, name="risk-chart-pathogen-meta"),
    path("api/risk-charts/pathogen-concentration/query/", pathogen_concentration_query, name="risk-chart-pathogen-query"),

]
