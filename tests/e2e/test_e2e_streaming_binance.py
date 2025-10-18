from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(
    cmd: str, env: dict[str, str] | None = None, cwd: Path | None = None
) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
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
@pytest.mark.network
def test_e2e_streaming_binance(tmp_path: Path):
    # Clear env and bring Redis
    print("[E2E] == Binance streaming: clean and up redis ==")
    for cmd in [
        "make clean",
        "docker-compose down -v || true",
        "docker-compose up -d",
    ]:
        cp = _run(cmd)
        assert (
            cp.returncode == 0
        ), f"Command failed: {cmd}\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"

    # Start streamer in background
    print("[E2E] == Binance streaming: start streamer ==")
    streamer = subprocess.Popen(
        [
            "bash",
            "-lc",
            ". .venv/bin/activate; python service/binance_stream_ingestor.py --zone current --symbols X:BTCUSD C:ETHUSD --push-online",
        ],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # Seed offline store with sufficient history (daily and minute)
        print("[E2E] == Binance streaming: seed daily (30d) ==")
        cp_seed_daily = _run(
            "python scripts/fetch_binance_to_parquet.py --zone current --start 2025-09-01 --end 2025-09-30 --freq daily --symbols X:BTCUSD C:ETHUSD"
        )
        assert (
            cp_seed_daily.returncode == 0
        ), f"seed daily failed\nstdout:\n{cp_seed_daily.stdout}\nstderr:\n{cp_seed_daily.stderr}"
        print("[E2E] == Binance streaming: seed minute (1d) ==")
        cp_seed_min = _run(
            "python scripts/fetch_binance_to_parquet.py --zone current --start 2025-10-01 --end 2025-10-01 --freq minute --symbols X:BTCUSD C:ETHUSD"
        )
        assert (
            cp_seed_min.returncode == 0
        ), f"seed minute failed\nstdout:\n{cp_seed_min.stdout}\nstderr:\n{cp_seed_min.stderr}"
        # Apply repo so the online FV exists
        print("[E2E] == Binance streaming: apply repo ==")
        cp_apply = _run("make apply-current")
        assert (
            cp_apply.returncode == 0
        ), f"make apply-current failed\nstdout:\n{cp_apply.stdout}\nstderr:\n{cp_apply.stderr}"
        # Give it some time to produce
        time.sleep(15)
        # Materialize to ensure online store has data
        print("[E2E] == Binance streaming: materialize ==")
        cp_mat = _run("make materialize")
        assert (
            cp_mat.returncode == 0
        ), f"make materialize failed\nstdout:\n{cp_mat.stdout}\nstderr:\n{cp_mat.stderr}"
        # Validate stream + parquet + online
        print("[E2E] == Binance streaming: validate_streaming ==")
        cp = _run(
            "python scripts/validate_streaming.py --zone current --symbols X:BTCUSD C:ETHUSD --check-online --provider binance"
        )
        assert (
            cp.returncode == 0
        ), f"validate_streaming failed\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
        # Also run online query demo explicitly
        cp2 = _run("python scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD")
        assert (
            cp2.returncode == 0
        ), f"online_query_demo failed\nstdout:\n{cp2.stdout}\nstderr:\n{cp2.stderr}"
    finally:
        # Stop streamer
        streamer.terminate()
        try:
            streamer.wait(timeout=5)
        except subprocess.TimeoutExpired:
            streamer.kill()
