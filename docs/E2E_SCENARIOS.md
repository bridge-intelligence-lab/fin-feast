# End-to-End Scenarios

This document provides step-by-step flows for common end-to-end (E2E) scenarios, including batch and streaming, current and experiment zones, and validation steps.

- Quick links
  - [A. Quickstart (synthetic → batch → online)](#a-quickstart-synthetic--batch--online)
  - [B. Streaming (Binance)](#b-streaming-binance)
  - [C. Streaming (Polygon)](#c-streaming-polygon)
  - [D. Real batch import (Polygon)](#d-real-batch-import-polygon)
  - [E. Real batch import (Binance)](#e-real-batch-import-binance)
  - [F. Experiment zone + historical features](#f-experiment-zone--historical-features)
  - [G. Retention pruning](#g-retention-pruning)
  - [H. Schema repair](#h-schema-repair)
  - [I. Clean-room recovery](#i-clean-room-recovery)

Prereqs
- Python 3.11 in a venv (`.venv`)
- `pip install -e .[dev]`
- Docker + docker-compose (for Redis/online store)
- Optional: POLYGON_API_KEY for Polygon flows

Conventions
- All commands run from repo root.
- Copy-paste friendly: export env vars first and reuse.

Environment setup (copy-paste)
```bash
# Optional: set log level
export LOG_LEVEL=INFO

# Default to current zone
export FEAST_DATA_ZONE=current
export FEAST_EXPERIMENT_ID=""

# For experiment scenarios, set once and reuse
export FEAST_EXPERIMENT_ID=my_exp_$(date -u +%Y%m%d)
export FEAST_DATA_ZONE=experiment

# Show current env and resolved base
make env-show
```

## A. Quickstart (synthetic → batch → online)
Description: Generate synthetic daily/minute data in current zone, apply Feast repo, materialize to Redis, and query online.

<details>
<summary>Clear environment (optional)</summary>

```bash
make clean
docker-compose down -v
docker-compose up -d
```

</details>

### Steps
1) Generate synthetic data
   - Daily:
     - python scripts/generate_synthetic_data.py --zone current --start 2025-09-01 --end 2025-10-12 --freq daily --symbols X:BTCUSD C:ETHUSD
   - Minute:
     - python scripts/generate_synthetic_data.py --zone current --start 2025-10-01 --end 2025-10-12 --freq minute --symbols X:BTCUSD C:ETHUSD
2) Apply and materialize (copy-paste):
   - make apply-current
   - make materialize
3) Online query demo
   - python scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD

### Verification
- Materialize logs include: "Materializing 2 feature views ..."
- online_query_demo prints non-null values for both symbols

## B. Streaming (Binance)
Description: Stream 1m klines from Binance, write Parquet, optionally push online, and validate.

<details>
<summary>Clear environment (optional)</summary>

```bash
make clean
docker-compose down -v
docker-compose up -d
```

</details>

### Steps
1) Start Binance streamer (writes Parquet, can push online)

   python service/binance_stream_ingestor.py --symbols X:BTCUSD C:ETHUSD --push-online

2) Validate streaming and storage in parallel

   python scripts/validate_streaming.py --zone current --symbols X:BTCUSD C:ETHUSD --check-online --provider binance

3) Optional: Online query demo

   python scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD

## C. Streaming (Polygon)

Description: Stream Polygon minute aggregates (requires POLYGON_API_KEY), write Parquet, optionally push online, and validate.
0) Clear environment (copy-paste):

   make clean
   docker-compose down -v
   docker-compose up -d

1) Export POLYGON_API_KEY in .env (or export in shell)

2) Start Polygon streamer

   python service/polygon_stream_ingestor.py --symbols X:BTCUSD C:ETHUSD --push-online

3) Validate

   python scripts/validate_streaming.py --zone current --symbols X:BTCUSD C:ETHUSD --check-online --provider polygon

## D. Real batch import (Polygon)
Description: Fetch historical aggregates from Polygon into Parquet, then apply and materialize.
0) Clear environment (copy-paste):
   make clean
   docker-compose down -v
   docker-compose up -d

1) Fetch aggregates to Parquet
   - Daily:
     python scripts/fetch_polygon_to_parquet.py --zone current --start 2025-09-01 --end 2025-10-12 --freq daily --symbols X:BTCUSD C:ETHUSD
   - Minute:
     python scripts/fetch_polygon_to_parquet.py --zone current --start 2025-10-01 --end 2025-10-12 --freq minute --symbols X:BTCUSD C:ETHUSD
2) Apply + materialize
   make apply
   make materialize
3) Online query demo
   python scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD

### Verification
- Materialize logs include: "Materializing 2 feature views ..."
- online_query_demo prints non-null values for both symbols

## E. Real batch import (Binance)
Description: Fetch historical klines from Binance (no API key) into Parquet, then apply and materialize.
0) Clear environment (copy-paste):
   make clean
   docker-compose down -v
   docker-compose up -d

1) Fetch klines to Parquet (no API key)
   - Daily (copy-paste):
     python scripts/fetch_binance_to_parquet.py \
       --zone "" \
       --start 2025-09-01 --end 2025-10-12 \
       --freq daily \
       --symbols X:BTCUSD C:ETHUSD
   - Minute (copy-paste):
     python scripts/fetch_binance_to_parquet.py \
       --zone "" \
       --start 2025-10-01 --end 2025-10-12 \
       --freq minute \
       --symbols X:BTCUSD C:ETHUSD
2) Apply + materialize
   make apply
   make materialize
3) Online query demo
   python scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD

### Verification
- Materialize logs include: "Materializing 2 feature views ..."
- online_query_demo prints non-null values for both symbols

## F. Experiment zone + historical features
Description: Populate experiments/ and build historical features for training.
0) Clear environment (copy-paste):
   make clean
   docker-compose down -v
   docker-compose up -d

1) Prepare experiment data (synthetic or fetched) under experiments/
   - Example with synthetic daily (copy-paste):
     python scripts/generate_synthetic_data.py \
       --zone experiment \
       --exp-id "" \
       --start 2025-10-01 --end 2025-10-03 \
       --freq daily \
       --symbols X:BTCUSD C:ETHUSD
2) Apply FVs
   make apply-experiment
3) Historical features (copy-paste):
   python scripts/build_training_dataset.py \
     --zone experiment \
     --exp-id "" \
     --start 2025-09-01 --end 2025-10-12 \
     --symbols X:BTCUSD C:ETHUSD \
     --out data/derived/training.parquet

## G. Retention pruning
Description: Review and prune old partitions per DAILY_RETENTION_DAYS and MINUTE_RETENTION_DAYS.
1) Dry-run
   - python scripts/prune_retention.py --dry-run
2) Execute after review
   - python scripts/prune_retention.py

## H. Schema repair (partition columns)
Description: Ensure both 'symbol' and 'date' columns exist inside Parquet files to avoid Arrow/Dask issues.
1) Run materialize script pre-step (includes fixer)
   - make materialize
2) Or run the internal fixer if needed (advanced users)
   - see scripts/materialize_incremental.py:_ensure_partition_columns

## I. Clean-room recovery
Description: Reset registry and Redis, re-apply and materialize, and verify online reads.
0) Clear environment (copy-paste):
   make clean
   docker-compose down -v
   docker-compose up -d

1) Reset registry (if needed)
   rm -f feature_repo/registry.db
2) Restart Redis
   docker-compose restart redis
3) Re-apply + materialize
   make apply
   make materialize
4) Verify online
   python scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD
