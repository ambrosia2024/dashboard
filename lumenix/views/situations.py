# lumenix/views/situations.py
"""
V2 design 05 — Saved situations and assessment history.

One page with two tabs: named saved situations (rename, duplicate, delete)
and the run history (search, filters, a detail panel per run with
Run again / Open original / Duplicate settings / Delete).
"""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from lumenix.models import AssessmentRun, SavedSituation


class SituationsView(LoginRequiredMixin, TemplateView):
    template_name = "lumenix/situations.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        g = self.request.GET

        q = (g.get("q") or "").strip()[:100]
        status = g.get("status") or ""
        when = g.get("when") or ""

        runs = AssessmentRun.active_objects.filter(user=user).select_related("parent_run")
        if q:
            runs = runs.filter(Q(name__icontains=q) | Q(crop_label__icontains=q) | Q(hazard_label__icontains=q) | Q(nuts2_code__icontains=q) | Q(nuts2_name__icontains=q))
        if status in AssessmentRun.Status.values:
            runs = runs.filter(run_status=status)
        if when in ("7", "30", "90"):
            runs = runs.filter(created_at__gte=timezone.now() - timedelta(days=int(when)))
        runs = list(runs[:50])

        selected = None
        rid = g.get("run")
        if rid and rid.isdigit():
            selected = next((r for r in runs if r.id == int(rid)), None) or AssessmentRun.active_objects.filter(user=user, pk=int(rid)).first()
        if selected is None and runs:
            selected = runs[0]

        newer = selected.reruns.filter(status=1).order_by("-created_at").first() if selected else None
        stats = (selected.snapshot or {}).get("stats", {}) if selected else {}
        fetched_ms = stats.get("fetched_at_ms")
        synced_at = timezone.datetime.fromtimestamp(fetched_ms / 1000, tz=timezone.get_current_timezone()) if fetched_ms else None

        ctx.update({
            "tab": "history" if g.get("tab") == "history" else "saved",
            "situations": SavedSituation.active_objects.filter(user=user).select_related("crop", "hazard"),
            "runs": runs,
            "selected": selected,
            "selected_newer": newer,
            "selected_stats": stats,
            "selected_synced_at": synced_at,
            "q": q, "status": status, "when": when,
            "statuses": AssessmentRun.Status.choices,
            "show_technical": getattr(getattr(user, "profile", None), "show_technical_details", False),
        })
        return ctx


class _SituationAction(LoginRequiredMixin, View):
    def get_situation(self):
        return get_object_or_404(SavedSituation.active_objects, pk=self.kwargs["situation_id"], user=self.request.user)

    def back(self):
        return redirect(reverse("situations"))


class SituationRenameView(_SituationAction):
    def post(self, request, *args, **kwargs):
        s = self.get_situation()
        name = (request.POST.get("name") or "").strip()[:120]
        if len(name) >= 2:
            s.name = name
            s.save(update_fields=["name", "updated_at"])
            messages.success(request, "Situation renamed.")
        else:
            messages.error(request, "Enter a name of at least 2 characters.")
        return self.back()


class SituationDuplicateView(_SituationAction):
    def post(self, request, *args, **kwargs):
        s = self.get_situation()
        s.pk = None
        s.name = f"{s.name} (copy)"[:120]
        s.last_used_at = None
        s.save()
        messages.success(request, "Situation duplicated.")
        return self.back()


class SituationDeleteView(_SituationAction):
    def post(self, request, *args, **kwargs):
        s = self.get_situation()
        s.soft_delete()  # runs keep their own copy of the inputs
        messages.success(request, "Situation deleted. Existing assessment results remain.")
        return self.back()


class RunDeleteView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        run = get_object_or_404(AssessmentRun.active_objects, pk=self.kwargs["run_id"], user=request.user)
        run.soft_delete()
        messages.success(request, f"{run.run_code} removed from your history.")
        return redirect(f"{reverse('situations')}?tab=history")
