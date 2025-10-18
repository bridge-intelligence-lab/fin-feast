# Feast — Restart + Operations Runbook

This document helps you reset, run, and troubleshoot this Feast project quickly, including a fix for the common PyArrow schema error and streaming guidance.

## 1) Environment
- Python: 3.11 (venv recommended)
- Docker: docker-compose
- Project root: `/home/rodrigo/repo/fin_feast/`

Create and activate venv (example for Ubuntu):
```bash
python -m venv .venv
source .venv/bin/activate
python -V  # 3.11.x
python -m pip install -U pip
python -m pip install -e ".[dev]"
```
Note for zsh: If you see 'no matches found' on extras, quote or escape the brackets:
- python -m pip install -e ".[dev]"
- python -m pip install -e .\[dev\]


Start Redis:
```bash
make up
```

## 2) Hard reset (safe anytime)
Use this if you see registry or data inconsistencies.
```bash
docker-compose down
rm -f feature_repo/registry.db
rm -rf data/offline
find . -type d -name __pycache__ -exec rm -rf {} +
make up
```

## 3) Fix: PyArrow "incompatible types" (symbol string vs dictionary)
### Root cause
We use Hive-style partitioning (`symbol=X:BTCUSD/date=YYYY-MM-DD`). If Parquet files also include a `symbol` column (and it's encoded as categorical/dictionary in any file), PyArrow sees a type mismatch between the partition-provided `symbol` and the file `symbol` and fails to merge.

### Solution A (recommended): rely only on partition key for symbol
Drop `symbol` from the file content before writing. Feast still reads `symbol` from the partition directory name, so joins will work.

Patch guidance (fin_feast/utils/io.py):
```python
def write_parquet_partitioned(base: Path, df: pd.DataFrame) -> None:
    ensure_columns(df)
    df = normalize_schema(df)
    for (symbol, date), g in df.groupby(["symbol", df["event_timestamp"].dt.date]):
        part_dir = partition_path(base, symbol, pd.Timestamp(date, tz="UTC").to_pydatetime())
        part_dir.mkdir(parents=True, exist_ok=True)
        file_path = part_dir / "data.parquet"
        # Drop symbol column to avoid duplicate/typed symbol in files
        g_no_sym = g.drop(columns=["symbol"]).sort_values("event_timestamp")
        if file_path.exists():
            existing = pd.read_parquet(file_path)
            combined = (
                pd.concat([existing, g_no_sym], ignore_index=True)
                .drop_duplicates(subset=["event_timestamp"], keep="last")
                .sort_values("event_timestamp")
            )
            combined.to_parquet(file_path, index=False)
        else:
            g_no_sym.to_parquet(file_path, index=False)
```

After applying, perform a hard reset (Section 2) and regenerate data (Section 6) before `feast apply`.

### Solution B (alternative): enforce uniform plain string type
If you keep `symbol` inside files, ensure every write uses a plain string dtype:
```python
df["symbol"] = df["symbol"].astype("string")
```
This can still collide with partition-provided symbol, so Solution A is more robust.

## 4) Silence Feast warnings (optional but recommended)
- feature_repo/entities.py
```python
from feast import Entity
from feast.value_type import ValueType
symbol = Entity(name="symbol", join_keys=["symbol"], value_type=ValueType.STRING)
```
- feature_repo/feature_store.yaml
```yaml
entity_key_serialization_version: 3
```

## 5) Happy-path commands (batch)
```bash
# 1) Synthetic data
python scripts/generate_synthetic_data.py --zone current --start 2025-09-01 --end 2025-10-12 --freq daily --symbols X:BTCUSD C:GBPUSD
python scripts/generate_synthetic_data.py --zone current --start 2025-10-01 --end 2025-10-12 --freq minute --symbols X:BTCUSD C:GBPUSD

# 2) Feast apply + materialize
make apply
make materialize

# 3) Online read demo
python scripts/online_query_demo.py --symbols X:BTCUSD C:GBPUSD
```

## 6) Streaming minute bars (low-latency)
Preferred (no API key): Binance streaming ingestor writes Parquet and can push online.
```bash
python service/binance_stream_ingestor.py --symbols X:BTCUSD C:ETHUSD --push-online
```
Optional (needs key): Polygon streaming
```bash
python service/polygon_stream_ingestor.py --symbols X:BTCUSD C:GBPUSD --push-online
```

## 7) Tests
```bash
pytest -q
```
Tests spin up Redis via docker-compose automatically (see tests/conftest.py).

## 8) Common recovery recipes
- Registry corrupted or out of sync:
```bash
rm -f feature_repo/registry.db
make apply
```
- Redis wiped:
```bash
make materialize
```
- Mixed schemas or Arrow merge errors:
```bash
rm -rf data/offline
# Ensure utils/io.py writes both partition columns (`symbol`, `date`) inside files
# Regenerate data and re-apply
```

## 9) Makefile convenience (optional)
Auto-detect python3.11:
```make
PY ?= $(shell command -v python3.11 || command -v python3 || echo python)
PIP = $(PY) -m pip
```

## 10) What features are available
- Base columns: `open, high, low, close, vwap, volume`
- Precomputed (offline): `return_1, ma_5, ma_20, vol_20, rsi_14, atr_14`
- On-demand (stateless): `hlc3, ohlc4, vol_log, spread, body, vwap_premium`

## 11) Directory layout (key parts)
```
fin-feast/
  feature_repo/
    feature_store.yaml
    entities.py
    data_sources.py
    feature_views.py
    repo.py
  fin_feast/
    utils/
      io.py
      env.py
    features/rolling.py
    online/push.py
  scripts/
    generate_synthetic_data.py
    fetch_polygon_to_parquet.py
    materialize_incremental.py
    build_training_dataset.py
    online_query_demo.py
    prune_retention.py
  service/
    polygon_stream_ingestor.py
  data/
    offline/current/{daily,minute}/
    offline/experiments/<exp_id>/{daily,minute}/
```

## 12) Support
If you’d like, I can:
- Apply Solution A (drop `symbol` column at write) and update code
- Patch the entity/value_type and serialization version
- Update Makefile for python3.11 auto-detection
- Expand README with a quick troubleshooting section
