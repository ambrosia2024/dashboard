# Ambrosia Data Platform API Report

Simple reference for the API endpoints currently used in the dashboard, with focus on plant/pathogen vocabulary sync.

## Base URL

- `https://dev.api.ambrosia.scio.services`

Configured in app settings as:

- `SCIO_VOCAB_API_BASE=https://dev.api.ambrosia.scio.services/api/vocabulary`
- `SCIO_NUTS_API_BASE=https://dev.api.ambrosia.scio.services/api/nuts`
- `SCIO_MODELS_API_URL=https://dev.api.ambrosia.scio.services/api/models`

---

## Endpoints used

### 1) Run simulation

- `POST /api/run-simulation/{simulationType}`
- Starts a simulation job and returns `job_id`, `status`.

### 2) Get simulation result

- `GET /api/run-simulation/{job_id}`
- Returns request metadata, job status, and `results` series.

### 3) Get vocabulary

- `GET /api/vocabulary/{vocabulary_id}`
- Supported IDs in current integration: `plants`, `pathogens`.

### 4) Get NUTS regions by level

- `GET /api/nuts/{level}`
- Supported levels: `0`, `1`, `2`, `3`
- Example: `/api/nuts/2`

### 5) Get SCiO models registry

- `GET /api/models`
- Returns model descriptors used by the SCiO execution backend.

---

## Plants vocabulary sync in this project

Current implementation already supports incremental refresh (new items + changed items):

1. API fetch from `/api/vocabulary/plants`
2. Upsert `Vocabulary` row (`plants`)
3. Upsert schemes into `vocabulary_scheme`
4. Upsert concepts into `vocabulary_concept` by concept `uri`
5. Detect changes via `content_hash`
6. Write create/update snapshots to `vocabulary_concept_history`

Main code:

- `lumenix/services/vocabulary_sync.py`
- `lumenix/management/commands/sync_vocabulary.py`

---

## NUTS sync in this project

NUTS data is persisted in `NUTS Regions` and upserted by `iri` from `/api/nuts/{level}`.
Missing upstream rows are tombstoned locally (`status=2`, `deleted_at` set), not hard-deleted.

Stored fields:

1. `iri`
2. `notation`
3. `level`
4. `pref_label`
5. `alt_labels_en`

Main code:

- `lumenix/services/nuts_sync.py`
- `lumenix/management/commands/sync_nuts.py`

---

## Models sync in this project

`/api/models` data is persisted in `SCiO Models` and upserted by API field `id`.
Missing upstream rows are tombstoned locally (`status=2`, `deleted_at` set), not hard-deleted.
If a tombstoned row reappears upstream, sync reactivates it (`status=1`, `deleted_at=null`).

Stored fields:

1. `external_id` (API `id`)
2. `name`
3. `source_url` (API `url`)
4. `image_tag`
5. `cpu_cores_required`
6. `ram_gb_required`
7. `gpu_count_required`
8. `gpu_memory_gb_required`
9. `min_cuda_version_required`
10. `source_timestamp` (API `_id.timestamp`)
11. `source_date_ms` (API `_id.date`)

Main code:

- `lumenix/services/models_sync.py`
- `lumenix/management/commands/sync_models.py`

---

## How to refresh plant list

Manual refresh command:

```bash
python manage.py sync_vocabulary --vocab=plants
```

Behavior:

1. Adds newly created concepts from API
2. Updates existing concepts if payload changed
3. Keeps unchanged rows as-is
4. Writes history only for created/updated rows
5. Tombstones concepts/schemes that disappear from upstream (`status=2`)

Full reset + reimport (use only when needed):

```bash
python manage.py sync_vocabulary --vocab=plants --reset
```

This deletes existing `plants` concepts/schemes/history first, then imports fresh.

Admin UI option (no terminal command):

1. Open `/admin`
2. Use the new **SCiO Sync** panel
3. Click:
   - `Sync Plants`
   - `Sync Pathogens`
   - `Sync All`

These buttons call the same sync service used by `manage.py sync_vocabulary`.

NUTS refresh commands:

```bash
python manage.py sync_nuts --level=2
python manage.py sync_nuts --level=all
```

NUTS admin buttons:

1. `Sync NUTS L0`
2. `Sync NUTS L1`
3. `Sync NUTS L2`
4. `Sync NUTS L3`
5. `Sync NUTS All`

Models refresh command:

```bash
python manage.py sync_models
```

Full reset + reimport:

```bash
python manage.py sync_models --reset
```

Models admin button:

1. `Sync Models`

---

## Frontend data usage (plants)

The UI currently needs only:

1. Concept ID
2. Display label (`pref_label`, language fallback)
3. `ambrosia_supported=True` filter

The backend already provides this via `PlantConcept` queries.

---

## Scheduling status

- Celery task exists: `lumenix.tasks.sync_vocabulary_task`
- Automatic beat schedule is present but commented in `config/settings.py`
- So refresh is currently manual unless schedule is enabled

---

## Notes

- Report updated: `2026-03-05`
- Source: user-shared Ambrosia/Postman API details and current repo implementation
