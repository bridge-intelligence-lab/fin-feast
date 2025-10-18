from __future__ import annotations

from pathlib import Path

import pytest

from fin_feast.utils.env import Paths, get_redis_cfg, get_retention_days


def test_paths_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Point CWD-like root to a temp dir using environment variables if Paths uses them,
    # otherwise construct directly from tmp dir.
    p = Paths(base=tmp_path)
    assert p.base == tmp_path
    assert p.data_offline_current == tmp_path / "data" / "offline" / "current"
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
