# lumenix/urls.py

from django.urls import path
from django.views.generic import RedirectView
from .views import DashboardView, ClimateDataGeoJSONView, RiskChartsView
from .views.chart_ai import chart_qa_stream
from .views.pathogen_api import pathogen_concentration_meta, pathogen_concentration_query
from .views.workspace import PreferencesView, WorkspaceView
from .views.ambra import AmbraAskView, AmbraDownloadView, AmbraMessagesView
from .views.situations import (
    RunDeleteView, SituationDeleteView, SituationDuplicateView, SituationRenameView, SituationsView,
)
from .views.assessment import (
    AssessmentCreateView, AssessmentExportView, AssessmentGeographicView, AssessmentOutcomeView,
    AssessmentRunAgainView, AssessmentSeasonalView, FutureConceptView,
)

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='overview', permanent=False), name='home'),
    path("overview/", WorkspaceView.as_view(), name="overview"),
    path("preferences/", PreferencesView.as_view(), name="account_preferences"),
    path("assessments/new/", AssessmentCreateView.as_view(), name="assessment-new"),
    path("assessments/<int:run_id>/", AssessmentOutcomeView.as_view(), name="assessment-outcome"),
    path("assessments/<int:run_id>/run-again/", AssessmentRunAgainView.as_view(), name="assessment-run-again"),
    path("assessments/<int:run_id>/export.csv", AssessmentExportView.as_view(), name="assessment-export"),
    path("assessments/<int:run_id>/delete/", RunDeleteView.as_view(), name="assessment-delete"),
    path("assessments/<int:run_id>/ambra.txt", AmbraDownloadView.as_view(), name="assessment-ambra-download"),
    path("api/assessments/<int:run_id>/ambra/", AmbraMessagesView.as_view(), name="assessment-ambra-messages"),
    path("api/assessments/<int:run_id>/ambra/ask/", AmbraAskView.as_view(), name="assessment-ambra-ask"),
    path("situations/", SituationsView.as_view(), name="situations"),
    path("situations/<int:situation_id>/rename/", SituationRenameView.as_view(), name="situation-rename"),
    path("situations/<int:situation_id>/duplicate/", SituationDuplicateView.as_view(), name="situation-duplicate"),
    path("situations/<int:situation_id>/delete/", SituationDeleteView.as_view(), name="situation-delete"),
    path("api/assessments/<int:run_id>/seasonal/", AssessmentSeasonalView.as_view(), name="assessment-seasonal"),
    path("api/assessments/<int:run_id>/geographic/", AssessmentGeographicView.as_view(), name="assessment-geographic"),
    path("guidance/", FutureConceptView.as_view(), {"concept": "guidance"}, name="guidance"),
    path("supply-chain/", FutureConceptView.as_view(), {"concept": "supply-chain"}, name="supply-chain"),
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
