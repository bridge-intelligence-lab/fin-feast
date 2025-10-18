# Feature Catalog

This document describes all features exposed by this project, their definitions, and how they are computed.

## Entities
- symbol: string key identifying an instrument

## Base columns (from Parquet)
- open, high, low, close: float
- vwap: float (volume-weighted average price if available; fallback to close)
- volume: float
- event_timestamp: UTC timestamp (partitioned by symbol/date)

## Precomputed indicators (offline)
These are computed in the ingestion scripts and written to Parquet to ensure offline-online parity.

- return_1
  - Definition: close / lag(close, 1) - 1 (per symbol)
- ma_5, ma_20
  - Definition: rolling mean of close over 5 and 20 bars
- vol_20
  - Definition: rolling standard deviation of close over 20 bars (ddof=0)
- rsi_14
  - Definition: 100 - 100 / (1 + RS), with RS = mean(up, 14) / mean(down, 14)
- atr_14
  - Definition: rolling mean of True Range over 14 bars; True Range = max(high-low, |high-prev_close|, |low-prev_close|)

Notes:
- Rolling windows are in bars; same defaults for daily and minute.
- Leading rows carry NaN until windows are warmed up; these NaNs will also be present online (first few bars).

## On-demand stateless features (ODFV)
These are derived at request time from already-materialized base columns.

- hlc3 = (high + low + close) / 3
- ohlc4 = (open + high + low + close) / 4
- vol_log = log1p(volume)
- spread = high - low
- body = close - open
- vwap_premium = vwap - close

ODFV source: minute_ohlcv_fv only (to avoid column collisions).

## Feature views
- daily_ohlcv_fv (TTL ~400 days)
- minute_ohlcv_fv (TTL ~14 days)
- derived_stateless_fv (OnDemand, stateless transforms on minute features)

## Offline-online parity
- All stateful indicators are precomputed offline to ensure the same values appear in the online store when materialized or pushed. ODFV remains lightweight and stateless.
