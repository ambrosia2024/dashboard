# lumenix/urls.py

from django.urls import path
from .views import DashboardView, ClimateDataGeoJSONView, RiskChartsView

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path("api/climate-data/", ClimateDataGeoJSONView.as_view(), name="climate_data_geojson"),

    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("risk-charts/", RiskChartsView.as_view(), name="risk-charts-all"),
    path("risk-charts/toxin/", RiskChartsView.as_view(), name="risk-charts-toxin"),

]
