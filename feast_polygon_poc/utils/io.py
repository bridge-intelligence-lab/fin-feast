from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from feast_polygon_poc.logging import get_logger

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
    float_cols = ["open", "high", "low", "close", "vwap"]
    for c in float_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    return df


def partition_path(base: Path, symbol: str, ts: datetime) -> Path:
    date_str = ts.strftime("%Y-%m-%d")
    return base / f"symbol={symbol}" / f"date={date_str}"


def write_parquet_partitioned(base: Path, df: pd.DataFrame) -> None:
    """Write hive-partitioned Parquet and retain `symbol` column in files.

    Some downstream consumers (tests, historical joins) expect `symbol` to be present
    in the file schema in addition to the partition path.
    """
    ensure_columns(df)
    df = normalize_schema(df)
    for (symbol, date), g in df.groupby(["symbol", df["event_timestamp"].dt.date]):
        part_dir = partition_path(base, symbol, pd.Timestamp(date, tz="UTC").to_pydatetime())
        part_dir.mkdir(parents=True, exist_ok=True)
        file_path = part_dir / "data.parquet"
        g_sorted = g.sort_values("event_timestamp")
        if file_path.exists():
            existing = pd.read_parquet(file_path)
            combined = (
                pd.concat([existing, g_sorted], ignore_index=True)
                .drop_duplicates(subset=["event_timestamp"], keep="last")
                .sort_values("event_timestamp")
            )
            combined.to_parquet(file_path, index=False)
        else:
            g_sorted.to_parquet(file_path, index=False)
        logger.info("Wrote %d rows to %s", len(g_sorted), file_path)


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
