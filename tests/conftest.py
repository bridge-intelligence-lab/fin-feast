from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def set_env_repo_root() -> None:
    # Ensure FEAST_DATA_ZONE defaults to current for tests unless overridden
    os.environ.setdefault("FEAST_DATA_ZONE", "current")
    os.environ.setdefault("FEAST_EXPERIMENT_ID", "")


@pytest.fixture(scope="session")
def redis_stack():
    subprocess.run(["docker-compose", "up", "-d"], check=True)
    yield
    subprocess.run(["docker-compose", "down"], check=True)
