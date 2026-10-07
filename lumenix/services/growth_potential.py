# lumenix/services/growth_potential.py
"""
Fixed-window AUC growth-potential index, as specified in
docs/AMBROSIA_WP4_FSKX_GrowthPotential_Visualisations_MVP.pdf.

The source model is deterministic in temperature, so the index is computed one
of two ways:

* at ingest, directly from the curve in the API response (exact);
* by backfill, interpolating stored temperatures against a sampled A(T) lookup
  (worst observed interpolation error 0.04%, bin error ~0.1%).

Nothing here stores curves: the lookup holds a few thousand (T, AUC) pairs per
crop + hazard, which is what makes the index affordable on a 24M-row table.
"""

from __future__ import annotations

import bisect
import logging

from django.db import connection, transaction
from django.utils import timezone

from lumenix.models import GrowthPotentialLookup, PathogenConcentrationRecord, PathogenQuerySpec
from lumenix.services.pathogen_query import curve_auc, fetch_pathogen_concentration  # noqa: F401 (re-export)

logger = logging.getLogger(__name__)

DEFAULT_T_EVAL_HOURS = 48.0

# Where the lookup samples come from: regions and windows chosen to span the
# temperature range in the data, from Finnish winters to Cypriot summers at the
# end of the projection. Each probe contributes one sample per day.
DEFAULT_PROBES = (
    ("FI1D", "1985-01-01", "1989-12-31"),
    ("NL22", "2000-01-01", "2004-12-31"),
    ("ES61", "2040-01-01", "2044-12-31"),
    ("CY00", "2091-01-01", "2095-12-31"),
)

# Backfill matches temperatures to the lookup on 0.01 °C bins; at the steepest
# observed slope (~11 AUC/°C) that is a worst-case error of ~0.06 AUC.
BIN = 0.01


def interpolate(samples, temperature):
    """Linear interpolation over sorted [T, A] samples; None outside the range."""
    if temperature is None or temperature != temperature or not samples:  # NaN-safe
        return None
    temps = [s[0] for s in samples]
    if not temps[0] <= temperature <= temps[-1]:
        return None
    i = bisect.bisect_left(temps, temperature)
    if i == 0:
        return samples[0][1]
    t1, a1 = samples[i - 1]
    t2, a2 = samples[i]
    if t2 == t1:
        return a1
    return a1 + (a2 - a1) * (temperature - t1) / (t2 - t1)


def build_lookup(plant, pathogen, probes=DEFAULT_PROBES, t_eval_hours=DEFAULT_T_EVAL_HOURS):
    """
    Harvest (temperature, AUC) samples from the source API and store them as
    the A(T) lookup for one crop + hazard. Returns the saved lookup.
    """
    samples = {}
    y0 = None
    horizon = None
    provenance = {}
    for nuts_code, start, end in probes:
        data = fetch_pathogen_concentration({
            "plant": plant,
            "pathogen": pathogen,
            "nutsCode": nuts_code,
            "startDate": start,
            "endDate": end,
            "timeScale": "daily",
        })
        provenance = data.get("provenance") or provenance
        for item in data.get("results") or []:
            temperature = item.get("variable")
            curve = item.get("outcome") or []
            if temperature is None or temperature != temperature or len(curve) < 2:
                continue
            if y0 is None:
                y0 = curve[0][1]
                horizon = curve[-1][0]
            value = curve_auc(curve, t_eval_hours, y0)
            if value is not None:
                # One sample per 0.01 C is plenty; later probes keep the first.
                samples.setdefault(round(temperature, 2), value)
        logger.info("growth lookup probe %s %s..%s -> %s samples so far", nuts_code, start, end, len(samples))

    if len(samples) < 50:
        raise RuntimeError(f"Only {len(samples)} usable samples for {plant} x {pathogen}; refusing to build a lookup.")

    ordered = sorted(samples.items())
    lookup, _ = GrowthPotentialLookup.objects.update_or_create(
        plant=plant,
        pathogen=pathogen,
        defaults={
            "model_id": (provenance.get("model_id") or "")[:256],
            "model_title": (provenance.get("model_title") or "")[:512],
            "y0": y0,
            "horizon_hours": horizon,
            "t_eval_hours": t_eval_hours,
            "samples": [[t, round(a, 4)] for t, a in ordered],
            "t_min": ordered[0][0],
            "t_max": ordered[-1][0],
            "sample_count": len(ordered),
            "built_at": timezone.now(),
            "status": 1,
            "deleted_at": None,
        },
    )
    return lookup


def lookup_for(plant, pathogen):
    return GrowthPotentialLookup.active_objects.filter(plant=plant, pathogen=pathogen).first()


def _densify(samples):
    """The lookup's irregular samples, expanded onto a regular 0.01 °C grid."""
    lo, hi = samples[0][0], samples[-1][0]
    steps = int(round((hi - lo) / BIN))
    grid = []
    for i in range(steps + 1):
        t = round(lo + i * BIN, 2)
        grid.append((t, round(interpolate(samples, t), 4)))
    return grid


def backfill(plant, pathogen, chunk_regions=10, log=lambda msg: None):
    """
    Set growth_potential_auc on existing records from their stored temperature.

    Runs as one set-based UPDATE per group of regions (so no 24M-row
    transaction), joining rounded temperatures against the densified lookup in
    a temporary table. Rows with NaN temperature, or temperatures outside the
    sampled range, are left NULL and counted.
    """
    lookup = lookup_for(plant, pathogen)
    if lookup is None:
        raise RuntimeError(f"No growth-potential lookup for {plant} x {pathogen}. Run build_growth_potential_lookup first.")

    regions = sorted(
        PathogenQuerySpec.objects.filter(plant=plant, pathogen=pathogen)
        .order_by().values_list("nuts_code", flat=True).distinct()
    )
    grid = _densify(lookup.samples)
    totals = {"updated": 0, "regions": len(regions)}

    with connection.cursor() as cursor:
        cursor.execute("CREATE TEMPORARY TABLE IF NOT EXISTS gp_bins (t_bin numeric(7,2) PRIMARY KEY, auc float8)")
        cursor.execute("TRUNCATE gp_bins")
        cursor.executemany("INSERT INTO gp_bins (t_bin, auc) VALUES (%s, %s)", grid)

    for i in range(0, len(regions), chunk_regions):
        chunk = regions[i:i + chunk_regions]
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE pathogen_concentration_records r
                SET growth_potential_auc = l.auc
                FROM gp_bins l
                WHERE r.plant = %s AND r.pathogen = %s AND r.nuts_code = ANY(%s)
                  AND r.growth_potential_auc IS NULL
                  AND r.temperature_c <> 'NaN'::float8
                  AND l.t_bin = round(r.temperature_c::numeric, 2)
                """,
                [plant, pathogen, chunk],
            )
            totals["updated"] += cursor.rowcount
        log(f"  {min(i + chunk_regions, len(regions))}/{len(regions)} regions, {totals['updated']:,} rows updated")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT count(*) FILTER (WHERE temperature_c = 'NaN'::float8),
                   count(*) FILTER (WHERE temperature_c <> 'NaN'::float8
                                      AND (temperature_c < %s OR temperature_c > %s)),
                   count(*) FILTER (WHERE growth_potential_auc IS NULL)
            FROM pathogen_concentration_records WHERE plant = %s AND pathogen = %s
            """,
            [lookup.t_min, lookup.t_max, plant, pathogen],
        )
        totals["nan_temperature"], totals["out_of_range"], totals["still_null"] = cursor.fetchone()
    return totals
