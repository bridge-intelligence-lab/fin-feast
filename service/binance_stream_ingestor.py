from __future__ import annotations

import argparse
import asyncio
import json

import pandas as pd
import websockets
from feast import FeatureStore

from fin_feast.features.rolling import add_indicators
from fin_feast.logging import get_logger
from fin_feast.utils.env import resolve_base_path
from fin_feast.utils.io import read_recent_bars, write_parquet_partitioned
from fin_feast.utils.symbols import SymbolMap, to_binance_symbol

logger = get_logger(__name__)

BINANCE_WS = "wss://stream.binance.com:9443/stream?streams={streams}"
INTERVAL = "1m"


def map_symbols(symbols: list[str]) -> list[SymbolMap]:
    out: list[SymbolMap] = []
    for s in symbols:
        out.append(SymbolMap(s, to_binance_symbol(s)))
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Binance 1m kline streamer -> Parquet (+optional online)"
    )
    p.add_argument(
        "--symbols", nargs="+", required=True, help="Feast symbols, e.g., X:BTCUSD C:ETHUSD"
    )
    p.add_argument("--zone", choices=["current"], default="current")
    p.add_argument("--push-online", action="store_true", help="Push latest to Redis via Feast")
    return p.parse_args()


async def stream_binance():  # noqa: PLR0912, PLR0915
    args = parse_args()
    sym_maps = map_symbols(args.symbols)

    base = resolve_base_path(args.zone, None) / "minute"
    base.mkdir(parents=True, exist_ok=True)

    # Warm state by reading recent bars if present (for robust indicators)
    recent: dict[str, pd.DataFrame] = {}
    for sm in sym_maps:
        try:
            df_prev = read_recent_bars(base, sm.feast_symbol, 200)
        except Exception:
            df_prev = pd.DataFrame()
        recent[sm.feast_symbol] = df_prev

    fs: FeatureStore | None = None
    if args.push_online:
        from pathlib import Path

        fs = FeatureStore(
            repo_path=str((Path(__file__).resolve().parents[1] / "feature_repo").resolve())
        )

    streams = "/".join([f"{sm.binance_symbol}@kline_{INTERVAL}" for sm in sym_maps])
    url = BINANCE_WS.format(streams=streams)
    logger.info("Connecting Binance combined WS: %s", url)

    attempt = 0
    async for ws in websockets.connect(url, ping_interval=20, ping_timeout=20):  # type: ignore
        try:
            attempt = 0  # reset on successful connect
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
                df_new = df_new.sort_values("event_timestamp").drop_duplicates(
                    ["symbol", "event_timestamp"], keep="last"
                )
                df_new = df_new.tail(200)  # keep window
                recent[feast_symbol] = df_new

                df_ind = add_indicators(df_new)
                latest = df_ind.tail(1)

                write_parquet_partitioned(base, latest)
                logger.info("Wrote latest kline to Parquet for %s at %s", feast_symbol, ts)

                if fs is not None:
                    # Push latest row to online store using current Feast signature
                    row = latest.iloc[0].to_dict()
                    # Normalize NaNs to None
                    clean = {
                        k: (None if (isinstance(v, float) and (pd.isna(v))) else v)
                        for k, v in row.items()
                    }
                    # Drop event_timestamp; online store doesn't require it
                    clean.pop("event_timestamp", None)
                    # Ensure entity is present
                    assert "symbol" in clean, "symbol is required for online write"
                    # Keep only FV-defined features plus entity
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
                    payload = {
                        "symbol": clean["symbol"],
                        **{k: clean.get(k) for k in fv_features if k in clean},
                    }
                    df_payload = pd.DataFrame([payload])
                    try:
                        fs.write_to_online_store(
                            feature_view_name="minute_ohlcv_fv",
                            df=df_payload,
                        )
                        logger.info(
                            "Pushed latest bar to Redis for %s via write_to_online_store",
                            feast_symbol,
                        )
                    except Exception as e:
                        # Log but do not break streaming loop
                        logger.error("Online write failed for %s: %s", feast_symbol, e)
        except Exception as e:
            # Exponential backoff with jitter
            attempt += 1
            import random

            delay = min(30, (2 ** min(attempt, 8)))  # cap growth
            jitter = random.uniform(-0.2, 0.2) * delay
            wait = max(1, delay + jitter)
            logger.warning("WS error/reconnect (attempt=%d wait=%.2fs): %s", attempt, wait, e)
            await asyncio.sleep(wait)
            continue


def main() -> None:
    asyncio.run(stream_binance())


if __name__ == "__main__":
    main()
