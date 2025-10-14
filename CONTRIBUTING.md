# Contributing

Thank you for your interest in contributing! This project welcomes contributions of
all kinds: bug reports, documentation improvements, tests, and features.

## Getting started
- Python 3.11 recommended
- Create a virtualenv and install dev dependencies:
  - python -m venv .venv
  - . .venv/bin/activate
  - pip install -U pip
  - pip install -e .[dev]
- Optional: install pre-commit hooks:
  - pip install pre-commit
  - pre-commit install

## Running tests
- Unit tests: pytest -q tests/unit
- Full test suite: pytest -q
- E2E tests are marked with @pytest.mark.e2e and may require network and Docker.
  - To run E2E: ensure .venv exists, docker-compose is available, and (optionally) POLYGON_API_KEY is set for Polygon tests.

## Linting and formatting
- Ruff is used for linting and formatting:
  - ruff check .
  - ruff format .

## Submitting changes
1. Fork the repo and create your branch from main.
2. Ensure tests pass and linters are clean.
3. If adding a feature or changing behavior, update documentation.
4. Open a PR with a clear description and rationale.

## Code of Conduct
By participating, you agree to abide by the Code of Conduct in CODE_OF_CONDUCT.md.
