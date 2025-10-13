from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from feast import FeatureStore

from fin_feast.logging import get_logger

logger = get_logger(__name__)


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
    logger.info("Running feast apply via CLI...")
    repo_dir = Path(__file__).resolve().parents[1] / "feature_repo"

    # Ensure no stale ODFV is loaded from previous runs
    reg = repo_dir / "registry.db"
    if reg.exists():
        reg.unlink()

    env = os.environ.copy()
    env.setdefault("FEAST_DISABLE_ODFV", "1")
    env.setdefault("FEAST_DATA_ZONE", "current")

    subprocess.run(["feast", "-c", str(repo_dir), "apply"], check=True, env=env)

    # Fix partition columns in current minute data before materialization
    project_root = Path(__file__).resolve().parents[1]
    _ensure_partition_columns(project_root)

    fs = FeatureStore(repo_path=str(repo_dir))
    now = datetime.now(tz=timezone.utc)
    logger.info("Materializing incrementally up to %s", now.isoformat())
    fs.materialize_incremental(end_date=now)
    logger.info("Done")


if __name__ == "__main__":
    main()
