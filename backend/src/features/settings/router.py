import asyncio

from fastapi import APIRouter

from src.config.settings import get_settings as get_env_settings
from src.dependencies import RegistryDep
from src.features.settings import service
from src.features.settings.schemas import SettingsPatch

router = APIRouter(prefix="/settings", tags=["settings"])


def _response(current, registry) -> dict:
    # * transcribe_enabled — из .env: фронт прячет выбор транскрипта звонков, когда распознавание выключено
    return {**current.model_dump(), "profiles": _profiles(registry), "transcribe_enabled": get_env_settings().transcribe_enabled}


def _profiles(registry) -> dict:
    return {
        name: {"provider": c.provider, "model": c.model, "base_url": c.profile.base_url if name == "local" else None,
               "active": name == registry.active_name}
        for name, c in registry.clients.items()
    }


@router.get("")
async def get_settings(registry: RegistryDep) -> dict:
    current = await asyncio.to_thread(service.load_app_settings)
    return _response(current, registry)


@router.put("")
@router.patch("")
async def update_settings(body: SettingsPatch, registry: RegistryDep) -> dict:
    # * PUT (фронт, весь объект) и PATCH (часть полей) — одно и то же частичное обновление
    current = await asyncio.to_thread(service.update, body, registry)
    return _response(current, registry)


@router.get("/models")
async def check_models(registry: RegistryDep) -> dict:
    # * Проверка доступности всех профилей: ключи Gemini и Luna, запущен ли LM Studio и загружена ли модель
    names = list(registry.clients)
    results = await asyncio.gather(*(registry.clients[n].ping() for n in names))
    return {n: {"model": registry.clients[n].model, **r} for n, r in zip(names, results)}
