# lumenix/tasks.py

import logging

from celery import shared_task
from django.conf import settings
from django.core.cache import cache

from lumenix.models import PathogenQuerySpec
from lumenix.services.pathogen_query import sync_pathogen_query_spec
from lumenix.services.vocabulary_sync import sync_vocabulary

logger = logging.getLogger(__name__)

# Shared with the worker-shutdown handler in config/celery.py.
PATHOGEN_AUTO_SYNC_LOCK_KEY = "pathogen-auto-sync:lock"


@shared_task(bind=True, max_retries=3)
def sync_vocabulary_task(self, vocab_id: str):
    """
    Celery wrapper so Beat can schedule it.
    """
    res = sync_vocabulary(vocab_id)
    return res


@shared_task(bind=True, max_retries=3)
def sync_pathogen_query_spec_task(self, spec_id: int, lock_key: str | None = None):
    try:
        spec = PathogenQuerySpec.active_objects.get(pk=spec_id)
        return sync_pathogen_query_spec(spec)
    finally:
        if lock_key:
            cache.delete(lock_key)


@shared_task(bind=True)
def auto_sync_pending_pathogen_specs_task(self, batch_size: int = 10):
    """
    Beat-driven, self-resuming sync. Each run picks up the next *pending* pathogen
    query specs (those with no ``last_synced_at``) and syncs them, then exits.

    Crucially, when no specs remain pending it returns immediately WITHOUT calling
    the source API, so once the whole backlog is synced the periodic tick becomes a
    cheap DB-only no-op — it never reconnects to SCiO again.

    Uses a dedicated, short-TTL lock (not the global admin sync lock) so overlapping
    beat ticks can't double-run, and a hard worker crash can't wedge it permanently:
    the lock auto-expires and the next tick resumes from the next pending spec.
    """
    lock_key = PATHOGEN_AUTO_SYNC_LOCK_KEY
    lock_ttl = max(60, int(getattr(settings, "PATHOGEN_AUTO_SYNC_LOCK_TTL", 6 * 60 * 60)))
    if not cache.add(lock_key, "running", timeout=lock_ttl):
        return {"skipped": "already running"}
    try:
        pending = list(
            PathogenQuerySpec.active_objects
            .filter(last_synced_at__isnull=True)
            .order_by("pk")[: max(1, int(batch_size))]
        )
        if not pending:
            # Backlog fully drained — no API call made.
            return {"done": True, "synced": 0, "remaining": 0}

        max_failed_runs = max(1, int(getattr(settings, "PATHOGEN_AUTO_SYNC_MAX_FAILED_RUNS", 5)))
        results = []
        deactivated = 0
        exhausted = 0
        for spec in pending:
            result = sync_pathogen_query_spec(spec)
            fail_key = f"pathogen-sync-failed-runs:{spec.pk}"
            if result.get("model_missing"):
                # No SCiO model for this plant/pathogen pair: park the spec (Inactive)
                # so beat stops retrying it forever. Re-activate it in admin if a model
                # is added later.
                spec.status = 0
                spec.save(update_fields=["status", "updated_at"])
                cache.delete(fail_key)
                deactivated += 1
            elif result.get("successful_chunks"):
                # Any progress at all resets the counter: a spec creeping forward
                # through a flaky upstream must not be parked for being slow.
                cache.delete(fail_key)
            else:
                # Whole run produced nothing. Park after repeated futile runs so a
                # permanently-failing spec stops retrying every beat tick forever.
                failed_runs = cache.get(fail_key, 0) + 1
                cache.set(fail_key, failed_runs, timeout=7 * 24 * 60 * 60)
                if failed_runs >= max_failed_runs:
                    spec.status = 0
                    spec.save(update_fields=["status", "updated_at"])
                    cache.delete(fail_key)
                    exhausted += 1
                    logger.warning(
                        "Pathogen sync: parking spec=%s (%s) after %s runs with no "
                        "successful chunk. Upstream returned no usable data. "
                        "Re-activate in admin once the source recovers.",
                        spec.pk, spec.name, failed_runs,
                    )
            results.append({"spec_id": spec.pk, "name": spec.name, "result": result})

        remaining = PathogenQuerySpec.active_objects.filter(last_synced_at__isnull=True).count()
        return {
            "done": remaining == 0,
            "synced": len(results),
            "deactivated": deactivated,
            "exhausted": exhausted,
            "remaining": remaining,
            "results": results,
        }
    finally:
        cache.delete(lock_key)


@shared_task(bind=True, max_retries=3)
def sync_pathogen_query_specs_batch_task(self, spec_ids: list[int], lock_key: str | None = None):
    results = []
    try:
        for spec_id in spec_ids:
            spec = PathogenQuerySpec.active_objects.get(pk=spec_id)
            results.append(
                {
                    "spec_id": spec_id,
                    "name": spec.name,
                    "result": sync_pathogen_query_spec(spec),
                }
            )
        return {
            "queued_specs": len(spec_ids),
            "processed_specs": len(results),
            "results": results,
        }
    finally:
        if lock_key:
            cache.delete(lock_key)
