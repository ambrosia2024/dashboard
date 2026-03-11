import requests

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from lumenix.models import ScioModel

URL = settings.SCIO_MODELS_API_URL


def fetch_models() -> dict:
    response = requests.get(URL, headers={"Accept": "application/json"}, timeout=120)
    response.raise_for_status()
    return response.json()


@transaction.atomic
def sync_models(reset: bool = False) -> dict:
    data = fetch_models()
    rows = data.get("models", []) or []

    if reset:
        ScioModel.objects.all().delete()

    # The API can return repeated ids; keep the last occurrence per id.
    deduped_by_id = {}
    for raw in rows:
        model_id = (raw.get("id") or "").strip()
        if model_id:
            deduped_by_id[model_id] = raw

    created, updated, unchanged = 0, 0, 0

    for model_id, raw in deduped_by_id.items():
        source_obj = raw.get("_id") or {}
        defaults = {
            "name": (raw.get("name") or "").strip(),
            "source_url": (raw.get("url") or "").strip(),
            "image_tag": (raw.get("image_tag") or "").strip(),
            "cpu_cores_required": float(raw.get("cpu_cores_required") or 0.0),
            "ram_gb_required": float(raw.get("ram_gb_required") or 0.0),
            "gpu_count_required": int(raw.get("gpu_count_required") or 0),
            "gpu_memory_gb_required": float(raw.get("gpu_memory_gb_required") or 0.0),
            "min_cuda_version_required": raw.get("min_cuda_version_required") or None,
            "source_timestamp": source_obj.get("timestamp"),
            "source_date_ms": source_obj.get("date"),
            "status": 1,
            "deleted_at": None,
        }

        obj, was_created = ScioModel.objects.select_for_update().get_or_create(
            external_id=model_id,
            defaults=defaults,
        )
        if was_created:
            created += 1
            continue

        changed = any(getattr(obj, field) != value for field, value in defaults.items())
        if changed:
            for field, value in defaults.items():
                setattr(obj, field, value)
            obj.save(update_fields=[*defaults.keys(), "updated_at"])
            updated += 1
        else:
            unchanged += 1

    deleted = (
        ScioModel.objects
        .filter(status=1)
        .exclude(external_id__in=list(deduped_by_id.keys()))
        .update(status=2, deleted_at=timezone.now())
    )

    return {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "deleted": deleted,
        "fetched": len(rows),
        "deduped": len(deduped_by_id),
    }
