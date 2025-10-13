from __future__ import annotations

import os
import subprocess
import time
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
        assert cp.returncode == 0, f"Command failed: {cmd}\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"

    # Start streamer in background
    print("[E2E] == Binance streaming: start streamer ==")
    streamer = subprocess.Popen(
        ["bash", "-lc", ". .venv/bin/activate; python service/binance_stream_ingestor.py --zone current --symbols X:BTCUSD C:ETHUSD --push-online"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # Give it some time to produce
        time.sleep(10)
        # Validate stream + parquet + online
        print("[E2E] == Binance streaming: validate_streaming ==")
        cp = _run("python scripts/validate_streaming.py --zone current --symbols X:BTCUSD C:ETHUSD --check-online --provider binance")
        assert cp.returncode == 0, f"validate_streaming failed\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
        # Also run online query demo explicitly
        cp2 = _run("python scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD")
        assert cp2.returncode == 0, f"online_query_demo failed\nstdout:\n{cp2.stdout}\nstderr:\n{cp2.stderr}"
    finally:
        # Stop streamer
        streamer.terminate()
        try:
            streamer.wait(timeout=5)
        except subprocess.TimeoutExpired:
            streamer.kill()
