import asyncio
import json
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response

from src.dependencies import LLMDep
from src.features.export.service import build_export, export_filename, save_export

router = APIRouter(prefix="/export", tags=["export"])


@router.get("")
async def export_results(
    llm: LLMDep,
    dataset: str | None = None,
    team_name: str = Query("", max_length=200),
    model_mode: Literal["local", "remote"] | None = None,
    model_name: str | None = Query(None, max_length=200),
    download: bool = False,
) -> Response:
    mode = model_mode or ("local" if llm.profile.name == "local" else "remote")
    export = await asyncio.to_thread(build_export, dataset, team_name, mode, model_name or llm.model)
    if not download:
        return JSONResponse(export)
    # * Кнопка «Скачать»: браузер сохраняет файл сам, без сборки Blob на фронте
    headers = {"Content-Disposition": f'attachment; filename="{export_filename(export)}"'}
    return Response(json.dumps(export, ensure_ascii=False, indent=2), media_type="application/json", headers=headers)


@router.post("/save")
async def save_results(
    llm: LLMDep,
    dataset: str | None = None,
    team_name: str = Query("", max_length=200),
    model_mode: Literal["local", "remote"] | None = None,
    model_name: str | None = Query(None, max_length=200),
) -> dict:
    # * Сохраняет выгрузку в RESULTS_DIR (по умолчанию results/ в корне проекта)
    mode = model_mode or ("local" if llm.profile.name == "local" else "remote")
    export = await asyncio.to_thread(build_export, dataset, team_name, mode, model_name or llm.model)
    return await asyncio.to_thread(save_export, export)
