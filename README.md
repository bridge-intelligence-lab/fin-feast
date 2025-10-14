# Feast Polygon POC (FX/Crypto)

Offline-first Feast pipeline with Redis online store, using Polygon for data. Supports both batch (REST) and low-latency streaming (WebSocket) for minute bars, plus immutable experiment snapshots.

[![CI](https://github.com/your-org/fin-feast-poc/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/fin-feast-poc/actions/workflows/ci.yml)

Note: Update the CI badge URL to your actual org/repo after publishing.

## Table of Contents
- Architecture: docs/ARCHITECTURE.md
- Usage: docs/USAGE.md
- Features: docs/FEATURES.md
- Testing: docs/TESTING.md
- Operations: docs/OPERATIONS.md
- Security: docs/SECURITY.md
- Design decisions: docs/DESIGN_DECISIONS.md
- Troubleshooting: docs/TROUBLESHOOTING.md
- Restart runbook: RESTART_RUNBOOK.md

## Highlights
- Assets: X:BTCUSD (crypto), C:GBPUSD (forex)
- Offline store: Parquet (current zone + experiments)
- Online store: Redis (docker-compose)
- Feature transforms
  - Base: open, high, low, close, vwap, volume
  - Precomputed (offline): return_1, ma_5, ma_20, vol_20, rsi_14, atr_14
  - On-demand (stateless): hlc3, ohlc4, vol_log, spread, body, vwap_premium
- Modes: current vs experiments snapshots (immutable), switch via env
- Materialize-incremental every 60s for batch mode; streaming ingestor can push online per bar

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
4. Generate synthetic data (via console script)
```bash
finfeast-generate --zone current --start 2025-09-01 --end 2025-10-12 --freq daily --symbols X:BTCUSD C:GBPUSD
finfeast-generate --zone current --start 2025-10-01 --end 2025-10-12 --freq minute --symbols X:BTCUSD C:GBPUSD
```
5. Apply + materialize (via console script)
```bash
make apply
finfeast-materialize --zone current
```
6. Online query
```bash
python scripts/online_query_demo.py --symbols X:BTCUSD C:GBPUSD
```

## Streaming minute bars
Preferred (no API key): Binance streaming ingestor writes Parquet and can push online:
```bash
python service/binance_stream_ingestor.py --symbols X:BTCUSD C:ETHUSD --push-online
```
Notes:
- Maps Feast symbols to Binance pairs: X:BTCUSD -> btcusdt, C:ETHUSD -> ethusdt
- Writes partitioned Parquet and optionally pushes to Redis via Feast
- Resilience: automatic reconnect with exponential backoff and jitter; online push errors are logged and do not stop ingestion

Optional: Polygon streaming (requires POLYGON_API_KEY):
```bash
python service/polygon_stream_ingestor.py --symbols X:BTCUSD C:GBPUSD --push-online
```
- Resilience: online push errors are caught and logged; streaming continues

## Repo layout
See the repository tree in docs/ARCHITECTURE.md and the requirement.

## Testing
- Unit tests: `pytest -q tests/unit`
- Full suite: `pytest -q`
- E2E tests may require Docker and network; CI runs unit tests by default.

## Security and privacy
- Do not commit secrets. Use `.env.example` as a template; `.env` is gitignored.
- If a secret was previously committed, rotate it and scrub history before publishing.

## License
- MIT License. See LICENSE file.

## Disclaimer
- This repository is for educational purposes and should not be considered financial advice.

## Troubleshooting
- See docs/TROUBLESHOOTING.md and RESTART_RUNBOOK.md
