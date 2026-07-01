"""Point-in-time join tests.

- ``test_manual_pit_as_of`` is a fast unit test with no Feast dependency: it
  builds a tiny offline layout and checks the as-of semantics of the oracle.
- ``test_feast_matches_manual`` is an opt-in integration test (needs Feast + an
  applied registry + generated data). Enable with ``FIN_FEAST_PIT_IT=1``.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from fin_feast.features.pit import manual_pit


def _write_partition(base, freq, symbol, ts, close):
    part_dir = base / freq / f"symbol={symbol}" / f"date={ts[:10]}"
    part_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {"symbol": [symbol], "event_timestamp": [pd.Timestamp(ts, tz="UTC")], "close": [close]}
    ).to_parquet(part_dir / "data.parquet", index=False)


def test_manual_pit_as_of(tmp_path):
    base = tmp_path / "offline" / "current"
    for ts, close in [("2025-10-01", 100.0), ("2025-10-02", 101.0), ("2025-10-03", 102.0)]:
        _write_partition(base, "daily", "X:BTCUSD", ts, close)

    entity_df = pd.DataFrame(
        {
            "symbol": ["X:BTCUSD", "X:BTCUSD", "X:BTCUSD"],
            "event_timestamp": pd.to_datetime(
                # before-any, exactly-on the 2nd bar, after-last
                ["2025-09-30 00:00", "2025-10-02 00:00", "2025-10-05 00:00"],
                utc=True,
            ),
        }
    )

    out = manual_pit(entity_df, base_path=base, feature_cols=["close"], views=["daily_ohlcv_fv"])
    got = out.sort_values("event_timestamp")["daily_ohlcv_fv__close"].tolist()

    # before any bar -> NaN; on the 2nd bar -> 101; after last -> latest (102)
    assert pd.isna(got[0])
    assert got[1] == 101.0
    assert got[2] == 102.0


@pytest.mark.skipif(
    os.getenv("FIN_FEAST_PIT_IT") != "1",
    reason="integration: set FIN_FEAST_PIT_IT=1 with Feast installed, data generated, and repo applied",
)
def test_feast_matches_manual():
    pytest.importorskip("feast")
    from fin_feast.features.pit import compare_pit
    from fin_feast.utils.env import resolve_base_path

    os.environ.setdefault("FEAST_DATA_ZONE", "current")
    syms = ["X:BTCUSD", "C:GBPUSD"]
    entity_df = pd.DataFrame(
        [(s, ts) for s in syms for ts in pd.date_range("2025-10-09", "2025-10-12", freq="h", tz="UTC")],
        columns=["symbol", "event_timestamp"],
    )
    summary = compare_pit(entity_df, base_path=resolve_base_path("current", None), repo_path="feature_repo")
    assert summary["match"], summary
    assert summary["max_abs_diff"] == 0.0, summary
