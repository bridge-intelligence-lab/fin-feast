from __future__ import annotations

from pathlib import Path

import pandas as pd

from feast import FeatureStore


def test_historical_features(tmp_path: Path, monkeypatch) -> None:
    # Create experiment snapshot
    exp_id = "exp_test"
    base = tmp_path / "offline/experiments" / exp_id
    daily = base / "daily"
    minute = base / "minute"
    for d in (daily, minute):
        d.mkdir(parents=True, exist_ok=True)

    for sym in ("X:BTCUSD", "C:GBPUSD"):
        ddir = daily / f"symbol={sym}" / "date=2025-01-01"
        ddir.mkdir(parents=True)
        pd.DataFrame(
            {
                "symbol": [sym],
                "event_timestamp": pd.to_datetime(["2025-01-01T00:00:00Z"], utc=True),
                "open": [1.0],
                "high": [1.1],
                "low": [0.9],
                "close": [1.05],
                "vwap": [1.05],
                "volume": [1000],
                "return_1": [None],
                "ma_5": [None],
                "ma_20": [None],
                "vol_20": [None],
                "rsi_14": [None],
                "atr_14": [None],
            }
        ).to_parquet(ddir / "data.parquet", index=False)

    # Env for experiment
    monkeypatch.setenv("FEAST_DATA_ZONE", "experiment")
    monkeypatch.setenv("FEAST_EXPERIMENT_ID", exp_id)

    fs = FeatureStore(repo_path=str(Path(__file__).resolve().parents[1] / "feature_repo"))

    entity_df = pd.DataFrame(
        [
            {"symbol": "X:BTCUSD", "event_timestamp": pd.Timestamp("2025-01-02T00:00:00Z")},
            {"symbol": "C:GBPUSD", "event_timestamp": pd.Timestamp("2025-01-02T00:00:00Z")},
        ]
    )

    features = [
        "daily_ohlcv_fv:open",
        "daily_ohlcv_fv:high",
        "daily_ohlcv_fv:low",
        "daily_ohlcv_fv:close",
    ]

    df = fs.get_historical_features(entity_df=entity_df, features=features).to_df()
    assert len(df) == 2
    for f in features:
        assert f.split(":")[1] in df.columns
