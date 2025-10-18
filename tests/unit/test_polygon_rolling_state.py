from __future__ import annotations

import pandas as pd

from service.polygon_rolling_state import PolygonRollingState


def test_polygon_rolling_state_add_bar_minimal():
    st = PolygonRollingState(window=5)
    out = st.add_bar(
        {
            "symbol": "X:BTCUSD",
            "event_timestamp": pd.Timestamp("2025-01-01T00:01:00Z"),
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": 1.0,
            "vwap": 1.0,
            "volume": 1.0,
        }
    )
    assert isinstance(out, pd.DataFrame)
    assert not out.empty
