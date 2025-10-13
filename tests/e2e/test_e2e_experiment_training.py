from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(cmd: str, env: dict[str, str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    bash_cmd = f"set -euo pipefail; . .venv/bin/activate; {cmd}"
    return subprocess.run(["bash", "-lc", bash_cmd], cwd=str(cwd or REPO_ROOT), env=full_env, capture_output=True, text=True)


@pytest.mark.e2e
def test_e2e_experiment_training(tmp_path: Path):
    # Clear env
    for cmd in [
        "make clean",
        "docker-compose down -v || true",
        "docker-compose up -d",
    ]:
        cp = _run(cmd)
        assert cp.returncode == 0, f"Command failed: {cmd}\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"

    # Set experiment env
    exp_id = f"my_exp_{os.getpid()}"

    # Generate synthetic under experiments
    cp = _run(
        "python scripts/generate_synthetic_data.py --zone experiment --exp-id '' --start 2025-10-01 --end 2025-10-03 --freq daily --symbols X:BTCUSD C:ETHUSD",
        env={"FEAST_EXPERIMENT_ID": exp_id, "FEAST_DATA_ZONE": "experiment"},
    )
    assert cp.returncode == 0, cp.stderr

    # Apply experiment + materialize
    cp = _run("make apply-experiment", env={"FEAST_EXPERIMENT_ID": exp_id})
    assert cp.returncode == 0, cp.stderr
    cp = _run("make materialize", env={"FEAST_EXPERIMENT_ID": exp_id, "FEAST_DATA_ZONE": "experiment"})
    assert cp.returncode == 0, cp.stderr

    # Build training dataset
    outp = REPO_ROOT / "data" / "derived" / "training.parquet"
    if outp.exists():
        outp.unlink()
    cp = _run(
        "python scripts/build_training_dataset.py --zone experiment --exp-id '' --start 2025-09-01 --end 2025-10-12 --symbols X:BTCUSD C:ETHUSD --out data/derived/training.parquet",
        env={"FEAST_EXPERIMENT_ID": exp_id, "FEAST_DATA_ZONE": "experiment"},
    )
    assert cp.returncode == 0, cp.stderr
    assert outp.exists() and outp.stat().st_size > 0
