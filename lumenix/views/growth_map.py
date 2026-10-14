# lumenix/views/growth_map.py
"""
Pathogen growth in Europe: the cardinal-model (Rosso 1993) growth response,
animated over time on a NUTS2 map. The page holds the controls and the player;
the frames endpoint returns every frame of the chosen period in one response,
so playback only recolours regions and never waits on the server.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.gzip import gzip_page
from django.views.generic import TemplateView

from lumenix.services.cardinal_growth import (
    INDICES, MAX_SPAN_YEARS, STEPS, YEAR_WINDOWS, daily_coverage, frames, index_payload, monthly_coverage,
)

DEFAULT_INDEX = "ecoli"
# The year of WP2's E. coli maps (meeting of 24 Sep 2026), so the two can be compared.
PREFERRED_YEAR = 2000


def _iso(value):
    return value.isoformat() if value else None


class PathogenGrowthMapView(LoginRequiredMixin, TemplateView):
    template_name = "lumenix/pathogen_growth.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        first, last = daily_coverage()
        if first and first.year <= PREFERRED_YEAR <= last.year:
            default_year = PREFERRED_YEAR
        else:
            default_year = first.year if first else PREFERRED_YEAR
        indices = {}
        for key, index in INDICES.items():
            m_first, m_last = monthly_coverage(index)
            indices[key] = {"label": index.label, "monthly": [_iso(m_first), _iso(m_last)]}
        ctx.update({
            "indices": list(INDICES.values()),
            "default_index": DEFAULT_INDEX,
            "index": INDICES[DEFAULT_INDEX],
            "daily_first": first,
            "daily_last": last,
            "default_year": default_year,
            "config": {
                "framesUrl": reverse("pathogen-growth-frames"),
                "daily": [_iso(first), _iso(last)],
                "indices": indices,
                "maxSpan": MAX_SPAN_YEARS,
                "windows": YEAR_WINDOWS,
                "defaultYear": default_year,
            },
        })
        return ctx


@method_decorator(gzip_page, name="dispatch")
class PathogenGrowthFramesView(LoginRequiredMixin, View):
    """
    GET ?index=ecoli&step=day|week|month|year&start=YYYY&end=YYYY[&window=1|5|10|30]

    {"index": {...cardinal temperatures, curve}, "frames": [label],
     "regions": [code], "mu": [[...]], "temperature": [[...]]} - one row per
    frame, one column per region. Up to ~180k cells (month step, 50 years),
    hence the gzip.
    """

    def get(self, request, *args, **kwargs):
        try:
            index, step, start, end, window = self._params(request)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        data = frames(index, step, start, end, window)
        payload = {"index": index_payload(index), "step": step, "start": start, "end": end, "window": window, **data}
        if not data["frames"]:
            payload["message"] = self._empty_message(index, step, start, end)
        return JsonResponse(payload)

    def _params(self, request):
        key = (request.GET.get("index") or DEFAULT_INDEX).strip()
        if key not in INDICES:
            raise ValueError("Unknown pathogen.")
        step = (request.GET.get("step") or "day").strip()
        if step not in STEPS:
            raise ValueError("The step must be day, week, month or year.")

        def year(name):
            raw = (request.GET.get(name) or "").strip()
            if not raw.isdigit() or not 1900 <= int(raw) <= 2100:
                raise ValueError("Years must be between 1900 and 2100.")
            return int(raw)

        start, end = year("start"), year("end")
        if end < start:
            raise ValueError("The period ends before it starts.")
        span = end - start + 1
        if span > MAX_SPAN_YEARS[step]:
            limit = MAX_SPAN_YEARS[step]
            raise ValueError(
                f"A {step} step covers at most {limit} year{'s' if limit > 1 else ''}. "
                f"Choose a shorter period or a longer step."
            )

        window = 1
        if step == "year":
            raw = (request.GET.get("window") or "1").strip()
            if not raw.isdigit() or int(raw) not in YEAR_WINDOWS:
                raise ValueError("The averaging window must be 1, 5, 10 or 30 years.")
            window = int(raw)
            if span < window:
                raise ValueError(f"A {window}-year average needs a period of at least {window} years.")
        return INDICES[key], step, start, end, window

    def _empty_message(self, index, step, start, end):
        if step in ("month", "year"):
            first, last = monthly_coverage(index)
            if first is None:
                return (
                    f"The monthly table for {index.label} has not been built yet, so month and year steps "
                    f"have nothing to show. An administrator can build it with "
                    f"'python manage.py build_cardinal_growth'."
                )
            return f"No monthly values for {start}–{end}. The monthly table covers {first:%Y-%m} to {last:%Y-%m}."
        first, last = daily_coverage()
        if first is None:
            return "There are no temperature records yet."
        return f"No temperature records for {start}–{end}. The records cover {first} to {last}."
