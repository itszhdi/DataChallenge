import asyncio
import json

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response

from src.dependencies import LLMDep
from src.features.export.submission import Target, build_submission, default_target, save_submission, validate_submission

router = APIRouter(prefix="/export", tags=["export"])


def _submission(dataset: str, team_name: str, target: Target, fallback_model: str) -> dict:
    submission = build_submission(dataset, team_name, fallback_model)
    return {"submission": submission, "target": target, "check": validate_submission(submission, dataset, target)}


@router.get("/submission")
async def preview_submission(
    llm: LLMDep,
    dataset: str = Query(min_length=1),
    target: Target | None = None,
    team_name: str = Query("", max_length=200),
    download: bool = False,
) -> Response:
    # * Файл для сдачи организаторам (формат JSON 1.0) и результат его проверки; download — сам results.json
    result = await asyncio.to_thread(_submission, dataset, team_name, target or default_target(dataset), llm.model)
    if not download:
        return JSONResponse(result)
    body = json.dumps(result["submission"], ensure_ascii=False, indent=2) + "\n"
    headers = {"Content-Disposition": 'attachment; filename="results.json"'}
    return Response(body, media_type="application/json; charset=utf-8", headers=headers)


@router.post("/submission/save")
async def save_submission_file(
    llm: LLMDep,
    dataset: str = Query(min_length=1),
    target: Target | None = None,
    team_name: str = Query("", max_length=200),
) -> dict:
    # ! При блокирующих ошибках файл не записывается: битый results.json хуже, чем отсутствующий
    target = target or default_target(dataset)
    result = await asyncio.to_thread(_submission, dataset, team_name, target, llm.model)
    check = result["check"]
    if check["errors"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"message": "Файл не прошёл проверку", **check})
    path = await asyncio.to_thread(save_submission, result["submission"], target)
    return {"path": str(path), "target": target, **check}
