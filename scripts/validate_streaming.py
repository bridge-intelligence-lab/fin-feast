import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Tuple

import pandas as pd
from feast import FeatureStore
from polygon import WebSocketClient

from fin_feast.logging import get_logger
from fin_feast.utils.env import resolve_base_path

logger = get_logger(__name__)

AGG_CHANNEL = "AM"  # Polygon minute aggregates


def _today_utc_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _partition_path(base: Path, symbol: str, freq: str, date_str: str) -> Path:
    return base / freq / f"symbol={symbol}" / f"date={date_str}" / "data.parquet"


def _read_partition_rows(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        df = pd.read_parquet(path)
        return len(df)
    except Exception as e:
        logger.warning("Failed reading %s: %s", path, e)
        return 0


def _file_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except Exception:
        return 0.0


def check_parquet_growth(
    zone: str, symbols: List[str], freq: str = "minute", poll_secs: int = 10
) -> Tuple[bool, Dict[str, Tuple[int, int, float, float]]]:
    base = resolve_base_path(zone, None)
    today = _today_utc_date()
    before_rows: Dict[str, int] = {}
    after_rows: Dict[str, int] = {}
    before_mtime: Dict[str, float] = {}
    after_mtime: Dict[str, float] = {}

    for sym in symbols:
        p = _partition_path(base, sym, freq, today)
        before_rows[sym] = _read_partition_rows(p)
        before_mtime[sym] = _file_mtime(p)
        logger.info(
            "Parquet before for %s: rows=%d mtime=%s (%s)",
            sym,
            before_rows[sym],
            before_mtime[sym],
            p,
        )

    time.sleep(poll_secs)

    for sym in symbols:
        p = _partition_path(base, sym, freq, today)
        after_rows[sym] = _read_partition_rows(p)
        after_mtime[sym] = _file_mtime(p)
        logger.info(
            "Parquet after for %s: rows=%d mtime=%s (%s)", sym, after_rows[sym], after_mtime[sym], p
        )

    grew = {
        sym: (before_rows[sym], after_rows[sym], before_mtime[sym], after_mtime[sym])
        for sym in symbols
    }
    ok = all(
        (after_rows[sym] > before_rows[sym]) or (after_mtime[sym] > before_mtime[sym])
        for sym in symbols
    )
    return ok, grew


class _WSCounter:
    def __init__(self, symbols: List[str]):
        self.symbols = set(symbols)
        self.counts: Dict[str, int] = {s: 0 for s in symbols}

    def handler(self, msg):
        # Polygon WS AM payloads may be list or dict depending on client
        events = msg if isinstance(msg, list) else [msg]
        for ev in events:
            sym = ev.get("sym") or ev.get("symbol")
            if not sym:
                continue
            if sym in self.counts:
                self.counts[sym] += 1


def check_ws_receive(
    symbols: List[str], timeout: int = 20, provider: str = "binance"
) -> Tuple[bool, Dict[str, int]]:
    counter = _WSCounter(symbols)

    if provider == "binance":
        # Simple binance WS check using websockets combined stream
        import websockets, json

        def to_binance(sym: str) -> str:
            return "btcusdt" if sym == "X:BTCUSD" else ("ethusdt" if sym == "C:ETHUSD" else "")

        streams = "/".join([f"{to_binance(s)}@kline_1m" for s in symbols])
        url = f"wss://stream.binance.com:9443/stream?streams={streams}"

        import threading
        import asyncio

        loop: asyncio.AbstractEventLoop | None = None

        async def runner():
            try:
                async for ws in websockets.connect(url, ping_interval=20, ping_timeout=20):  # type: ignore
                    try:
                        async for raw in ws:
                            try:
                                msg = json.loads(raw)
                            except Exception:
                                continue
                            data = msg.get("data", {})
                            k = data.get("k", {})
                            if not k:
                                continue
                            stream = msg.get("stream", "")
                            sym = None
                            if "btcusdt" in stream:
                                sym = "X:BTCUSD"
                            elif "ethusdt" in stream:
                                sym = "C:ETHUSD"
                            if sym:
                                counter.handler({"sym": sym})
                            if all(counter.counts[s] > 0 for s in symbols):
                                break
                    except Exception:
                        await asyncio.sleep(1)
                        continue
            except Exception as e:
                logger.error("Binance WS error: %s", e)

        def thread_main():
            nonlocal loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(runner())

        t = threading.Thread(target=thread_main, daemon=True)
        logger.info("Connecting to Binance WS for symbols: %s", symbols)
        t.start()

        start = time.time()
        while time.time() - start < timeout:
            if all(counter.counts[s] > 0 for s in symbols):
                break
            time.sleep(0.5)
        return all(counter.counts[s] > 0 for s in symbols), counter.counts

    # polygon branch
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        logger.error("POLYGON_API_KEY not set in environment")
        return False, {s: 0 for s in symbols}

    # In some versions, connect/close are async. We'll host an event loop in a background thread
    # and run the async connect there with our callback.
    ws = WebSocketClient(subscriptions=[f"{AGG_CHANNEL}.{s}" for s in symbols], api_key=api_key)

    import threading
    import asyncio

    stop_flag = {"stop": False}
    loop: asyncio.AbstractEventLoop | None = None

    def cb(msg):
        if stop_flag["stop"]:
            return
        counter.handler(msg)

    async def runner():
        try:
            await ws.connect(cb)
        except TypeError:
            # Fallback to sync connect if this version is sync
            ws.connect(cb)
        except Exception as e:
            logger.error("WS connect error: %s", e)

    def thread_main():
        nonlocal loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(runner())
        finally:
            try:
                loop.close()
            except Exception:
                pass

    logger.info("Connecting to Polygon WS for symbols: %s", symbols)
    t = threading.Thread(target=thread_main, daemon=True)
    t.start()

    start = time.time()
    try:
        while time.time() - start < timeout:
            if all(counter.counts[s] > 0 for s in symbols):
                break
            time.sleep(0.5)
    finally:
        stop_flag["stop"] = True
        try:
            if loop and hasattr(ws, "close"):
                coro = ws.close()
                if asyncio.iscoroutine(coro):
                    # Schedule close in the loop thread
                    assert loop is not None
                    fut = asyncio.run_coroutine_threadsafe(coro, loop)
                    try:
                        fut.result(timeout=2)
                    except Exception:
                        pass
                else:
                    ws.close()
        except Exception:
            pass
        t.join(timeout=2)

    ok = all(counter.counts[s] > 0 for s in symbols)
    return ok, counter.counts


def check_online_features(
    symbols: List[str], repo_path: str | None = None
) -> Tuple[bool, Dict[str, bool]]:
    if repo_path is None:
        # Resolve repo root relative to this file
        repo_path = str((Path(__file__).resolve().parents[1] / "feature_repo").resolve())
    store = FeatureStore(repo_path=repo_path)
    # Ensure registry load
    try:
        from feature_repo.feature_views import minute_ohlcv_fv  # type: ignore  # noqa: F401
    except Exception:
        pass

    entity_rows = [{"symbol": s} for s in symbols]
    fvs = [
        "minute_ohlcv_fv:open",
        "minute_ohlcv_fv:high",
        "minute_ohlcv_fv:low",
        "minute_ohlcv_fv:close",
        "minute_ohlcv_fv:volume",
    ]
    resp = store.get_online_features(features=fvs, entity_rows=entity_rows).to_dict()

    def get_val(feature_name: str, idx: int):
        # Support both key styles: "fv__field" and just "field"
        key1 = f"minute_ohlcv_fv__{feature_name}"
        key2 = feature_name
        if key1 in resp:
            return resp[key1][idx]
        if key2 in resp:
            return resp[key2][idx]
        return None

    ok_by_symbol: Dict[str, bool] = {}
    for i, sym in enumerate(symbols):
        has_open = get_val("open", i) is not None
        has_close = get_val("close", i) is not None
        ok_by_symbol[sym] = bool(has_open and has_close)
    ok = all(ok_by_symbol.values())
    return ok, ok_by_symbol


def parse_args():
    p = argparse.ArgumentParser(
        description="Validate streaming (Binance/Polygon), Parquet growth, and online store"
    )
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--zone", default="current", choices=["current", "experiment"], help="Data zone")
    p.add_argument("--ws-timeout", type=int, default=20, help="Seconds to wait for WS messages")
    p.add_argument("--poll-secs", type=int, default=10, help="Seconds between Parquet row polls")
    p.add_argument("--check-online", action="store_true", help="Validate online features in Redis")
    p.add_argument(
        "--provider",
        choices=["binance", "polygon"],
        default="binance",
        help="WS provider to validate",
    )
    p.add_argument(
        "--ws-optional",
        action="store_true",
        help="Do not fail validation if WS messages are not received; continue with parquet/online checks",
    )
    return p.parse_args()


def main():
    args = parse_args()

    overall_ok = True

    # 1) WebSocket reception
    ws_ok, counts = check_ws_receive(args.symbols, timeout=args.ws_timeout, provider=args.provider)
    if ws_ok:
        logger.info("WS OK. Message counts: %s", counts)
    else:
        if args.ws_optional:
            logger.warning("WS FAILED but continuing due to --ws-optional. Message counts: %s", counts)
        else:
            logger.error("WS FAILED. Message counts: %s", counts)
            overall_ok = False

    # 2) Parquet partition growth
    pq_ok, growth = check_parquet_growth(
        args.zone, args.symbols, freq="minute", poll_secs=args.poll_secs
    )
    if pq_ok:
        logger.info(
            "Parquet growth OK. before->after (rows_before, rows_after, mtime_before, mtime_after): %s",
            growth,
        )
    else:
        if args.ws_optional:
            logger.warning(
                "Parquet growth FAILED but continuing due to --ws-optional. before->after: %s",
                growth,
            )
        else:
            logger.error(
                "Parquet growth FAILED. before->after (rows_before, rows_after, mtime_before, mtime_after): %s",
                growth,
            )
            overall_ok = False

    # 3) Online check (optional)
    if args.check_online:
        try:
            on_ok, by_sym = check_online_features(args.symbols)
            if on_ok:
                logger.info("Online features OK: %s", by_sym)
            else:
                logger.error("Online features FAILED: %s", by_sym)
                overall_ok = False
        except Exception as e:
            logger.error("Online features check error: %s", e)
            overall_ok = False

    if overall_ok:
        logger.info("VALIDATION SUCCESS")
        sys.exit(0)
    else:
        logger.error("VALIDATION FAILED")
        sys.exit(2)


if __name__ == "__main__":
    main()
