#!/usr/bin/env bash
#
# pathogen_sync_ops.sh — operate the online pathogen concentration sync.
#
# Usage (run on the server, from anywhere):
#   ./pathogen_sync_ops.sh check    # progress: specs synced/pending, record count, last sync time
#   ./pathogen_sync_ops.sh active   # is a sync task running on the worker right now?
#   ./pathogen_sync_ops.sh beat     # prove the scheduler is firing (recent due-task ticks)
#   ./pathogen_sync_ops.sh logs     # tail the worker's beat/sync activity
#   ./pathogen_sync_ops.sh reset    # DESTRUCTIVE: wipe records, mark all specs pending
#
# Container names default to the dev-ambrosia compose project; override via env:
#   WEB_CONTAINER=... WORKER_CONTAINER=... ./pathogen_sync_ops.sh check
#
# Python is piped via a quoted heredoc and `docker exec -i` (no TTY), so the
# code runs flush-left exactly as written here — immune to paste-indentation.
set -euo pipefail

WEB="${WEB_CONTAINER:-dev-ambrosia-dashboard-dev_ambrosia_dashboard-1}"
WORKER="${WORKER_CONTAINER:-dev-ambrosia-dashboard-dev_ambrosia_celery_worker-1}"

case "${1:-check}" in
  check)
    docker exec -i "$WEB" python manage.py shell <<'PY'
from django.utils import timezone
from lumenix.models import PathogenConcentrationRecord as R, PathogenQuerySpec as S
total = S.objects.count()
done = S.objects.exclude(last_synced_at__isnull=True).count()
print(f"specs: {done}/{total} synced  |  {total - done} pending")
print("records:", R.objects.count())
last = S.objects.exclude(last_synced_at__isnull=True).order_by("-last_synced_at").first()
if last:
    age = (timezone.now() - last.last_synced_at).total_seconds()
    print(f"most recent sync: {last.name}  @ {last.last_synced_at:%Y-%m-%d %H:%M:%S}  ({age:.0f}s ago)")
else:
    print("most recent sync: none yet")
PY
    ;;
  active)
    # Is a sync task executing on the worker right now?
    docker exec "$WORKER" celery -A config inspect active 2>/dev/null || echo "(no active tasks / worker not responding)"
    ;;
  beat)
    # Prove the scheduler is firing: recent due-task dispatches.
    docker logs --since 15m "$WORKER" 2>&1 | grep -iE "Scheduler: Sending due task|auto_sync_pending" || echo "(no beat ticks in the last 15 min)"
    ;;
  reset)
    docker exec -i "$WEB" python manage.py shell <<'PY'
from django.db import connection
from lumenix.models import PathogenQuerySpec
with connection.cursor() as c:
    c.execute("TRUNCATE TABLE pathogen_concentration_records RESTART IDENTITY")
n = PathogenQuerySpec.objects.update(last_synced_at=None)
print("records truncated; specs reset to pending:", n)
PY
    ;;
  logs)
    docker logs --tail 60 "$WORKER" | grep -iE "beat|auto_sync|pathogen sync|created=" || true
    ;;
  *)
    echo "usage: $0 {check|active|beat|logs|reset}" >&2
    exit 1
    ;;
esac
