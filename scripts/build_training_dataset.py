from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

from fin_feast.features.pit import compare_pit, feast_pit, manual_pit
from fin_feast.utils.env import resolve_base_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build a point-in-time training dataset from the offline store."
    )
    p.add_argument("--zone", choices=["current", "experiment"], required=True)
    p.add_argument("--exp-id", default="")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--out", default="data/derived/training.parquet")
    p.add_argument(
        "--engine",
        choices=["feast", "manual"],
        default="feast",
        help="feast: Feast-native get_historical_features (default). "
        "manual: dependency-light pandas as-of join (the oracle).",
    )
    p.add_argument("--repo", default="feature_repo", help="Feast repo path (for --engine feast).")
    p.add_argument(
        "--freq",
        default="min",
        help="Entity-grid sampling frequency for the as-of timestamps (pandas offset alias).",
    )
    p.add_argument(
        "--verify",
        action="store_true",
        help="Run both engines and assert they agree bit-for-bit; exit non-zero on drift.",
    )
    return p.parse_args()


def build_entity_grid(symbols: list[str], start: str, end: str, freq: str) -> pd.DataFrame:
    """Cartesian grid of (symbol, event_timestamp) as-of query points."""
    idx = pd.date_range(pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC"), freq=freq, tz="UTC")
    syms = list(dict.fromkeys(symbols))
    entity_df = pd.DataFrame(
        [(s, ts) for s in syms for ts in idx], columns=["symbol", "event_timestamp"]
    )
    entity_df["event_timestamp"] = pd.to_datetime(entity_df["event_timestamp"], utc=True)
    return entity_df


def main() -> None:
    args = parse_args()

    # Keep Feast repo modules resolving the same zone/experiment as this run.
    os.environ.setdefault("FEAST_DATA_ZONE", args.zone)
    os.environ["FEAST_EXPERIMENT_ID"] = args.exp_id if args.zone == "experiment" else ""

    entity_df = build_entity_grid(args.symbols, args.start, args.end, args.freq)
    base = resolve_base_path(args.zone, args.exp_id or None)
    print(
        f"[TRAIN] zone={args.zone} exp_id={args.exp_id or '-'} engine={args.engine} "
        f"rows={len(entity_df)} window={args.start}..{args.end} base={base}"
    )

    if args.verify:
        summary = compare_pit(entity_df, base_path=base, repo_path=args.repo)
        print(f"[VERIFY] {summary}")
        if not summary["match"]:
            print("[VERIFY] FAIL: Feast-native PIT diverged from the manual oracle.", file=sys.stderr)
            sys.exit(1)
        print("[VERIFY] OK: Feast-native PIT matches the manual oracle bit-for-bit.")
        return

    if args.engine == "feast":
        df = feast_pit(entity_df, repo_path=args.repo)
    else:
        df = manual_pit(entity_df, base_path=base)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix == ".csv":
        df.to_csv(out_path, index=False)
    else:
        df.to_parquet(out_path, index=False)
    print(f"[TRAIN] wrote {out_path} ({len(df)} rows, {len(df.columns)} cols)")


if __name__ == "__main__":
    main()
