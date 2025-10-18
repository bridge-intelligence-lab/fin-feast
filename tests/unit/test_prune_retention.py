from __future__ import annotations

from datetime import datetime
from pathlib import Path

from scripts.prune_retention import prune_dir


def _mk_part(base: Path, sym: str, date_str: str) -> Path:
    d = base / f"symbol={sym}" / f"date={date_str}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "data.parquet").write_text("x")
    return d


def test_prune_retention_delete_and_dry_run(tmp_path: Path) -> None:
    base = tmp_path
    old = _mk_part(base, "X:BTCUSD", "2024-01-01")
    new = _mk_part(base, "X:BTCUSD", "2025-01-01")

    cutoff = datetime.fromisoformat("2024-06-01")

    # Dry run: nothing deleted
    prune_dir(base, cutoff, dry_run=True)
    assert old.exists() and new.exists()

    # Actual: old deleted, new kept
    prune_dir(base, cutoff, dry_run=False)
    assert not old.exists()
    assert new.exists()
