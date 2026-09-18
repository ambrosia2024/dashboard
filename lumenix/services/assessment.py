# lumenix/services/assessment.py
"""
Outcome data for an assessment run, derived from the synced pathogen records.

Everything here is computed from PathogenConcentrationRecord rows for one
crop + hazard (+ region) and a period. No values are invented: when there is
nothing to aggregate the functions return empty results.
"""

from django.db.models import Avg, Count, Max, Min
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek, TruncYear

from lumenix.models import PathogenConcentrationRecord

TRUNC = {
    "daily": TruncDay,
    "weekly": TruncWeek,
    "monthly": TruncMonth,
    "yearly": TruncYear,
}


def aggregate_series(qs, resolution):
    """[{date, value, temperature_c, days}] averaged per period at the requested time scale."""
    trunc = TRUNC.get(resolution, TruncMonth)
    rows = (
        qs.annotate(period=trunc("observed_on"))
        .values("period")
        .annotate(value=Avg("pathogen_model_value"), temperature_c=Avg("temperature_c"), days=Count("id"))
        .order_by("period")
    )
    return [
        {
            "date": r["period"].date().isoformat() if hasattr(r["period"], "date") else r["period"].isoformat(),
            "value": round(r["value"], 4) if r["value"] is not None else None,
            "temperature_c": round(r["temperature_c"], 2) if r["temperature_c"] is not None else None,
            "days": r["days"],
        }
        for r in rows
    ]


def series_stats(qs):
    agg = qs.aggregate(
        days=Count("id"),
        mean=Avg("pathogen_model_value"),
        low=Min("pathogen_model_value"),
        high=Max("pathogen_model_value"),
        first=Min("observed_on"),
        last=Max("observed_on"),
        fetched_at_ms=Max("provenance_fetched_at_ms"),
    )
    peak = (
        qs.exclude(pathogen_model_value__isnull=True).order_by("-pathogen_model_value", "observed_on").values("observed_on", "pathogen_model_value").first()
    )
    return {
        "days": agg["days"] or 0,
        "mean": round(agg["mean"], 4) if agg["mean"] is not None else None,
        "min": round(agg["low"], 4) if agg["low"] is not None else None,
        "max": round(agg["high"], 4) if agg["high"] is not None else None,
        "first_date": agg["first"].isoformat() if agg["first"] else None,
        "last_date": agg["last"].isoformat() if agg["last"] else None,
        "peak_date": peak["observed_on"].isoformat() if peak else None,
        "fetched_at_ms": agg["fetched_at_ms"],
    }


def seasonal_matrix(qs):
    """[{year, month, value}] mean model value per calendar month, for the seasonal heatmap."""
    rows = (
        qs.annotate(period=TruncMonth("observed_on"))
        .values("period")
        .annotate(value=Avg("pathogen_model_value"))
        .order_by("period")
    )
    out = []
    for r in rows:
        d = r["period"].date() if hasattr(r["period"], "date") else r["period"]
        out.append({"year": d.year, "month": d.month, "value": round(r["value"], 4) if r["value"] is not None else None})
    return out


def geographic_means(plant, pathogen, start_date, end_date):
    """{nuts_code: mean model value} for every synced region of this crop + hazard in the period."""
    rows = (
        PathogenConcentrationRecord.active_objects.filter(
            plant=plant, pathogen=pathogen, observed_on__gte=start_date, observed_on__lte=end_date
        )
        .values("nuts_code")
        .annotate(value=Avg("pathogen_model_value"), days=Count("id"))
        .order_by("nuts_code")
    )
    return {r["nuts_code"]: {"value": round(r["value"], 4) if r["value"] is not None else None, "days": r["days"]} for r in rows}


def provenance(qs):
    first = qs.exclude(provenance_model_id="").values(
        "provenance_model_id", "provenance_model_title", "provenance_variable_name"
    ).first()
    if not first:
        return {}
    return {
        "model_id": first["provenance_model_id"],
        "model_title": first["provenance_model_title"],
        "variable_name": first["provenance_variable_name"],
    }


def build_snapshot(qs, resolution):
    """The stored outcome for a run: series at the requested scale, summary stats and provenance."""
    return {
        "schema": 1,
        "unit": "model output",
        "series": aggregate_series(qs, resolution),
        "stats": series_stats(qs),
        "provenance": provenance(qs),
        "limitations": [
            "Values are the source model's output for the region's climate input, not a validated risk prediction.",
            "Results represent the supported NUTS2 region, not an individual field.",
            "Uncertainty is not supplied by the source; do not interpret its absence as low uncertainty.",
        ],
    }
