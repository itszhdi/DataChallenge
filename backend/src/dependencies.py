from typing import Annotated

from fastapi import Depends, Request

from src.config.settings import Settings
from src.llm.client import LLMClient, LLMRegistry


def get_settings_dep(request: Request) -> Settings:
    return request.state.settings


def get_registry(request: Request) -> LLMRegistry:
    return request.state.llm


def get_llm(request: Request) -> LLMClient:
    # * Активный профиль на момент запроса (переключается в /api/settings)
    return request.state.llm.active()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
RegistryDep = Annotated[LLMRegistry, Depends(get_registry)]
LLMDep = Annotated[LLMClient, Depends(get_llm)]
