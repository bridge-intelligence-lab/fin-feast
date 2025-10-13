from __future__ import annotations

import argparse
import asyncio
import os
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List

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
        self.buffers: Dict[str, Deque[dict]] = {}
        self.max_bars = max_bars

    def warm_start(self, base: Path, symbols: List[str]) -> None:
        for sym in symbols:
            df = read_recent_bars(base, sym, self.max_bars)
            self.buffers[sym] = deque(df.to_dict("records"), maxlen=self.max_bars)

    def add_bar(self, bar: dict) -> pd.DataFrame:
        sym = bar["symbol"]
        if sym not in self.buffers:
            self.buffers[sym] = deque(maxlen=self.max_bars)
        self.buffers[sym].append(bar)
        df = pd.DataFrame(list(self.buffers[sym]))
        return df


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

    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        raise RuntimeError("POLYGON_API_KEY is required for streaming")

    fs: FeatureStore | None = None
    if args.push_online:
        fs = FeatureStore(repo_path=str(Path(__file__).resolve().parents[1] / "feature_repo"))

    ws = WebSocketClient(subscriptions=[f"{AGG_CHANNEL}.{s}" for s in args.symbols], api_key=api_key)

    async def handle_msg(msgs: List[dict]) -> None:  # type: ignore[type-arg]
        for m in msgs:
            if m.get("ev") != AGG_CHANNEL:
                continue
            ts = pd.to_datetime(m["e"], unit="ms", utc=True)
            sym = m["T"]
            bar = {
                "symbol": sym,
                "event_timestamp": ts,
                "open": float(m["o"]),
                "high": float(m["h"]),
                "low": float(m["l"]),
                "close": float(m["c"]),
                "vwap": float(m.get("vw", m["c"])),
                "volume": float(m["v"]),
            }
            df = state.add_bar(bar)
            df_ind = add_indicators(df)
            latest = df_ind.tail(1)
            # Write to Parquet for offline parity
            write_parquet_partitioned(base, latest)
            logger.info("Wrote latest bar to Parquet for %s at %s", sym, ts)
            # Optionally push to online store for immediate inference
            if fs is not None:
                row = latest.iloc[0].to_dict()
                fs.write_to_online_store(
                    table="minute_ohlcv_fv",
                    values={
                        "symbol": row.pop("symbol"),
                        **{k: (None if (isinstance(v, float) and (np.isnan(v))) else v) for k, v in row.items()},
                    },
                )
                logger.info("Pushed latest bar to Redis for %s", sym)

    await ws.connect(handle_msg)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
