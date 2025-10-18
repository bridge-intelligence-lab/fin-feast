from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

import pandas as pd

from fin_feast.logging import get_logger

logger = get_logger(__name__)


REQUIRED_COLUMNS = [
    "symbol",
    "event_timestamp",
    "open",
    "high",
    "low",
    "close",
    "vwap",
    "volume",
]


def ensure_columns(df: pd.DataFrame, required: Iterable[str] = REQUIRED_COLUMNS) -> pd.DataFrame:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return df


def normalize_schema(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["symbol"] = df["symbol"].astype(str)
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"], utc=True)
    float_cols = ["open", "high", "low", "close", "vwap", "volume"]
    for c in float_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    # Cast known indicator columns to float if present
    for c in ["return_1", "ma_5", "ma_20", "vol_20", "rsi_14", "atr_14"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    return df


def partition_path(base: Path, symbol: str, ts: datetime) -> Path:
    date_str = ts.strftime("%Y-%m-%d")
    return base / f"symbol={symbol}" / f"date={date_str}"


def write_parquet_partitioned(base: Path, df: pd.DataFrame) -> list[Path]:
    """Write hive-partitioned Parquet and retain partition columns in files.

    Dask requires that if any partition column is present inside the file, then
    all partition columns must be present. We therefore retain both `symbol` and
    `date` in the file schema in addition to the partition path.

    Concurrent safety: best-effort per-file lock using a sibling `.lock` file
    combined with atomic temp+rename writes.
    """
    ensure_columns(df)
    df = normalize_schema(df)
    # Add date column derived from event_timestamp for in-file partition columns
    df = df.copy()
    df["date"] = df["event_timestamp"].dt.strftime("%Y-%m-%d")

    written: list[Path] = []
    # Group by computed date to avoid inconsistencies
    for (symbol, date_str), g in df.groupby(["symbol", "date"], sort=False):
        # date_str is YYYY-MM-DD
        part_dir = partition_path(base, symbol, pd.Timestamp(date_str, tz="UTC").to_pydatetime())
        part_dir.mkdir(parents=True, exist_ok=True)
        file_path = part_dir / "data.parquet"
        g_sorted = g.sort_values("event_timestamp")
        # Write atomically with a simple lock: write to temp file then rename
        lock_path = file_path.with_suffix(".parquet.lock")
        tmp_path = file_path.with_suffix(".parquet.tmp")
        try:
            # Acquire lock
            while True:
                try:
                    with lock_path.open("x"):
                        pass
                    break
                except FileExistsError:
                    # Busy-wait briefly; for a more robust approach consider timeouts/backoff
                    import time

                    time.sleep(0.05)
            if file_path.exists():
                existing = pd.read_parquet(file_path)
                combined = (
                    pd.concat([existing, g_sorted], ignore_index=True)
                    .drop_duplicates(subset=["event_timestamp"], keep="last")
                    .sort_values("event_timestamp")
                )
                combined.to_parquet(tmp_path, index=False)
            else:
                g_sorted.to_parquet(tmp_path, index=False)
            tmp_path.replace(file_path)  # atomic on same filesystem
            written.append(file_path)
        finally:
            from contextlib import suppress

            with suppress(Exception):
                lock_path.unlink(missing_ok=True)
        logger.info("Wrote %d rows to %s", len(g_sorted), file_path)
    return written


def read_recent_bars(base: Path, symbol: str, n: int) -> pd.DataFrame:
    """Read last n rows for warm-start of rolling indicators.

    Files do not contain `symbol`, so we inject it from the partition path.
    """
    sym_dir = base / f"symbol={symbol}"
    if not sym_dir.exists():
        return pd.DataFrame(columns=[c for c in REQUIRED_COLUMNS if c != "symbol"])  # empty
    parts = sorted(sym_dir.glob("date=*/data.parquet"))
    if not parts:
        return pd.DataFrame(columns=[c for c in REQUIRED_COLUMNS if c != "symbol"])  # empty
    dfs = []
    for p in parts[-10:]:  # last 10 partitions should be enough to cover n
        try:
            df = pd.read_parquet(p)
            df.insert(0, "symbol", symbol)
            dfs.append(df)
        except Exception:  # noqa: BLE001
            continue
    if not dfs:
        return pd.DataFrame(columns=[c for c in REQUIRED_COLUMNS if c != "symbol"])  # empty
    df_all = pd.concat(dfs, ignore_index=True).sort_values("event_timestamp")
    return df_all.tail(n)
