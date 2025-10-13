# Troubleshooting

## Common issues

### 1) ArrowTypeError: Field symbol has incompatible types: string vs dictionary
- Symptom: `feast apply` fails while inspecting FileSource schema
- Cause: Parquet files include a `symbol` column (sometimes encoded as dictionary), while hive partitioning also provides `symbol`. PyArrow cannot merge these types.
- Fix (implemented): Drop `symbol` from Parquet files; rely on partition key.
  - Implemented in `feast_polygon_poc/utils/io.py::write_parquet_partitioned`.
  - For existing data, delete `data/offline` and regenerate.

### 2) Registry issues (lock, corruption, drift)
- Fix:
```bash
rm -f feature_repo/registry.db
make apply
```

### 3) Redis connectivity
- Ensure docker-compose is running:
```bash
make up
```
- Check env:
  - REDIS_HOST=localhost, REDIS_PORT=6379

### 4) Python version mismatch
- Error: Package requires Python >=3.11
- Fix: Use Python 3.11 venv or Conda env.

### 5) Polygon rate limits / connectivity
- Use built-in retries (tenacity) in batch fetcher; adjust backoff if needed.
- For WebSocket, implement reconnect/backoff if connection drops. Current service is minimal; extend as needed.

### 6) OnDemandFeatureView warnings
- ODFV is experimental and not intended for heavy offline joins at scale. In this POC it’s used for lightweight stateless transforms only.

### 7) Missing features online
- Ensure recent materialize run (`make materialize`) or run the streamer with `--push-online`.
- Verify partitions exist for the symbol and date: `data/offline/current/minute/symbol=<sym>/date=YYYY-MM-DD/data.parquet`.

### 8) Zone switching (current vs experiment)
- Set `FEAST_DATA_ZONE` and, for experiments, `FEAST_EXPERIMENT_ID`.
- Re-run `make apply` so Feast resolves sources correctly.

## Quick recovery recipes
- Full reset:
```bash
docker-compose down
rm -f feature_repo/registry.db
rm -rf data/offline
make up
```
- Rebuild online store after Redis reset:
```bash
make materialize
```
