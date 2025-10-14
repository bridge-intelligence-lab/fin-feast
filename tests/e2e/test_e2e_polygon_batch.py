from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest
from feast import FeatureStore

from .utils import REPO_ROOT, run_shell, clean_and_up_redis, assert_ok


@pytest.mark.e2e
@pytest.mark.network
@pytest.mark.polygon
def test_e2e_polygon_batch():
    if not os.getenv("POLYGON_API_KEY"):
        pytest.skip("POLYGON_API_KEY not set; skipping Polygon E2E")

    print("[E2E] == Polygon batch: clean and up redis ==")
    clean_and_up_redis()

    # Fetch Polygon daily + minute
    print("[E2E] == Polygon batch: fetch daily ==")
    cp = run_shell(
        "python scripts/fetch_polygon_to_parquet.py --zone current --start 2025-09-01 --end 2025-09-03 --freq daily --symbols X:BTCUSD C:ETHUSD"
    )
    assert_ok(cp, "fetch_polygon daily")
    print("[E2E] == Polygon batch: fetch minute ==")
    cp = run_shell(
        "python scripts/fetch_polygon_to_parquet.py --zone current --start 2025-10-01 --end 2025-10-02 --freq minute --symbols X:BTCUSD C:ETHUSD"
    )
    assert_ok(cp, "fetch_polygon minute")

    # Apply + materialize
    print("[E2E] == Polygon batch: apply ==")
    cp = run_shell("make apply-current")
    assert_ok(cp, "make apply-current")
    print("[E2E] == Polygon batch: materialize ==")
    cp = run_shell("make materialize")
    assert_ok(cp, "make materialize")

    # Online query demo
    print("[E2E] == Polygon batch: online query demo ==")
    cp = run_shell("python scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD")
    assert_ok(cp, "online_query_demo")
    out = cp.stdout + cp.stderr
    assert "Symbol=X:BTCUSD" in out and "Symbol=C:ETHUSD" in out

    # Offline historical check
    fs = FeatureStore(repo_path=str(REPO_ROOT / "feature_repo"))
    rows = [
        {"symbol": "X:BTCUSD", "event_timestamp": pd.Timestamp("2025-10-01T00:00:00Z")},
        {"symbol": "C:ETHUSD", "event_timestamp": pd.Timestamp("2025-10-01T00:00:00Z")},
    ]
    entity_df = pd.DataFrame(rows)
    features = [
        "minute_ohlcv_fv:open",
        "minute_ohlcv_fv:close",
    ]
    hf = fs.get_historical_features(entity_df=entity_df, features=features).to_df()
    assert not hf.empty
