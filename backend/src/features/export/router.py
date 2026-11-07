import asyncio
from typing import Literal

from fastapi import APIRouter, Query

from src.dependencies import SettingsDep
from src.features.export.service import build_export

router = APIRouter(prefix="/export", tags=["export"])


@router.get("")
async def export_results(
    settings: SettingsDep,
    dataset: str | None = None,
    team_name: str = Query("", max_length=200),
    model_mode: Literal["local", "remote"] | None = None,
    model_name: str | None = Query(None, max_length=200),
) -> dict:
    mode = model_mode or ("remote" if settings.llm_provider == "gemini" else "local")
    return await asyncio.to_thread(build_export, dataset, team_name, mode, model_name or settings.llm_model)
