from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from scripts.generate_synthetic_data import daterange, synthetic_series, gen_bars


def test_daterange_daily_and_minute():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = datetime(2025, 1, 3, tzinfo=timezone.utc)
    d = daterange(start, end, "daily")
    assert len(d) == 3

    start_m = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_m = datetime(2025, 1, 1, 0, 2, tzinfo=timezone.utc)
    m = daterange(start_m, end_m, "minute")
    assert len(m) == 3


def test_synthetic_series_shape_positive():
    s = synthetic_series(100.0, 10, vol=0.01)
    assert s.shape == (10,)
    assert np.all(s > 0)


def test_gen_bars_required_columns():
    ts = daterange(datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2025, 1, 1, 0, 2, tzinfo=timezone.utc), "minute")
    df = gen_bars("X:BTCUSD", ts, 100.0)
    for c in ["symbol", "event_timestamp", "open", "high", "low", "close", "vwap", "volume"]:
        assert c in df.columns
