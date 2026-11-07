import asyncio

from fastapi import APIRouter, HTTPException, status

from src import db

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
