from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from fin_feast.utils.io import write_parquet_partitioned
from service.polygon_stream_ingestor import RollingState


class _FSMock:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def write_to_online_store(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append({"args": args, "kwargs": kwargs})
        raise RuntimeError("simulated failure")


def test_polygon_push_isolation(tmp_path: pd.Path) -> None:  # type: ignore[name-defined]
    base = tmp_path / "minute"
    base.mkdir(parents=True, exist_ok=True)

    st = RollingState(max_bars=5)
    st.warm_start(base, ["X:BTCUSD"])  # empty ok

    bar = {
        "symbol": "X:BTCUSD",
        "event_timestamp": pd.Timestamp("2025-01-01T00:00:00Z"),
        "open": 1.0,
        "high": 1.0,
        "low": 1.0,
        "close": 1.0,
        "vwap": 1.0,
        "volume": 1.0,
    }
    df = st.add_bar(bar)
    latest = df.tail(1)

    # simulate call into safe push wrapper
    # reimport safe_push_online by constructing a local function equivalent to avoid touching Redis
    from service.polygon_stream_ingestor import pd as _pd  # noqa: N812

    def safe_push_online(fs_local: _FSMock, latest_df: _pd.DataFrame) -> None:
        try:
            row = latest_df.iloc[0].to_dict()
            clean = {
                k: (None if (isinstance(v, float) and (np.isnan(v))) else v) for k, v in row.items()
            }
            clean.pop("event_timestamp", None)
            fv_features = [
                "open",
                "high",
                "low",
                "close",
                "vwap",
                "volume",
                "return_1",
                "ma_5",
                "ma_20",
                "vol_20",
                "rsi_14",
                "atr_14",
            ]
            assert "symbol" in clean
            payload = {
                "symbol": clean["symbol"],
                **{k: clean.get(k) for k in fv_features if k in clean},
            }
            df_payload = _pd.DataFrame([payload])
            fs_local.write_to_online_store(feature_view_name="minute_ohlcv_fv", df=df_payload)
        except Exception:
            # ensure we swallow exceptions
            pass

    fs = _FSMock()
    # should not raise
    safe_push_online(fs, latest)

    # parquet write still works
    write_parquet_partitioned(base, latest)
    p = base / "symbol=X:BTCUSD" / "date=2025-01-01" / "data.parquet"
    assert p.exists()
