from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, List

import pandas as pd
import requests

from fin_feast.features.rolling import add_indicators
from fin_feast.logging import get_logger
from fin_feast.utils.env import resolve_base_path, Zone
from fin_feast.utils.io import write_parquet_partitioned
from fin_feast.utils.symbols import to_binance_symbol

logger = get_logger(__name__)

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"

INTERVALS = {
    "daily": "1d",
    "minute": "1m",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch Binance klines -> Parquet")
    p.add_argument("--zone", choices=["current", "experiment"], required=True)
    p.add_argument("--exp-id", default="")
    p.add_argument("--start", required=True, help="ISO timestamp/date")
    p.add_argument("--end", required=True, help="ISO timestamp/date")
    p.add_argument("--freq", choices=["daily", "minute"], required=True)
    p.add_argument(
        "--symbols", nargs="+", required=True, help="Feast symbols, e.g., X:BTCUSD C:ETHUSD"
    )
    return p.parse_args()


def _chunks(start: datetime, end: datetime, freq: str) -> Iterator[tuple[datetime, datetime]]:
    # Binance returns up to 1000 klines per request; chunk by approx window lengths
    if freq == "minute":
        step = timedelta(days=1)  # 1440 klines/day
    else:
        step = timedelta(days=1000)  # safe upper bound for 1d
    cur = start
    while cur <= end:
        nxt = min(end, cur + step)
        yield cur, nxt
        cur = nxt + (timedelta(seconds=0) if freq == "daily" else timedelta(minutes=0))


def _fetch_klines(symbol: str, interval: str, start: datetime, end: datetime) -> pd.DataFrame:
    params = {
        "symbol": symbol.upper(),
        "interval": interval,
        "startTime": int(start.timestamp() * 1000),
        "endTime": int(end.timestamp() * 1000),
        "limit": 1000,
    }
    resp = requests.get(BINANCE_KLINES, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return pd.DataFrame(columns=["event_timestamp", "open", "high", "low", "close", "volume"])
    rows = []
    for k in data:
        # Kline array indices: open time, open, high, low, close, volume, close time, ...
        ts = pd.to_datetime(k[0], unit="ms", utc=True)
        rows.append(
            {
                "event_timestamp": ts,
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    zone: Zone = args.zone  # type: ignore[assignment]
    base = resolve_base_path(zone, args.exp_id or None) / args.freq
    base.mkdir(parents=True, exist_ok=True)

    start = pd.to_datetime(args.start, utc=True)
    end = pd.to_datetime(args.end, utc=True)

    interval = INTERVALS[args.freq]

    for feast_sym in args.symbols:
        binance_sym = to_binance_symbol(feast_sym).upper()
        all_rows: List[pd.DataFrame] = []
        for s, e in _chunks(start.to_pydatetime(), end.to_pydatetime(), args.freq):
            df = _fetch_klines(binance_sym, interval, s, e)
            if df.empty:
                continue
            all_rows.append(df)
        if not all_rows:
            logger.warning("No data for %s", feast_sym)
            continue
        ts_df = pd.concat(all_rows, ignore_index=True).sort_values("event_timestamp")
        ts_df.insert(0, "symbol", feast_sym)
        ts_df["vwap"] = (ts_df["high"] + ts_df["low"] + ts_df["close"]) / 3.0
        ts_df = add_indicators(ts_df)
        write_parquet_partitioned(base, ts_df)
        logger.info("Binance data fetched for %s in %s", feast_sym, base)


if __name__ == "__main__":
    main()
