# Alerts Implementation Log

This document records the alerts feature work completed in this repository (Phase 1), including UI, behavior changes, and extension points for Phase 2.

## Overview

Alerts are exposed via a bell icon in the top header and are available across pages.

Current behavior:

- Bell is visible globally.
- Unread count is shown as a badge.
- Dropdown has:
  - `Current context`
  - `All alerts` (outside current context)
- Client-side rule engine currently generates alerts for:
  - C1 (`toxin_over_time`)
  - C3 (`probability_over_time`)

## Implemented Features (Phase 1)

### 1) Header bell and dropdown

- Added bell icon in header, positioned between `View` selector and user menu.
- Added unread badge.
- Added dropdown with:
  - `Mark all read`
  - `Current context` list
  - `All alerts` list

### 2) Client-side alert generation

- Alerts are generated from chart rows currently available in frontend state:
  - `window.__riskBaseRowsCurrent`
  - `window.__toxinsRowsCurrent`
  - `window.__probRowsCurrent`
  - (and other chart row caches as available)
- Triggered on chart render lifecycle event: `risk:charts-rendered`.
- Alerts are regenerated whenever charts are rendered and persisted into local storage. This means the dropdown is not backed by a fixed server-side alert list in Phase 1; it reflects the currently computed client-side dataset.

Implemented rules:

- Toxin alert (`Toxin limit exceeded`):
  - Created when at least one row has `toxin_level_ug_per_kg > toxin_limit_ug_per_kg`.
  - Message includes exceedance count and the peak value versus the configured limit.
  - Severity is `high` when the peak exceeds the limit by at least 50%; otherwise `medium`.
- Probability alert (`Probability trend elevated`):
  - Created when the maximum `prob_illness_pct / baseline` ratio in the current range is at least `1.25x`.
  - Message includes the peak multiplier versus baseline.
  - Severity is `high` at `1.5x` or above; otherwise `medium`.
- No other chart types currently generate alerts in Phase 1.

Refresh behavior:

- A page refresh recomputes alerts from the chart rows available after render.
- If the underlying dataset is stable, the same alerts should be regenerated and prior read state can still apply.
- If the dataset changes between renders, the alert list can change as well.
- In the current dummy-data implementation, the chart rows include random noise, so a full refresh can change the underlying values and therefore the generated alerts.

### 3) Context split logic

- Alerts are split by current page/chart route:
  - `Current context`: alerts tied to active chart.
  - `All alerts`: all other alerts.
- Added chart identifier normalization (e.g., `c1_*` alias handling).

### 4) Read controls

- `Mark all read` action.
- Per-alert `Mark read` action.
- Clicking alert card marks it read.

### 5) Navigation

- Alerts support chart navigation:
  - Click alert row in `All alerts` -> navigate to chart route.
  - Per-alert `Go to chart` button available.

### 6) Visual improvements

- Severity visuals:
  - Icon per severity
  - Severity badge labels
  - Left border color by severity
- Added `time ago` metadata display.
- Bell icon sizing/badge positioning tuned.

### 7) Filtering

Added dropdown filter chips:

- `All`
- `Current context`
- `Unread`
- `High+`

### 8) List limiting / pagination

- Per-section show limit (page size).
- `Show more` button for each section when list exceeds visible page size.

### 9) High-priority signal

- For new `high/critical` unread alerts:
  - short beep (best-effort WebAudio)
  - bootstrap toast message
- Uses local notified cache to avoid repeating the same alert signal.

## Local Storage Keys

- `lx_alerts_cache_v1`: active alerts
- `lx_alerts_read_ids_v1`: read alert IDs
- `lx_alerts_notified_ids_v1`: already signaled high/critical IDs

## Main Files

- `templates/lumenix/base/header.html`
- `templates/lumenix/base/base.html`
- `static/js/pages/dashboard/alerts.js`
- `static/js/pages/dashboard/risk/init.js`
- `docs/alerts_phase1_phase2_plan.md`

## Phase 2 Readiness

The frontend alert object shape is kept compatible with backend-driven alerts. See:

- `docs/alerts_phase1_phase2_plan.md`

Suggested migration:

1. Replace client rule generation with `/api/alerts` fetch.
2. Keep existing dropdown rendering/state logic.
3. Replace local read/notified handling with server-backed read state where appropriate.
