import asyncio
from typing import Literal

from fastapi import APIRouter, status

from src.features.appeals import service
from src.features.appeals.schemas import AppealCreate, AppealResolve

router = APIRouter(tags=["appeals"])


@router.post("/evaluations/{evaluation_id}/appeals", status_code=status.HTTP_201_CREATED)
async def create_appeal(evaluation_id: int, body: AppealCreate) -> dict:
    return await asyncio.to_thread(service.create_appeal, evaluation_id, body)


@router.get("/appeals")
async def list_appeals(status: Literal["open", "resolved"] | None = None) -> list[dict]:
    return await asyncio.to_thread(service.list_appeals, status)


@router.post("/appeals/{appeal_id}/resolve")
async def resolve_appeal(appeal_id: int, body: AppealResolve) -> dict:
    return await asyncio.to_thread(service.resolve_appeal, appeal_id, body)
