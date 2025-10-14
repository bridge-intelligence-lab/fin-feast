# Code Review Checklist

Use this to guide the review scope and mark progress.

- [ ] Security & Secrets
  - [ ] No secrets tracked; .env in .gitignore
  - [ ] History scrubbed for leaks; CI has optional secrets scan
  - [ ] SECURITY.md present and clear

- [ ] CI & Testing
  - [ ] Linting (ruff) in CI
  - [ ] Unit tests deterministic/offline; integration/E2E properly marked
  - [ ] Optional E2E behind env flags; no flaky sleeps
  - [ ] Consider mypy type-checking in CI

- [ ] Data I/O & Schema
  - [ ] Partition layout consistent with docs
  - [ ] Atomic writes; idempotent merges; concurrency-safe
  - [ ] Clear normalize_schema and types; NaN handling

- [ ] Services & Streaming
  - [ ] Reconnect/backoff, error handling
  - [ ] Warm start logic, buffer bounds
  - [ ] Logging and observability

- [ ] Code Quality & Packaging
  - [ ] Typing coverage and mypy strictness
  - [ ] Minimal script/API surfaces; console entry points
  - [ ] Makefile targets clear and non-duplicated

- [ ] Documentation & OSS
  - [ ] README has quickstart/CI/license/security/disclaimer
  - [ ] CONTRIBUTING, CODE_OF_CONDUCT, LICENSE, NOTICE present
  - [ ] Architecture/Usage/Operations consistent with code
