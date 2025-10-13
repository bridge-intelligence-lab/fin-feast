# Test Coverage Plan

Purpose: Track the incremental work to increase unit test coverage across fin_feast and helper scripts. This document records the planned tests, their status, and notes.

Coverage goals
- fin_feast package: >= 85%
- Project-wide: >= 75%

Status legend
- Planned: to be implemented
- Implemented: tests created and committed
- Passing: tests green locally in CI/dev

Checklist

1) fin_feast.utils.env [Planned]
- Tests: get_zone (valid/invalid), resolve_base_path (current/experiment), get_repo_root override, get_paths structure, get_redis_cfg defaults/overrides, get_retention_days defaults/overrides
- File: tests/test_env_utils.py

2) fin_feast.utils.io [Planned]
- Tests: ensure_columns missing raises; normalize_schema type coercion; partition_path format; write_parquet_partitioned append/sort/dedup; read_recent_bars last n and symbol present
- File: tests/test_io_utils.py

3) fin_feast.features.rolling [Planned]
- Tests: compute_return_1, compute_ma, compute_vol, compute_rsi, compute_atr (small windows), add_indicators columns present
- File: tests/test_rolling_features_unit.py

4) fin_feast.logging.get_logger [Planned]
- Tests: obeys LOG_LEVEL, avoids duplicate handlers
- File: tests/test_logging_utils.py

5) fin_feast.online.push.push_rows_to_online [Planned]
- Tests: tries multiple write_to_online_store signatures; NaN->None normalization; event_timestamp dropped; missing symbol error
- File: tests/test_online_push.py

6) scripts/prune_retention.prune_dir [Planned]
- Tests: deletes partitions older than cutoff; respects --dry-run
- File: tests/test_prune_retention.py

7) service.polygon_stream_ingestor.RollingState [Planned]
- Tests: warm_start seeds buffer from parquet; add_bar appends and returns DataFrame
- File: tests/test_polygon_rolling_state.py

8) scripts.materialize_incremental._ensure_partition_columns [Planned]
- Tests: rewrites files to include symbol and date when missing
- File: tests/test_materialize_partition_columns.py

9) scripts.validate_streaming helpers [Planned]
- Tests: _today_utc_date format; _file_mtime; check_parquet_growth with poll_secs=0 using monkeypatched base path and prewritten parquet
- File: tests/test_validate_streaming_helpers.py

10) scripts.generate_synthetic_data helpers [Planned]
- Tests: daterange (daily/minute steps), synthetic_series (shape/positivity), gen_bars (required columns)
- File: tests/test_generate_synthetic_data_functions.py

11) scripts.fetch_polygon_to_parquet.fetch_aggregates (optional) [Planned]
- Tests: with fake REST client payload structure
- File: tests/test_fetch_polygon_to_parquet_unit.py

Notes
- All tests should be offline and deterministic; mock external services and avoid docker/redis dependencies.
- Update this document after each batch of tests is added and passing.
