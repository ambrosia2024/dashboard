"""
Per-participant funnel for the T5.2 Phase 2 workshops, as CSV.

Combines what the domain tables already know (runs created, situations saved
and reused, whether a run returned data) with the UserEvent log (did they reach
the form, which fields blocked them, did they open the charts or ask Ambra).

    python manage.py workshop_funnel --cohort dr-greece-2026-11
    python manage.py workshop_funnel --date 2026-11-12 --out funnel.csv
"""

import csv
import sys
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Min, Max, Q
from django.utils import timezone

from lumenix.models import AssessmentRun, SavedSituation, UserEvent

COLUMNS = [
    "email", "cohort", "role",
    "form_opened", "submits_rejected", "blocking_fields",
    "situations_saved", "situations_reused",
    "runs", "runs_with_data", "runs_no_data",
    "combinations_tried",
    "outcomes_viewed", "exports", "charts_viewed", "ambra_questions",
    "first_activity", "last_activity", "minutes_active",
    "completed_scenario_1",
]


class Command(BaseCommand):
    help = "Per-participant workshop funnel as CSV (stdout, or --out FILE)."

    def add_arguments(self, parser):
        parser.add_argument("--cohort", default="", help="Only accounts with this profile cohort.")
        parser.add_argument("--date", default="", help="Only activity on this day, YYYY-MM-DD.")
        parser.add_argument("--out", default="", help="Write to this file instead of stdout.")

    def handle(self, *args, **options):
        cohort = options["cohort"].strip()
        day = self._parse_day(options["date"])

        users = get_user_model().objects.all().select_related("profile")
        if cohort:
            users = users.filter(profile__cohort=cohort)

        events = UserEvent.objects.all()
        runs = AssessmentRun.objects.all()
        situations = SavedSituation.objects.all()
        if day:
            start, end = self._day_bounds(day)
            events = events.filter(occurred_at__gte=start, occurred_at__lt=end)
            runs = runs.filter(created_at__gte=start, created_at__lt=end)
            situations = situations.filter(created_at__gte=start, created_at__lt=end)

        rows = [self._row(u, events, runs, situations) for u in users.order_by("email")]
        rows = [r for r in rows if r["first_activity"]]  # drop accounts that did nothing

        stream = open(options["out"], "w", newline="", encoding="utf-8") if options["out"] else sys.stdout
        try:
            writer = csv.DictWriter(stream, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        finally:
            if options["out"]:
                stream.close()
                self.stdout.write(self.style.SUCCESS(f"Wrote {len(rows)} participants to {options['out']}"))

    # ---- one participant -------------------------------------------------

    def _row(self, user, events, runs, situations):
        ev = events.filter(user=user)
        counts = {
            c["event"]: c["n"]
            for c in ev.values("event").annotate(n=Count("id"))
        }
        span = ev.aggregate(first=Min("occurred_at"), last=Max("occurred_at"))

        user_runs = runs.filter(user=user)
        run_stats = user_runs.aggregate(
            total=Count("id"),
            with_data=Count("id", filter=Q(run_status=AssessmentRun.Status.COMPLETED)),
        )
        combinations = (
            user_runs.values("crop_label", "hazard_label", "nuts2_code").distinct().count()
        )

        blocking = sorted({
            field
            for payload in ev.filter(event=UserEvent.Event.SUBMIT_REJECTED).values_list("payload", flat=True)
            for field in (payload or {}).get("fields", [])
        })

        saved = situations.filter(user=user).count()
        reused = counts.get(UserEvent.Event.SITUATION_REUSED, 0)
        first, last = span["first"], span["last"]

        return {
            "email": user.email,
            "cohort": getattr(getattr(user, "profile", None), "cohort", "") or "",
            "role": getattr(getattr(user, "profile", None), "role", "") or "",
            "form_opened": counts.get(UserEvent.Event.FORM_OPENED, 0),
            "submits_rejected": counts.get(UserEvent.Event.SUBMIT_REJECTED, 0),
            "blocking_fields": " ".join(blocking),
            "situations_saved": saved,
            "situations_reused": reused,
            "runs": run_stats["total"],
            "runs_with_data": run_stats["with_data"],
            "runs_no_data": run_stats["total"] - run_stats["with_data"],
            "combinations_tried": combinations,
            "outcomes_viewed": counts.get(UserEvent.Event.OUTCOME_VIEWED, 0),
            "exports": counts.get(UserEvent.Event.EXPORTED, 0),
            "charts_viewed": counts.get(UserEvent.Event.CHART_VIEWED, 0),
            "ambra_questions": counts.get(UserEvent.Event.AMBRA_ASKED, 0),
            "first_activity": first.isoformat() if first else "",
            "last_activity": last.isoformat() if last else "",
            "minutes_active": round((last - first).total_seconds() / 60, 1) if first and last else "",
            # Scenario 1 asks for a situation that was saved and can be returned to.
            "completed_scenario_1": "yes" if saved and run_stats["total"] else "no",
        }

    # ---- helpers ---------------------------------------------------------

    def _parse_day(self, value):
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise CommandError("--date must be YYYY-MM-DD")

    def _day_bounds(self, day):
        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.combine(day, datetime.min.time()), tz)
        return start, start + timedelta(days=1)
