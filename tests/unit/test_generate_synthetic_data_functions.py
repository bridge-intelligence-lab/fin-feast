from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from scripts.generate_synthetic_data import daterange, gen_bars, synthetic_series


def test_daterange_daily_and_minute():
    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = datetime(2025, 1, 3, tzinfo=UTC)
    d = daterange(start, end, "daily")
    assert len(d) == 3

    start_m = datetime(2025, 1, 1, tzinfo=UTC)
    end_m = datetime(2025, 1, 1, 0, 2, tzinfo=UTC)
    m = daterange(start_m, end_m, "minute")
    assert len(m) == 3


def test_synthetic_series_shape_positive():
    s = synthetic_series(100.0, 10, vol=0.01)
    assert s.shape == (10,)
    assert np.all(s > 0)


def test_gen_bars_required_columns():
    ts = daterange(
        datetime(2025, 1, 1, tzinfo=UTC),
        datetime(2025, 1, 1, 0, 2, tzinfo=UTC),
        "minute",
    )
    df = gen_bars("X:BTCUSD", ts, 100.0)
    for c in ["symbol", "event_timestamp", "open", "high", "low", "close", "vwap", "volume"]:
        assert c in df.columns
