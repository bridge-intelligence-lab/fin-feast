from __future__ import annotations

import argparse

import pandas as pd
from polygon import RESTClient
from tenacity import retry, stop_after_attempt, wait_exponential

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
    p.add_argument("--adjusted", default="true")
    p.add_argument("--push-latest", action="store_true")
    p.add_argument(
        "--symbols-delay-secs",
        type=float,
        default=1.0,
        help="Sleep seconds between symbol requests to avoid 429s on free tier",
    )
    return p.parse_args()


@retry(wait=wait_exponential(multiplier=1, min=1, max=30), stop=stop_after_attempt(5))
def fetch_aggregates(
    client: RESTClient, ticker: str, start: str, end: str, timespan: str
) -> pd.DataFrame:
    """Fetch aggregates and normalize to a DataFrame.

    Supports the following response shapes:
    - list/tuple of dicts or Agg-like objects
    - object with attribute `.results`
    - HTTPResponse-like with `.data` or `.json()` returning a dict containing `results`.
    """
    # Call client.get_aggs with minimal, broadly compatible signature. Some mocks
    # or older SDKs don't accept `adjusted` kwarg, so we avoid it here.
    resp = client.get_aggs(
        ticker=ticker,
        multiplier=1,
        timespan=timespan,
        from_=start,
        to=end,
    )

    # Normalize to an iterable of row-like objects
    data_iter = None
    if isinstance(resp, list | tuple):
        data_iter = resp
    else:
        # Try .results first (used by tests), then .data / .json()
        results_attr = getattr(resp, "results", None)
        if results_attr is not None:
            data_iter = results_attr
        else:
            payload = getattr(resp, "data", None)
            if payload is None:
                try:
                    payload = resp.json()  # type: ignore[attr-defined]
                except Exception:
                    payload = None
            if isinstance(payload, dict):
                data_iter = payload.get("results") or []
            elif isinstance(payload, list | tuple):
                data_iter = payload

    if not data_iter:
        return pd.DataFrame(
            columns=["event_timestamp", "open", "high", "low", "close", "vwap", "volume"]
        )

    rows = []
    for r in data_iter:
        # r may be a dict-like or Agg object with attributes
        if isinstance(r, dict):
            tval = r.get("t") or r.get("timestamp")
            o = r.get("o") if r.get("o") is not None else r.get("open")
            h = r.get("h") if r.get("h") is not None else r.get("high")
            low = r.get("l") if r.get("l") is not None else r.get("low")
            c = r.get("c") if r.get("c") is not None else r.get("close")
            vw = r.get("vw") if r.get("vw") is not None else r.get("vwap")
            v = r.get("v", 0.0) if r.get("v") is not None else r.get("volume", 0.0)
        else:
            tval = getattr(r, "t", None) or getattr(r, "timestamp", None)
            o = getattr(r, "o", None) or getattr(r, "open", None)
            h = getattr(r, "h", None) or getattr(r, "high", None)
            low = getattr(r, "l", None) or getattr(r, "low", None)
            c = getattr(r, "c", None) or getattr(r, "close", None)
            vw = getattr(r, "vw", None) or getattr(r, "vwap", None)
            v = getattr(r, "v", 0.0) or getattr(r, "volume", 0.0)
        if tval is None:
            continue
        # Detect seconds vs milliseconds
        try:
            tval_int = int(tval)
        except Exception:
            ts = pd.to_datetime(tval, utc=True)
        else:
            TS_THRESHOLD_S = 10_000_000_000
            unit = "s" if tval_int < TS_THRESHOLD_S else "ms"
            ts = pd.to_datetime(tval_int, unit=unit, utc=True)
        c = 0.0 if c is None else c
        vw = c if vw is None else vw
        rows.append(
            {
                "event_timestamp": ts,
                "open": float(o),
                "high": float(h),
                "low": float(low),
                "close": float(c),
                "vwap": float(vw),
                "volume": float(v),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    zone: Zone = args.zone  # type: ignore[assignment]
    base = resolve_base_path(zone, args.exp_id or None) / args.freq
    base.mkdir(parents=True, exist_ok=True)

    client = RESTClient()

    # Map Feast symbols to Polygon tickers where needed
    from fin_feast.utils.symbols import to_polygon_ticker

    for i, sym in enumerate(args.symbols):
        ticker = to_polygon_ticker(sym)
        ts_df = fetch_aggregates(
            client,
            ticker=ticker,
            start=args.start,
            end=args.end,
            timespan="day" if args.freq == "daily" else "minute",
        )
        if ts_df.empty:
            logger.warning("No data for %s", sym)
        else:
            ts_df.insert(0, "symbol", sym)
            ts_df["event_timestamp"] = pd.to_datetime(ts_df["event_timestamp"], utc=True)
            ts_df = add_indicators(ts_df)
            write_parquet_partitioned(base, ts_df)
        # Throttle between symbols to avoid free-tier 429s
        if i < len(args.symbols) - 1:
            import time as _time

            _time.sleep(float(args.symbols_delay_secs))

    logger.info("Polygon data fetched for %s in %s", args.symbols, base)


if __name__ == "__main__":
    main()
