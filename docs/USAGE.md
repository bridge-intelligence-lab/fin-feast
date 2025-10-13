# Usage Guide

This guide covers setup, environment, commands, and typical workflows for batch and streaming modes.

## Prerequisites
- Python 3.11 (venv recommended)
- Docker with docker-compose

## Setup
```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -V  # ensure 3.11.x
python -m pip install -U pip
python -m pip install -e .[dev]
cp .env.example .env
make up
```

## Environment variables (.env)
- POLYGON_API_KEY=
- REDIS_HOST=localhost
- REDIS_PORT=6379
- FEAST_DATA_ZONE=current | experiment
- FEAST_EXPERIMENT_ID= (required for experiment zone)
- DAILY_RETENTION_DAYS=400
- MINUTE_RETENTION_DAYS=30

## Makefile targets
- setup: install dev deps into current interpreter/venv
- up / down: docker-compose up/down Redis
- apply: feast apply
- materialize: run materialize_incremental.py (apply + materialize-incremental now)
- synth-daily / synth-minute: generate synthetic Parquet data
- poly-daily / poly-minute: fetch Polygon aggregates to Parquet
- train-ds: build historical features dataset
- query: demo online query
- prune: dry-run pruning of old partitions
- test: run pytest
- lint / format: ruff check / ruff format

## Batch (happy path)
```bash
# 1) Synthetic data
python scripts/generate_synthetic_data.py --zone current --start 2025-09-01 --end 2025-10-12 --freq daily --symbols X:BTCUSD C:GBPUSD
python scripts/generate_synthetic_data.py --zone current --start 2025-10-01 --end 2025-10-12 --freq minute --symbols X:BTCUSD C:GBPUSD

# 2) Apply + materialize
make apply
make materialize

# 3) Online read demo
python scripts/online_query_demo.py --symbols X:BTCUSD C:GBPUSD
```

## Streaming minute bars
```bash
# Push latest bar to Redis immediately and write Parquet
python service/polygon_stream_ingestor.py --symbols X:BTCUSD C:GBPUSD --push-online
```
Notes:
- Requires POLYGON_API_KEY in .env
- Uses Polygon WS AM (minute aggregates); adjust to aggregate ticks if needed
- On restart, ingestor warm-starts rolling state from recent Parquet

## Historical training datasets
```bash
FEAST_DATA_ZONE=experiment FEAST_EXPERIMENT_ID=<exp_id> \
python scripts/build_training_dataset.py --zone experiment --exp-id <exp_id> --start 2024-08-12 --end 2025-08-12 --symbols X:BTCUSD C:GBPUSD --out data/derived/training.parquet
```
This uses Feast get_historical_features with both daily and minute FVs.

## Retention pruning
```bash
python scripts/prune_retention.py --dry-run
```
Add a confirm flag (or remove --dry-run) only after reviewing the planned deletions.

## Troubleshooting quick tips
- If `feast apply` fails with Arrow schema merge errors, see TROUBLESHOOTING.md (Solution A).
- If registry is stale/corrupt: remove feature_repo/registry.db and re-apply.
- If Redis is empty: run materialize or enable --push-online in the streaming ingestor.

