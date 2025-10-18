from __future__ import annotations

from pathlib import Path

import pytest

from fin_feast.utils.env import get_redis_cfg, get_retention_days


def test_paths_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Point CWD-like root to a temp dir using environment variables if Paths uses them,
    # otherwise construct directly from tmp dir.
    monkeypatch.setenv("FEAST_REPO_ROOT", str(tmp_path))
    from fin_feast.utils.env import get_paths

    p = get_paths()
    assert p.repo_root == tmp_path
    assert p.data_offline == tmp_path / "data" / "offline"
    assert p.data_current_daily == tmp_path / "data" / "offline" / "current" / "daily"
    assert p.data_current_minute == tmp_path / "data" / "offline" / "current" / "minute"
    assert p.data_experiments == tmp_path / "data" / "offline" / "experiments"


def test_get_redis_cfg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("REDIS_PORT", raising=False)
    assert get_redis_cfg() == ("localhost", 6379)
    monkeypatch.setenv("REDIS_HOST", "redis")
    monkeypatch.setenv("REDIS_PORT", "6380")
    assert get_redis_cfg() == ("redis", 6380)


def test_get_retention_days(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DAILY_RETENTION_DAYS", raising=False)
    monkeypatch.delenv("MINUTE_RETENTION_DAYS", raising=False)
    assert get_retention_days() == (400, 30)
    monkeypatch.setenv("DAILY_RETENTION_DAYS", "7")
    monkeypatch.setenv("MINUTE_RETENTION_DAYS", "3")
    assert get_retention_days() == (7, 3)
