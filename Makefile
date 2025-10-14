PY=python
PIP=pip

help:
	@echo "Available targets:"
	@echo "  setup           - install dev deps into current interpreter/venv"
	@echo "  up / down       - docker-compose up/down Redis"
	@echo "  apply           - feast apply with ODFV disabled"
	@echo "  materialize     - run materialize_incremental.py (apply + materialize)"
	@echo "  synth-daily     - generate synthetic daily data into current zone"
	@echo "  synth-minute    - generate synthetic minute data into current zone"
	@echo "  poly-daily      - fetch Polygon daily aggregates into current zone"
	@echo "  poly-minute     - fetch Polygon minute aggregates into current zone"
	@echo "  binance-stream  - run Binance streaming ingestor (no API key)"
	@echo "  validate-stream - validate WS, parquet growth, and online features"
	@echo "  train-ds        - build historical training dataset"
	@echo "  query           - run online query demo"
	@echo "  prune           - dry-run retention pruning"
	@echo "  test            - run pytest"
	@echo "  lint / format   - ruff check / format"
	@echo "  clean           - remove offline data (current/experiments) and registry"
	@echo "  env-current     - print export commands for current zone"
	@echo "  env-experiment  - print export commands for experiment zone"
	@echo "  env-show        - print current env and resolved base path"

.PHONY: help setup up down apply materialize synth-daily synth-minute poly-daily poly-minute train-ds query prune test lint format clean

setup:
# 	$(PY) -m venv .venv
# 	. .venv/bin/activate && 
	$(PIP) install -U pip
	$(PIP) install -U ruff
	$(PIP) install -U -e ".[dev]"

up:
	docker-compose up -d
	sleep 2
	docker ps

down:
	docker-compose down

apply:
	cd feature_repo && rm -f registry.db && \
	FEAST_DATA_ZONE=${FEAST_DATA_ZONE:-current} \
	FEAST_EXPERIMENT_ID=${FEAST_EXPERIMENT_ID:-} \
	FEAST_DISABLE_ODFV=1 feast apply

apply-current:
	cd feature_repo && rm -f registry.db && FEAST_DATA_ZONE=current FEAST_EXPERIMENT_ID= FEAST_DISABLE_ODFV=1 feast apply

apply-experiment:
	cd feature_repo && rm -f registry.db && FEAST_DATA_ZONE=experiment FEAST_EXPERIMENT_ID=${FEAST_EXPERIMENT_ID:?set FEAST_EXPERIMENT_ID} FEAST_DISABLE_ODFV=1 feast apply

test:
	pytest -q

materialize:
	@Z=$${FEAST_EXPERIMENT_ID:-}; \
	$(PY) scripts/materialize_incremental.py --zone $${FEAST_DATA_ZONE:-current} --exp-id "$$Z"

synth-daily:
	$(PY) scripts/generate_synthetic_data.py --zone current --start $$(date -u -d '400 days ago' +%F) --end $$(date -u +%F) --freq daily --symbols X:BTCUSD C:GBPUSD

synth-minute:
	$(PY) scripts/generate_synthetic_data.py --zone current --start $$(date -u -d '2 days ago' +%F) --end $$(date -u +%F) --freq minute --symbols X:BTCUSD C:GBPUSD

poly-daily:
	$(PY) scripts/fetch_polygon_to_parquet.py --zone current --start $$(date -u -d '30 days ago' +%F) --end $$(date -u +%F) --freq daily --symbols X:BTCUSD C:GBPUSD

poly-minute:
	$(PY) scripts/fetch_polygon_to_parquet.py --zone current --start $$(date -u -d '1 day ago' +%F) --end $$(date -u +%F) --freq minute --symbols X:BTCUSD C:GBPUSD

validate-stream:
	$(PY) scripts/validate_streaming.py --zone current --symbols X:BTCUSD C:ETHUSD --check-online --provider binance

binance-stream:
	$(PY) service/binance_stream_ingestor.py --zone current --symbols X:BTCUSD C:ETHUSD --push-online

train-ds:
	$(PY) scripts/build_training_dataset.py --zone current --start $$(date -u -d '30 days ago' +%F) --end $$(date -u +%F) --symbols X:BTCUSD C:ETHUSD

query:
	$(PY) scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD

query-odfv:
	FEAST_ENABLE_ODFV=1 $(PY) scripts/online_query_demo.py --symbols X:BTCUSD C:ETHUSD

prune:
	$(PY) scripts/prune_retention.py --dry-run

test:
	pytest -q

lint:
	ruff check .

format:
		ruff format .

clean:
		rm -rf data/offline/current/daily/* data/offline/current/minute/* data/offline/experiments/*
		rm -f feature_repo/registry.db

# E2E shortcuts
.PHONY: e2e e2e-all e2e-experiment

e2e:
	E2E_VERBOSE=1 pytest -q tests/e2e/test_e2e_quickstart.py -s
	E2E_VERBOSE=1 pytest -q tests/e2e/test_e2e_binance_batch.py -s -k binance_batch
	E2E_VERBOSE=1 pytest -q tests/e2e/test_e2e_streaming_binance.py -s -k streaming_binance

e2e-all: e2e
	@if [ -n "$$POLYGON_API_KEY" ]; then \
		echo "Running Polygon E2E..."; \
		E2E_VERBOSE=1 pytest -q tests/e2e/test_e2e_polygon_batch.py -s -k polygon_batch; \
		E2E_VERBOSE=1 pytest -q tests/e2e/test_e2e_streaming_polygon.py -s -k streaming_polygon; \
	else \
		echo "POLYGON_API_KEY not set; skipping Polygon E2E."; \
	fi

e2e-experiment:
	E2E_VERBOSE=1 pytest -q tests/e2e/test_e2e_experiment_training.py -s

