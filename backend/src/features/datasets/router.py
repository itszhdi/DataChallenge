import asyncio
import json

from fastapi import APIRouter, File, Query, UploadFile

from src import db
from src.features.datasets import service
from src.features.datasets.exceptions import InvalidDatasetPayload
from src.features.datasets.schemas import ImportRequest, ImportResult

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("")
async def list_datasets() -> list[dict]:
    return await asyncio.to_thread(db.list_datasets)


@router.post("/import")
async def import_from_api(body: ImportRequest) -> ImportResult:
    return await service.fetch_and_import(body.group_id)


@router.post("/upload")
async def import_from_file(file: UploadFile = File(...), dataset: str | None = Query(None)) -> ImportResult:
    try:
        payload = json.loads(await file.read())
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise InvalidDatasetPayload(f"файл не является JSON ({e})") from e
    return await asyncio.to_thread(service.import_payload, payload, dataset)
