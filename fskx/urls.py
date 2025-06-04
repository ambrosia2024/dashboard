from django.urls import path
from .views import (
    fskx_run_test,
    fskx_status_test,
    fskx_res_test,
)

urlpatterns = [
    path('fskx-run/<int:model_type>/', fskx_run_test, name='fskx-run'),
    path('fskx-status/<str:simulation_id>/', fskx_status_test, name='fskx-status'),
    path('fskx-res/<str:simulation_id>/', fskx_res_test, name='fskx-res'),
]
