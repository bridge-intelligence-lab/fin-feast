from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from fin_feast.logging import get_logger
from fin_feast.utils.env import get_paths, get_retention_days

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def prune_dir(base: Path, cutoff: datetime, dry_run: bool) -> None:
    if not base.exists():
        return
    for sym_dir in base.glob("symbol=*"):
        for part in sym_dir.glob("date=*"):
            date_str = part.name.split("=", 1)[1]
            dt = datetime.fromisoformat(date_str)
            if dt < cutoff:
                if dry_run:
                    logger.info("Would delete %s", part)
                else:
                    logger.info("Deleting %s", part)
                    for f in part.glob("*"):
                        f.unlink(missing_ok=True)
                    part.rmdir()


def main() -> None:
    args = parse_args()
    paths = get_paths()
    daily_ret, minute_ret = get_retention_days()

    now = datetime.utcnow()
    daily_cutoff = now - timedelta(days=daily_ret)
    minute_cutoff = now - timedelta(days=minute_ret)

    prune_dir(paths.data_current_daily, daily_cutoff, args.dry_run)
    prune_dir(paths.data_current_minute, minute_cutoff, args.dry_run)


if __name__ == "__main__":
    main()
