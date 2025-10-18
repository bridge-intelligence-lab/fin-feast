from __future__ import annotations

import argparse
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from feast import FeatureStore

from fin_feast.logging import get_logger

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply repo and materialize to online store")
    p.add_argument("--zone", choices=["current", "experiment"], default="current")
    p.add_argument("--exp-id", default="", help="Experiment ID when zone=experiment")
    return p.parse_args()


def _ensure_partition_columns(project_root: Path) -> None:
    """Ensure both partition columns ('symbol','date') exist in parquet files.

    Dask requires that if any partition column is written inside the file, all
    partition columns must be present. This rewrites files under current/daily
    and current/minute to include both.
    """
    import pandas as pd

    bases = [
        project_root / "data" / "offline" / "current" / "minute",
        project_root / "data" / "offline" / "current" / "daily",
    ]
    for base in bases:
        if not base.exists():
            continue
        for p in base.glob("symbol=*/date=*/data.parquet"):
            try:
                # Extract partition values
                date = p.parent.name.split("=", 1)[1]
                sym = p.parent.parent.name.split("=", 1)[1]
                df = pd.read_parquet(p)
                changed = False
                if "symbol" not in df.columns:
                    df.insert(0, "symbol", sym)
                    changed = True
                if "date" not in df.columns:
                    df.insert(1, "date", date)
                    changed = True
                if changed:
                    df.to_parquet(p, index=False)
            except Exception:
                continue


def main() -> None:
    args = parse_args()

    # Force environment for this run (affects FeatureStore in-process)
    os.environ["FEAST_DATA_ZONE"] = args.zone
    if args.zone == "experiment":
        os.environ["FEAST_EXPERIMENT_ID"] = args.exp_id or os.environ.get("FEAST_EXPERIMENT_ID", "")
    else:
        os.environ["FEAST_EXPERIMENT_ID"] = ""

    logger.info("Running feast apply via CLI...")
    repo_dir = Path(__file__).resolve().parents[1] / "feature_repo"

    # Ensure no stale ODFV is loaded from previous runs
    reg = repo_dir / "registry.db"
    if reg.exists():
        reg.unlink()

    env = os.environ.copy()
    env["FEAST_DISABLE_ODFV"] = "1"

    subprocess.run(["feast", "-c", str(repo_dir), "apply"], check=True, env=env)

    # Fix partition columns in current minute data before materialization
    project_root = Path(__file__).resolve().parents[1]
    _ensure_partition_columns(project_root)

    fs = FeatureStore(repo_path=str(repo_dir))
    now = datetime.now(tz=UTC)
    logger.info("Materializing incrementally up to %s", now.isoformat())
    fs.materialize_incremental(end_date=now)
    logger.info("Done")


if __name__ == "__main__":
    main()
