from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import pytest

from fin_feast.online.push import push_rows_to_online


class _FSMock:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    # Simulate multiple signatures; succeed only for list positional or entity_rows keyword
    def write_to_online_store(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append({"args": args, "kwargs": kwargs})
        # Succeed if second positional arg is a list (positional list form)
        if args and len(args) >= 2 and isinstance(args[1], list):
            return None
        # Or if entity_rows keyword provided (newer API)
        if "entity_rows" in kwargs:
            return None
        # Otherwise fail to force fallback to next variant
        raise RuntimeError("signature mismatch")


def test_push_rows_to_online_variants(monkeypatch):
    # Patch FeatureStore ctor to return our mock
    store = _FSMock()
    monkeypatch.setattr("fin_feast.online.push.FeatureStore", lambda repo_path: store)

    df = pd.DataFrame([
        {
            "symbol": "X:BTCUSD",
            "event_timestamp": pd.Timestamp("2025-01-01T00:00:00Z"),
            "open": 1.0,
            "close": 1.0,
            "return_1": float("nan"),  # should become None
        }
    ])

    # Should not raise
    push_rows_to_online("/tmp/repo", "minute_ohlcv_fv", df, entity_keys=["symbol"])  # type: ignore[arg-type]

    # Ensure calls were recorded
    assert len(store.calls) > 0
    # Find the first successful call (where our mock would have returned)
    success = None
    for call in store.calls:
        args, kwargs = call["args"], call["kwargs"]
        if (args and len(args) >= 2 and isinstance(args[1], list)) or ("entity_rows" in kwargs):
            success = call
            break
    assert success is not None
    # Check that NaN was normalized to None in the payload
    if success:
        args, kwargs = success["args"], success["kwargs"]
        if args and len(args) >= 2 and isinstance(args[1], list):
            payload = args[1][0]
        else:
            payload = kwargs["entity_rows"][0]
        assert payload.get("return_1", "sentinel") is None


def test_push_rows_to_online_missing_symbol(monkeypatch):
    monkeypatch.setattr("fin_feast.online.push.FeatureStore", lambda repo_path: _FSMock())

    df = pd.DataFrame([
        {"event_timestamp": pd.Timestamp("2025-01-01T00:00:00Z"), "open": 1.0, "close": 1.0}
    ])
    with pytest.raises(ValueError):
        push_rows_to_online("/tmp/repo", "minute_ohlcv_fv", df, entity_keys=["symbol"])  # type: ignore[arg-type]
