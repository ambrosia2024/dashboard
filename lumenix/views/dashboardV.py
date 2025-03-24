from django.views.generic import TemplateView

from lumenix.models import CropMaster


class DashboardView(TemplateView):
    template_name = "lumenix/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["crops"] = CropMaster.active_objects.values()
        context["climate_data_api"] = "/api/climate-data/"
        return context

