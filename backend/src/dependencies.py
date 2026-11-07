from typing import Annotated

from fastapi import Depends, Request

from src.config.settings import Settings
from src.llm.client import LLMClient


def get_settings_dep(request: Request) -> Settings:
    return request.state.settings


def get_llm(request: Request) -> LLMClient:
    return request.state.llm


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
LLMDep = Annotated[LLMClient, Depends(get_llm)]
