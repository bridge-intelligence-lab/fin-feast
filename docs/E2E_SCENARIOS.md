# End-to-End Scenarios

This document provides step-by-step flows for common end-to-end (E2E) scenarios, including batch and streaming, current and experiment zones, and validation steps.

Prereqs
- Python 3.11 in a venv (`.venv`)
- `pip install -e .[dev]`
- Docker + docker-compose (for Redis/online store)
- Optional: POLYGON_API_KEY for Polygon flows

Conventions
- Replace placeholders like `<exp_id>` with your values.
- All commands are run from the repo root.

Scenario A: Quickstart (synthetic -> batch -> online)
1) Generate synthetic data
   - Daily:
     python scripts/generate_synthetic_data.py --zone current --start 2025-09-01 --end 2025-10-12 --freq daily --symbols X:BTCUSD C:ETHUSD
   - Minute:
     python scripts/generate_synthetic_data.py --zone current --start 2025-10-01 --end 2025-10-12 --freq minute --symbols X:BTCUSD C:ETHUSD
2) Apply and materialize
   - make apply
   - make materialize
3) Online query demo
   - python scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD

Scenario B: Streaming quickstart (Binance, no API key)
1) Start Binance streamer (writes Parquet, can push online)
   - python service/binance_stream_ingestor.py --symbols X:BTCUSD C:ETHUSD --push-online
2) Validate streaming and storage in parallel
   - python scripts/validate_streaming.py --symbols X:BTCUSD C:ETHUSD --zone current --check-online --provider binance
3) Optional: Online query demo
   - python scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD

Scenario C: Streaming with Polygon (requires POLYGON_API_KEY)
1) Export POLYGON_API_KEY in .env
2) Start Polygon streamer
   - python service/polygon_stream_ingestor.py --symbols X:BTCUSD C:ETHUSD --push-online
3) Validate
   - python scripts/validate_streaming.py --symbols X:BTCUSD C:ETHUSD --zone current --check-online --provider polygon

Scenario D: Real data batch import (Polygon)
1) Fetch aggregates to Parquet
   - Daily:
     python scripts/fetch_polygon_to_parquet.py --zone current --start 2025-09-01 --end 2025-10-12 --freq daily --symbols X:BTCUSD C:ETHUSD
   - Minute:
     python scripts/fetch_polygon_to_parquet.py --zone current --start 2025-10-01 --end 2025-10-12 --freq minute --symbols X:BTCUSD C:ETHUSD
2) Apply + materialize
   - make apply
   - make materialize
3) Online query demo
   - python scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD

Scenario E: Real data batch import (Binance)
1) Fetch klines to Parquet (no API key)
   - Daily:
     python scripts/fetch_binance_to_parquet.py --zone current --start 2025-09-01 --end 2025-10-12 --freq daily --symbols X:BTCUSD C:ETHUSD
   - Minute:
     python scripts/fetch_binance_to_parquet.py --zone current --start 2025-10-01 --end 2025-10-12 --freq minute --symbols X:BTCUSD C:ETHUSD
2) Apply + materialize
   - make apply
   - make materialize
3) Online query demo
   - python scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD

Scenario F: Experiment zone snapshot + historical features
1) Prepare experiment data (synthetic or fetched) under experiments/<exp_id>
   - Example with synthetic daily:
     FEAST_DATA_ZONE=experiment FEAST_EXPERIMENT_ID=<exp_id> \
     python scripts/generate_synthetic_data.py --zone experiment --exp-id <exp_id> --start 2025-10-01 --end 2025-10-03 --freq daily --symbols X:BTCUSD C:ETHUSD
2) Apply FVs
   - make apply
3) Historical features
   - Use FeatureStore.get_historical_features or build_training_dataset.py
   - Example:
     FEAST_DATA_ZONE=experiment FEAST_EXPERIMENT_ID=<exp_id> \
     python scripts/build_training_dataset.py --zone experiment --exp-id <exp_id> --start 2025-09-01 --end 2025-10-12 --symbols X:BTCUSD C:ETHUSD --out data/derived/training.parquet

Scenario G: Retention pruning
1) Dry-run
   - python scripts/prune_retention.py --dry-run
2) Execute after review
   - python scripts/prune_retention.py

Scenario H: Schema repair (partition columns)
1) Run materialize script pre-step (includes fixer)
   - make materialize
2) Or run the internal fixer if needed (advanced users)
   - see scripts/materialize_incremental.py:_ensure_partition_columns

Scenario I: Clean-room recovery
1) Reset registry
   - rm feature_repo/registry.db (or `git clean` if desired)
2) Restart Redis
   - docker-compose restart redis
3) Re-apply + materialize
   - make apply && make materialize
4) Verify online
   - python scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD

Troubleshooting
- See docs/TROUBLESHOOTING.md for Arrow/Dask schema issues and registry resets.
- For networking hiccups, re-run fetch or streaming with a shorter time window.
- Ensure `FEAST_DATA_ZONE` and `FEAST_EXPERIMENT_ID` match the intended state.
