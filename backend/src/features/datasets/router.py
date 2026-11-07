import asyncio
import json
import logging

from fastapi import APIRouter, File, Query, UploadFile

from src import db
from src.dependencies import LLMDep
from src.features.datasets import service
from src.features.datasets.exceptions import InvalidDatasetPayload
from src.features.datasets.schemas import ImportRequest, ImportResult, SourceCheck
from src.features.evaluation.exceptions import JobAlreadyRunning
from src.features.evaluation.service import start_batch
from src.features.settings.service import load_app_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/datasets", tags=["datasets"])


async def with_auto_evaluation(result: ImportResult, llm: LLMDep) -> ImportResult:
    # * Автооценка после импорта: очередь строится по текущим настройкам
    app = await asyncio.to_thread(load_app_settings)
    if app.auto_evaluate_on_import and result.imported:
        try:
            job = await start_batch(llm, result.dataset, only_missing=app.only_missing)
            result.job_id = job["id"]
        except JobAlreadyRunning:
            logger.info("Auto evaluation skipped for %s: another job is running", result.dataset)
    return result


@router.get("")
async def list_datasets() -> list[dict]:
    return await asyncio.to_thread(db.list_datasets)


@router.get("/check")
async def check_source(group_id: str = Query(min_length=1, max_length=64)) -> SourceCheck:
    return await service.check_source(group_id)


@router.post("/import")
async def import_from_api(body: ImportRequest, llm: LLMDep) -> ImportResult:
    return await with_auto_evaluation(await service.fetch_and_import(body.group_id, body.url), llm)


@router.post("/upload")
async def import_from_file(llm: LLMDep, file: UploadFile = File(...), dataset: str | None = Query(None)) -> ImportResult:
    try:
        payload = json.loads(await file.read())
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise InvalidDatasetPayload(f"файл не является JSON ({e})") from e
    return await with_auto_evaluation(await asyncio.to_thread(service.import_payload, payload, dataset), llm)
