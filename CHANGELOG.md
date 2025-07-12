_# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- SCiO API test scripts for `/models`, `/modelexecutionservice/models`, and `/simulation`, using `.env` configuration and structured output.
- FastAPI app for testing pidrive integration.
- New test helpers and API utilities to standardise response handling for pidrive.
- IPCC dashboard link added to frontend for external reference.

### Changed
- Helper functions improved and refactored for better reuse and structure.
- `.env.sample` updated with new variables for pidrive.
- General project clean-up, including consolidation of main branch changes.

### Fixed
- Upload and download behaviour for Pi client testing corrected and made robust.

### Removed
- Deleted previously committed `.deb` file from repository.
- `.deb` files added to `.gitignore` to avoid future accidental commits.

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
- Crop fetching logic handled more robustly._

