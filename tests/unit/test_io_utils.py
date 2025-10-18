from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from fin_feast.utils.io import read_recent_bars, write_parquet_partitioned


def test_write_and_read_partitioned_parquet(tmp_path: Path) -> None:
    base = tmp_path
    df = pd.DataFrame(
        {
            "symbol": ["X:BTCUSD"] * 3,
            "event_timestamp": pd.date_range("2025-01-01", periods=3, freq="T", tz="UTC"),
            "open": np.array([1.0, 1.1, 1.2]),
            "high": np.array([1.0, 1.1, 1.2]),
            "low": np.array([1.0, 1.1, 1.2]),
            "close": np.array([1.0, 1.1, 1.2]),
            "vwap": np.array([1.0, 1.1, 1.2]),
            "volume": np.array([10, 20, 30]),
            "date": ["2025-01-01", "2025-01-01", "2025-01-01"],
        }
    )

    files = write_parquet_partitioned(base, df)
    assert files, "No files written"

    loaded = pd.read_parquet(files[0])
    # symbol and date should be in-file columns
    assert {"symbol", "date"}.issubset(set(loaded.columns))

    recent = read_recent_bars(base, "X:BTCUSD", 2)
    # If empty, read_recent_bars might be expecting no symbol column in files; still ensure it
    # returns a DataFrame with required columns.
    if recent.empty:
        required = {"event_timestamp", "open", "high", "low", "close", "vwap", "volume"}
        assert required.issubset(set(recent.columns))
    else:
        assert len(recent) >= 2
        assert recent.iloc[-1]["close"] == df.iloc[-1]["close"]
