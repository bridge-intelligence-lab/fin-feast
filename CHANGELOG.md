# Changelog

All notable changes to this project will be documented in this file.

## Unreleased
### Added
- OSS readiness: LICENSE (Apache-2.0), NOTICE, CODE_OF_CONDUCT, CONTRIBUTING, SECURITY.
- CI: Ruff linting, mypy type checking, unit tests; optional E2E and optional gitleaks secrets scan.
- Pre-commit hooks (ruff, hygiene) and pre-push unit tests.
- Console scripts: finfeast-generate, finfeast-materialize, finfeast-validate.
- Atomic parquet writes with temp+rename and simple per-file lock.
- Unit tests: push_rows_to_online behavior, partition grouping/paths, backoff helper, polygon push isolation.

### Changed
- Docs aligned to retain both partition columns (`symbol`, `date`) inside Parquet files.
- CI unit job skips integration/network tests; markers added to integration fixtures.
- Streaming resilience: Binance reconnect backoff with jitter; Polygon push-online isolation.

### Fixed
- tests/unit/test_online_push: corrected assertion and behavior checks.
- Minor lints and formatting across service and utils.
