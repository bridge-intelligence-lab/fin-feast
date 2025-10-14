from __future__ import annotations

from pathlib import Path

import pandas as pd

from fin_feast.utils.io import write_parquet_partitioned


def test_partition_grouping_and_paths(tmp_path: Path) -> None:
    base = tmp_path / "minute"
    base.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(
        [
            {
                "symbol": "X:BTCUSD",
                "event_timestamp": pd.Timestamp("2025-01-01T00:00:00Z"),
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "vwap": 1.0,
                "volume": 1.0,
            },
            {
                "symbol": "X:BTCUSD",
                "event_timestamp": pd.Timestamp("2025-01-02T00:00:00Z"),
                "open": 2.0,
                "high": 2.0,
                "low": 2.0,
                "close": 2.0,
                "vwap": 2.0,
                "volume": 2.0,
            },
        ]
    )

    write_parquet_partitioned(base, df)

    p1 = base / "symbol=X:BTCUSD" / "date=2025-01-01" / "data.parquet"
    p2 = base / "symbol=X:BTCUSD" / "date=2025-01-02" / "data.parquet"
    assert p1.exists()
    assert p2.exists()

    # Check ordering is preserved within each file
    d1 = pd.read_parquet(p1)
    d2 = pd.read_parquet(p2)
    assert list(d1["event_timestamp"]) == sorted(d1["event_timestamp"])  # already sorted
    assert list(d2["event_timestamp"]) == sorted(d2["event_timestamp"])  # already sorted
