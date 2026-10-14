# lumenix/services/cardinal_growth.py
"""
Temperature-driven growth response of a pathogen across Europe, from the
cardinal temperature model with inflection (CTMI) of Rosso et al. (1993),
proposed by WP2 as a "climate food-safety index" (WP2 meeting, 24 Sep 2026).

mu(T) is the growth rate relative to the optimum, on a 0-1 scale: 0 at or
beyond the cardinal minimum and maximum temperatures, 1 at the optimum. It is
a growth rate, not a risk.

The input is the daily mean air temperature already stored on the pathogen
records: one value per NUTS2 region per day, 1971-2095, from the single
unlabelled projection the source serves. No other data is needed. Several
crop + hazard pairs can hold the same region-day, so their temperatures are
averaged first and each day counts once.

Two read paths, chosen by the time step:

* day / week: aggregated straight from the daily records (spans of a few
  years at most);
* month / year: read from CardinalGrowthMonthly, filled by the
  `build_cardinal_growth` command, because aggregating the full 24M-row
  record table takes far longer than a web request may.

The formula runs in SQL for every data path (MU_SQL), so the map, the curve
and the precomputed table agree; `mu()` is the same formula in Python, used
for the response curve and for checking the SQL.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta

from django.db import connection, transaction


@dataclass(frozen=True)
class CardinalIndex:
    key: str
    label: str
    t_min: float
    t_opt: float
    t_max: float
    source: str


# Cardinal temperatures per pathogen. WP2 has asked for Listeria and
# Campylobacter values; add them here once agreed, then run
# `build_cardinal_growth --index <key>` for the month and year steps.
INDICES = {
    "ecoli": CardinalIndex(
        key="ecoli",
        label="E. coli",
        t_min=6.0,
        t_opt=36.0,
        t_max=45.5,
        source="EFSA cardinal temperatures for E. coli on fresh produce, as used by WP2",
    ),
}

STEPS = ("day", "week", "month", "year")

# Longest span per step, in calendar years. Day and week read the daily
# records directly; month and year read the precomputed monthly table.
MAX_SPAN_YEARS = {"day": 1, "week": 3, "month": 50, "year": 200}

# Rolling windows offered for the year step. A single year shows weather,
# not climate (see docs on the baseline-versus-future comparison).
YEAR_WINDOWS = (1, 5, 10, 30)

# A region-period with fewer days than this is left empty rather than shown
# as a full one: a year holding only January to June would read as a cold year.
MIN_DAYS = {"day": 1, "week": 5, "month": 20, "year": 330}


def mu(temperature, index):
    """Relative growth rate mu(T)/mu_opt (0-1) for one temperature; None for a missing one."""
    if temperature is None or temperature != temperature:  # NaN-safe
        return None
    t, lo, opt, hi = temperature, index.t_min, index.t_opt, index.t_max
    if t <= lo or t >= hi:
        return 0.0
    denominator = (opt - lo) * ((opt - lo) * (t - opt) - (opt - hi) * (opt + lo - 2 * t))
    if denominator == 0:
        return 0.0
    return max(0.0, (t - lo) ** 2 * (t - hi) / denominator)


def response_curve(index, low=-10.0, high=50.0, step=0.5):
    """[[T, mu]] sampled across the plotted temperature range, for the curve panel."""
    points = []
    count = int(round((high - low) / step))
    for i in range(count + 1):
        t = round(low + i * step, 2)
        points.append([t, round(mu(t, index), 4)])
    return points


def _mu_sql(column):
    """The CTMI as a SQL expression over `column`, with the cardinal temperatures as named parameters."""
    t = column
    return f"""
        CASE WHEN {t} > %(t_min)s::float8 AND {t} < %(t_max)s::float8 THEN GREATEST(0.0,
            power({t} - %(t_min)s::float8, 2) * ({t} - %(t_max)s::float8)
            / NULLIF((%(t_opt)s::float8 - %(t_min)s::float8)
                * ((%(t_opt)s::float8 - %(t_min)s::float8) * ({t} - %(t_opt)s::float8)
                   - (%(t_opt)s::float8 - %(t_max)s::float8) * (%(t_opt)s::float8 + %(t_min)s::float8 - 2 * {t})), 0)
        ) ELSE 0.0 END
    """


MU_SQL = _mu_sql("d.t")

# One temperature per region-day, averaged over the crop + hazard pairs that
# hold it. `{where}` narrows the scan (a date range, or a group of regions).
DAILY_SQL = """
    SELECT nuts_code, observed_on, avg(temperature_c) AS t
    FROM pathogen_concentration_records
    WHERE status = 1 AND temperature_c IS NOT NULL AND temperature_c <> 'NaN'::float8
      AND {where}
    GROUP BY nuts_code, observed_on
"""


def _params(index, **extra):
    return {"t_min": index.t_min, "t_opt": index.t_opt, "t_max": index.t_max, **extra}


def index_payload(index):
    return {**asdict(index), "curve": response_curve(index)}


# ---- coverage ---------------------------------------------------------------

def daily_coverage():
    """(first, last) date in the daily records; (None, None) when there are none."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT min(observed_on), max(observed_on) FROM pathogen_concentration_records WHERE status = 1")
        return cursor.fetchone()


def monthly_coverage(index):
    """(first, last) month in the precomputed table for this index; (None, None) before a build."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT min(month), max(month) FROM cardinal_growth_monthly WHERE index_key = %s", [index.key])
        return cursor.fetchone()


# ---- frames -----------------------------------------------------------------

def frames(index, step, start_year, end_year, window=1):
    """
    Map frames for one index: {"frames": [label], "regions": [code],
    "mu": [[value per region] per frame], "temperature": [...],
    "gaps": [{"from", "to", "frames"}]}. Values are None where a region has no
    (or too little) data in that frame. `gaps` lists the runs of frames that
    the data should cover but that no region has, so the page can say why
    playback jumps; year steps also name the `short_years` behind them.
    """
    complete_years = None
    if step in ("day", "week"):
        rows = _rows_from_daily(index, step, start_year, end_year)
        first, last = daily_coverage()
    else:
        if step == "month":
            rows = _rows_from_monthly(index, start_year, end_year)
        else:
            rows, complete_years = _rows_by_year(index, start_year, end_year, window)
        first, last = monthly_coverage(index)
        last = _month_end(last) if last else None
    data = _to_matrix(rows, MIN_DAYS[step])
    expected, coverable_years = _expected_labels(step, start_year, end_year, window, first, last)
    data["gaps"] = _gaps(expected, set(data["frames"]))
    if complete_years is not None:
        data["short_years"] = [y for y in coverable_years if y not in complete_years]
    return data


def _rows_from_daily(index, step, start_year, end_year):
    sql = f"""
        SELECT d.nuts_code, date_trunc(%(trunc)s, d.observed_on::timestamp)::date AS period,
               avg({MU_SQL}) AS mu, avg(d.t) AS t, count(*) AS days
        FROM ({DAILY_SQL.format(where="observed_on BETWEEN %(start)s AND %(end)s")}) d
        GROUP BY 1, 2
    """
    params = _params(index, trunc=step, start=date(start_year, 1, 1), end=date(end_year, 12, 31))
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return [(code, period.isoformat(), m, t, days) for code, period, m, t, days in cursor.fetchall()]


def _rows_from_monthly(index, start_year, end_year):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT nuts_code, month, mu_mean, temperature_mean, days FROM cardinal_growth_monthly
            WHERE index_key = %s AND month BETWEEN %s AND %s
            """,
            [index.key, date(start_year, 1, 1), date(end_year, 12, 1)],
        )
        return [(code, month.isoformat()[:7], m, t, days) for code, month, m, t, days in cursor.fetchall()]


def _rows_by_year(index, start_year, end_year, window):
    """
    Day-weighted yearly means, then a trailing `window`-year mean per region:
    the frame labelled "1991–2000" averages those ten years. A year short of
    MIN_DAYS["year"] does not count towards a window. Returns (rows, the years
    that at least one region has in full).
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT nuts_code, extract(year FROM month)::int AS yr,
                   sum(mu_mean * days), sum(temperature_mean * days), sum(days)
            FROM cardinal_growth_monthly
            WHERE index_key = %s AND month BETWEEN %s AND %s
            GROUP BY 1, 2
            """,
            [index.key, date(start_year, 1, 1), date(end_year, 12, 1)],
        )
        yearly = {}
        for code, year, mu_sum, t_sum, days in cursor.fetchall():
            if days >= MIN_DAYS["year"]:
                yearly[(code, year)] = (mu_sum, t_sum, days)
    complete_years = {year for _, year in yearly}

    rows = []
    for code in {code for code, _ in yearly}:
        for last in range(start_year + window - 1, end_year + 1):
            years = [yearly.get((code, y)) for y in range(last - window + 1, last + 1)]
            if any(y is None for y in years):
                continue
            days = sum(y[2] for y in years)
            label = str(last) if window == 1 else f"{last - window + 1}–{last}"
            rows.append((code, label, sum(y[0] for y in years) / days, sum(y[1] for y in years) / days, days))
    return rows, complete_years


def _to_matrix(rows, min_days):
    usable = [r for r in rows if r[4] >= min_days]
    labels = sorted({r[1] for r in usable}, key=_label_order)
    regions = sorted({r[0] for r in usable})
    frame_at = {label: i for i, label in enumerate(labels)}
    region_at = {code: i for i, code in enumerate(regions)}
    mu_grid = [[None] * len(regions) for _ in labels]
    t_grid = [[None] * len(regions) for _ in labels]
    for code, label, m, t, _days in usable:
        f, r = frame_at[label], region_at[code]
        mu_grid[f][r] = round(m, 3) if m is not None else None
        t_grid[f][r] = round(t, 1) if t is not None else None
    return {"frames": labels, "regions": regions, "mu": mu_grid, "temperature": t_grid}


def _label_order(label):
    # ISO dates, "YYYY-MM" and "YYYY" sort as strings; a window label sorts by its last year.
    return label.split("–")[-1] if "–" in label else label


def _month_end(day):
    following = date(day.year + (day.month == 12), day.month % 12 + 1, 1)
    return following - timedelta(days=1)


def _days_between(lo, hi):
    return (hi - lo).days + 1 if hi >= lo else 0


def _expected_labels(step, start_year, end_year, window, first, last):
    """
    The frame labels the data could fill: the requested period clipped to the
    data's coverage, with the same minimum-days rule as the frames. Also
    returns the years that coverage spans in full (for naming short years).
    """
    if first is None or last is None:
        return [], []
    lo, hi = max(date(start_year, 1, 1), first), min(date(end_year, 12, 31), last)
    if lo > hi:
        return [], []
    if step == "day":
        return [(lo + timedelta(days=i)).isoformat() for i in range(_days_between(lo, hi))], []
    if step == "week":
        labels, monday = [], lo - timedelta(days=lo.weekday())
        while monday <= hi:
            if _days_between(max(monday, lo), min(monday + timedelta(days=6), hi)) >= MIN_DAYS["week"]:
                labels.append(monday.isoformat())
            monday += timedelta(days=7)
        return labels, []
    if step == "month":
        labels, month = [], date(lo.year, lo.month, 1)
        while month <= hi:
            if _days_between(max(month, lo), min(_month_end(month), hi)) >= MIN_DAYS["month"]:
                labels.append(month.isoformat()[:7])
            month = _month_end(month) + timedelta(days=1)
        return labels, []
    years = [
        y for y in range(lo.year, hi.year + 1)
        if _days_between(max(date(y, 1, 1), lo), min(date(y, 12, 31), hi)) >= MIN_DAYS["year"]
    ]
    full = set(years)
    labels = []
    for last_year in range(start_year + window - 1, end_year + 1):
        if all(y in full for y in range(last_year - window + 1, last_year + 1)):
            labels.append(str(last_year) if window == 1 else f"{last_year - window + 1}–{last_year}")
    return labels, years


def _gaps(expected, present):
    """Runs of expected labels with no frame: [{"from", "to", "frames"}]."""
    runs, run = [], []
    for label in expected:
        if label in present:
            if run:
                runs.append(run)
                run = []
        else:
            run.append(label)
    if run:
        runs.append(run)
    return [{"from": r[0], "to": r[-1], "frames": len(r)} for r in runs]


# ---- monthly table ----------------------------------------------------------

def build_monthly(index, chunk_regions=20, log=lambda msg: None):
    """
    (Re)compute CardinalGrowthMonthly for one index from the daily records.

    One transaction per group of regions, each replacing that group's rows, so
    the map keeps working (on partly old values) while a rebuild runs. Regions
    that no longer have records are removed at the end. Returns
    {"regions": n, "rows": n}.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT nuts_code FROM pathogen_concentration_records WHERE status = 1")
        regions = sorted(code for (code,) in cursor.fetchall())

    insert = f"""
        INSERT INTO cardinal_growth_monthly (index_key, nuts_code, month, mu_mean, temperature_mean, days)
        SELECT %(key)s, d.nuts_code, date_trunc('month', d.observed_on::timestamp)::date,
               avg({MU_SQL}), avg(d.t), count(*)
        FROM ({DAILY_SQL.format(where="nuts_code = ANY(%(regions)s)")}) d
        GROUP BY 2, 3
    """
    totals = {"regions": len(regions), "rows": 0}
    for i in range(0, len(regions), chunk_regions):
        chunk = regions[i:i + chunk_regions]
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM cardinal_growth_monthly WHERE index_key = %s AND nuts_code = ANY(%s)",
                [index.key, chunk],
            )
            cursor.execute(insert, _params(index, key=index.key, regions=chunk))
            totals["rows"] += cursor.rowcount
        log(f"  {min(i + chunk_regions, len(regions))}/{len(regions)} regions, {totals['rows']:,} monthly rows")

    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM cardinal_growth_monthly WHERE index_key = %s AND NOT (nuts_code = ANY(%s))",
            [index.key, regions],
        )
    return totals
