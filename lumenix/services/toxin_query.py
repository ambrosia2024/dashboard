import logging
import time

import requests
from datetime import date, datetime, timedelta

from django.db import transaction
from django.utils import timezone

from django.conf import settings

from lumenix.models import ToxinConcentrationRecord, ToxinQuerySpec

URL = settings.SCIO_TOXIN_QUERY_URL
DEFAULT_CHUNK_DAYS = max(1, int(getattr(settings, "SCIO_TOXIN_SYNC_CHUNK_DAYS", 7)))
REQUEST_DELAY_SECONDS = max(0.0, float(getattr(settings, "SCIO_TOXIN_SYNC_REQUEST_DELAY_SECONDS", 2)))
MAX_RETRIES_PER_CHUNK = max(0, int(getattr(settings, "SCIO_TOXIN_SYNC_CHUNK_MAX_RETRIES", 2)))
MAX_CONSECUTIVE_FAILURES = max(1, int(getattr(settings, "SCIO_TOXIN_SYNC_MAX_CONSECUTIVE_FAILURES", 5)))
logger = logging.getLogger(__name__)


def fetch_toxin_concentration(payload: dict) -> dict:
    response = requests.post(
        URL,
        json=payload,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def normalize_toxin_response(data: dict) -> dict:
    request_meta = data.get("request") or {}
    provenance = data.get("provenance") or {}
    rows = []

    for item in data.get("results") or []:
        outcome = item.get("outcome") or []
        final_pair = outcome[-1] if outcome else [None, None]
        toxin_value = final_pair[1] if len(final_pair) > 1 else None

        date_value = (item.get("time") or item.get("period") or "")[:10]
        rows.append(
            {
                "date": date_value,
                "crop": request_meta.get("plant") or "",
                "pathogen": request_meta.get("pathogen") or "",
                "toxin_level_ug_per_kg": toxin_value,
                "toxin_limit_ug_per_kg": None,
                "temperature_c": item.get("variable"),
                "humidity_pct": None,
                "event": "none",
                "source": "scio_api",
                "nuts_code": item.get("nuts_code") or request_meta.get("nutsCode") or "",
                "time": item.get("time"),
                "period": item.get("period"),
                "outcome": outcome,
            }
        )

    return {
        "request": request_meta,
        "provenance": provenance,
        "rows": rows,
    }


def _parse_observed_on(item: dict) -> date | None:
    raw = (item.get("time") or item.get("period") or "").strip()
    if not raw:
        return None

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m"):
        try:
            dt = datetime.strptime(raw, fmt)
            if fmt == "%Y-%m":
                dt = dt.replace(day=1)
            return dt.date()
        except ValueError:
            continue
    return None


def _chunk_date_range(start_date: date, end_date: date, chunk_days: int = DEFAULT_CHUNK_DAYS) -> list[tuple[date, date]]:
    chunks = []
    chunk_start = start_date
    while chunk_start <= end_date:
        chunk_end = min(chunk_start + timedelta(days=chunk_days - 1), end_date)
        chunks.append((chunk_start, chunk_end))
        chunk_start = chunk_end + timedelta(days=1)
    return chunks


def sync_toxin_query_spec(spec: ToxinQuerySpec) -> dict:
    created = updated = unchanged = fetched = 0
    seen_dates = set()
    failed_ranges = []
    successful_chunks = 0
    consecutive_failures = 0
    chunks = _chunk_date_range(spec.start_date, spec.end_date)
    logger.info(
        "Starting toxin sync for spec=%s name=%s chunks=%s range=%s..%s",
        spec.pk,
        spec.name,
        len(chunks),
        spec.start_date,
        spec.end_date,
    )
    for index, (chunk_start, chunk_end) in enumerate(chunks):
        payload = {
            "plant": spec.plant,
            "pathogen": spec.pathogen,
            "nutsCode": spec.nuts_code,
            "startDate": chunk_start.isoformat(),
            "endDate": chunk_end.isoformat(),
            "timeScale": "daily",
        }
        logger.info(
            "Toxin sync chunk start spec=%s chunk=%s/%s range=%s..%s",
            spec.pk,
            index + 1,
            len(chunks),
            chunk_start,
            chunk_end,
        )
        raw = None
        last_exc = None
        for attempt in range(MAX_RETRIES_PER_CHUNK + 1):
            try:
                raw = fetch_toxin_concentration(payload)
                last_exc = None
                break
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < MAX_RETRIES_PER_CHUNK:
                    sleep_seconds = REQUEST_DELAY_SECONDS * (attempt + 1)
                    logger.warning(
                        "Toxin sync chunk retry %s/%s for spec=%s range=%s..%s after error: %s",
                        attempt + 1,
                        MAX_RETRIES_PER_CHUNK,
                        spec.pk,
                        chunk_start,
                        chunk_end,
                        exc,
                    )
                    if sleep_seconds > 0:
                        time.sleep(sleep_seconds)
        if raw is None:
            failed_ranges.append(
                {
                    "startDate": chunk_start.isoformat(),
                    "endDate": chunk_end.isoformat(),
                    "error": str(last_exc),
                }
            )
            logger.warning(
                "Toxin sync chunk failed for spec=%s range=%s..%s: %s",
                spec.pk,
                chunk_start,
                chunk_end,
                last_exc,
            )
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.warning(
                    "Stopping toxin sync early for spec=%s after %s consecutive failed chunks.",
                    spec.pk,
                    consecutive_failures,
                )
                break
            if REQUEST_DELAY_SECONDS > 0 and index < len(chunks) - 1:
                time.sleep(REQUEST_DELAY_SECONDS)
            continue

        request_meta = raw.get("request") or payload
        provenance = raw.get("provenance") or {}
        chunk_results = raw.get("results") or []
        fetched += len(chunk_results)
        successful_chunks += 1
        consecutive_failures = 0
        chunk_created = chunk_updated = chunk_unchanged = 0

        with transaction.atomic():
            for item in chunk_results:
                observed_on = _parse_observed_on(item)
                if not observed_on:
                    continue

                seen_dates.add(observed_on)
                outcome = item.get("outcome") or []
                final_pair = outcome[-1] if outcome else [None, None]
                toxin_value = final_pair[1] if len(final_pair) > 1 else None

                defaults = {
                    "source_time": (item.get("time") or "").strip(),
                    "source_period": (item.get("period") or "").strip(),
                    "toxin_value": toxin_value,
                    "temperature_c": item.get("variable"),
                    "outcome": outcome,
                    "provenance_model_id": provenance.get("model_id") or "",
                    "provenance_model_title": provenance.get("model_title") or "",
                    "provenance_variable_name": provenance.get("variable_name") or "",
                    "provenance_fetched_at_ms": provenance.get("fetched_at"),
                    "source_payload": item,
                    "status": 1,
                    "deleted_at": None,
                }

                obj, was_created = ToxinConcentrationRecord.objects.select_for_update().get_or_create(
                    plant=request_meta.get("plant") or spec.plant,
                    pathogen=request_meta.get("pathogen") or spec.pathogen,
                    nuts_code=item.get("nuts_code") or request_meta.get("nutsCode") or spec.nuts_code,
                    observed_on=observed_on,
                    defaults=defaults,
                )
                if was_created:
                    created += 1
                    chunk_created += 1
                    continue

                changed = any(getattr(obj, field) != value for field, value in defaults.items())
                if changed:
                    for field, value in defaults.items():
                        setattr(obj, field, value)
                    obj.save(update_fields=[*defaults.keys(), "updated_at"])
                    updated += 1
                    chunk_updated += 1
                else:
                    unchanged += 1
                    chunk_unchanged += 1

        logger.info(
            "Toxin sync chunk success spec=%s chunk=%s/%s range=%s..%s fetched=%s created=%s updated=%s unchanged=%s",
            spec.pk,
            index + 1,
            len(chunks),
            chunk_start,
            chunk_end,
            len(chunk_results),
            chunk_created,
            chunk_updated,
            chunk_unchanged,
        )

        if REQUEST_DELAY_SECONDS > 0 and index < len(chunks) - 1:
            time.sleep(REQUEST_DELAY_SECONDS)

    if successful_chunks:
        spec.last_synced_at = timezone.now()
        spec.save(update_fields=["last_synced_at", "updated_at"])

    summary = {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "fetched": fetched,
        "successful_chunks": successful_chunks,
        "failed_chunks": len(failed_ranges),
        "failed_ranges": failed_ranges,
    }
    logger.info(
        "Finished toxin sync for spec=%s name=%s fetched=%s created=%s updated=%s unchanged=%s successful_chunks=%s failed_chunks=%s",
        spec.pk,
        spec.name,
        fetched,
        created,
        updated,
        unchanged,
        successful_chunks,
        len(failed_ranges),
    )
    return summary
