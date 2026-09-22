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

from django.contrib import admin
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, Max, Min, Q
from django.utils.functional import cached_property

CACHE_SECONDS = 300

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


class EstimatedCountPaginator(Paginator):
    """
    Paginator that asks PostgreSQL's planner how many rows a query will return
    instead of counting them. `EXPLAIN` only plans the query, so this is a
    fraction of a millisecond whatever the table size.

    Small result sets still get a real count, so an operator who has filtered
    down to one region and year sees an exact number. `estimated` says which
    kind of number the page is showing.
    """

    estimated = False

    @cached_property
    def count(self):
        queryset = self.object_list
        query = getattr(queryset, "query", None)
        if query is None or connection.vendor != "postgresql":
            return super().count

        try:
            sql, params = query.sql_with_params()
            with connection.cursor() as cursor:
                cursor.execute(f"EXPLAIN (FORMAT JSON) {sql}", params)
                plan = cursor.fetchone()[0]
            if isinstance(plan, str):
                plan = json.loads(plan)
            estimate = int(plan[0]["Plan"]["Plan Rows"])
        except Exception:
            # Empty querysets, unsupported SQL, a planner hiccup: fall back to
            # the accurate (and possibly slow) count rather than guessing.
            return super().count

        if estimate < EXACT_COUNT_BELOW:
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
