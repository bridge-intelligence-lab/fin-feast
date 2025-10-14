from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from feast import FeatureStore


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--zone", choices=["current", "experiment"], required=True)
    p.add_argument("--exp-id", default="")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--out", default="data/derived/training.parquet")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    fs = FeatureStore(repo_path="feature_repo")

    # Build an entity dataframe of (symbol, event_timestamp) grid
    start = pd.Timestamp(args.start, tz="UTC")
    end = pd.Timestamp(args.end, tz="UTC")

    # For simplicity, use minute feature view for fine granularity; could be parameterized
    # We will sample at 1-minute frequency in the range
    idx = pd.date_range(start, end, freq="min", inclusive="both", tz="UTC")
    rows = []
    for sym in args.symbols:
        for ts in idx:
            rows.append({"symbol": sym, "event_timestamp": ts})
    entity_df = pd.DataFrame(rows)

    features = [
        "daily_ohlcv_fv:open",
        "daily_ohlcv_fv:high",
        "daily_ohlcv_fv:low",
        "daily_ohlcv_fv:close",
        "daily_ohlcv_fv:vwap",
        "daily_ohlcv_fv:volume",
        "daily_ohlcv_fv:return_1",
        "daily_ohlcv_fv:ma_5",
        "daily_ohlcv_fv:ma_20",
        "daily_ohlcv_fv:vol_20",
        "daily_ohlcv_fv:rsi_14",
        "daily_ohlcv_fv:atr_14",
        "minute_ohlcv_fv:open",
        "minute_ohlcv_fv:high",
        "minute_ohlcv_fv:low",
        "minute_ohlcv_fv:close",
        "minute_ohlcv_fv:vwap",
        "minute_ohlcv_fv:volume",
        "minute_ohlcv_fv:return_1",
        "minute_ohlcv_fv:ma_5",
        "minute_ohlcv_fv:ma_20",
        "minute_ohlcv_fv:vol_20",
        "minute_ohlcv_fv:rsi_14",
        "minute_ohlcv_fv:atr_14",
    ]

    print(f"[TRAIN] Entity DF rows={len(entity_df)}, features={len(features)}")
    print(f"[TRAIN] Time window: {start} to {end}")
    try:
        hf = fs.get_historical_features(
            entity_df=entity_df, features=features, full_feature_names=True
        ).to_df()
    except Exception as e:
        print(f"[TRAIN][ERROR] Historical features build failed: {e}")
        raise

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix == ".csv":
        hf.to_csv(out_path, index=False)
    else:
        hf.to_parquet(out_path, index=False)
    print(f"[TRAIN] Wrote training dataset: {out_path} ({len(hf)} rows)")


if __name__ == "__main__":
    main()
