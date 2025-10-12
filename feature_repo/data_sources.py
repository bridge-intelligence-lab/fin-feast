from __future__ import annotations

from pathlib import Path

from feast import FileSource

from feast_polygon_poc.utils.env import get_zone, get_experiment_id, resolve_base_path


def _base_path() -> Path:
    return resolve_base_path(get_zone(), get_experiment_id())


daily_ohlcv_source = FileSource(
    name="daily_ohlcv_source",
    path=str(_base_path() / "daily"),
    timestamp_field="event_timestamp",
)


minute_ohlcv_source = FileSource(
    name="minute_ohlcv_source",
    path=str(_base_path() / "minute"),
    timestamp_field="event_timestamp",
)
