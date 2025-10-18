from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.materialize_incremental import _ensure_partition_columns


def test_ensure_partition_columns(tmp_path: Path) -> None:
    project_root = tmp_path
    # Create current minute and daily partitions missing symbol/date in file
    for freq in ("minute", "daily"):
        d = (
            project_root
            / "data"
            / "offline"
            / "current"
            / freq
            / "symbol=X:BTCUSD"
            / "date=2025-01-01"
        )
        d.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(
            {
                "event_timestamp": pd.to_datetime(["2025-01-01T00:00:00Z"], utc=True),
                "open": [1.0],
                "high": [1.0],
                "low": [1.0],
                "close": [1.0],
                "vwap": [1.0],
                "volume": [1.0],
            }
        )
        (d / "data.parquet").parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(d / "data.parquet", index=False)

    # Run fixer
    _ensure_partition_columns(project_root)

    # Verify symbol and date columns added in both
    for freq in ("minute", "daily"):
        p = (
            project_root
            / "data"
            / "offline"
            / "current"
            / freq
            / "symbol=X:BTCUSD"
            / "date=2025-01-01"
            / "data.parquet"
        )
        loaded = pd.read_parquet(p)
        assert "symbol" in loaded.columns
        assert "date" in loaded.columns
