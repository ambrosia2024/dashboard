# lumenix/views/profile.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import FormView

from lumenix.forms import ProfileCompletionForm


class CompleteProfileView(LoginRequiredMixin, FormView):
    """
    Intermediary page shown after login if the user has no first/last name.
    """
    template_name = "account/complete_profile.html"
    form_class = ProfileCompletionForm
    success_url = reverse_lazy("dashboard")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)
