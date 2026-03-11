import requests

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from lumenix.models import NutsRegion

BASE = settings.SCIO_NUTS_API_BASE.rstrip("/")


def fetch_nuts(level: int) -> dict:
    r = requests.get(f"{BASE}/{level}", headers={"Accept": "application/json"}, timeout=60)
    r.raise_for_status()
    return r.json()


@transaction.atomic
def sync_nuts(level: int, reset: bool = False) -> dict:
    data = fetch_nuts(level)
    rows = data.get("levels", []) or []

    if reset:
        NutsRegion.objects.filter(level=level).delete()

    created, updated, unchanged = 0, 0, 0
    seen_iris = set()

    for raw in rows:
        iri = (raw.get("iri") or "").strip()
        notation = (raw.get("notation") or "").strip()
        pref_label = (raw.get("prefLabel") or "").strip()
        alt_labels_en = raw.get("altLabels_en") or []

        # API is level-specific, but keep row-level value as source of truth when available.
        raw_level = raw.get("level")
        try:
            item_level = int(raw_level) if raw_level is not None else int(level)
        except (TypeError, ValueError):
            item_level = int(level)

        if not iri or not notation:
            continue
        seen_iris.add(iri)

        defaults = {
            "notation": notation,
            "level": item_level,
            "pref_label": pref_label,
            "alt_labels_en": alt_labels_en,
            "status": 1,
            "deleted_at": None,
        }

        obj, was_created = NutsRegion.objects.select_for_update().get_or_create(
            iri=iri,
            defaults=defaults,
        )
        if was_created:
            created += 1
            continue

        changed = (
            obj.notation != notation
            or obj.level != item_level
            or obj.pref_label != pref_label
            or obj.alt_labels_en != alt_labels_en
            or obj.status != 1
            or obj.deleted_at is not None
        )
        if changed:
            obj.notation = notation
            obj.level = item_level
            obj.pref_label = pref_label
            obj.alt_labels_en = alt_labels_en
            obj.status = 1
            obj.deleted_at = None
            obj.save(update_fields=["notation", "level", "pref_label", "alt_labels_en", "status", "deleted_at", "updated_at"])
            updated += 1
        else:
            unchanged += 1

    deleted = (
        NutsRegion.objects
        .filter(level=level, status=1)
        .exclude(iri__in=list(seen_iris))
        .update(status=2, deleted_at=timezone.now())
    )

    return {"created": created, "updated": updated, "unchanged": unchanged, "deleted": deleted, "fetched": len(rows)}
