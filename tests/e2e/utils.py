from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _should_verbose() -> bool:
    return os.getenv("E2E_VERBOSE") == "1"


def run_shell(cmd: str, env: dict[str, str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a shell command from repo root with .venv activation.

    Always prints the command. Prints stdout/stderr when E2E_VERBOSE=1 or on failure.
    """
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    activate = REPO_ROOT / ".venv" / "bin" / "activate"
    if not activate.exists():
        pytest.skip(".venv not found. Create it and install project: python -m venv .venv && . .venv/bin/activate && pip install -e .[dev]")
    bash_cmd = f"set -euo pipefail; . .venv/bin/activate; {cmd}"
    print(f"[E2E] RUN: {cmd}")
    cp = subprocess.run(["bash", "-lc", bash_cmd], cwd=str(cwd or REPO_ROOT), env=full_env, capture_output=True, text=True)
    if cp.returncode != 0 or _should_verbose():
        print(f"[E2E] STDOUT (code={cp.returncode}):\n{cp.stdout}")
        print(f"[E2E] STDERR (code={cp.returncode}):\n{cp.stderr}")
    return cp


def clean_and_up_redis() -> None:
    print("[E2E] == Clean and start Redis ==")
    for cmd in [
        "make clean",
        "docker-compose down -v || true",
        "docker-compose up -d",
    ]:
        cp = run_shell(cmd)
        if cp.returncode != 0:
            raise AssertionError(f"Command failed: {cmd}\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}")


def assert_ok(cp: subprocess.CompletedProcess, context: str | None = None) -> None:
    if cp.returncode != 0:
        raise AssertionError(f"{context or 'Command'} failed with code {cp.returncode}\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}")
