from __future__ import annotations

import pandas as pd

from scripts.fetch_polygon_to_parquet import fetch_aggregates


class _ClientMock:
    def __init__(self, results):
        self._results = results

    def get_aggs(self, ticker, multiplier, timespan, from_, to):  # type: ignore[no-untyped-def]
        return self._results


class _Res:
    def __init__(self, rows):
        self.results = rows


def test_fetch_aggregates_basic():
    rows = [
        {"t": 1735689600000, "o": 1.0, "h": 1.1, "l": 0.9, "c": 1.05, "v": 10, "vw": 1.02},
        {"t": 1735689660000, "o": 1.05, "h": 1.15, "l": 0.95, "c": 1.06, "v": 11, "vw": 1.03},
    ]
    client = _ClientMock(_Res(rows))
    df = fetch_aggregates(client, "X:BTCUSD", "2025-01-01", "2025-01-02", "minute")
    assert not df.empty
    assert set(["event_timestamp", "open", "high", "low", "close", "vwap", "volume"]).issubset(df.columns)
