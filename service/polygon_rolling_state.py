from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class PolygonRollingState:
    window: int = 20
    buffer: deque[dict] = field(default_factory=lambda: deque(maxlen=1000))

    def add_bar(self, row: dict) -> pd.DataFrame:
        # Minimal validation
        required = {"symbol", "event_timestamp", "open", "high", "low", "close", "vwap", "volume"}
        missing = required - set(row)
        if missing:
            raise ValueError(f"Missing fields: {missing}")
        self.buffer.append(row)
        return pd.DataFrame([row])
