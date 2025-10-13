from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import threading
import time

import pandas as pd

from scripts.validate_streaming import (
    _today_utc_date,
    _file_mtime,
    _partition_path,
    _read_partition_rows,
    check_parquet_growth,
)
import fin_feast.utils.env as env_mod


def test_today_utc_date_format():
    s = _today_utc_date()
    assert len(s.split("-")) == 3


def test_file_mtime(tmp_path: Path):
    p = tmp_path / "x.txt"
    p.write_text("a")
    mt = _file_mtime(p)
    assert mt > 0


def test_check_parquet_growth_zero_poll(tmp_path: Path, monkeypatch):
    # Monkeypatch base path resolver to use tmp
    def fake_resolve(zone: str, exp_id: str | None = None) -> Path:  # type: ignore[override]
        b = tmp_path / "offline" / zone
        (b / "minute").mkdir(parents=True, exist_ok=True)
        return b

    # Patch resolver in both modules and use the module reference for calls
    monkeypatch.setattr("fin_feast.utils.env.resolve_base_path", fake_resolve)
    monkeypatch.setattr("scripts.validate_streaming.resolve_base_path", fake_resolve)

    zone = "current"
    sym = "X:BTCUSD"
    base = env_mod.resolve_base_path(zone, None)

    # Initially empty
    today = datetime.now(timezone.utc).date().isoformat()
    part = _partition_path(base, sym, "minute", today)
    assert _read_partition_rows(part) == 0

    # Background writer that writes between the before/after reads inside check_parquet_growth
    from fin_feast.utils.io import write_parquet_partitioned

    def writer():
        # Ensure we write after check_parquet_growth has taken the 'before' snapshot
        time.sleep(0.05)
        df1 = pd.DataFrame(
            [
                {
                    "symbol": sym,
                    "event_timestamp": pd.Timestamp(datetime.now(timezone.utc)),
                    "open": 1.0,
                    "high": 1.0,
                    "low": 1.0,
                    "close": 1.0,
                    "vwap": 1.0,
                    "volume": 1.0,
                }
            ]
        )
        write_parquet_partitioned(base / "minute", df1)
        # Write another row to strengthen the growth signal
        time.sleep(0.05)
        df2 = pd.DataFrame(
            [
                {
                    "symbol": sym,
                    "event_timestamp": pd.Timestamp(
                        datetime.now(timezone.utc) + pd.Timedelta(seconds=1)
                    ),
                    "open": 2.0,
                    "high": 2.0,
                    "low": 2.0,
                    "close": 2.0,
                    "vwap": 2.0,
                    "volume": 2.0,
                }
            ]
        )
        write_parquet_partitioned(base / "minute", df2)

    t = threading.Thread(target=writer, daemon=True)
    t.start()

    # Use a small positive poll_secs so the writer can act between checks
    ok, grew = check_parquet_growth(zone, [sym], freq="minute", poll_secs=0.2)
    t.join(timeout=1)

    assert ok
    assert sym in grew
