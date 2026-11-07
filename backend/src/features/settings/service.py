import logging
from typing import Any

from src import db
from src.config.settings import get_settings
from src.features.settings.schemas import AppSettings, SettingsPatch

logger = logging.getLogger(__name__)


def load() -> AppSettings:
    stored = db.get_app_settings()
    stored.setdefault("llm_profile", get_settings().default_llm_profile)
    return AppSettings.model_validate(stored)


def update(patch: SettingsPatch) -> AppSettings:
    # ** auto_dataset можно сбросить в null явно, поэтому берём именно переданные поля
    changes: dict[str, Any] = patch.model_dump(exclude_unset=True)
    current = load().model_dump()
    current.update(changes)
    validated = AppSettings.model_validate(current)
    db.set_app_settings(validated.model_dump())
    logger.info("Settings updated: %s", changes)
    return validated
