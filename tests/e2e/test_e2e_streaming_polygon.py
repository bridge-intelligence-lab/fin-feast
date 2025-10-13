from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

from .utils import run_shell, clean_and_up_redis, assert_ok, REPO_ROOT


@pytest.mark.e2e
@pytest.mark.network
@pytest.mark.polygon
def test_e2e_streaming_polygon():
    if not os.getenv("POLYGON_API_KEY"):
        pytest.skip("POLYGON_API_KEY not set; skipping Polygon streaming E2E")

    print("[E2E] == Polygon streaming: clean and up redis ==")
    clean_and_up_redis()

    # Start Polygon streamer in background with push-online
    print("[E2E] == Polygon streaming: start streamer ==")
    streamer = subprocess.Popen(
        [
            "bash",
            "-lc",
            ". .venv/bin/activate; python service/polygon_stream_ingestor.py --symbols X:BTCUSD C:ETHUSD --push-online",
        ],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        time.sleep(10)
        # Validate with provider polygon
        cp = run_shell(
            "python scripts/validate_streaming.py --zone current --symbols X:BTCUSD C:ETHUSD --check-online --provider polygon"
        )
        assert_ok(cp, "validate_streaming polygon")
        # Optional: run online query demo
        cp2 = run_shell("python scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD")
        assert_ok(cp2, "online_query_demo after polygon streaming")
    finally:
        streamer.terminate()
        try:
            streamer.wait(timeout=5)
        except subprocess.TimeoutExpired:
            streamer.kill()
