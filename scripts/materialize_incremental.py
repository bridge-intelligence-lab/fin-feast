from __future__ import annotations

import subprocess
from datetime import datetime, timezone

from feast import FeatureStore

from feast_polygon_poc.logging import get_logger

logger = get_logger(__name__)


def main() -> None:
    logger.info("Running feast apply via CLI...")
    subprocess.run(["feast", "-c", "feature_repo", "apply"], check=True)

    fs = FeatureStore(repo_path="feature_repo")
    now = datetime.now(tz=timezone.utc)
    logger.info("Materializing incrementally up to %s", now.isoformat())
    fs.materialize_incremental(end_date=now)
    logger.info("Done")


if __name__ == "__main__":
    main()
