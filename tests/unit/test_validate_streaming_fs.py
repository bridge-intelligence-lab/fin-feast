from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.network]

from fin_feast.utils.env import resolve_base_path
from fin_feast.utils.io import write_parquet_partitioned


def test_parquet_partition_detection(tmp_path: Path, monkeypatch):
    # Use a temp dir as base zone by monkeypatching resolve_base_path
    def fake_resolve_base_path(zone: str, exp_id: str | None = None) -> Path:  # type: ignore[override]
        base = tmp_path / "offline" / zone
        (base / "minute").mkdir(parents=True, exist_ok=True)
        return base

    monkeypatch.setattr("fin_feast.utils.env.resolve_base_path", fake_resolve_base_path)

    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.validate_streaming import _partition_path, _read_partition_rows

    zone = "current"
    symbol = "X:TEST"
    base = resolve_base_path(zone, None)

    # Initially no partition for today
    today = datetime.now(UTC).date().isoformat()
    p = _partition_path(base, symbol, "minute", today)
    assert _read_partition_rows(p) == 0

    # Write one row, then another, verify counts grow
    df1 = pd.DataFrame(
        [
            {
                "symbol": symbol,
                "event_timestamp": pd.Timestamp(datetime.now(UTC)),
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "vwap": 1.0,
                "volume": 1.0,
            }
        ]
    )
    write_parquet_partitioned(base / "minute", df1)
    c1 = _read_partition_rows(p)
    assert c1 == 1

    df2 = pd.DataFrame(
        [
            {
                "symbol": symbol,
                "event_timestamp": pd.Timestamp(datetime.now(UTC)),
                "open": 2.0,
                "high": 2.0,
                "low": 2.0,
                "close": 2.0,
                "vwap": 2.0,
                "volume": 2.0,
            }
        ]
    )
    write_parquet_partitioned(base / "minute", df2)
    c2 = _read_partition_rows(p)
    assert c2 == 2
