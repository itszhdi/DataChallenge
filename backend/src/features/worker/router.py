import logging

from fastapi import APIRouter

from src.features.worker import service, state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/worker", tags=["worker"])


@router.get("")
async def worker_status() -> dict:
    return state.snapshot()


@router.post("/stop")
async def stop_worker() -> dict:
    interrupted = await service.stop()
    logger.info("Auto worker stopped by user (interrupted=%s)", interrupted)
    return {**state.snapshot(), "interrupted": interrupted}
