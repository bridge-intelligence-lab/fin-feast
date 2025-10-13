from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

import scripts.fetch_binance_to_parquet as fb


class _Resp:
    def __init__(self, payload: Any):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_fetch_klines_and_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock requests.get to return two klines
    def fake_get(url, params=None, timeout=None):  # type: ignore[no-untyped-def]
        ts0 = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        ts1 = int(datetime(2025, 1, 1, 0, 1, tzinfo=timezone.utc).timestamp() * 1000)
        klines = [
            [ts0, "1.0", "1.1", "0.9", "1.05", "10", ts0 + 60000, "", "", "", "", ""],
            [ts1, "1.05", "1.15", "0.95", "1.06", "11", ts1 + 60000, "", "", "", "", ""],
        ]
        return _Resp(klines)

    monkeypatch.setattr(fb, "requests", type("_R", (), {"get": staticmethod(fake_get)}))

    # Prepare base path via resolver monkeypatch
    def fake_resolve(zone: str, exp_id: str | None = None) -> Path:  # type: ignore[override]
        b = tmp_path / "offline" / zone / "minute"
        b.mkdir(parents=True, exist_ok=True)
        return tmp_path / "offline" / zone

    monkeypatch.setattr(fb, "resolve_base_path", fake_resolve)

    # Run main flow via internal functions
    start = "2025-01-01T00:00:00Z"
    end = "2025-01-01T00:02:00Z"
    base = fake_resolve("current") / "minute"

    # Build DataFrame similar to main flow
    df = fb._fetch_klines(
        "BTCUSDT",
        "1m",
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        datetime(2025, 1, 1, 0, 2, tzinfo=timezone.utc),
    )
    assert not df.empty
    df.insert(0, "symbol", "X:BTCUSD")
    df["vwap"] = (df["high"] + df["low"] + df["close"]) / 3.0

    from fin_feast.features.rolling import add_indicators
    from fin_feast.utils.io import write_parquet_partitioned

    df = add_indicators(df)
    write_parquet_partitioned(base, df)

    files = list((base / "symbol=X:BTCUSD").glob("date=*/data.parquet"))
    assert files
