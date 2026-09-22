# lumenix/admin_support.py
"""
Admin helpers for the very large, API-synced pathogen table.

`pathogen_concentration_records` holds millions of rows (13.2M in production for
a single crop/hazard pair). Django's default changelist runs five whole-table
queries on every load: one `SELECT DISTINCT` per plain-field `list_filter`
(plant, pathogen, nuts_code) plus two `COUNT(*)`. That is seconds of waiting
before anything renders, and the facet counts ("Show counts") would be far
worse.

This module removes those queries:

* `EstimatedCountPaginator` takes the row count from the query planner.
* The filters read their choices from `PathogenQuerySpec` (a few hundred rows)
  and `NutsRegion`, never from the big table, and render as dropdowns because a
  300-item list of links is unusable.
* Region names, the observed date span and the coverage summary are cached.

Everything here is read-only and safe to call on every request.
"""

from __future__ import annotations

import datetime as dt
import json
import re

from django.conf import settings
from django.contrib import admin
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, Max, Min, Q
from django.utils import timezone
from django.utils.functional import cached_property

CACHE_SECONDS = 300

# A spec that has not been synced in this long is worth a second look.
STALE_SYNC_DAYS = 30

# Below this, an exact COUNT runs off an index in well under a second, so prefer
# the true number: page links built from a rough estimate would otherwise make
# the last pages of a filtered view unreachable. Above it, only the estimate is
# affordable, and the changelist says so.
EXACT_COUNT_BELOW = 250_000

NUTS_CODE_RE = re.compile(r"^[A-Za-z]{2}[A-Za-z0-9]{0,2}$")
DATE_TERM_RE = re.compile(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?$")


# ---------------------------------------------------------------------------
# Counting rows without COUNT(*)
# ---------------------------------------------------------------------------


def planner_row_estimate(queryset) -> int | None:
    """
    How many rows PostgreSQL expects a queryset to return. `EXPLAIN` plans the
    query without running it, so the answer costs a fraction of a millisecond
    whatever the table size. None when the estimate is unavailable.
    """
    if connection.vendor != "postgresql" or not hasattr(queryset, "query"):
        return None
    try:
        sql, params = queryset.query.sql_with_params()
        with connection.cursor() as cursor:
            cursor.execute(f"EXPLAIN (FORMAT JSON) {sql}", params)
            plan = cursor.fetchone()[0]
        if isinstance(plan, str):
            plan = json.loads(plan)
        return int(plan[0]["Plan"]["Plan Rows"])
    except Exception:
        # Empty querysets, unsupported SQL, a planner hiccup.
        return None


class EstimatedCountPaginator(Paginator):
    """
    Paginator that asks the planner how many rows a query will return instead
    of counting them.

    Small result sets still get a real count, so an operator who has filtered
    down to one region and year sees an exact number. `estimated` says which
    kind of number the page is showing.
    """

    estimated = False

    @cached_property
    def count(self):
        estimate = planner_row_estimate(self.object_list)
        if estimate is None or estimate < EXACT_COUNT_BELOW:
            # Fall back to the accurate (and possibly slow) count, never a guess.
            return super().count
        self.estimated = True
        return estimate


def table_row_estimate(model) -> int | None:
    """Whole-table row estimate from the statistics collector (no scan)."""
    if connection.vendor != "postgresql":
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT reltuples::bigint FROM pg_class WHERE oid = %s::regclass",
                [model._meta.db_table],
            )
            row = cursor.fetchone()
    except Exception:
        return None
    if not row or row[0] is None or row[0] < 0:
        return None
    return int(row[0])


# ---------------------------------------------------------------------------
# Select2 on the filter dropdowns
# ---------------------------------------------------------------------------

# The admin serves minified assets unless DEBUG is on; follow it so a page does
# not end up loading jQuery twice under two different names.
_MIN = "" if settings.DEBUG else ".min"


class Select2FilterAdminMixin:
    """
    Gives the filter dropdowns a type-ahead box.

    Select2 has to run after jQuery but before the admin's `noConflict` call in
    jquery.init.js, so all three files are declared together and Django's media
    merge interleaves them with the admin's own scripts - the same arrangement
    the admin uses for its autocomplete widgets. The initialisation lives in
    templates/admin/lumenix/pathogen_filter_script.html.
    """

    class Media:
        css = {
            "screen": (
                f"admin/css/vendor/select2/select2{_MIN}.css",
                "admin/css/autocomplete.css",
            )
        }
        js = (
            f"admin/js/vendor/jquery/jquery{_MIN}.js",
            f"admin/js/vendor/select2/select2.full{_MIN}.js",
            "admin/js/jquery.init.js",
        )


# ---------------------------------------------------------------------------
# Cheap choice sources
# ---------------------------------------------------------------------------


def spec_values(column: str) -> list[str]:
    """
    Distinct plant / pathogen / nuts_code values, read from the query-spec table
    (a few hundred rows) rather than DISTINCT over millions of records. Every
    record originates from a spec, so the two agree.
    """
    key = f"admin:pathogen:values:{column}"
    values = cache.get(key)
    if values is None:
        from lumenix.models import PathogenQuerySpec

        values = sorted(
            value
            for value in PathogenQuerySpec.objects.order_by()
            .values_list(column, flat=True)
            .distinct()
            if value
        )
        cache.set(key, values, CACHE_SECONDS)
    return values


def _strip_code_prefix(notation: str, label: str) -> str:
    label = (label or "").strip()
    if notation and label.upper().startswith(f"{notation.upper()} "):
        return label[len(notation) + 1:].strip()
    return label or notation


def region_labels() -> dict[str, str]:
    """{'NL22': 'Gelderland', ...} for NUTS2 regions."""
    key = "admin:pathogen:nuts2-labels"
    labels = cache.get(key)
    if labels is None:
        from lumenix.models import NutsRegion

        labels = {
            region.notation: _strip_code_prefix(region.notation, region.pref_label)
            for region in NutsRegion.objects.filter(level=2).only("notation", "pref_label")
        }
        cache.set(key, labels, CACHE_SECONDS)
    return labels


def country_labels() -> dict[str, str]:
    """{'NL': 'Nederland', ...} used to group the region dropdown."""
    key = "admin:pathogen:country-labels"
    labels = cache.get(key)
    if labels is None:
        from lumenix.models import NutsRegion

        labels = {
            region.notation: _strip_code_prefix(region.notation, region.pref_label)
            for region in NutsRegion.objects.filter(level=0).only("notation", "pref_label")
        }
        cache.set(key, labels, CACHE_SECONDS)
    return labels


def observed_span() -> tuple[dt.date | None, dt.date | None]:
    """First and last observed date in the table; served by the date index."""
    key = "admin:pathogen:observed-span"
    span = cache.get(key)
    if span is None:
        from lumenix.models import PathogenConcentrationRecord

        bounds = PathogenConcentrationRecord.objects.aggregate(
            first=Min("observed_on"), last=Max("observed_on")
        )
        span = (bounds["first"], bounds["last"])
        cache.set(key, span, CACHE_SECONDS)
    return span


def coverage_rows() -> list[dict]:
    """
    What is synced, per crop/hazard pair, read from the spec table. Includes the
    parked count: parked specs (status 0) are never retried by the sync, so a
    non-zero number here is the usual reason data looks missing.
    """
    key = "admin:pathogen:coverage"
    rows = cache.get(key)
    if rows is None:
        from lumenix.models import PathogenQuerySpec

        rows = list(
            PathogenQuerySpec.objects.order_by()
            .values("plant", "pathogen")
            .annotate(
                regions=Count("nuts_code", distinct=True),
                first=Min("start_date"),
                last=Max("end_date"),
                synced=Max("last_synced_at"),
                parked=Count("id", filter=Q(status=0)),
                pending=Count("id", filter=Q(last_synced_at__isnull=True, status=1)),
            )
            .order_by("plant", "pathogen")
        )
        cache.set(key, rows, CACHE_SECONDS)
    return rows


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class SelectFilter(admin.SimpleListFilter):
    """
    A SimpleListFilter rendered as a dropdown. The default template prints one
    link per value, which is unusable for 300 regions or 125 years.
    """

    template = "admin/filter_select.html"
    optgroups = None  # subclasses may fill this in choices() to build <optgroup>s

    def _grouped(self, items, group_of):
        """Turn a flat choice list into [(optgroup label, [choices]), ...]."""
        groups: list[tuple[str | None, list[dict]]] = [(None, [items[0]])] if items else []
        current = object()
        for item in items[1:]:
            label = group_of(item)
            if label != current:
                groups.append((label, []))
                current = label
            groups[-1][1].append(item)
        return groups


class CropFilter(SelectFilter):
    title = "crop"
    parameter_name = "plant"

    def lookups(self, request, model_admin):
        return [(value, value.replace("_", " ").replace("-", " ").title()) for value in spec_values("plant")]

    def queryset(self, request, queryset):
        return queryset.filter(plant=self.value()) if self.value() else queryset


class HazardFilter(SelectFilter):
    title = "hazard"
    parameter_name = "pathogen"

    def lookups(self, request, model_admin):
        return [(value, value.replace("_", " ").replace("-", " ").title()) for value in spec_values("pathogen")]

    def queryset(self, request, queryset):
        return queryset.filter(pathogen=self.value()) if self.value() else queryset


class RegionFilter(SelectFilter):
    title = "region"
    parameter_name = "nuts_code"

    def lookups(self, request, model_admin):
        labels = region_labels()
        return [
            (code, f"{code} · {labels[code]}" if labels.get(code) else code)
            for code in spec_values("nuts_code")
        ]

    def choices(self, changelist):
        items = list(super().choices(changelist))
        countries = country_labels()
        self.optgroups = self._grouped(
            items, lambda item: countries.get(str(item["display"])[:2], str(item["display"])[:2])
        )
        return items

    def queryset(self, request, queryset):
        return queryset.filter(nuts_code=self.value()) if self.value() else queryset


class YearFilter(SelectFilter):
    title = "year"
    parameter_name = "year"

    def lookups(self, request, model_admin):
        first, last = observed_span()
        if not first or not last:
            return []
        return [(str(year), str(year)) for year in range(last.year, first.year - 1, -1)]

    def choices(self, changelist):
        items = list(super().choices(changelist))
        self.optgroups = self._grouped(items, lambda item: f"{str(item['display'])[:3]}0s")
        return items

    def queryset(self, request, queryset):
        value = self.value() or ""
        if not value.isdigit():
            return queryset
        year = int(value)
        # A range, not __year, so the observed_on index is used.
        return queryset.filter(observed_on__gte=dt.date(year, 1, 1), observed_on__lte=dt.date(year, 12, 31))


class TimeSpanFilter(SelectFilter):
    title = "time span"
    parameter_name = "span"

    def lookups(self, request, model_admin):
        return [
            ("past", "Historical (up to today)"),
            ("future", "Projected (after today)"),
            ("last12", "Last 12 months"),
            ("next12", "Next 12 months"),
        ]

    def queryset(self, request, queryset):
        today = dt.date.today()
        value = self.value()
        if value == "past":
            return queryset.filter(observed_on__lte=today)
        if value == "future":
            return queryset.filter(observed_on__gt=today)
        if value == "last12":
            return queryset.filter(observed_on__gte=today - dt.timedelta(days=365), observed_on__lte=today)
        if value == "next12":
            return queryset.filter(observed_on__gt=today, observed_on__lte=today + dt.timedelta(days=365))
        return queryset


class ModelValueFilter(SelectFilter):
    title = "model value"
    parameter_name = "value"

    def lookups(self, request, model_admin):
        return [("present", "Present"), ("missing", "Missing")]

    def queryset(self, request, queryset):
        value = self.value()
        if value == "present":
            return queryset.filter(pathogen_model_value__isnull=False)
        if value == "missing":
            return queryset.filter(pathogen_model_value__isnull=True)
        return queryset


class RecordStatusFilter(SelectFilter):
    title = "status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [(str(value), label) for value, label in model_admin.model.STATUS_CHOICES]

    def queryset(self, request, queryset):
        value = self.value() or ""
        return queryset.filter(status=int(value)) if value.isdigit() else queryset


# ---------------------------------------------------------------------------
# Changelist summary panel
# ---------------------------------------------------------------------------


def coverage_summary(model) -> dict:
    """Everything the summary panel shows. All of it is cached or index-served."""
    rows = coverage_rows()
    first, last = observed_span()
    pairs = [
        {
            **row,
            "crop_label": (row["plant"] or "").replace("_", " ").title(),
            "hazard_label": (row["pathogen"] or "").replace("_", " ").title(),
        }
        for row in rows
    ]
    synced = [row["synced"] for row in rows if row["synced"]]
    total = table_row_estimate(model)
    return {
        "total": f"{total:,}".replace(",", " ") if total is not None else None,
        "pairs": pairs,
        "pair_count": len(pairs),
        "pair_names": ", ".join(f"{p['crop_label']} · {p['hazard_label']}" for p in pairs[:3]),
        "regions": len(spec_values("nuts_code")),
        "first": first,
        "last": last,
        "last_synced": max(synced) if synced else None,
        "parked": sum(row["parked"] for row in rows),
        "pending": sum(row["pending"] for row in rows),
    }


# ---------------------------------------------------------------------------
# Query specs
# ---------------------------------------------------------------------------


# Per-spec counts below this run for real: the composite index makes a count of
# a few thousand rows trivial, and the planner never estimates below 1, so an
# empty scope would otherwise be reported as "1 record".
SPEC_EXACT_COUNT_BELOW = 5_000


def spec_record_count(spec) -> tuple[int, bool] | None:
    """
    How many records a spec's scope holds, as (value, is_estimate).

    Large scopes are planned rather than counted, so a page of 50 specs costs
    milliseconds instead of 50 counts over a multi-million-row table. Results
    are cached, so paging back and forth is free.
    """
    key = (
        f"admin:spec:records:{spec.plant}:{spec.pathogen}:{spec.nuts_code}"
        f":{spec.start_date}:{spec.end_date}"
    )
    cached = cache.get(key)
    if cached is not None:
        return cached

    from lumenix.models import PathogenConcentrationRecord

    queryset = PathogenConcentrationRecord.objects.filter(
        plant=spec.plant,
        pathogen=spec.pathogen,
        nuts_code=spec.nuts_code,
        observed_on__gte=spec.start_date,
        observed_on__lte=spec.end_date,
    )
    estimate = planner_row_estimate(queryset)
    if estimate is None:
        return None
    result = (estimate, True) if estimate >= SPEC_EXACT_COUNT_BELOW else (queryset.count(), False)
    cache.set(key, result, CACHE_SECONDS)
    return result


def spec_summary() -> dict:
    """
    Counts for the query-spec panel. One aggregate over a few hundred rows, so
    it runs live and reflects an action the moment it finishes.
    """
    from lumenix.models import PathogenQuerySpec

    stale_before = timezone.now() - dt.timedelta(days=STALE_SYNC_DAYS)
    totals = PathogenQuerySpec.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status=1)),
        parked=Count("id", filter=Q(status=0)),
        removed=Count("id", filter=Q(status=2)),
        never=Count("id", filter=Q(last_synced_at__isnull=True)),
        stale=Count("id", filter=Q(last_synced_at__lt=stale_before)),
        last_sync=Max("last_synced_at"),
    )
    rows = coverage_rows()
    return {
        **totals,
        "stale_days": STALE_SYNC_DAYS,
        "pairs": [
            {
                **row,
                "crop_label": (row["plant"] or "").replace("_", " ").title(),
                "hazard_label": (row["pathogen"] or "").replace("_", " ").title(),
            }
            for row in rows
        ],
        "pair_count": len(rows),
        "regions": len(spec_values("nuts_code")),
    }


class CountryFilter(SelectFilter):
    title = "country"
    parameter_name = "country"

    def lookups(self, request, model_admin):
        labels = country_labels()
        codes = sorted({code[:2] for code in spec_values("nuts_code") if code})
        return [(code, f"{code} · {labels[code]}" if labels.get(code) else code) for code in codes]

    def queryset(self, request, queryset):
        return queryset.filter(nuts_code__startswith=self.value()) if self.value() else queryset


class SpecSyncFilter(SelectFilter):
    title = "sync state"
    parameter_name = "sync"

    def lookups(self, request, model_admin):
        return [
            ("never", "Never synced"),
            ("stale", f"Synced over {STALE_SYNC_DAYS} days ago"),
            ("recent", f"Synced in the last {STALE_SYNC_DAYS} days"),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        cutoff = timezone.now() - dt.timedelta(days=STALE_SYNC_DAYS)
        if value == "never":
            return queryset.filter(last_synced_at__isnull=True)
        if value == "stale":
            return queryset.filter(last_synced_at__lt=cutoff)
        if value == "recent":
            return queryset.filter(last_synced_at__gte=cutoff)
        return queryset


class SpecStatusFilter(SelectFilter):
    """Status, spelled out: a parked spec is simply skipped by every sync run."""

    title = "status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [
            ("1", "Active — included in syncs"),
            ("0", "Parked — skipped by syncs"),
            ("2", "Deleted"),
        ]

    def queryset(self, request, queryset):
        value = self.value() or ""
        return queryset.filter(status=int(value)) if value.isdigit() else queryset
