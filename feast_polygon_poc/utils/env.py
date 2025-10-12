from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

Zone = Literal["current", "experiment"]


@dataclass(frozen=True)
class Paths:
    repo_root: Path
    data_offline: Path
    data_current_daily: Path
    data_current_minute: Path
    data_experiments: Path


load_dotenv(override=False)


def get_repo_root() -> Path:
    # Allow override for tests or custom layouts
    override = os.getenv("FEAST_REPO_ROOT")
    if override:
        return Path(override).resolve()
    # Default: project root two levels up from this file
    return Path(__file__).resolve().parents[2]


def get_zone() -> Zone:
    zone = os.getenv("FEAST_DATA_ZONE", "current").strip()
    if zone not in ("current", "experiment"):
        raise ValueError("FEAST_DATA_ZONE must be 'current' or 'experiment'")
    return zone  # type: ignore[return-value]


def get_experiment_id() -> str | None:
    exp_id = os.getenv("FEAST_EXPERIMENT_ID", "").strip()
    return exp_id or None


def get_paths() -> Paths:
    root = get_repo_root()
    data_offline = root / "data" / "offline"
    return Paths(
        repo_root=root,
        data_offline=data_offline,
        data_current_daily=data_offline / "current" / "daily",
        data_current_minute=data_offline / "current" / "minute",
        data_experiments=data_offline / "experiments",
    )


def resolve_base_path(zone: Zone, exp_id: str | None) -> Path:
    paths = get_paths()
    if zone == "current":
        return paths.data_offline / "current"
    if not exp_id:
        raise ValueError("FEAST_EXPERIMENT_ID is required for experiment zone")
    return paths.data_experiments / exp_id


def get_redis_cfg() -> tuple[str, int]:
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    return host, port


def get_retention_days() -> tuple[int, int]:
    daily = int(os.getenv("DAILY_RETENTION_DAYS", "400"))
    minute = int(os.getenv("MINUTE_RETENTION_DAYS", "30"))
    return daily, minute
