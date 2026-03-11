# Alerts: Phase 1 and Phase 2 Plan

## Current status (Phase 1)

The header now includes a bell dropdown with:

- `Current context` alerts (for the chart/page currently being viewed).
- `All alerts` (all active alerts known to the client).
- Unread badge count.
- Read-state persistence in `localStorage`.

### Data source

Phase 1 uses client-generated chart rows from risk pages:

- `window.__toxinsRowsCurrent`
- `window.__probRowsCurrent`
- `window.__pathogenRowsCurrent`
- `window.__casesRowsCurrent`
- `window.__seasonalRowsCurrent`

The alert engine currently creates rule-based alerts for:

- C1 toxin limit exceedance (`toxin_over_time`)
- C3 probability multiplier elevation (`probability_over_time`)

### Storage keys

- `lx_alerts_cache_v1`: active alert objects
- `lx_alerts_read_ids_v1`: list of read alert IDs

## Alert object shape (forward-compatible)

```json
{
  "id": "string",
  "source": "client_rule|backend",
  "scope": "chart|system",
  "chart_identifier": "toxin_over_time",
  "chart_label": "Toxin concentration vs time",
  "severity": "low|medium|high|critical",
  "title": "string",
  "message": "string",
  "created_at": "ISO-8601",
  "expires_at": null,
  "rule_key": "string",
  "context": {}
}
```

## Phase 2 migration (backend alerts)

### Goals

- Move alert generation to backend.
- Keep the same frontend dropdown and rendering logic.
- Preserve `current context` vs `all alerts`.

### Suggested backend model

`Alert` fields:

- `id` (UUID)
- `user` (nullable if tenant/global)
- `scope` (`chart` / `system`)
- `chart_identifier` (nullable)
- `severity`
- `title`
- `message`
- `context` (JSON)
- `is_active`
- `created_at`
- `expires_at`

`AlertRead` fields:

- `alert` FK
- `user` FK
- `read_at`

### Suggested APIs

- `GET /api/alerts/` -> list active alerts for current user
- `POST /api/alerts/read/` -> mark specific alerts read
- `POST /api/alerts/read-all/` -> mark all read

### Frontend switch strategy

1. Keep current rendering UI unchanged.
2. Replace client rule generator with API fetch in `alerts.js`.
3. Keep fallback to client rules when API is unavailable in development.
4. Remove local `active alerts` cache once backend is stable (retain optional read cache as UI fallback).

