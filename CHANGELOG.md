# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Risk charts module with dedicated pages/routes and chart scripts (`toxin`, `pathogen`, `probability`, `cases`, `seasonal heatmap`) and map support.
- Chart interpretation/assumption content and chart export flows (image/data).
- Dashboard view modes and DB-driven chart composition (`DashboardViewMode`, `DashboardChart`, `DashboardViewChart`).
- Authentication UX and account flow (login templates, password reset, email verification, profile completion).
- SCiO vocabulary sync pipeline (`Vocabulary`, `Scheme`, `Concept`, history tracking + sync command).
- PiDrive FastAPI utility app plus transload/upload/download/system-info capabilities.
- Header alerts center with context/global sections, per-alert read, mark-all-read, filters, pagination, severity styling, and chart navigation.
- Alerts implementation docs: `docs/alerts_phase1_phase2_plan.md` and `docs/alerts_implementation_log.md`.
- GPU footprint documentation for Sweden-hosted A40 inference estimation: `docs/gpu_footprint_estimation_sweden.md`.
- SCiO API helper/testing scripts for model discovery and simulation workflows.
- IPCC dashboard external link in sidebar.

### Changed
- Transitioned from earlier crop/fetch approach toward SCiO-backed vocabulary usage and filtered supported crop/hazard lists.
- Refactored and expanded PiDrive helper modules and routing logic across multiple iterations.
- Updated Docker/runtime setup over time (health/status patterns, dev/prod adjustments, dependency updates).
- Switched key frontend/vendor usage toward offline/local static bundles where needed.
- Risk chart UX enhancements across multiple commits (interpretation, heatmap behavior, selector and view-mode wiring).
- Changelog reconstructed from actual git diff history through `ee60ead` (2026-02-23), not only commit-message summaries.

### Fixed
- Upload/download robustness for Pi client workflows.
- Multiple simulation and API handling paths in iterative updates (error handling and request/response handling improvements).

### Removed
- Previously committed `.deb` artifact removed and ignored.
- Legacy `fskx` app/workflow removed in favor of current direction.
- Older crop-fetch command paths removed during SCiO transition.

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
