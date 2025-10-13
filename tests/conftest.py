from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure project root is importable so `scripts` and top-level modules can be imported
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session", autouse=True)
def global_env_defaults() -> None:
    # Default Feast envs, can be overridden per-test
    os.environ.setdefault("FEAST_DATA_ZONE", "current")
    os.environ.setdefault("FEAST_EXPERIMENT_ID", "")


# Register custom markers to avoid warnings
def pytest_configure(config):  # type: ignore[no-redef]
    config.addinivalue_line("markers", "e2e: end-to-end test")
    config.addinivalue_line("markers", "network: requires network access")
    config.addinivalue_line("markers", "polygon: requires POLYGON_API_KEY and Polygon network access")
