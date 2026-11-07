import logging

from src import db
from src.features.settings.schemas import AppSettings
from src.llm.client import LLMClient

logger = logging.getLogger(__name__)


def load_app_settings() -> AppSettings:
    return AppSettings.model_validate(db.get_app_settings() or {})


def apply_app_settings(llm: LLMClient, settings: AppSettings) -> None:
    llm.configure(settings.concurrency, settings.request_delay_ms / 1000)


def save_app_settings(llm: LLMClient, settings: AppSettings) -> AppSettings:
    db.save_app_settings(settings.model_dump())
    apply_app_settings(llm, settings)
    logger.info("App settings saved: %s", settings.model_dump())
    return settings
