from typing import Annotated

from fastapi import Depends, Request

from src.config.settings import Settings


def get_settings_dep(request: Request) -> Settings:
    return request.state.settings


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
