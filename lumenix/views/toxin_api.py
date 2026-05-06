import json
from datetime import datetime

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from lumenix.models import ToxinConcentrationRecord


def _parse_request_date(value: str):
    raw = (value or "").strip()
    if not raw:
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


@require_POST
def toxin_concentration_query(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    required = ["plant", "pathogen", "nutsCode", "startDate", "endDate", "timeScale"]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        return JsonResponse({"error": f"Missing required fields: {', '.join(missing)}"}, status=400)

    start_date = _parse_request_date(payload["startDate"])
    end_date = _parse_request_date(payload["endDate"])
    if not start_date or not end_date:
        return JsonResponse({"error": "Invalid startDate or endDate. Use YYYY-MM-DD or DD/MM/YYYY."}, status=400)

    base_qs = ToxinConcentrationRecord.active_objects.filter(
        plant=payload["plant"],
        pathogen=payload["pathogen"],
        observed_on__gte=start_date,
        observed_on__lte=end_date,
    )
    rows = list(base_qs.filter(nuts_code=payload["nutsCode"]).order_by("observed_on"))
    resolved_nuts_code = payload["nutsCode"]

    if not rows:
        prefix_codes = list(
            base_qs.filter(nuts_code__startswith=payload["nutsCode"])
            .values_list("nuts_code", flat=True)
            .distinct()[:2]
        )
        if len(prefix_codes) == 1:
            resolved_nuts_code = prefix_codes[0]
            rows = list(base_qs.filter(nuts_code=resolved_nuts_code).order_by("observed_on"))

    if not rows:
        return JsonResponse({"error": "No synced toxin data found for this query."}, status=404)

    first = rows[0]
    return JsonResponse(
        {
            "request": payload,
            "resolved_nuts_code": resolved_nuts_code,
            "provenance": {
                "model_id": first.provenance_model_id,
                "model_title": first.provenance_model_title,
                "variable_name": first.provenance_variable_name,
                "fetched_at": first.provenance_fetched_at_ms,
            },
            "rows": [
                {
                    "date": r.observed_on.isoformat(),
                    "crop": r.plant,
                    "pathogen": r.pathogen,
                    "toxin_level_ug_per_kg": r.toxin_value,
                    "toxin_limit_ug_per_kg": None,
                    "temperature_c": r.temperature_c,
                    "humidity_pct": None,
                    "event": "none",
                    "source": "scio_db",
                    "nuts_code": r.nuts_code,
                    "time": r.source_time,
                    "period": r.source_period,
                    "outcome": r.outcome,
                }
                for r in rows
            ],
        }
    )
