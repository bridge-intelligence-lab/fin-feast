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

Preferred (no API key): Binance streaming ingestor writes Parquet and can push online:

```bash
python service/binance_stream_ingestor.py --symbols X:BTCUSD C:ETHUSD --push-online
```

Notes:

- Maps Feast symbols to Binance pairs: X:BTCUSD -> btcusdt, C:ETHUSD -> ethusdt
- Writes partitioned Parquet and can push to Redis via Feast
- On restart, ingestor warm-starts rolling state from recent Parquet

Optional: Polygon streaming (requires POLYGON_API_KEY):

```bash
python service/polygon_stream_ingestor.py --symbols X:BTCUSD C:GBPUSD --push-online
```

## Validate streaming and storage

In a separate terminal while the ingestor is running:

```bash
python scripts/validate_streaming.py --symbols X:BTCUSD C:ETHUSD --zone current --check-online --provider binance
```

This verifies that:

- WebSocket receives messages for the symbols (Binance by default)
- Parquet partitions for today grow over time (rows or mtime)
- Online features are present in Redis (if --check-online is provided)

## Binance streaming (no API key required)

```bash
python service/binance_stream_ingestor.py --symbols X:BTCUSD C:ETHUSD --push-online
```

Notes:

- Uses Binance combined streams for 1m klines (btcusdt, ethusdt) mapped to Feast symbols X:BTCUSD and C:ETHUSD
- Writes Parquet and can push to Redis for immediate online features

## Historical training datasets

```bash
export FEAST_DATA_ZONE=experiment
export FEAST_EXPERIMENT_ID=my_exp_$(date -u +%Y%m%d)

python scripts/build_training_dataset.py \
  --zone experiment \
  --exp-id "$FEAST_EXPERIMENT_ID" \
  --start 2024-08-12 --end 2025-08-12 \
  --symbols X:BTCUSD C:ETHUSD \
  --out data/derived/training.parquet
```

This uses Feast get_historical_features with both daily and minute FVs.

See docs/E2E_SCENARIOS.md for a full set of copy-paste end-to-end flows, including Binance batch import.

## Retention pruning

```bash
python scripts/prune_retention.py --dry-run
```

Add a confirm flag (or remove --dry-run) only after reviewing the planned deletions.

## Troubleshooting quick tips

- If `feast apply` fails with Arrow schema merge errors, ensure partition columns are consistent (retain both `symbol` and `date` in files) and see TROUBLESHOOTING.md.
- If registry is stale/corrupt: remove feature_repo/registry.db and re-apply.
- If Redis is empty: run materialize or enable --push-online in the streaming ingestor.
