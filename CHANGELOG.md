# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Placeholder for changes not yet released.

---

## [1.5.0] - 2026-03-11

### Added
- Header alerts center with context/global sections, per-alert read, mark-all-read, filters, pagination, severity styling, and chart navigation.
- Ambra chart assistant UI for toxin, pathogen, and probability charts, including quick prompts, streaming answers, and chat transcript download.
- Risk chart AI/Q&A streaming endpoint for chart-specific interpretation.
- Risk context bubble UI and role-aware chart interpretation support.
- Authentication hardening utilities including login throttling/challenge handling, optional reCAPTCHA verification, and session idle logout.
- SCiO models registry sync and NUTS region sync, including models, services, management commands, and admin integration.
- Admin/dashboard navigation enhancements, including sidebar chart links and admin index sync actions.
- Alerts implementation docs: `docs/alerts_phase1_phase2_plan.md` and `docs/alerts_implementation_log.md`.
- GPU footprint documentation for Sweden-hosted A40 inference estimation: `docs/gpu_footprint_estimation_sweden.md`.

### Changed
- SCiO vocabulary/admin integrations expanded with status tracking, tombstoning, and sync UX improvements.
- Chart-page and dashboard composition logic expanded across multiple iterations, including role/view-aware rendering and route-specific chart selection.
- Frontend dashboard/risk-chart UX refined with new partials, routing, and header/sidebar wiring.
- Risk chart templates expanded to embed Ambra chat panels and current-chart-only assistant behavior.

### Fixed
- Multiple simulation and API handling paths in iterative updates (error handling and request/response handling improvements).

---

## [1.4.0] - 2026-02-23

### Added
- Dashboard view modes and DB-driven chart composition (`DashboardViewMode`, `DashboardChart`, `DashboardViewChart`).
- Mode-aware dashboard/risk chart selection and persistence helpers.
- New dashboard mode selector UI and supporting template tags.

### Changed
- Risk chart selector and dashboard rendering reworked around view-mode-driven composition.
- README and configuration/docs updated to reflect dashboard-mode support.

---

## [1.3.0] - 2025-11-16

### Added
- Risk charts module with dedicated pages/routes and chart scripts (`toxin`, `pathogen`, `probability`, `cases`, `seasonal heatmap`) and map support.
- Chart interpretation/assumption content and chart export flows (image/data).
- Authentication UX and account flow (login templates, password reset, email verification, profile completion).
- SCiO API helper/testing scripts for model discovery and simulation workflows.

### Changed
- Risk chart UX enhancements across multiple commits (interpretation, heatmap behavior, selector wiring, and offline/local vendor bundling).
- Transitioned from earlier crop/fetch approach toward SCiO-backed vocabulary usage and filtered supported crop/hazard lists.

### Fixed
- Upload/download robustness for Pi client workflows.

### Removed
- Older crop-fetch command paths removed during SCiO transition.

---

## [1.2.0] - 2025-10-29

### Added
- SCiO vocabulary sync pipeline (`Vocabulary`, `Scheme`, `Concept`, history tracking + sync command).
- Celery wiring for background sync tasks and updated Docker/runtime support for the SCiO transition.

### Changed
- Replaced the earlier crop ontology / fetch approach with SCiO-backed vocabulary usage.
- Updated dashboard/admin/data models to support SCiO concepts and current risk workflow direction.

### Removed
- Legacy `fskx` app/workflow removed in favor of current direction.

---

## [1.1.0] - 2025-09-30

### Added
- PiDrive FastAPI utility app plus transload/upload/download/system-info capabilities.
- Helper/testing utilities for Pi client workflows and SCiO API probing.
- IPCC dashboard external link in sidebar.

### Changed
- Refactored and expanded PiDrive helper modules and routing logic across multiple iterations.
- Updated Docker/runtime setup over time (health/status patterns, dev/prod adjustments, dependency updates).

### Fixed
- Upload/download robustness for Pi client workflows.

### Removed
- Previously committed `.deb` artifact removed and ignored.

---

## [1.0.0] - 2025-06-04

### Added
- Initial version of interactive farm risk dashboard.
- Integration of Leaflet and basic charting components.
- Added Docker support for the full application.
- Implemented FSKX client and model execution workflow.
- New app for dashboard with crop ontology and NUTS2 region support.
- Dummy charts and temperature risk index simulation added.
- Initial test method for mock risk index.
- README and `.env.sample` introduced and updated for local dev.
- Log handling for NUTS2 and crop data inclusion.

### Changed
- Refactored settings and environment configuration handling.
- Dashboard model modified to support location data efficiently.
- Updated requirements and added new variables to `.env.sample`.
- Dockerfile updated to support development and debugging.
- Error handling improved across multiple methods.
- Enhanced model execution with more robust logging and graceful failures.

### Fixed
- Fixed simulation call to FSKX server.
- Location handling bug fixed.
- Crop fetching logic handled more robustly.
