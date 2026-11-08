import asyncio
import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response

from src.dependencies import LLMDep
from src.features.export.service import build_export, export_filename, save_export
from src.features.export.submission import Target, build_submission, save_submission, validate_submission

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


def _submission(dataset: str, team_name: str, target: Target, fallback_model: str) -> dict:
    submission = build_submission(dataset, team_name, fallback_model)
    return {"submission": submission, "check": validate_submission(submission, dataset, target)}


@router.get("/submission")
async def preview_submission(
    llm: LLMDep, dataset: str = Query(min_length=1), target: Target = "dev", team_name: str = Query("", max_length=200)
) -> dict:
    # * Файл для сдачи организаторам (формат JSON 1.0) и результат его проверки, без записи на диск
    return await asyncio.to_thread(_submission, dataset, team_name, target, llm.model)


@router.post("/submission/save")
async def save_submission_file(
    llm: LLMDep, dataset: str = Query(min_length=1), target: Target = "dev", team_name: str = Query("", max_length=200)
) -> dict:
    # ! При блокирующих ошибках файл не записывается: битый results.json хуже, чем отсутствующий
    result = await asyncio.to_thread(_submission, dataset, team_name, target, llm.model)
    check = result["check"]
    if check["errors"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"message": "Файл не прошёл проверку", **check})
    path = await asyncio.to_thread(save_submission, result["submission"], target)
    return {"path": str(path), **check}
