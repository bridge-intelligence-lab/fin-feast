from __future__ import annotations

from datetime import timedelta

from feast import FeatureView, Field, OnDemandFeatureView
from feast.types import Float32

from entities import symbol
from data_sources import daily_ohlcv_source, minute_ohlcv_source

# Base features including precomputed indicators
base_fields = [
    Field(name="open", dtype=Float32),
    Field(name="high", dtype=Float32),
    Field(name="low", dtype=Float32),
    Field(name="close", dtype=Float32),
    Field(name="vwap", dtype=Float32),
    Field(name="volume", dtype=Float32),
    Field(name="return_1", dtype=Float32),
    Field(name="ma_5", dtype=Float32),
    Field(name="ma_20", dtype=Float32),
    Field(name="vol_20", dtype=Float32),
    Field(name="rsi_14", dtype=Float32),
    Field(name="atr_14", dtype=Float32),
]


daily_ohlcv_fv = FeatureView(
    name="daily_ohlcv_fv",
    entities=[symbol],
    ttl=timedelta(days=400),
    schema=base_fields,
    online=True,
    source=daily_ohlcv_source,
)


minute_ohlcv_fv = FeatureView(
    name="minute_ohlcv_fv",
    entities=[symbol],
    ttl=timedelta(days=14),
    schema=base_fields,
    online=True,
    source=minute_ohlcv_source,
)


# On-demand stateless transforms derived from minute features only to avoid column collisions

def stateless_transforms(df):  # type: ignore[no-untyped-def]
    import numpy as np

    out = {}
    out["hlc3"] = (df["high"] + df["low"] + df["close"]) / 3.0
    out["ohlc4"] = (df["open"] + df["high"] + df["low"] + df["close"]) / 4.0
    out["vol_log"] = np.log1p(df["volume"].astype(float))
    out["spread"] = df["high"] - df["low"]
    out["body"] = df["close"] - df["open"]
    out["vwap_premium"] = df["vwap"] - df["close"]
    return out


stateless_features = [
    Field(name="hlc3", dtype=Float32),
    Field(name="ohlc4", dtype=Float32),
    Field(name="vol_log", dtype=Float32),
    Field(name="spread", dtype=Float32),
    Field(name="body", dtype=Float32),
    Field(name="vwap_premium", dtype=Float32),
]


derived_stateless_fv = OnDemandFeatureView(
    name="derived_stateless_fv",
    sources=[minute_ohlcv_fv],
    schema=stateless_features,
    udf=stateless_transforms,
)
