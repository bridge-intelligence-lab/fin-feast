# Feast Polygon POC (FX/Crypto)

Offline-first Feast pipeline with Redis online store, using Polygon for data. Supports both batch (REST) and low-latency streaming (WebSocket) for minute bars, plus immutable experiment snapshots.

## Features
- Assets: X:BTCUSD (crypto), C:GBPUSD (forex)
- Offline store: Parquet (current zone + experiments)
- Online store: Redis (docker-compose)
- Feature transforms
  - Base: open, high, low, close, vwap, volume
  - Precomputed (offline): return_1, ma_5, ma_20, vol_20, rsi_14, atr_14
  - On-demand (stateless): hlc3, ohlc4, vol_log, spread, body, vwap_premium
- Modes: current vs experiments snapshots (immutable), switch via env
- Materialize-incremental every 60s for batch mode; streaming ingestor pushes to Redis on each new bar

## Quickstart
1. Copy env
```bash
cp .env.example .env
```
2. Start Redis
```bash
make up
```
3. Install
```bash
make setup
```
4. Generate synthetic data
```bash
python scripts/generate_synthetic_data.py --zone current --start 2025-09-01 --end 2025-10-12 --freq daily --symbols X:BTCUSD C:GBPUSD
python scripts/generate_synthetic_data.py --zone current --start 2025-10-01 --end 2025-10-12 --freq minute --symbols X:BTCUSD C:GBPUSD
```
5. Apply + materialize
```bash
make apply
make materialize
```
6. Online query
```bash
python scripts/online_query_demo.py --symbols X:BTCUSD C:GBPUSD
```

## Streaming minute bars
Run the streaming ingestor (pushes to Redis immediately and writes Parquet):
```bash
python service/polygon_stream_ingestor.py --symbols X:BTCUSD C:GBPUSD
```
Requires POLYGON_API_KEY in .env. Uses Polygon WebSocket for 1-minute aggregates where available; otherwise aggregates ticks locally.

## Repo layout
See the repository tree in the requirement section.

## Testing
- `pytest -q` runs the suite. Tests will spin up Redis via docker-compose automatically.

## Troubleshooting
- Feast registry lock issues: remove `feature_repo/registry.db` and re-apply.
- Redis not reachable: ensure `make up` and that REDIS_HOST/PORT in `.env` match.

