from __future__ import annotations

import numpy as np
import pandas as pd

from fin_feast.features.rolling import (
    add_indicators,
    compute_atr,
    compute_ma,
    compute_return_1,
    compute_rsi,
    compute_vol,
)


def make_df(sym: str = "X:BTCUSD", n: int = 10) -> pd.DataFrame:
    ts = pd.date_range("2025-01-01", periods=n, freq="T", tz="UTC")
    close = np.linspace(1.0, 2.0, n)
    return pd.DataFrame(
        {
            "symbol": [sym] * n,
            "event_timestamp": ts,
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.98,
            "close": close,
            "vwap": close,
            "volume": np.arange(1, n + 1) * 10,
        }
    )


def test_compute_return_1() -> None:
    df = make_df(n=3)
    s = compute_return_1(df)
    assert s.isna().sum() == 1
    assert np.isclose(s.iloc[-1], (df["close"].iloc[-1] / df["close"].iloc[-2]) - 1)


def test_compute_ma_and_vol() -> None:
    df = make_df(n=5)
    ma = compute_ma(df, 3)
    vol = compute_vol(df, 3)
    assert ma.isna().sum() == 2
    assert vol.isna().sum() == 2


def test_compute_rsi_and_atr() -> None:
    df = make_df(n=20)
    rsi = compute_rsi(df, 5)
    atr = compute_atr(df, 5)
    assert rsi.isna().sum() >= 4
    assert atr.isna().sum() >= 4


def test_add_indicators_columns() -> None:
    df = make_df(n=20)
    out = add_indicators(df)
    for c in ["return_1", "ma_5", "ma_20", "vol_20", "rsi_14", "atr_14"]:
        assert c in out.columns
