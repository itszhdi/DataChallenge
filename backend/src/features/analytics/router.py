import asyncio

from fastapi import APIRouter

from src.features.analytics.service import build_analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("")
async def analytics(dataset: str | None = None) -> dict:
    return await asyncio.to_thread(build_analytics, dataset)
