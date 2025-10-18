from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(
    cmd: str, env: dict[str, str] | None = None, cwd: Path | None = None
) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    # Activate venv then run
    bash_cmd = f"set -euo pipefail; . .venv/bin/activate; {cmd}"
    return subprocess.run(
        ["bash", "-lc", bash_cmd],
        cwd=str(cwd or REPO_ROOT),
        env=full_env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.e2e
def test_e2e_quickstart(tmp_path: Path):
    # Clear environment (data + redis + registry)
    print("[E2E] == Clear environment and start Redis ==")
    for cmd in [
        "make clean",
        "docker-compose down -v || true",
        "docker-compose up -d",
    ]:
        cp = _run(cmd)
        assert (
            cp.returncode == 0
        ), f"Command failed: {cmd}\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"

    # Generate synthetic data
    print("[E2E] == Generate synthetic data (daily and minute) ==")
    cp = _run(
        "python scripts/generate_synthetic_data.py --zone current --start 2025-09-01 --end 2025-10-12 --freq daily --symbols X:BTCUSD C:ETHUSD"
    )
    assert cp.returncode == 0, cp.stderr
    cp = _run(
        "python scripts/generate_synthetic_data.py --zone current --start 2025-10-01 --end 2025-10-12 --freq minute --symbols X:BTCUSD C:ETHUSD"
    )
    assert cp.returncode == 0, cp.stderr

    # Apply + materialize
    print("[E2E] == Apply and materialize ==")
    for cmd in [
        "make apply-current",
        "make materialize",
    ]:
        cp = _run(cmd)
        assert (
            cp.returncode == 0
        ), f"Command failed: {cmd}\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
        if cmd == "make materialize":
            assert "Materializing" in (cp.stdout + cp.stderr)

    # Online query demo
    print("[E2E] == Online query demo ==")
    cp = _run("python scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD")
    assert cp.returncode == 0, cp.stderr
    # Logs go to stderr via logging.StreamHandler default; check both
    out = cp.stdout + cp.stderr
    assert "Symbol=X:BTCUSD" in out and "Symbol=C:ETHUSD" in out
