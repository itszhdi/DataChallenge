import logging
from typing import Any

from src import db
from src.config.settings import get_settings
from src.features.settings.schemas import AppSettings, SettingsPatch
from src.llm.client import LLMRegistry

logger = logging.getLogger(__name__)


def load_app_settings() -> AppSettings:
    stored = db.get_app_settings()
    stored.setdefault("llm_profile", get_settings().default_llm_profile)
    # * Поля, которых больше нет в схеме (старые версии), игнорируются
    return AppSettings.model_validate({k: v for k, v in stored.items() if k in AppSettings.model_fields})


def apply_app_settings(registry: LLMRegistry, settings: AppSettings) -> None:
    registry.configure(settings.concurrency, settings.request_delay_ms / 1000)
    registry.use(settings.llm_profile)


def update(patch: SettingsPatch, registry: LLMRegistry | None = None) -> AppSettings:
    # ** Берём только переданные поля: auto_dataset можно явно сбросить в null
    changes: dict[str, Any] = patch.model_dump(exclude_unset=True)
    current = load_app_settings().model_dump()
    current.update(changes)
    validated = AppSettings.model_validate(current)
    db.set_app_settings(validated.model_dump())
    if registry is not None:
        apply_app_settings(registry, validated)
    logger.info("Settings updated: %s", changes)
    return validated
