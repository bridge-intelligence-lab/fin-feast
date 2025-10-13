PY=python
PIP=pip

.PHONY: setup up down apply materialize synth-daily synth-minute poly-daily poly-minute train-ds query prune test lint format

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
	cd feature_repo && rm -f registry.db && FEAST_DISABLE_ODFV=1 feast apply

test:
	pytest -q

materialize:
	$(PY) scripts/materialize_incremental.py

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
