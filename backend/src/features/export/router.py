import asyncio
from typing import Literal

from fastapi import APIRouter, Query

from src.dependencies import LLMDep
from src.features.export.service import build_export

router = APIRouter(prefix="/export", tags=["export"])


@router.get("")
async def export_results(
    llm: LLMDep,
    dataset: str | None = None,
    team_name: str = Query("", max_length=200),
    model_mode: Literal["local", "remote"] | None = None,
    model_name: str | None = Query(None, max_length=200),
) -> dict:
    mode = model_mode or ("local" if llm.profile.name == "local" else "remote")
    return await asyncio.to_thread(build_export, dataset, team_name, mode, model_name or llm.model)
