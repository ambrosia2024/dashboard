# config/celery.py

from __future__ import absolute_import, unicode_literals

import os
from celery import Celery
from celery.signals import worker_shutting_down

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")


@worker_shutting_down.connect
def release_pathogen_sync_lock(**_kwargs):
    """Drop the auto-sync run lock when the worker stops.

    The lock lives in Redis, so unlike the old per-container file cache it
    outlives the container. Without this, a `docker stop` mid-run leaves the
    lock held for its full TTL (6h by default) and every beat tick afterwards
    silently returns {"skipped": "already running"} while doing nothing.

    Imports are deferred to keep Django out of module import time.
    """
    try:
        from django.core.cache import cache
        from lumenix.tasks import PATHOGEN_AUTO_SYNC_LOCK_KEY

        cache.delete(PATHOGEN_AUTO_SYNC_LOCK_KEY)
    except Exception:  # shutdown path must never raise
        pass
