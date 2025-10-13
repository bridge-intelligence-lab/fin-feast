from __future__ import annotations

from pathlib import Path

import pandas as pd

from fin_feast.features.rolling import add_indicators
from fin_feast.utils.io import write_parquet_partitioned


def test_stream_simulated_partition_write(tmp_path: Path) -> None:
    base = tmp_path / "offline/current/minute"
    base.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(
        {
            "symbol": ["X:BTCUSD"] * 5,
            "event_timestamp": pd.to_datetime(
                [
                    "2025-01-01T00:00:00Z",
                    "2025-01-01T00:01:00Z",
                    "2025-01-01T00:02:00Z",
                    "2025-01-01T00:03:00Z",
                    "2025-01-01T00:04:00Z",
                ],
                utc=True,
            ),
            "open": [1, 1.01, 1.02, 1.03, 1.04],
            "high": [1.02, 1.03, 1.04, 1.05, 1.06],
            "low": [0.99, 1.0, 1.01, 1.02, 1.03],
            "close": [1.01, 1.02, 1.03, 1.04, 1.05],
            "vwap": [1.01, 1.02, 1.03, 1.04, 1.05],
            "volume": [1000, 1100, 1200, 1300, 1400],
        }
    )
    df = add_indicators(df)
    write_parquet_partitioned(base, df.tail(1))

    files = list((base / "symbol=X:BTCUSD").glob("date=*/data.parquet"))
    assert files
