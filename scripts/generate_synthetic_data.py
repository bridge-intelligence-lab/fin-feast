from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from fin_feast.features.rolling import add_indicators
from fin_feast.logging import get_logger
from fin_feast.utils.env import Zone, resolve_base_path
from fin_feast.utils.io import write_parquet_partitioned

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--zone", choices=["current", "experiment"], required=True)
    p.add_argument("--exp-id", default="")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--freq", choices=["daily", "minute"], required=True)
    p.add_argument("--symbols", nargs="+", required=True)
    return p.parse_args()


def daterange(start: datetime, end: datetime, freq: str) -> list[datetime]:
    if freq == "daily":
        step = timedelta(days=1)
    else:
        step = timedelta(minutes=1)
    out = []
    cur = start
    while cur <= end:
        out.append(cur)
        cur += step
    return out


def synthetic_series(start_price: float, n: int, vol: float = 0.02) -> np.ndarray:
    rng = np.random.default_rng(42)
    rets = rng.normal(0, vol, size=n)
    prices = [start_price]
    for r in rets:
        prices.append(max(0.0001, prices[-1] * (1 + r)))
    return np.array(prices[1:])


def gen_bars(symbol: str, ts_list: list[datetime], start_price: float) -> pd.DataFrame:
    close = synthetic_series(
        start_price, len(ts_list), vol=0.001 if (ts_list[1] - ts_list[0]).seconds < 3600 else 0.02
    )
    df = pd.DataFrame(
        {
            "symbol": symbol,
            "event_timestamp": pd.to_datetime(ts_list, utc=True),
            "close": close,
        }
    )
    df["open"] = df["close"].shift(1).fillna(df["close"]) * (
        1 + np.random.normal(0, 0.0005, len(df))
    )
    hl_spread = np.abs(np.random.normal(0.001, 0.0005, len(df))) * df["close"]
    df["high"] = df[["open", "close"]].max(axis=1) + hl_spread
    df["low"] = df[["open", "close"]].min(axis=1) - hl_spread
    df["volume"] = np.random.lognormal(mean=10, sigma=0.5, size=len(df))
    df["vwap"] = (df["high"] + df["low"] + df["close"]) / 3.0
    return df


def main() -> None:
    args = parse_args()
    zone: Zone = args.zone  # type: ignore[assignment]
    base = resolve_base_path(zone, args.exp_id or None) / args.freq
    base.mkdir(parents=True, exist_ok=True)

    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)

    for sym in args.symbols:
        ts_list = daterange(start, end, args.freq)
        start_price = 30000.0 if "BTC" in sym else 1.25
        df = gen_bars(sym, ts_list, start_price)
        df = add_indicators(df)
        write_parquet_partitioned(base, df)

    logger.info("Synthetic data generated for %s in %s", args.symbols, base)


if __name__ == "__main__":
    main()
