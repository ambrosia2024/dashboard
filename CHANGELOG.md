# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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

