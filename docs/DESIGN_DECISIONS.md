# Design Decisions (ADR-style)

This file captures key decisions and rationale for Fin Feast.

## ADR-001: Offline precompute of rolling indicators
- Context: Indicators like MA, RSI, ATR require window state.
- Decision: Compute offline at ingestion (both synthetic and REST) and store in Parquet.
- Rationale: Ensures offline-online parity, avoids heavy ODFV state, predictable performance, idempotent writes.
- Consequence: Ingestors must handle rolling state and warm-start from Parquet; ODFV limited to stateless transforms.

## ADR-002: Hybrid freshness (materialize + push-online)
- Context: Need low-latency access (<60s) for trading signals.
- Decision: Keep batch materialize-incremental every ~60s; streaming ingestor optionally pushes latest bar to Redis per event.
- Rationale: Retains offline-first guarantees and resilience; meets freshness targets when streaming.
- Consequence: Slight increase in operational complexity; requires schema alignment with FeatureView.

## ADR-003: Parquet partitioning and schema in-file partition keys
- Context: Schema merging across partitions was brittle when partition keys were inconsistently present/absent inside files.
- Decision: Retain both partition columns (`symbol`, `date`) in Parquet files and in the partition path.
- Rationale: Avoids merge conflicts and meets tools’ expectations (if any partition key is present, include all); keeps upserts idempotent by event_timestamp.
- Consequence: Readers can rely on consistent schemas; warm-start logic can inject or ignore `symbol` as needed.

## ADR-004: On-Demand Feature View scope
- Context: ODFV is experimental and not ideal for heavy offline usage.
- Decision: Limit ODFV to stateless transforms derived from the minute FeatureView.
- Rationale: Keeps ODFV lightweight; avoids column collisions across daily and minute sources.
- Consequence: Stateless transforms only; stateful indicators must be precomputed.

## ADR-005: Redis as online store
- Context: Need a simple, fast online feature store for the project.
- Decision: Use Redis via Feast's Redis online store.
- Rationale: Easy local setup, good performance, supported by Feast.
- Consequence: Consider managed Redis and HA configurations for production.

## ADR-006: Data zones (current vs experiment)
- Context: Need to switch between rolling data and immutable snapshots without code changes.
- Decision: Resolve FileSource paths from `FEAST_DATA_ZONE` and `FEAST_EXPERIMENT_ID` env vars.
- Rationale: Simple, explicit control; aligns with snapshot experimentation.
- Consequence: Users must set env vars correctly and re-apply Feast when switching zones.
