from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pandas as pd
from polygon import RESTClient
from tenacity import retry, stop_after_attempt, wait_exponential

from fin_feast.features.rolling import add_indicators
from fin_feast.logging import get_logger
from fin_feast.utils.env import resolve_base_path
from fin_feast.utils.env import Zone
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
    p.add_argument("--adjusted", default="true")
    p.add_argument("--push-latest", action="store_true")
    return p.parse_args()


@retry(wait=wait_exponential(multiplier=1, min=1, max=30), stop=stop_after_attempt(5))
def fetch_aggregates(
    client: RESTClient, ticker: str, start: str, end: str, timespan: str
) -> pd.DataFrame:
    # Polygon format differs for crypto (X:) and forex (C:)
    # polygon-api-client returns Aggregate objects; we convert to DataFrame
    results = client.get_aggs(ticker=ticker, multiplier=1, timespan=timespan, from_=start, to=end)
    if not results or not results.results:
        return pd.DataFrame(columns=["ts", "o", "h", "l", "c", "v"])
    rows = []
    for r in results.results:
        ts = pd.to_datetime(r["t"], unit="ms", utc=True)
        rows.append(
            {
                "event_timestamp": ts,
                "open": float(r["o"]),
                "high": float(r["h"]),
                "low": float(r["l"]),
                "close": float(r["c"]),
                "vwap": float(r.get("vw", r["c"])),
                "volume": float(r["v"]),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    zone: Zone = args.zone  # type: ignore[assignment]
    base = resolve_base_path(zone, args.exp_id or None) / args.freq
    base.mkdir(parents=True, exist_ok=True)

    client = RESTClient()

    for sym in args.symbols:
        ts_df = fetch_aggregates(
            client,
            ticker=sym,
            start=args.start,
            end=args.end,
            timespan="day" if args.freq == "daily" else "minute",
        )
        if ts_df.empty:
            logger.warning("No data for %s", sym)
            continue
        ts_df.insert(0, "symbol", sym)
        ts_df["event_timestamp"] = pd.to_datetime(ts_df["event_timestamp"], utc=True)
        ts_df = add_indicators(ts_df)
        write_parquet_partitioned(base, ts_df)

    logger.info("Polygon data fetched for %s in %s", args.symbols, base)


if __name__ == "__main__":
    main()
