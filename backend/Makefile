.PHONY: install run test import-dev upload eval batch job jobs queue retry-failed settings models use-gemini use-local auto-on auto-off worker save-results transcribe analytics golden clean-db docker-build docker-up docker-down docker-logs

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

golden:
	@uv run python -m src.cli golden $(or $(FILE),tests/golden.csv) $(if $(PROFILE),--profile $(PROFILE)) $(if $(LIMIT),--limit $(LIMIT))

docker-build:
	docker compose build

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f api

jobs:
	@curl -s localhost:$(PORT)/api/jobs

queue:
	@curl -s "localhost:$(PORT)/api/queue?dataset=$(DATASET)"

retry-failed:
	@curl -s -X POST localhost:$(PORT)/api/evaluate/batch -H 'Content-Type: application/json' -d '{"only_failed":true}'

settings:
	@curl -s localhost:$(PORT)/api/settings

models:
	@curl -s localhost:$(PORT)/api/settings/models

use-gemini:
	@curl -s -X PATCH localhost:$(PORT)/api/settings -H 'Content-Type: application/json' -d '{"llm_profile":"gemini"}'

use-local:
	@curl -s -X PATCH localhost:$(PORT)/api/settings -H 'Content-Type: application/json' -d '{"llm_profile":"local"}'

# * SORT: short_first | long_first | newest_first | oldest_first (общий порядок пакета и воркера); CALLS: mixed | first | last
auto-on:
	@curl -s -X PATCH localhost:$(PORT)/api/settings -H 'Content-Type: application/json' -d '{"auto_mode":true,"queue_sort":"$(or $(SORT),short_first)","auto_calls":"$(or $(CALLS),mixed)"}'

auto-off:
	@curl -s -X PATCH localhost:$(PORT)/api/settings -H 'Content-Type: application/json' -d '{"auto_mode":false}'

worker:
	@curl -s localhost:$(PORT)/api/worker

# * Сохраняет результаты набора в results/<DATASET>_<время>.json и <DATASET>_latest.json
save-results:
	@curl -s -X POST "localhost:$(PORT)/api/export/save?dataset=$(or $(DATASET),DEV)&team_name=$(TEAM)"

# * Заново распознать запись звонка: make transcribe ID=DEV:p4-ru-002
transcribe:
	@curl -s -X POST "localhost:$(PORT)/api/conversations/$(ID)/transcribe"

clean-db:
	rm -f cqa.sqlite3 cqa.sqlite3-wal cqa.sqlite3-shm
