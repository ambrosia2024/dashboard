# lumenix/services/assessment.py
"""
Outcome data for an assessment run, derived from the synced pathogen records.

Everything here is computed from PathogenConcentrationRecord rows for one
crop + hazard (+ region) and a period. No values are invented: when there is
nothing to aggregate the functions return empty results.
"""

from django.db.models import Avg, Count, Max, Min, StdDev

from lumenix.services.pathogen_query import identifier_variants
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
        .annotate(
            value=Avg("pathogen_model_value"),
            value_min=Min("pathogen_model_value"),
            value_max=Max("pathogen_model_value"),
            temperature_c=Avg("temperature_c"),
            days=Count("id"),
        )
        .order_by("period")
    )
    return [
        {
            "date": r["period"].date().isoformat() if hasattr(r["period"], "date") else r["period"].isoformat(),
            "value": round(r["value"], 4) if r["value"] is not None else None,
            "value_min": round(r["value_min"], 4) if r["value_min"] is not None else None,
            "value_max": round(r["value_max"], 4) if r["value_max"] is not None else None,
            "temperature_c": round(r["temperature_c"], 2) if r["temperature_c"] is not None else None,
            "days": r["days"],
        }
        for r in rows
    ]


def variability(qs):
    """
    Spread of the model output over the period, computed from the stored daily
    values. This describes how much the output swings; it is NOT a model
    uncertainty estimate (the source supplies none).
    """
    agg = qs.aggregate(mean=Avg("pathogen_model_value"), sd=StdDev("pathogen_model_value"), low=Min("pathogen_model_value"), high=Max("pathogen_model_value"))
    if agg["mean"] is None:
        return {}
    yearly = list(
        qs.annotate(y=TruncYear("observed_on")).values("y").annotate(peak=Max("pathogen_model_value"), low=Min("pathogen_model_value")).order_by("y")
    )
    peaks = [r["peak"] for r in yearly if r["peak"] is not None]
    lows = [r["low"] for r in yearly if r["low"] is not None]
    sd = agg["sd"] or 0.0
    return {
        "stddev": round(sd, 4),
        "cv_pct": round(100 * sd / agg["mean"], 1) if agg["mean"] else None,
        "min": round(agg["low"], 4),
        "max": round(agg["high"], 4),
        "years": len(yearly),
        "yearly_peak_min": round(min(peaks), 4) if peaks else None,
        "yearly_peak_max": round(max(peaks), 4) if peaks else None,
        "yearly_peak_mean": round(sum(peaks) / len(peaks), 4) if peaks else None,
        "yearly_low_mean": round(sum(lows) / len(lows), 4) if lows else None,
        "basis": "daily model output values in the requested period and region",
    }


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
            # Same spelling tolerance as the main lookup: specs store the source
            # API's spaced identifiers, the vocabulary gives hyphenated ones.
            plant__in=identifier_variants(plant),
            pathogen__in=identifier_variants(pathogen),
            observed_on__gte=start_date,
            observed_on__lte=end_date,
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
        "variability": variability(qs),
        "provenance": provenance(qs),
        "limitations": [
            "Values are the source model's output for the region's climate input, not a validated risk prediction.",
            "Results represent the supported NUTS2 region, not an individual field.",
            "Uncertainty is not supplied by the source; do not interpret its absence as low uncertainty.",
            "The variability figures describe the spread of the model output itself; they are not an uncertainty estimate.",
        ],
    }
