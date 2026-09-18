# lumenix/views/assessment.py
"""
V2 design 03 — "Describe your situation".

One confirmed context (name, purpose, resolved region, crop, hazard, period,
resolution) is validated server-side, checked against the synced pathogen data,
optionally saved as a named SavedSituation, and then handed to the existing
chart pages. The browser stores the same context in localStorage (see the
page script) because the current chart pages read it from there.
"""

import re
from datetime import date
from urllib.parse import urlencode, urlparse

import csv
import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Max, Min
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language
from django.views import View
from django.views.generic import TemplateView

from lumenix.models import AssessmentRun, NutsRegion, PathogenConcept, PlantConcept, SavedSituation
from lumenix.services.assessment import build_snapshot, geographic_means, seasonal_matrix
from lumenix.views.pathogen_api import _models_for_queryset, _resolve_pathogen_queryset

# Input rules (server-side; the browser hints are a convenience only).
NAME_MIN, NAME_MAX = 2, 120
NAME_RE = re.compile(r"^[\w .,'’\-()/&·]+$", re.UNICODE)      # letters, digits, spaces, light punctuation
NUTS2_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{1,2}$")               # e.g. NL42, FRY1, ITC4
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
DATE_MIN, DATE_MAX = date(1900, 1, 1), date(2100, 12, 31)


def _clean_text(value, max_len):
    """Strip control characters and surrounding whitespace, cap the length."""
    return CONTROL_RE.sub("", (value or "")).strip()[:max_len]


def concept_identifier(concept):
    """SCiO API identifier for a vocabulary concept: the tail of its URI (same rule as the admin)."""
    parsed = urlparse(concept.uri or "")
    fragment = (parsed.fragment or "").rstrip("/")
    source = fragment or parsed.path
    tail = source.rstrip("/").split("/")[-1]
    return tail or concept.uri


def _label(concept, lang):
    payload = concept.pref_label or {}
    return payload.get(lang) or payload.get("en") or next(iter(payload.values()), "")


def _parse_date(value):
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def _parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class AssessmentCreateView(LoginRequiredMixin, TemplateView):
    template_name = "lumenix/assessment_new.html"

    # ---- context ---------------------------------------------------------

    def _choices(self):
        lang = get_language() or "en"
        crops = PlantConcept.objects.filter(ambrosia_supported=True).order_by("id")
        hazards = PathogenConcept.objects.filter(ambrosia_supported=True).order_by("id")
        return (
            [{"id": c.id, "label": _label(c, lang), "identifier": concept_identifier(c)} for c in crops],
            [{"id": h.id, "label": _label(h, lang), "identifier": concept_identifier(h)} for h in hazards],
        )

    def _initial(self):
        """Prefill from POST (re-render), a ?situation=<id> to reuse, or the last used saved situation."""
        if self.request.method == "POST":
            return {k: v for k, v in self.request.POST.items()}

        rid = self.request.GET.get("run")
        if rid and rid.isdigit():
            run = AssessmentRun.active_objects.filter(user=self.request.user, pk=int(rid)).first()
            if run:
                return {
                    "name": f"{run.name} (copy)"[:120],
                    "purpose": run.purpose,
                    "location": run.location_label,
                    "latitude": run.latitude if run.latitude is not None else "",
                    "longitude": run.longitude if run.longitude is not None else "",
                    "nuts2_code": run.nuts2_code,
                    "nuts2_name": run.nuts2_name,
                    "crop": run.crop_id or "",
                    "hazard": run.hazard_id or "",
                    "start_date": run.start_date.isoformat(),
                    "end_date": run.end_date.isoformat(),
                    "resolution": run.resolution,
                    "model_uuid": run.model_uuid,
                    "model_name": run.model_name,
                }

        situation = None
        sid = self.request.GET.get("situation")
        qs = SavedSituation.active_objects.filter(user=self.request.user)
        if sid and sid.isdigit():
            situation = qs.filter(pk=int(sid)).first()
        if situation is None:
            situation = qs.first()

        if situation is None:
            return {"purpose": SavedSituation.Purpose.ASSESS, "resolution": SavedSituation.Resolution.MONTHLY}

        return {
            "name": situation.name,
            "purpose": situation.purpose,
            "location": situation.location_label,
            "latitude": situation.latitude if situation.latitude is not None else "",
            "longitude": situation.longitude if situation.longitude is not None else "",
            "nuts2_code": situation.nuts2_code,
            "nuts2_name": situation.nuts2_name,
            "crop": situation.crop_id or "",
            "hazard": situation.hazard_id or "",
            "start_date": situation.start_date.isoformat(),
            "end_date": situation.end_date.isoformat(),
            "resolution": situation.resolution,
            "model_uuid": situation.model_uuid,
            "model_name": situation.model_name,
            "situation_id": situation.id,
            "save": "on" if sid else "",
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        crops, hazards = self._choices()
        ctx.update({
            "form": self._initial(),
            "errors": kwargs.get("errors", {}),
            "availability": kwargs.get("availability"),
            "crops": crops,
            "hazards": hazards,
            "purposes": SavedSituation.Purpose.choices,
            "resolutions": SavedSituation.Resolution.choices,
            "saved_situations": SavedSituation.active_objects.filter(user=self.request.user)[:10],
        })
        return ctx

    # ---- submit ----------------------------------------------------------

    def post(self, request, *args, **kwargs):
        data = request.POST
        errors = {}

        name = _clean_text(data.get("name"), NAME_MAX)
        if len(name) < NAME_MIN:
            errors["name"] = "Enter a situation name (at least 2 characters)."
        elif not NAME_RE.match(name):
            errors["name"] = "Use letters, numbers, spaces and simple punctuation only."

        purpose = data.get("purpose") or ""
        if purpose not in SavedSituation.Purpose.values:
            errors["purpose"] = "Choose a purpose."
        elif purpose != SavedSituation.Purpose.ASSESS:
            errors["purpose"] = "Only \"Assess my situation\" is available at the moment."

        location = _clean_text(data.get("location"), 255)
        nuts2_code = _clean_text(data.get("nuts2_code"), 16).upper()
        nuts2_name = _clean_text(data.get("nuts2_name"), 255)
        lat, lon = _parse_float(data.get("latitude")), _parse_float(data.get("longitude"))
        if lat is not None and not -90 <= lat <= 90:
            lat = None
        if lon is not None and not -180 <= lon <= 180:
            lon = None
        if not nuts2_code:
            errors["location"] = "Choose a location so the supported region (NUTS2) can be resolved."
        elif not NUTS2_RE.match(nuts2_code):
            errors["location"] = "The resolved region code is not valid. Search for the location again."
        elif NutsRegion.objects.filter(level=2).exists() and not NutsRegion.objects.filter(level=2, notation=nuts2_code).exists():
            errors["location"] = "The resolved region is not a known NUTS2 region. Search for the location again."

        crop = PlantConcept.objects.filter(pk=data.get("crop") or 0, ambrosia_supported=True).first()
        hazard = PathogenConcept.objects.filter(pk=data.get("hazard") or 0, ambrosia_supported=True).first()
        if not crop:
            errors["crop"] = "Choose a crop."
        if not hazard:
            errors["hazard"] = "Choose a hazard."

        start, end = _parse_date(data.get("start_date")), _parse_date(data.get("end_date"))
        if not start:
            errors["start_date"] = "Enter a start date."
        if not end:
            errors["end_date"] = "Enter an end date."
        if start and end and end < start:
            errors["end_date"] = "End date must be on or after start date."
        for key, value in (("start_date", start), ("end_date", end)):
            if value and not DATE_MIN <= value <= DATE_MAX:
                errors[key] = "Enter a date between 1900 and 2100."

        resolution = data.get("resolution") or ""
        if resolution not in SavedSituation.Resolution.values:
            errors["resolution"] = "Choose a resolution."

        model_uuid = _clean_text(data.get("model_uuid"), 64).lower()
        if model_uuid and not UUID_RE.match(model_uuid):
            errors["model"] = "The selected model is not valid."

        if errors:
            return self.render_to_response(self.get_context_data(errors=errors))

        # Model / data availability for this exact combination.
        qs, resolved_code = _resolve_pathogen_queryset(concept_identifier(crop), concept_identifier(hazard), nuts2_code)
        agg = qs.aggregate(first=Min("observed_on"), last=Max("observed_on"))
        if not agg["first"]:
            errors["availability"] = (
                f"No data is available for {_label(crop, 'en')} · {_label(hazard, 'en')} in "
                f"{nuts2_name or nuts2_code}. Change the crop, hazard or location."
            )
            return self.render_to_response(self.get_context_data(errors=errors))
        if end < agg["first"] or start > agg["last"]:
            errors["availability"] = (
                f"No data between {start.isoformat()} and {end.isoformat()} for this combination. "
                f"Data is available from {agg['first'].isoformat()} to {agg['last'].isoformat()}."
            )
            return self.render_to_response(self.get_context_data(errors=errors))

        # The model must be one that actually produced this data; its name comes from our side, not the form.
        models = _models_for_queryset(qs)
        chosen = next((m for m in models if m["uuid"] == model_uuid), None) if model_uuid else (models[0] if models else None)
        if model_uuid and chosen is None:
            errors["model"] = "The selected model does not match this combination. Choose again."
            return self.render_to_response(self.get_context_data(errors=errors))
        model_uuid, model_name = (chosen["uuid"], chosen["name"]) if chosen else ("", "")

        # Optional named save (create or update the situation being edited).
        situation = None
        if data.get("save") == "on":
            sid = data.get("situation_id") or ""
            if sid.isdigit():
                situation = SavedSituation.active_objects.filter(user=request.user, pk=int(sid)).first()
            if situation is None:
                situation = SavedSituation(user=request.user)
            situation.name = name or f"{_label(crop, 'en')} · {nuts2_name or nuts2_code}"
            situation.purpose = purpose
            situation.location_label = location
            situation.latitude, situation.longitude = lat, lon
            situation.nuts2_code, situation.nuts2_name = nuts2_code, nuts2_name
            situation.crop, situation.hazard = crop, hazard
            situation.start_date, situation.end_date = start, end
            situation.resolution = resolution
            situation.model_uuid, situation.model_name = model_uuid, model_name
            situation.last_used_at = timezone.now()
            situation.save()

        # Freeze the request as a run with its outcome snapshot, then show the outcome.
        period_qs = qs.filter(observed_on__gte=start, observed_on__lte=end)
        run = AssessmentRun.objects.create(
            user=request.user,
            situation=situation if data.get("save") == "on" else None,
            name=name,
            purpose=purpose,
            location_label=location,
            latitude=lat,
            longitude=lon,
            nuts2_code=resolved_code or nuts2_code,
            nuts2_name=nuts2_name,
            crop=crop,
            hazard=hazard,
            crop_label=_label(crop, "en"),
            hazard_label=_label(hazard, "en"),
            start_date=start,
            end_date=end,
            resolution=resolution,
            model_uuid=model_uuid,
            model_name=model_name,
            run_status=AssessmentRun.Status.COMPLETED if period_qs.exists() else AssessmentRun.Status.NO_DATA,
            snapshot=build_snapshot(period_qs, resolution),
        )
        return redirect("assessment-outcome", run_id=run.id)


class FutureConceptView(LoginRequiredMixin, TemplateView):
    """Placeholder for designs 06/07: labelled future concepts, not active in this build."""
    template_name = "lumenix/future_concept.html"
    concepts = {
        "guidance": {
            "title": "Guidance and monitoring",
            "text": "Situation-specific guidance, intervention effectiveness and monitoring are future concepts. "
                    "General references remain available under External Resources.",
        },
        "supply-chain": {
            "title": "Supply chain",
            "text": "Following a product through field, storage, processing, transport, distribution and retail "
                    "is a future concept. This build does not run supply-chain assessments.",
        },
    }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self.concepts.get(self.kwargs.get("concept"), self.concepts["guidance"]))
        return ctx


# All seven catalogue charts, and what this outcome can honestly show for them.
CHART_STATUS = [
    ("c2_pathogen_over_time", "Pathogen concentration vs time", "real", "Source model output for your region and period."),
    ("c5_seasonal_heatmap", "Seasonal heatmap", "derived", "Monthly means of the same model output."),
    ("c6_geographic_risk_heatmap", "Geographic heatmap", "derived", "Period mean per NUTS2 region for the same crop and hazard."),
    ("c1_toxin_over_time", "Toxin concentration vs time", "n/a", "Not applicable: this hazard has no toxin model."),
    ("c3_probability_over_time", "Probability of illness vs time", "n/a", "Needs a dose-response model that the source does not provide."),
    ("c4_cases_per_100k", "Cases per 100k vs time", "n/a", "Needs exposure and population data that the source does not provide."),
    ("c7_climate_scenarios", "Climate-adjusted scenarios", "n/a", "Only one climate-driven run is available; no scenarios to compare."),
]


class _OwnedRunMixin(LoginRequiredMixin):
    def get_run(self):
        return get_object_or_404(
            AssessmentRun.active_objects.select_related("crop", "hazard", "situation", "parent_run"),
            pk=self.kwargs["run_id"],
            user=self.request.user,
        )


class AssessmentOutcomeView(_OwnedRunMixin, TemplateView):
    template_name = "lumenix/assessment_outcome.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        run = self.get_run()
        snap = run.snapshot or {}
        stats = snap.get("stats") or {}
        fetched_ms = stats.get("fetched_at_ms")
        retrieved_at = timezone.datetime.fromtimestamp(fetched_ms / 1000, tz=timezone.get_current_timezone()) if fetched_ms else None
        ctx.update({
            "run": run,
            "snapshot": snap,
            "snapshot_json": json.dumps(snap),
            "stats": stats,
            "provenance": snap.get("provenance") or {},
            "retrieved_at": retrieved_at,
            "newer_runs": run.reruns.filter(status=1).order_by("-created_at")[:3],
            "chart_status": CHART_STATUS,
            "show_technical": getattr(getattr(self.request.user, "profile", None), "show_technical_details", False),
        })
        return ctx


class AssessmentRunAgainView(_OwnedRunMixin, View):
    """New run with the same frozen inputs and freshly read data, linked to the original."""

    def post(self, request, *args, **kwargs):
        run = self.get_run()
        plant, pathogen = concept_identifier(run.crop) if run.crop else "", concept_identifier(run.hazard) if run.hazard else ""
        qs, resolved = _resolve_pathogen_queryset(plant, pathogen, run.nuts2_code, start_date=run.start_date, end_date=run.end_date)
        new = AssessmentRun.objects.create(
            user=request.user, situation=run.situation, parent_run=run,
            name=run.name, purpose=run.purpose, location_label=run.location_label,
            latitude=run.latitude, longitude=run.longitude, nuts2_code=resolved or run.nuts2_code, nuts2_name=run.nuts2_name,
            crop=run.crop, hazard=run.hazard, crop_label=run.crop_label, hazard_label=run.hazard_label,
            start_date=run.start_date, end_date=run.end_date, resolution=run.resolution,
            model_uuid=run.model_uuid, model_name=run.model_name,
            run_status=AssessmentRun.Status.COMPLETED if qs.exists() else AssessmentRun.Status.NO_DATA,
            snapshot=build_snapshot(qs, run.resolution),
        )
        return redirect("assessment-outcome", run_id=new.id)


class AssessmentExportView(_OwnedRunMixin, View):
    """CSV export of the stored series with enough context to identify the run."""

    def get(self, request, *args, **kwargs):
        run = self.get_run()
        snap = run.snapshot or {}
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="ambrosia-{run.run_code}.csv"'
        w = csv.writer(response)
        for key, value in [
            ("run", run.run_code), ("name", run.name), ("created_at", run.created_at.isoformat()),
            ("crop", run.crop_label), ("hazard", run.hazard_label), ("region", f"{run.nuts2_name} ({run.nuts2_code})"),
            ("period", f"{run.start_date.isoformat()} to {run.end_date.isoformat()}"), ("time_scale", run.resolution),
            ("model", run.model_name), ("model_uuid", run.model_uuid), ("unit", snap.get("unit", "")),
            ("status", run.run_status),
        ]:
            w.writerow([f"# {key}", value])
        for line in snap.get("limitations", []):
            w.writerow(["# limitation", line])
        w.writerow(["date", "value", "temperature_c", "days_aggregated"])
        for r in snap.get("series", []):
            w.writerow([r.get("date"), r.get("value"), r.get("temperature_c"), r.get("days")])
        return response


class AssessmentSeasonalView(_OwnedRunMixin, View):
    def get(self, request, *args, **kwargs):
        run = self.get_run()
        plant, pathogen = concept_identifier(run.crop) if run.crop else "", concept_identifier(run.hazard) if run.hazard else ""
        qs, _ = _resolve_pathogen_queryset(plant, pathogen, run.nuts2_code, start_date=run.start_date, end_date=run.end_date)
        return JsonResponse({"rows": seasonal_matrix(qs), "unit": "model output"})


class AssessmentGeographicView(_OwnedRunMixin, View):
    def get(self, request, *args, **kwargs):
        run = self.get_run()
        plant, pathogen = concept_identifier(run.crop) if run.crop else "", concept_identifier(run.hazard) if run.hazard else ""
        values = geographic_means(plant, pathogen, run.start_date, run.end_date)
        return JsonResponse({"values": values, "selected": run.nuts2_code, "unit": "model output", "regions": len(values)})
