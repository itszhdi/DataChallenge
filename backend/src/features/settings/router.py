import asyncio

from fastapi import APIRouter

from src.dependencies import RegistryDep
from src.features.settings import service
from src.features.settings.schemas import SettingsPatch

router = APIRouter(prefix="/settings", tags=["settings"])


def _profiles(registry) -> dict:
    return {
        name: {"provider": c.provider, "model": c.model, "base_url": c.profile.base_url if name == "local" else None,
               "active": name == registry.active_name}
        for name, c in registry.clients.items()
    }


@router.get("")
async def get_settings(registry: RegistryDep) -> dict:
    current = await asyncio.to_thread(service.load)
    return {**current.model_dump(), "profiles": _profiles(registry)}


@router.patch("")
async def patch_settings(body: SettingsPatch, registry: RegistryDep) -> dict:
    current = await asyncio.to_thread(service.update, body)
    registry.use(current.llm_profile)
    return {**current.model_dump(), "profiles": _profiles(registry)}


@router.get("/models")
async def check_models(registry: RegistryDep) -> dict:
    # * Проверка доступности обоих профилей: ключ Gemini, запущен ли LM Studio и загружена ли модель
    names = list(registry.clients)
    results = await asyncio.gather(*(registry.clients[n].ping() for n in names))
    return {n: {"model": registry.clients[n].model, **r} for n, r in zip(names, results)}
