# Point-in-time (PIT) training data

Training rows must be built **as-of** each decision time: for a query point
`(symbol, event_timestamp)`, join the latest feature whose own timestamp is
`<= event_timestamp`. Getting this wrong leaks the future into training and
inflates backtests.

`fin_feast/features/pit.py` provides two implementations of that join and a
comparator:

| Function | Engine | Role |
|---|---|---|
| `manual_pit` | pandas over Parquet | Dependency-light **oracle**. Returns every entity row (missing views -> NaN). No TTL. |
| `feast_pit` | Feast `get_historical_features` | Production path. TTL-aware, hardened against the drop described below. |
| `compare_pit` | both | Runs each on the same grid and diffs every numeric cell. |

## Run it

```bash
export FEAST_DATA_ZONE=current
finfeast-generate --zone current --start 2025-09-01 --end 2025-10-12 --freq daily  --symbols X:BTCUSD C:GBPUSD
finfeast-generate --zone current --start 2025-10-08 --end 2025-10-12 --freq minute --symbols X:BTCUSD C:GBPUSD
feast -c feature_repo apply

# Feast-native build
python -m scripts.build_training_dataset --zone current --start 2025-10-09 --end 2025-10-12 \
  --freq h --symbols X:BTCUSD C:GBPUSD --engine feast --out data/derived/train.parquet

# Oracle check: assert Feast-native == manual, bit-for-bit
python -m scripts.build_training_dataset --zone current --start 2025-10-09 --end 2025-10-12 \
  --freq h --symbols X:BTCUSD C:GBPUSD --verify
```

## Two sharp edges in Feast's file/dask offline store

Both are why the earlier revision hand-rolled the join "to avoid engine-specific
issues." They are real; the module handles them so you don't have to.

### 1. Feature-name collisions -> `full_feature_names=True`

`daily_ohlcv_fv` and `minute_ohlcv_fv` share column names (`close`, `rsi_14`, …).
A single `get_historical_features` call over both raises
`FeatureNameCollisionError` unless you pass `full_feature_names=True`, which
returns columns as `<view>__<feature>` (e.g. `daily_ohlcv_fv__close`).

### 2. Silent cross-TTL row drops -> query per view, then merge

This is the dangerous one. If you request features from several views **in one
call** and any view has no in-TTL row for an entity/timestamp, the file/dask
store drops the **entire** entity row, not just that view's columns, with no
error. You lose the features that *were* available.

Example: an as-of point before the minute history starts still has a valid daily
bar, but a combined daily+minute call drops it outright:

```
combined  daily+minute call : 1 row   (the early point vanished — daily lost too)
per-view  daily then minute : 2 rows   (early point kept: daily present, minute NaN)
```

`feast_pit` therefore queries **each view independently and left-merges** onto
the entity grid, so a TTL miss in one view can never evict rows or another
view's features. It logs a warning when a view drops rows so the loss is visible
rather than silent.

TTLs today: `daily_ohlcv_fv` = 400d, `minute_ohlcv_fv` = 14d
(`feature_repo/feature_views.py`).

## Verification discipline

`compare_pit` (and `--verify`) treats the manual join as ground truth and
asserts the Feast path reproduces it exactly on a valid window:

```
[VERIFY] {'rows_manual': 146, 'rows_feast': 146, 'cols': 24, 'max_abs_diff': 0.0, 'mismatches': {}, 'match': True}
```

Keeping a cheap independent oracle next to the real engine is how you catch a
silent as-of regression before it reaches a model. `tests/test_pit_parity.py`
runs the fast oracle in unit CI and the full parity check under
`FIN_FEAST_PIT_IT=1`.
