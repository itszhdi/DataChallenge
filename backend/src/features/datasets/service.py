import asyncio
import logging
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from src import db
from src.config.settings import get_settings
from src.features.datasets.exceptions import DatasetFetchError, DatasetSourceNotConfigured, InvalidDatasetPayload
from src.features.datasets.schemas import ImportResult, Record

logger = logging.getLogger(__name__)


def dataset_url(base_url: str, group_id: str) -> str:
    # ! Дописываем group_id строкой: httpx params= затирает существующие параметры и подпись sig пропадает
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}group_id={quote(group_id, safe='')}"


def extract_records(payload: Any) -> tuple[str | None, list[Any]]:
    # * Принимаем полный ответ API, только data или голый список записей
    if isinstance(payload, list):
        return None, payload
    if not isinstance(payload, dict):
        raise InvalidDatasetPayload("ожидался JSON-объект или список")
    if payload.get("isSuccess") is False:
        raise InvalidDatasetPayload(payload.get("error") or "isSuccess=false")
    data = payload.get("data", payload)
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise InvalidDatasetPayload("нет поля data.records")
    return data.get("dataset_group_id"), data["records"]


def import_payload(payload: Any, dataset: str | None = None) -> ImportResult:
    group_id, raw_records = extract_records(payload)
    dataset = dataset or group_id or "UPLOAD"
    valid, errors = [], []
    for i, raw in enumerate(raw_records):
        try:
            valid.append(Record.model_validate(raw).model_dump())
        except ValidationError as e:
            cid = raw.get("conversation_id", f"#{i}") if isinstance(raw, dict) else f"#{i}"
            errors.append(f"{cid}: {e.errors()[0]['msg']}")
    imported = db.upsert_conversations(dataset, valid) if valid else 0
    logger.info("Dataset %s imported: %d ok, %d skipped", dataset, imported, len(errors))
    if errors:
        logger.warning("Dataset %s skipped records: %s", dataset, errors[:10])
    return ImportResult(dataset=dataset, imported=imported, skipped=len(errors), errors=errors)


async def fetch_and_import(group_id: str) -> ImportResult:
    base = get_settings().dataset_api_url
    if not base:
        raise DatasetSourceNotConfigured()
    url = dataset_url(base, group_id)
    logger.info("Fetching dataset group_id=%s", group_id)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        # ! Не логируем URL целиком — в нём секретная подпись
        logger.error("Dataset fetch failed for group_id=%s: %s", group_id, type(e).__name__)
        raise DatasetFetchError(type(e).__name__) from e
    return await asyncio.to_thread(import_payload, payload, group_id)
