import asyncio

from fastapi import APIRouter, HTTPException, status

from src import db
from src.dependencies import LLMDep
from src.features.checklists import service
from src.features.checklists.schemas import SaveChecklistRequest, WeightsRequest
from src.features.evaluation.service import reapply_many

router = APIRouter(prefix="/checklists", tags=["checklists"])


@router.get("")
async def list_checklists() -> list[dict]:
    return await asyncio.to_thread(db.list_checklists)


@router.get("/active")
async def get_active() -> dict:
    checklist = await asyncio.to_thread(db.get_active_checklist)
    if not checklist:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Активный чек-лист не найден")
    return checklist


@router.get("/{checklist_id}")
async def get_checklist(checklist_id: int) -> dict:
    checklist = await asyncio.to_thread(db.get_checklist, checklist_id)
    if not checklist:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Чек-лист не найден")
    return checklist


@router.post("", status_code=status.HTTP_201_CREATED)
async def save_checklist(body: SaveChecklistRequest) -> dict:
    # * Каждое сохранение — новая активная версия; старые оценки переводятся на неё через reapply
    return await asyncio.to_thread(service.save_checklist, body.data, body.comment)


@router.patch("/active/weights")
async def update_weights(body: WeightsRequest, llm: LLMDep) -> dict:
    try:
        result = await asyncio.to_thread(service.update_weights, body.weights, body.comment)
    except LookupError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    if body.reapply_all:
        # ** Только веса изменились — модель не вызывается, ответы копируются
        result["reapplied"] = await reapply_many(llm, None)
    return result


@router.post("/{checklist_id}/activate")
async def activate(checklist_id: int) -> dict:
    if not await asyncio.to_thread(db.activate_checklist, checklist_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Чек-лист не найден")
    return await asyncio.to_thread(db.get_checklist, checklist_id)
