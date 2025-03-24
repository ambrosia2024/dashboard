from django.urls import path
from .views import DashboardView, ClimateDataGeoJSONView

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path("api/climate-data/", ClimateDataGeoJSONView.as_view(), name="climate_data_geojson"),
]
