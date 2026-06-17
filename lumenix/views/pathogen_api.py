import json
from datetime import datetime

from django.db.models import Max, Min
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST

from lumenix.models import PathogenConcentrationRecord


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


def _resolve_pathogen_queryset(plant, pathogen, nuts_code, start_date=None, end_date=None):
    base_qs = PathogenConcentrationRecord.active_objects.filter(
        plant=plant,
        pathogen=pathogen,
    )
    if start_date:
        base_qs = base_qs.filter(observed_on__gte=start_date)
    if end_date:
        base_qs = base_qs.filter(observed_on__lte=end_date)

    resolved_nuts_code = nuts_code
    qs = base_qs.filter(nuts_code=nuts_code).order_by("observed_on")
    if qs.exists():
        return qs, resolved_nuts_code

    prefix_codes = list(
        base_qs.filter(nuts_code__startswith=nuts_code)
        .values_list("nuts_code", flat=True)
        .distinct()[:2]
    )
    if len(prefix_codes) == 1:
        resolved_nuts_code = prefix_codes[0]
        return base_qs.filter(nuts_code=resolved_nuts_code).order_by("observed_on"), resolved_nuts_code

    return base_qs.none(), resolved_nuts_code


@require_GET
def pathogen_concentration_meta(request):
    plant = (request.GET.get("plant") or "").strip()
    pathogen = (request.GET.get("pathogen") or "").strip()
    nuts_code = (request.GET.get("nutsCode") or "").strip()

    missing = [
        key for key, value in {"plant": plant, "pathogen": pathogen, "nutsCode": nuts_code}.items() if not value
    ]
    if missing:
        return JsonResponse({"error": f"Missing required fields: {', '.join(missing)}"}, status=400)

    qs, resolved_nuts_code = _resolve_pathogen_queryset(plant, pathogen, nuts_code)
    aggregates = qs.aggregate(available_start_date=Min("observed_on"), available_end_date=Max("observed_on"))

    if not aggregates["available_start_date"] or not aggregates["available_end_date"]:
        return JsonResponse({"error": "No synced pathogen metadata found for this query."}, status=404)

    return JsonResponse(
        {
            "plant": plant,
            "pathogen": pathogen,
            "nutsCode": nuts_code,
            "resolved_nuts_code": resolved_nuts_code,
            "available_start_date": aggregates["available_start_date"].isoformat(),
            "available_end_date": aggregates["available_end_date"].isoformat(),
        }
    )


@require_POST
def pathogen_concentration_query(request):
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

    qs, resolved_nuts_code = _resolve_pathogen_queryset(
        payload["plant"],
        payload["pathogen"],
        payload["nutsCode"],
        start_date=start_date,
        end_date=end_date,
    )
    rows = list(qs)

    if not rows:
        return JsonResponse({"error": "No synced pathogen data found for this query."}, status=404)

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
                    "pathogen_model_value": r.pathogen_model_value,
                    "pathogen_model_unit": "model output",
                    "temperature_c": r.temperature_c,
                    "humidity_pct": None,
                    "event": "none",
                    "source": "scio_db",
                    "nuts_code": r.nuts_code,
                    "time": r.source_time,
                    "period": r.source_period,
                    # NOTE: r.outcome (a ~4 KB nested array per row) is intentionally
                    # omitted. The pathogen chart currently plots the final model value, and including it inflated
                    # the response ~14x (21 MB vs 1.5 MB for a multi-year daily range),
                    # which stalled the chart loading overlay.
                }
                for r in rows
            ],
        }
    )
