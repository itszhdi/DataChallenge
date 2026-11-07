import asyncio

from fastapi import APIRouter

from src.dependencies import LLMDep
from src.features.settings.schemas import AppSettings
from src.features.settings.service import load_app_settings, save_app_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_app_settings() -> AppSettings:
    return await asyncio.to_thread(load_app_settings)


@router.put("")
async def update_app_settings(body: AppSettings, llm: LLMDep) -> AppSettings:
    return await asyncio.to_thread(save_app_settings, llm, body)
