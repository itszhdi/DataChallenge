from fastapi import APIRouter

from src.features.worker import state

router = APIRouter(prefix="/worker", tags=["worker"])


@router.get("")
async def worker_status() -> dict:
    return state.snapshot()
