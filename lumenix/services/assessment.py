# lumenix/services/assessment.py
"""
Outcome data for an assessment run, derived from the synced pathogen records.

Everything here is computed from PathogenConcentrationRecord rows for one
crop + hazard (+ region) and a period. No values are invented: when there is
nothing to aggregate the functions return empty results.

The value aggregated everywhere is the fixed-window AUC growth-potential index
(growth_potential_auc), per the WP4 FSKX visualisation spec - not the model
curve's end value, which saturates at warm temperatures and flattens exactly
where growth potential differs most.
"""

from django.db.models import Avg, Count, Max, Min, StdDev

from lumenix.services.pathogen_query import identifier_variants
from django.db.models.functions import ExtractMonth, TruncDay, TruncMonth, TruncWeek, TruncYear

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
            value=Avg("growth_potential_auc"),
            value_min=Min("growth_potential_auc"),
            value_max=Max("growth_potential_auc"),
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
    agg = qs.aggregate(mean=Avg("growth_potential_auc"), sd=StdDev("growth_potential_auc"), low=Min("growth_potential_auc"), high=Max("growth_potential_auc"))
    if agg["mean"] is None:
        return {}
    yearly = list(
        qs.annotate(y=TruncYear("observed_on")).values("y").annotate(peak=Max("growth_potential_auc"), low=Min("growth_potential_auc")).order_by("y")
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
        "basis": "daily growth-potential index values in the requested period and region",
    }


def series_stats(qs):
    agg = qs.aggregate(
        days=Count("id"),
        mean=Avg("growth_potential_auc"),
        low=Min("growth_potential_auc"),
        high=Max("growth_potential_auc"),
        first=Min("observed_on"),
        last=Max("observed_on"),
        fetched_at_ms=Max("provenance_fetched_at_ms"),
    )
    peak = (
        qs.exclude(growth_potential_auc__isnull=True).order_by("-growth_potential_auc", "observed_on").values("observed_on", "growth_potential_auc").first()
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
    """[{year, month, value}] mean growth-potential index per calendar month, for the seasonal heatmap."""
    rows = (
        qs.annotate(period=TruncMonth("observed_on"))
        .values("period")
        .annotate(value=Avg("growth_potential_auc"))
        .order_by("period")
    )
    out = []
    for r in rows:
        d = r["period"].date() if hasattr(r["period"], "date") else r["period"]
        out.append({"year": d.year, "month": d.month, "value": round(r["value"], 4) if r["value"] is not None else None})
    return out


def geographic_means(plant, pathogen, start_date, end_date):
    """{nuts_code: mean growth-potential index} for every synced region of this crop + hazard in the period."""
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
        .annotate(value=Avg("growth_potential_auc"), days=Count("id"))
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


def monthly_window_means(qs, start_year, end_year):
    """
    Mean growth-potential index per calendar month over a window of years -
    one line of the baseline-versus-future comparison chart.
    """
    rows = (
        qs.filter(observed_on__year__gte=start_year, observed_on__year__lte=end_year)
        .annotate(month=ExtractMonth("observed_on"))
        .values("month")
        .annotate(value=Avg("growth_potential_auc"), days=Count("id"))
        .order_by("month")
    )
    by_month = {r["month"]: r for r in rows}
    return [
        {
            "month": m,
            "value": round(by_month[m]["value"], 4) if m in by_month and by_month[m]["value"] is not None else None,
            "days": by_month[m]["days"] if m in by_month else 0,
        }
        for m in range(1, 13)
    ]


SNAPSHOT_SCHEMA = 2  # 1 plotted the curve's end value; 2 plots the AUC index.


def build_snapshot(qs, resolution):
    """The stored outcome for a run: series at the requested scale, summary stats and provenance."""
    return {
        "schema": SNAPSHOT_SCHEMA,
        "unit": "growth-potential index (AUC)",
        "series": aggregate_series(qs, resolution),
        "stats": series_stats(qs),
        "variability": variability(qs),
        "provenance": provenance(qs),
        "limitations": [
            "Demonstrator output based on a packaged/fresh-cut product model; not validated for growth on living plants.",
            "The index is the model's growth response to each day's temperature over a fixed 48-hour window, not a measured amount and not a validated risk prediction.",
            "Results represent the supported NUTS2 region, not an individual field.",
            "Uncertainty is not supplied by the source; do not interpret its absence as low uncertainty.",
            "The variability figures describe the spread of the index itself; they are not an uncertainty estimate.",
        ],
    }
