import asyncio
import logging
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from src import db
from src.config.settings import get_settings
from src.features.datasets.exceptions import DatasetFetchError, DatasetSourceNotConfigured, InvalidDatasetPayload
from src.features.datasets.schemas import ImportResult, Record, SourceCheck

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
    valid: dict[str, dict[str, Any]] = {}
    errors, warnings = [], []
    for i, raw in enumerate(raw_records):
        try:
            record = Record.model_validate(raw).model_dump()
        except ValidationError as e:
            cid = raw.get("conversation_id", f"#{i}") if isinstance(raw, dict) else f"#{i}"
            errors.append(f"{cid}: {e.errors()[0]['loc'][0]} — {e.errors()[0]['msg']}")
            continue
        cid, tr = record["conversation_id"], record["transcript"]
        if cid in valid:
            warnings.append(f"{cid}: повтор id в файле — оставлена последняя запись")
        if not tr:
            hint = "будет распознан из записи" if record.get("audio_url") else "оценка невозможна"
            warnings.append(f"{cid}: пустой транскрипт — {hint}")
        notes = [
            (sum(1 for m in tr if m.get("attachments")), "вложений"),
            (sum(1 for m in tr if m["speaker"] == "unknown"), "реплик с неизвестной ролью"),
            (sum(1 for m in tr if m.get("empty")), "пустых реплик"),
            (sum(1 for m in tr if not m.get("timestamp")), "реплик без времени"),
        ]
        warnings += [f"{cid}: {n} {label}" for n, label in notes if n]
        record["seq"] = i
        valid[cid] = record
    imported = db.upsert_conversations(dataset, list(valid.values())) if valid else 0
    logger.info("Dataset %s imported: %d ok, %d skipped, %d warnings", dataset, imported, len(errors), len(warnings))
    if errors:
        logger.warning("Dataset %s skipped records: %s", dataset, errors[:10])
    return ImportResult(dataset=dataset, imported=imported, skipped=len(errors), errors=errors, warnings=warnings)


async def fetch_payload(group_id: str | None, url: str | None = None) -> Any:
    custom = url is not None
    if not url:
        base = get_settings().dataset_api_url
        if not base:
            raise DatasetSourceNotConfigured()
        url = dataset_url(base, group_id)
    logger.info("Fetching dataset group_id=%s custom_url=%s", group_id, custom)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        # ! Не логируем URL целиком — в нём секретная подпись
        logger.error("Dataset fetch failed for group_id=%s: %s", group_id, type(e).__name__)
        raise DatasetFetchError(type(e).__name__) from e
    return payload


async def fetch_and_import(group_id: str | None, url: str | None = None) -> ImportResult:
    payload = await fetch_payload(group_id, url)
    return await asyncio.to_thread(import_payload, payload, group_id)


async def check_source(group_id: str) -> SourceCheck:
    # * Проверка подключения: скачиваем набор, но ничего не записываем в БД
    remote_id, records = extract_records(await fetch_payload(group_id))
    return SourceCheck(dataset=remote_id or group_id, total_records=len(records))
