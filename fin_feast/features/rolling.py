from __future__ import annotations

import numpy as np
import pandas as pd


def compute_return_1(df: pd.DataFrame) -> pd.Series:
    return df.groupby("symbol")["close"].pct_change()


def compute_ma(df: pd.DataFrame, window: int) -> pd.Series:
    return df.groupby("symbol")["close"].transform(
        lambda s: s.rolling(window, min_periods=window).mean()
    )


def compute_vol(df: pd.DataFrame, window: int) -> pd.Series:
    return df.groupby("symbol")["close"].transform(
        lambda s: s.rolling(window, min_periods=window).std(ddof=0)
    )


def compute_rsi(df: pd.DataFrame, window: int = 14) -> pd.Series:
    def rsi_series(s: pd.Series) -> pd.Series:
        delta = s.diff()
        up = delta.clip(lower=0)
        down = -delta.clip(upper=0)
        roll_up = up.rolling(window, min_periods=window).mean()
        roll_down = down.rolling(window, min_periods=window).mean()
        rs = roll_up / roll_down.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    return df.groupby("symbol")["close"].transform(rsi_series)


def compute_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    # True Range per row: max(high - low, abs(high - prev_close), abs(low - prev_close))
    df = df.copy()
    df["prev_close"] = df.groupby("symbol")["close"].shift(1)
    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - df["prev_close"]).abs()
    tr3 = (df["low"] - df["prev_close"]).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.groupby(df["symbol"]).transform(lambda s: s.rolling(window, min_periods=window).mean())
    return atr


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["symbol", "event_timestamp"]).copy()
    df["return_1"] = compute_return_1(df)
    df["ma_5"] = compute_ma(df, 5)
    df["ma_20"] = compute_ma(df, 20)
    df["vol_20"] = compute_vol(df, 20)
    df["rsi_14"] = compute_rsi(df, 14)
    df["atr_14"] = compute_atr(df, 14)
    return df
