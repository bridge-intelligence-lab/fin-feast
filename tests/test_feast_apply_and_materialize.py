from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from feast import FeatureStore


@pytest.fixture(scope="session", autouse=True)
def redis_stack():
    subprocess.run(["docker-compose", "up", "-d"], check=True)
    yield
    subprocess.run(["docker-compose", "down"], check=True)


def test_apply_and_materialize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Prepare minimal offline data for minute inside project data dir
    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data" / "offline" / "current" / "minute"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(
        {
            "symbol": ["X:BTCUSD", "C:GBPUSD"],
            "event_timestamp": pd.to_datetime(["2025-01-01T00:00:00Z", "2025-01-01T00:00:00Z"], utc=True),
            "open": [1.0, 1.0],
            "high": [1.1, 1.1],
            "low": [0.9, 0.9],
            "close": [1.05, 1.02],
            "vwap": [1.05, 1.02],
            "volume": [1000, 2000],
            "return_1": [None, None],
            "ma_5": [None, None],
            "ma_20": [None, None],
            "vol_20": [None, None],
            "rsi_14": [None, None],
            "atr_14": [None, None],
        }
    )

    # Write partitions
    for sym, g in df.groupby("symbol"):
        d = data_dir / f"symbol={sym}" / "date=2025-01-01"
        d.mkdir(parents=True)
        g.drop(columns=["symbol"]).to_parquet(d / "data.parquet", index=False)

    # Point env to current zone
    monkeypatch.setenv("FEAST_DATA_ZONE", "current")
    monkeypatch.setenv("FEAST_EXPERIMENT_ID", "")

    # Run apply + materialize
    # Ensure a clean registry to avoid stale ODFV entries from previous runs
    reg_path = project_root / "feature_repo" / "registry.db"
    if reg_path.exists():
        reg_path.unlink()

    fs = FeatureStore(repo_path=str(project_root / "feature_repo"))
    # Apply all repo objects explicitly to support current Feast version
    import importlib.util
    import sys
    sys.path.insert(0, str(project_root))
    from feature_repo import repo  # type: ignore
    objects = [
        repo.symbol,
        repo.make_daily_ohlcv_source(),
        repo.make_minute_ohlcv_source(),
        repo.daily_ohlcv_fv,
        repo.minute_ohlcv_fv,
        # Omit ODFV to avoid dill serialization issues in this Feast version
    ]
    fs.apply(objects)
    fs.materialize_incremental(pd.Timestamp.utcnow())

    # Query
    features = [
        "minute_ohlcv_fv:open",
        "minute_ohlcv_fv:high",
        "minute_ohlcv_fv:low",
        "minute_ohlcv_fv:close",
        "minute_ohlcv_fv:vwap",
        "minute_ohlcv_fv:volume",
    ]

    res = fs.get_online_features(
        features=features,
        entity_rows=[{"symbol": "X:BTCUSD"}, {"symbol": "C:GBPUSD"}],
    ).to_dict()

    expected_keys = ["open", "high", "low", "close", "vwap", "volume"]
    for k in expected_keys:
        assert k in res
        assert len(res[k]) == 2
