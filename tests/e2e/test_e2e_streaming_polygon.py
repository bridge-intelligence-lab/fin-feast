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
        # Seed daily and minute parquet to guarantee offline availability for both FVs
        print("[E2E] == Polygon streaming: seed daily (30d) ==")
        cp_seed_daily = run_shell(
            "python scripts/fetch_polygon_to_parquet.py --zone current --start 2025-09-01 --end 2025-09-30 --freq daily --symbols X:BTCUSD C:ETHUSD --symbols-delay-secs 1.0"
        )
        assert_ok(cp_seed_daily, "seed daily polygon")
        print("[E2E] == Polygon streaming: seed minute (1d) ==")
        cp_seed_min = run_shell(
            "python scripts/fetch_polygon_to_parquet.py --zone current --start 2025-10-01 --end 2025-10-01 --freq minute --symbols X:BTCUSD C:ETHUSD --symbols-delay-secs 1.0"
        )
        assert_ok(cp_seed_min, "seed minute polygon")
        # Apply & materialize to ensure FV exists and Redis is populated
        print("[E2E] == Polygon streaming: apply repo ==")
        cp_apply = run_shell("make apply-current")
        assert_ok(cp_apply, "make apply-current polygon")
        print("[E2E] == Polygon streaming: materialize ==")
        cp_mat = run_shell("make materialize")
        assert_ok(cp_mat, "make materialize polygon")
        time.sleep(10)
        # Validate with provider polygon (WS optional)
        cp = run_shell(
            "python scripts/validate_streaming.py --zone current --symbols X:BTCUSD C:ETHUSD --check-online --provider polygon --ws-timeout 30 --ws-optional"
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
