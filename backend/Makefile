.PHONY: install run test import-dev upload clean-db

PORT ?= 8000

install:
	uv sync

run:
	uv run uvicorn src.main:app --reload --port $(PORT) --loop uvloop --http httptools

test:
	uv run pytest -q

import-dev:
	curl -s -X POST localhost:$(PORT)/api/datasets/import -H 'Content-Type: application/json' -d '{"group_id":"DEV"}'

upload:
	curl -s -X POST "localhost:$(PORT)/api/datasets/upload?dataset=$(DATASET)" -F "file=@$(FILE)"

clean-db:
	rm -f cqa.sqlite3 cqa.sqlite3-wal cqa.sqlite3-shm
