from __future__ import annotations

import argparse
import asyncio
import os
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd
from feast import FeatureStore
from polygon import WebSocketClient

from fin_feast.features.rolling import add_indicators
from fin_feast.logging import get_logger
from fin_feast.utils.env import resolve_base_path
from fin_feast.utils.io import read_recent_bars, write_parquet_partitioned

logger = get_logger(__name__)

AGG_CHANNEL = "AM"  # Minute aggregates


class RollingState:
    def __init__(self, max_bars: int = 200):
        self.buffers: dict[str, deque[dict]] = {}
        self.max_bars = max_bars

    def warm_start(self, base: Path, symbols: list[str]) -> None:
        for sym in symbols:
            df = read_recent_bars(base, sym, self.max_bars)
            self.buffers[sym] = deque(df.to_dict("records"), maxlen=self.max_bars)

    def add_bar(self, bar: dict) -> pd.DataFrame:
        sym = bar["symbol"]
        if sym not in self.buffers:
            self.buffers[sym] = deque(maxlen=self.max_bars)
        self.buffers[sym].append(bar)
        return pd.DataFrame(list(self.buffers[sym]))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--zone", choices=["current"], default="current")
    p.add_argument("--push-online", action="store_true", help="Push latest to Redis via Feast")
    return p.parse_args()


async def main_async() -> None:
    args = parse_args()
    base = resolve_base_path("current", None) / "minute"
    base.mkdir(parents=True, exist_ok=True)

    state = RollingState()
    state.warm_start(base, args.symbols)
    seen_symbols = set()

    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        raise RuntimeError("POLYGON_API_KEY is required for streaming")

    fs: FeatureStore | None = None
    if args.push_online:
        fs = FeatureStore(repo_path=str(Path(__file__).resolve().parents[1] / "feature_repo"))

    ws = WebSocketClient(
        subscriptions=[f"{AGG_CHANNEL}.{s}" for s in args.symbols], api_key=api_key
    )

    def safe_push_online(fs_local: FeatureStore, latest_df: pd.DataFrame) -> None:
        symbol_str = "?"
        try:
            row = latest_df.iloc[0].to_dict()
            symbol_str = str(row.get("symbol", "?"))
            # Normalize NaNs and drop event_timestamp
            clean = {
                k: (None if (isinstance(v, float) and (np.isnan(v))) else v) for k, v in row.items()
            }
            clean.pop("event_timestamp", None)
            # Build payload restricted to FV features + entity
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
            assert "symbol" in clean, "symbol is required for online write"
            payload = {
                "symbol": clean["symbol"],
                **{k: clean.get(k) for k in fv_features if k in clean},
            }
            df_payload = pd.DataFrame([payload])
            fs_local.write_to_online_store(
                feature_view_name="minute_ohlcv_fv",
                df=df_payload,
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Online write failed for %s: %s", symbol_str, e)

    async def handle_msg(msgs: list[dict]) -> None:  # type: ignore[type-arg]
        for m in msgs:
            if m.get("ev") != AGG_CHANNEL:
                continue
            ts = pd.to_datetime(m.get("e") or m.get("t"), unit="ms", utc=True)
            sym = m.get("T") or m.get("sym") or m.get("symbol")
            if not sym:
                continue
            if sym not in seen_symbols:
                logger.info("Received first %s message for %s", AGG_CHANNEL, sym)
                seen_symbols.add(sym)
            bar = {
                "symbol": sym,
                "event_timestamp": ts,
                "open": float(m.get("o") or m.get("open")),
                "high": float(m.get("h") or m.get("high")),
                "low": float(m.get("l") or m.get("low")),
                "close": float(m.get("c") or m.get("close")),
                "vwap": float(m.get("vw") or m.get("vwap") or m.get("c") or m.get("close")),
                "volume": float(m.get("v") or m.get("volume", 0.0)),
            }
            df = state.add_bar(bar)
            df_ind = add_indicators(df)
            latest = df_ind.tail(1)
            # Write to Parquet for offline parity
            write_parquet_partitioned(base, latest)
            logger.info("Wrote latest bar to Parquet for %s at %s", sym, ts)
            # Optionally push to online store for immediate inference
            if fs is not None:
                safe_push_online(fs, latest)
                logger.info("Pushed latest bar to Redis for %s", sym)

    await ws.connect(handle_msg)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
