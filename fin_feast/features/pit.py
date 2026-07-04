"""Point-in-time (PIT) feature retrieval.

Two implementations of the same as-of join, kept side by side on purpose:

- ``manual_pit``  : a dependency-light pandas join straight off the offline
  Parquet, used as a correctness *oracle*.
- ``feast_pit``   : Feast-native ``get_historical_features``.

Why keep both? Feast's file/dask offline store has two sharp edges that are
easy to hit and hard to notice:

1. **Feature-name collisions.** ``daily_ohlcv_fv`` and ``minute_ohlcv_fv`` share
   column names, so a single ``get_historical_features`` call must pass
   ``full_feature_names=True`` (columns come back as ``<view>__<feature>``).

2. **Silent row drops across TTLs.** If you request features from several views
   in one call and *any* view has no in-TTL row for a given entity/timestamp,
   the file/dask store drops the **entire** entity row, not just that view's
   columns. You lose the features that *were* available (e.g. the daily bar)
   with no error. The fix is to query each view separately and left-merge the
   results back onto the entity grid, which is what ``feast_pit`` does.

The parity between ``manual_pit`` and ``feast_pit`` on a valid window is asserted
by ``compare_pit`` and exercised in the tests, so the fast oracle guards the
Feast path against regressions.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import pandas as pd

from fin_feast.logging import get_logger

logger = get_logger(__name__)

# Precomputed feature columns shared by the daily and minute feature views.
FEATURE_COLS: tuple[str, ...] = (
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
)

# Map of Feast feature view name -> offline partition sub-directory.
VIEW_TO_FREQ: dict[str, str] = {
    "daily_ohlcv_fv": "daily",
    "minute_ohlcv_fv": "minute",
}

ENTITY_KEYS: tuple[str, str] = ("symbol", "event_timestamp")


def _normalize_entity_df(entity_df: pd.DataFrame) -> pd.DataFrame:
    ent = entity_df.copy()
    ent["symbol"] = ent["symbol"].astype(str)
    ent["event_timestamp"] = pd.to_datetime(ent["event_timestamp"], utc=True)
    return ent


def _load_partitions(base_path: Path, freq: str, symbols: Iterable[str]) -> pd.DataFrame:
    """Read every ``symbol=.../date=.../data.parquet`` partition for ``freq``."""
    frames: list[pd.DataFrame] = []
    for sym in symbols:
        for part_path in sorted((base_path / freq / f"symbol={sym}").glob("date=*/data.parquet")):
            part = pd.read_parquet(part_path)
            # ``symbol`` is a hive-partition column; force it back to a plain
            # string so downstream merges never hit object-vs-category mismatches.
            part["symbol"] = str(sym)
            frames.append(part)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"], utc=True)
    return df.sort_values(["symbol", "event_timestamp"]).reset_index(drop=True)


def manual_pit(
    entity_df: pd.DataFrame,
    base_path: str | Path,
    feature_cols: Sequence[str] = FEATURE_COLS,
    views: Sequence[str] = tuple(VIEW_TO_FREQ),
) -> pd.DataFrame:
    """As-of join computed directly from Parquet (the oracle).

    For each ``(symbol, event_timestamp)`` row, take the latest feature row with
    ``feature_timestamp <= event_timestamp``. No TTL is applied, so this returns
    every requested entity row (missing views come back as NaN columns).
    """
    ent = _normalize_entity_df(entity_df)
    symbols = list(dict.fromkeys(ent["symbol"].tolist()))
    sources = {v: _load_partitions(Path(base_path), VIEW_TO_FREQ[v], symbols) for v in views}

    records: list[dict] = []
    for _, row in ent.iterrows():
        rec: dict = {"symbol": row["symbol"], "event_timestamp": row["event_timestamp"]}
        for view, src in sources.items():
            if src.empty:
                continue
            pool = src[(src["symbol"] == row["symbol"]) & (src["event_timestamp"] <= row["event_timestamp"])]
            if not pool.empty:
                last = pool.iloc[-1]
                for col in feature_cols:
                    rec[f"{view}__{col}"] = last.get(col)
        records.append(rec)
    return pd.DataFrame(records).sort_values(list(ENTITY_KEYS)).reset_index(drop=True)


def feast_pit(
    entity_df: pd.DataFrame,
    repo_path: str | Path = "feature_repo",
    feature_cols: Sequence[str] = FEATURE_COLS,
    views: Sequence[str] = tuple(VIEW_TO_FREQ),
) -> pd.DataFrame:
    """Feast-native as-of join, hardened against the silent cross-TTL row drop.

    Each feature view is queried independently and left-merged onto the entity
    grid, so a TTL miss in one view can never evict rows (or other views'
    features) for that entity. Columns are returned as ``<view>__<feature>`` to
    match :func:`manual_pit`.
    """
    from feast import FeatureStore

    ent = _normalize_entity_df(entity_df)
    store = FeatureStore(repo_path=str(repo_path))

    result = ent[list(ENTITY_KEYS)].copy()
    for view in views:
        refs = [f"{view}:{col}" for col in feature_cols]
        view_df = store.get_historical_features(
            entity_df=ent, features=refs, full_feature_names=True
        ).to_df()
        view_df["symbol"] = view_df["symbol"].astype(str)
        view_df["event_timestamp"] = pd.to_datetime(view_df["event_timestamp"], utc=True)

        dropped = len(ent) - len(view_df)
        if dropped > 0:
            logger.warning(
                "feast_pit: view=%s dropped %d/%d as-of rows outside its TTL; "
                "restoring them via per-view merge (values NaN for this view only)",
                view,
                dropped,
                len(ent),
            )
        want = list(ENTITY_KEYS) + [f"{view}__{col}" for col in feature_cols]
        keep = [c for c in want if c in view_df.columns]
        result = result.merge(view_df[keep], on=list(ENTITY_KEYS), how="left")

    return result.sort_values(list(ENTITY_KEYS)).reset_index(drop=True)


def compare_pit(
    entity_df: pd.DataFrame,
    base_path: str | Path,
    repo_path: str | Path = "feature_repo",
    feature_cols: Sequence[str] = FEATURE_COLS,
) -> dict:
    """Run both engines on the same entity grid and diff them.

    Returns a summary dict with row counts, columns compared, the max absolute
    numeric difference, and any per-column mismatch counts. ``match`` is True
    only when row counts agree and every numeric cell is within tolerance
    (``rtol=atol=1e-9``).
    """
    import numpy as np

    man = manual_pit(entity_df, base_path, feature_cols)
    fe = feast_pit(entity_df, repo_path, feature_cols)

    cols = [c for c in man.columns if c not in ENTITY_KEYS and c in fe.columns]
    mismatches: dict[str, int] = {}
    max_abs_diff = 0.0
    for col in cols:
        a = pd.to_numeric(man[col], errors="coerce").to_numpy(dtype=float)
        b = pd.to_numeric(fe[col], errors="coerce").to_numpy(dtype=float)
        ok = np.isclose(a, b, rtol=1e-9, atol=1e-9, equal_nan=True)
        diff = np.abs(a - b)
        if np.isfinite(diff).any():
            max_abs_diff = max(max_abs_diff, float(np.nanmax(diff[np.isfinite(diff)])))
        if not ok.all():
            mismatches[col] = int((~ok).sum())

    return {
        "rows_manual": len(man),
        "rows_feast": len(fe),
        "cols": len(cols),
        "max_abs_diff": max_abs_diff,
        "mismatches": mismatches,
        "match": (not mismatches) and (len(man) == len(fe)),
    }
