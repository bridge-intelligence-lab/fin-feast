from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd
import websockets

from fin_feast.features.rolling import add_indicators
from fin_feast.logging import get_logger
from fin_feast.utils.env import resolve_base_path
from fin_feast.utils.io import write_parquet_partitioned, read_recent_bars
from feast import FeatureStore
from fin_feast.online.push import push_rows_to_online

logger = get_logger(__name__)

BINANCE_WS = "wss://stream.binance.com:9443/stream?streams={streams}"
INTERVAL = "1m"


@dataclass
class SymbolMap:
    feast_symbol: str
    binance_symbol: str  # lowercase, e.g., btcusdt


def map_symbols(symbols: List[str]) -> List[SymbolMap]:
    out: List[SymbolMap] = []
    for s in symbols:
        if s == "X:BTCUSD":
            out.append(SymbolMap(s, "btcusdt"))
        elif s == "C:ETHUSD":
            out.append(SymbolMap(s, "ethusdt"))
        else:
            raise ValueError(f"Unsupported symbol for Binance mapping: {s}")
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Binance 1m kline streamer -> Parquet (+optional online)")
    p.add_argument("--symbols", nargs="+", required=True, help="Feast symbols, e.g., X:BTCUSD C:ETHUSD")
    p.add_argument("--zone", choices=["current"], default="current")
    p.add_argument("--push-online", action="store_true", help="Push latest to Redis via Feast")
    return p.parse_args()


async def stream_binance():
    args = parse_args()
    sym_maps = map_symbols(args.symbols)

    base = resolve_base_path(args.zone, None) / "minute"
    base.mkdir(parents=True, exist_ok=True)

    # Warm state by reading recent bars if present (for robust indicators)
    recent: Dict[str, pd.DataFrame] = {}
    for sm in sym_maps:
        try:
            df_prev = read_recent_bars(base, sm.feast_symbol, 200)
        except Exception:
            df_prev = pd.DataFrame()
        recent[sm.feast_symbol] = df_prev

    fs: FeatureStore | None = None
    if args.push_online:
        from pathlib import Path
        fs = FeatureStore(repo_path=str((Path(__file__).resolve().parents[1] / "feature_repo").resolve()))

    streams = "/".join([f"{sm.binance_symbol}@kline_{INTERVAL}" for sm in sym_maps])
    url = BINANCE_WS.format(streams=streams)
    logger.info("Connecting Binance combined WS: %s", url)

    async for ws in websockets.connect(url, ping_interval=20, ping_timeout=20):  # type: ignore
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                ev = msg.get("data", {})
                k = ev.get("k", {})
                if not k:
                    continue
                # Only process when k["x"] (bar closed) or process live? We'll process both, but write on close for idempotence
                feast_symbol = None
                stream = msg.get("stream", "")
                for sm in sym_maps:
                    if sm.binance_symbol in stream:
                        feast_symbol = sm.feast_symbol
                        break
                if not feast_symbol:
                    continue

                ts = pd.to_datetime(k.get("t"), unit="ms", utc=True)  # start time
                bar = {
                    "symbol": feast_symbol,
                    "event_timestamp": ts,
                    "open": float(k.get("o")),
                    "high": float(k.get("h")),
                    "low": float(k.get("l")),
                    "close": float(k.get("c")),
                    "volume": float(k.get("v")),
                }
                # Accumulate with any previous to compute indicators
                df_prev = recent.get(feast_symbol, pd.DataFrame())
                df_new = pd.concat([df_prev, pd.DataFrame([bar])], ignore_index=True)
                df_new = df_new.sort_values("event_timestamp").drop_duplicates(["symbol", "event_timestamp"], keep="last")
                df_new = df_new.tail(200)  # keep window
                recent[feast_symbol] = df_new

                df_ind = add_indicators(df_new)
                latest = df_ind.tail(1)

                write_parquet_partitioned(base, latest)
                logger.info("Wrote latest kline to Parquet for %s at %s", feast_symbol, ts)

                if fs is not None:
                    # Fallback 1: direct write using older Feast signature known to work on this env
                    try:
                        row = latest.iloc[0].to_dict()
                        values = {k: (None if (isinstance(v, float) and (np.isnan(v))) else v) for k, v in row.items()}
                        fs.write_to_online_store(table="minute_ohlcv_fv", values=values)
                        logger.info("Pushed latest bar to Redis for %s via direct write", feast_symbol)
                    except Exception as e:
                        logger.error("Direct online write failed: %s", e)
                        # Fallback 2: materialize incremental
                        try:
                            fs.materialize_incremental(pd.Timestamp.utcnow())
                            logger.info("Materialized incremental to online for latest data")
                        except Exception as e2:
                            logger.error("Online materialize failed: %s", e2)
        except Exception as e:
            logger.warning("WS error/reconnect: %s", e)
            await asyncio.sleep(2)
            continue


def main() -> None:
    asyncio.run(stream_binance())


if __name__ == "__main__":
    main()
