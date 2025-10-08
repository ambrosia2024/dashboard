# api_test/scio/get_simulation.py

import os
import sys

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

import argparse

import pandas as pd
import requests

from django.utils import timezone

from lumenix.models import SimulationKey, SimulationRun, SimulationResult


BASE = "https://dev.api.ambrosia.scio.services"

HEADER_MAP = {
    "disease-risk": ("time_index", "risk_score"),
}
def get_headers(sim_type: str):
    return HEADER_MAP.get(sim_type, ("x", "y"))

def build_original_request_from_db(job_id: str) -> dict:
    """
    Get SimulationRun + SimulationKey from DB and reconstruct the request payload fields.
    This lets us back-fill missing fields if the GET response omits 'request' or 'metadata'.
    """
    run = SimulationRun.objects.select_related("sim_key").get(job_id=job_id)
    sk = run.sim_key
    # Convert dates to ISO strings for a uniform 'original_request' structure
    time_period = [
        sk.time_period_start.isoformat() if sk.time_period_start else "",
        sk.time_period_end.isoformat() if sk.time_period_end else "",
    ]
    return {
        "simulation_type": sk.simulation_type,
        "crop": sk.crop,
        "nuts_id": sk.nuts_id,
        "climate_model": sk.climate_model,
        "time_period": time_period,
        "time_scale": sk.time_scale,
    }

def normalise_simulation_response(api_res: dict, fallback_req: dict, job_id: str) -> dict:
    """
    Coerce backend GET payload to the expected shape.
    - Many fields are (currently) missing in the API; we back-fill from fallback_req (DB).
    """
    req = api_res.get("request") or {}
    merged_request = {
        "crop": req.get("crop") or fallback_req.get("crop", ""),
        "nuts_id": req.get("nuts_id") or fallback_req.get("nuts_id", ""),
        "climate_model": req.get("climate_model") or fallback_req.get("climate_model", ""),
        "time_period": req.get("time_period") or fallback_req.get("time_period", []),
        "time_scale": (api_res.get("time_scale") or req.get("time_scale") or fallback_req.get("time_scale", "")),
        "simulation_type": req.get("simulation_type") or fallback_req.get("simulation_type", ""),
    }
    meta = api_res.get("metadata") or {}
    metadata = {
        "completion_timestamp": meta.get("completion_timestamp") or "",
        "submission_timestamp": meta.get("submission_timestamp") or 0,
    }
    return {
        "request": merged_request,
        "metadata": metadata,
        "job_id": api_res.get("job_id") or job_id,
        "status": api_res.get("status") or "",
        "results": api_res.get("results") or [],
    }

def upsert_from_api_payload(normalised: dict):
    """
    Persist GET payload into SimulationKey/Run/Result and return (run, df).
    Replaces existing results for that job_id (idempotent).
    """
    req = normalised["request"]
    # Use get_or_create in case this job_id was created without a stub (defensive)
    sim_key, _ = SimulationKey.objects.get_or_create(
        simulation_type=req["simulation_type"],
        crop=req["crop"],
        nuts_id=req["nuts_id"],
        climate_model=req["climate_model"],
        time_scale=req["time_scale"],
        time_period_start=req["time_period"][0],  # strings accepted for DateField via ORM? safer to convert in model form,
        time_period_end=req["time_period"][-1],   # but we saved them already from stub; get_or_create won't run .save() clean
    )

    run, _ = SimulationRun.objects.update_or_create(
        job_id=normalised["job_id"],
        defaults={
            "sim_key": sim_key,
            "status": (normalised.get("status") or "").lower(),
            "submission_timestamp": normalised.get("metadata", {}).get("submission_timestamp"),
            "completion_timestamp": normalised.get("metadata", {}).get("completion_timestamp"),
            "updated_at": timezone.now(),
        },
    )

    # Replace results
    SimulationResult.objects.filter(job=run).delete()
    bulk = []
    for i, row in enumerate(normalised.get("results") or []):
        x = row[0] if len(row) > 0 else None
        y = row[1] if len(row) > 1 else None
        bulk.append(SimulationResult(job=run, idx=i, x=x, y=y))
    if bulk:
        SimulationResult.objects.bulk_create(bulk, batch_size=1000)

    # Build DF for output
    h0, h1 = get_headers(req["simulation_type"])
    rows = SimulationResult.objects.filter(job=run).order_by("idx").values_list("x", "y")
    df = pd.DataFrame(list(rows), columns=[h0, h1])
    return run, df

def find_cached_dataframe(job_id: str):
    """
    If we already have results for this EXACT job_id, return (run, df).
    Useful when you don’t want to hit the API again.
    """
    run = SimulationRun.objects.filter(job_id=job_id).select_related("sim_key").first()
    if not run:
        return None, None
    rows = SimulationResult.objects.filter(job=run).order_by("idx").values_list("x", "y")
    rows = list(rows)
    if not rows:
        return run, None
    h0, h1 = get_headers(run.sim_key.simulation_type)
    df = pd.DataFrame(rows, columns=[h0, h1])
    return run, df


def main():
    # CLI: allow overriding job_id (default: last printed one)
    parser = argparse.ArgumentParser(description="GET simulation results by job_id and print df.head()")
    parser.add_argument("--job-id", dest="job_id", required=False,
                        help="Simulation job_id. If omitted, you can paste it in the code or fail fast.")
    parser.add_argument("--force-refresh", action="store_true",
                        help="Ignore cache and GET from API again, then overwrite DB results.")
    args = parser.parse_args()

    # 1) Resolve job_id
    job_id = args.job_id or "1b074cdcb0e8e1d6a7cb00b1563d4ad35e339acac6ab8f51d2527f6afbce68e7"
    if not job_id:
        raise SystemExit("No job_id provided. Use --job-id=...")

    # 2) Cache-first (optional)
    if not args.force_refresh:
        cached_run, cached_df = find_cached_dataframe(job_id)
        if cached_df is not None:
            print(f"[cache] job_id={cached_run.job_id} status={cached_run.status} rows={len(cached_df)}")
            print(cached_df.head())
            return

    # 3) Build fallback original request from DB
    try:
        original_request = build_original_request_from_db(job_id)
    except SimulationRun.DoesNotExist:
        raise SystemExit(f"No SimulationRun found in DB for job_id={job_id}. "
                         f"Run the POST script first or pass a known job_id.")

    # 4) GET the results from API
    url = f"{BASE}/api/run-simulation/{job_id}"
    headers = {"Accept": "application/json"}
    resp = requests.get(url, headers=headers, timeout=20)
    if resp.status_code == 404:
        raise SystemExit(f"Unknown job_id at API: {job_id}")
    resp.raise_for_status()
    api_data = resp.json()

    # 5) Normalise with back-fill (DB → fills missing fields)
    normalised = normalise_simulation_response(api_data, original_request, job_id)

    # 6) Persist results and print df.head()
    run, df = upsert_from_api_payload(normalised)
    print(f"[api] job_id={run.job_id} status={run.status} rows={len(df)}")
    print(df.head())

if __name__ == "__main__":
    main()
