# api_test/scio/run_simulation.py

import os
import requests
import sys

from datetime import date
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import django
django.setup()

from django.utils import timezone

from lumenix.models import SimulationRun, SimulationKey

BASE = "https://dev.api.ambrosia.scio.services"
SIM_TYPE = "disease-risk"
url = f"{BASE}/api/run-simulation/{SIM_TYPE}"
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

payload = {
    "crop": "Lettuce",
    "nuts_id": "NL42",
    "climate_model": "RCP4.5",
    "time_period": ["2025-06-11", "2025-12-11"],
    "time_scale": "weekly"
}

original_request = {
    "simulation_type": SIM_TYPE,
    "crop": payload["crop"],
    "nuts_id": payload["nuts_id"],
    "climate_model": payload["climate_model"],
    "time_period": payload["time_period"],
    "time_scale": payload["time_scale"],
}

# Guard against accidental bad inputs
start, end = payload["time_period"][0], payload["time_period"][-1]
if start > end:
    raise ValueError(f"time_period start {start} must be <= end {end}")

def _to_date(iso_str: str) -> date:
    # Parses 'YYYY-MM-DD' into a date object
    return date.fromisoformat(iso_str)

def upsert_run_stub(request_dict: dict, job_id: str, status: str):
    """Create/attach SimulationKey and store a SimulationRun without results yet."""
    sim_key, _ = SimulationKey.objects.get_or_create(
        simulation_type=request_dict["simulation_type"],
        crop=request_dict["crop"],
        nuts_id=request_dict["nuts_id"],
        climate_model=request_dict["climate_model"],
        time_scale=request_dict["time_scale"],
        time_period_start=_to_date(request_dict["time_period"][0]),
        time_period_end=_to_date(request_dict["time_period"][-1]),
    )

    print(f"sim_key: {sim_key.id} → {sim_key.simulation_type}/{sim_key.crop}/{sim_key.nuts_id} "
          f"[{sim_key.time_period_start}→{sim_key.time_period_end}]")

    SimulationRun.objects.update_or_create(
        job_id=job_id,
        defaults={
            "sim_key": sim_key,
            "status": (status or "").lower(),
            "submission_timestamp": None,
            "completion_timestamp": None,
            "updated_at": timezone.now(),
        },
    )

def post_with_retry(u, j, h, tries=3, timeout=20):
    last_exc = None
    for i in range(tries):
        try:
            r = requests.post(u, json=j, headers=h, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last_exc = e
    raise last_exc

# Use a timeout; raise for non-2xx responses
resp = post_with_retry(url, payload, headers)
data = resp.json()

job_id = (data or {}).get("job_id")
status = ((data or {}).get("status") or "").lower()

if not job_id:
    raise RuntimeError(f"POST succeeded but no job_id in response: {data}")

# Persist stub so “last run” shows up in DB immediately
upsert_run_stub(original_request, job_id, status)

print(f"job_id: {job_id} status: {status or 'submitted'}")
print(f"Next: python api_test/scio/get_simulation.py  # and use job_id={job_id}")
print(f"GET URL: {BASE}/api/run-simulation/{job_id}")
