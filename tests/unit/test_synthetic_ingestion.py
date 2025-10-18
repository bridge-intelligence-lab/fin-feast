from __future__ import annotations

from pathlib import Path

import pandas as pd

from fin_feast.features.rolling import add_indicators
from fin_feast.utils.io import write_parquet_partitioned


def test_synthetic_parquet_schema(tmp_path: Path) -> None:
    base = tmp_path / "offline/current/minute"
    base.mkdir(parents=True)

    df = pd.DataFrame(
        {
            "symbol": ["X:BTCUSD"] * 3,
            "event_timestamp": pd.to_datetime(
                ["2025-01-01T00:00:00Z", "2025-01-01T00:01:00Z", "2025-01-01T00:02:00Z"],
                utc=True,
            ),
            "open": [1.0, 1.1, 1.2],
            "high": [1.2, 1.2, 1.3],
            "low": [0.9, 1.0, 1.1],
            "close": [1.05, 1.15, 1.25],
            "vwap": [1.05, 1.15, 1.25],
            "volume": [1000, 1100, 1200],
        }
    )
    df = add_indicators(df)
    write_parquet_partitioned(base, df)

    files = list((base / "symbol=X:BTCUSD").glob("date=*/data.parquet"))
    assert files, "Partition file not written"

    loaded = pd.read_parquet(files[0])
    required_cols = {
        "symbol",
        "event_timestamp",
        "open",
        "high",
        "low",
        "close",
        "vwap",
        "volume",
        "return_1",
        "ma_5",
        "ma_20",
        "vol_20",
        "rsi_14",
        "atr_14",
    }
    assert required_cols.issubset(loaded.columns)
    assert str(loaded["event_timestamp"].dtype).startswith("datetime64[ns, UTC]")
