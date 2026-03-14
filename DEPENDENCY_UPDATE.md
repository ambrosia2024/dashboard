# Dependency Update Runbook

This repository now uses:

- `requirements.in`: top-level dependency list used as the update input
- `requirements.txt`: fully pinned, resolver-generated output

## Why two files

- Edit `requirements.in` when you want to add, remove, or constrain top-level packages.
- Regenerate `requirements.txt` from `requirements.in` instead of hand-editing every pin.

## Important platform constraint

`GDAL` must match the system `libgdal` version on the machine.

Check it with:

```bash
gdal-config --version
```

In this environment, the installed system version is `3.8.4`, so `requirements.in` pins:

```txt
GDAL==3.8.4
```

If `libgdal` changes on another machine, update that pin before recompiling.

## Important compatibility constraints

Some packages are intentionally constrained to avoid unnecessary major-version migrations:

- `Django>=5.2.12,<6`
- `openai<2`
- `huggingface-hub<1`
- `pandas<3`
- `paramiko<4`

These constraints keep the project on the latest versions within the currently safer compatibility lines.

## Update all packages to latest compatible versions

From the project root:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv pip compile requirements.in \
  -o requirements.txt \
  --python .venv/bin/python \
  --upgrade \
  --resolution highest \
  --no-header \
  --no-annotate
```

## Install the regenerated lock file

```bash
UV_CACHE_DIR=/tmp/uv-cache .venv/bin/pip install -r requirements.txt
```

## Preferred flow: security-only updates

Use this when Dependabot reports vulnerabilities and you want the smallest practical change set.

1. Update only the affected packages:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv pip compile requirements.in \
  -o requirements.txt \
  --python .venv/bin/python \
  --upgrade-package Django \
  --upgrade-package aiohttp \
  --upgrade-package urllib3 \
  --upgrade-package h11 \
  --upgrade-package pillow \
  --upgrade-package cryptography \
  --upgrade-package sqlparse \
  --upgrade-package starlette \
  --resolution highest \
  --no-header \
  --no-annotate
```

2. Install the result:

```bash
UV_CACHE_DIR=/tmp/uv-cache .venv/bin/pip install -r requirements.txt
```

3. Run the verification checks from this document.

This keeps the rest of the dependency graph as stable as possible while still letting the resolver pick compatible patched versions.

## Full refresh flow

Use this only when you intentionally want to refresh the broader stack.

```bash
UV_CACHE_DIR=/tmp/uv-cache uv pip compile requirements.in \
  -o requirements.txt \
  --python .venv/bin/python \
  --upgrade \
  --resolution highest \
  --no-header \
  --no-annotate
```

Then install and run all checks below.

## Verification checks

Basic dependency consistency:

```bash
.venv/bin/python -m pip check
```

Basic import smoke test:

```bash
.venv/bin/python - <<'PY'
import django, pandas, osgeo.gdal, aiohttp, fastapi
print('django', django.get_version())
print('pandas', pandas.__version__)
print('gdal', osgeo.gdal.VersionInfo())
print('aiohttp', aiohttp.__version__)
print('fastapi', fastapi.__version__)
PY
```

See what changed:

```bash
git diff -- requirements.in requirements.txt
```

## Targeted package update flow

If you want to refresh only a few packages outside a security cycle, specify them explicitly:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv pip compile requirements.in \
  -o requirements.txt \
  --python .venv/bin/python \
  --upgrade-package Django \
  --upgrade-package aiohttp \
  --upgrade-package urllib3 \
  --resolution highest \
  --no-header \
  --no-annotate
```

Then reinstall and rerun the verification checks.

## Final validation

Dependency resolution succeeding does not guarantee application compatibility.

After updating:

```bash
python manage.py check
```

And run the project test suite if available:

```bash
pytest
```

If there is no maintained test suite, manually smoke-test the main app flows before merging.

## Suggested review policy

- Use the security-only flow by default.
- Use the full refresh flow only when you are prepared to smoke-test the main application paths.
- Treat changes to `Django`, `openai`, `pandas`, `paramiko`, `huggingface-hub`, and `GDAL` as higher-risk than routine library bumps.
