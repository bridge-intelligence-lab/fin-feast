from __future__ import annotations

from pathlib import Path

from feast import FileSource
from feast.data_format import ParquetFormat

from feast_polygon_poc.utils.env import get_zone, get_experiment_id, resolve_base_path


def _base_path() -> Path:
    return resolve_base_path(get_zone(), get_experiment_id())


def make_daily_ohlcv_source() -> FileSource:
    return FileSource(
        name="daily_ohlcv_source",
        path=str(_base_path() / "daily"),
        timestamp_field="event_timestamp",
        file_format=ParquetFormat(),
    )


def make_minute_ohlcv_source() -> FileSource:
    return FileSource(
        name="minute_ohlcv_source",
        path=str(_base_path() / "minute"),
        timestamp_field="event_timestamp",
        file_format=ParquetFormat(),
    )
