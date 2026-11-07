.PHONY: install run test import-dev upload eval batch job analytics clean-db docker-build docker-up docker-down docker-logs

PORT ?= 8000

install:
	uv sync

run:
	uv run uvicorn src.main:app --reload --port $(PORT) --loop asyncio --http httptools

test:
	uv run pytest -q

import-dev:
	@curl -s -X POST localhost:$(PORT)/api/datasets/import -H 'Content-Type: application/json' -d '{"group_id":"DEV"}'

upload:
	@curl -s -X POST "localhost:$(PORT)/api/datasets/upload?dataset=$(DATASET)" -F "file=@$(FILE)"

eval:
	@curl -s -X POST localhost:$(PORT)/api/evaluate -H 'Content-Type: application/json' -d '{"conversation_id":"$(ID)"}'

batch:
	@curl -s -X POST localhost:$(PORT)/api/evaluate/batch -H 'Content-Type: application/json' -d '{"dataset":"$(or $(DATASET),DEV)","mode":"$(or $(MODE),evaluate)","only_missing":$(or $(ONLY_MISSING),false)}'

job:
	@curl -s localhost:$(PORT)/api/jobs/$(JOB)

analytics:
	@curl -s "localhost:$(PORT)/api/analytics?dataset=$(DATASET)"

docker-build:
	docker compose build

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f api

clean-db:
	rm -f cqa.sqlite3 cqa.sqlite3-wal cqa.sqlite3-shm
