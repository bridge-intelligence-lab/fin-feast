from __future__ import annotations

import argparse
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
    # Ensure env is set consistently for experiment/current selection
    import os

    if os.getenv("FEAST_DATA_ZONE") is None:
        os.environ["FEAST_DATA_ZONE"] = args.zone
    if args.zone == "experiment":
        os.environ["FEAST_EXPERIMENT_ID"] = args.exp_id or os.getenv("FEAST_EXPERIMENT_ID", "")
    else:
        os.environ["FEAST_EXPERIMENT_ID"] = ""

    print(f"[TRAIN] Zone={args.zone} exp_id={args.exp_id}")

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
    # Normalize dtypes to align with Feast/Dask parquet (partition columns often categorical)
    syms = list(dict.fromkeys(args.symbols))
    entity_df["symbol"] = pd.Categorical(entity_df["symbol"], categories=syms)
    entity_df["event_timestamp"] = pd.to_datetime(entity_df["event_timestamp"], utc=True)
    print(
        f"[TRAIN] Entity grid rows={len(entity_df)} symbols={len(syms)} start={entity_df['event_timestamp'].min()} end={entity_df['event_timestamp'].max()}"
    )

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
    # Build features via manual point-in-time join from parquet to avoid engine-specific issues
    from fin_feast.utils.env import resolve_base_path

    base = resolve_base_path(args.zone, args.exp_id or None)
    daily_base = base / "daily"
    minute_base = base / "minute"
    print(f"[TRAIN] Base path resolved: {base}")
    rows = []
    # Read all features for requested symbols
    daily_rows = []
    minute_rows = []
    for sym in args.symbols:
        # Daily partitions
        for p in sorted((daily_base / f"symbol={sym}").glob("date=*/data.parquet")):
            part = pd.read_parquet(p)
            part["symbol"] = sym
            daily_rows.append(part)
        # Minute partitions
        for p in sorted((minute_base / f"symbol={sym}").glob("date=*/data.parquet")):
            part = pd.read_parquet(p)
            part["symbol"] = sym
            minute_rows.append(part)
    daily_df = pd.concat(daily_rows, ignore_index=True) if daily_rows else pd.DataFrame()
    minute_df = pd.concat(minute_rows, ignore_index=True) if minute_rows else pd.DataFrame()
    print(
        f"[TRAIN] Loaded daily parts: files={len(daily_rows)} rows={0 if daily_df.empty else len(daily_df)}; minute parts: files={len(minute_rows)} rows={0 if minute_df.empty else len(minute_df)}"
    )
    if not daily_df.empty:
        daily_df = daily_df.sort_values(["symbol", "event_timestamp"])  # keep order
    if not minute_df.empty:
        minute_df = minute_df.sort_values(["symbol", "event_timestamp"])  # keep order
    # Build per-entity PIT selection
    for _, ent in entity_df.reset_index(drop=True).iterrows():
        sym = ent["symbol"]
        v = pd.Timestamp(ent["event_timestamp"])  # may be naive or tz-aware
        if v.tzinfo is None:
            ts = v.tz_localize("UTC")
        else:
            ts = v.tz_convert("UTC")
        row = {"symbol": sym, "event_timestamp": ts}
        if not daily_df.empty:
            pool = daily_df[(daily_df["symbol"] == sym) & (daily_df["event_timestamp"] <= ts)]
            if not pool.empty:
                last = pool.iloc[-1]
                for col in [
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
                ]:
                    row[f"daily_ohlcv_fv__{col}"] = last.get(col)
        if not minute_df.empty:
            pool = minute_df[(minute_df["symbol"] == sym) & (minute_df["event_timestamp"] <= ts)]
            if not pool.empty:
                last = pool.iloc[-1]
                for col in [
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
                ]:
                    row[f"minute_ohlcv_fv__{col}"] = last.get(col)
        rows.append(row)
    hf = pd.DataFrame(rows)
    print(f"[TRAIN] Manual PIT join produced rows={len(hf)}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix == ".csv":
        hf.to_csv(out_path, index=False)
    else:
        hf.to_parquet(out_path, index=False)
    print(f"[TRAIN] Wrote training dataset: {out_path} ({len(hf)} rows)")


if __name__ == "__main__":
    main()
