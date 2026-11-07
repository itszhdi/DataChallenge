from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # ** URL организаторов уже содержит подпись sig — хранить только в .env
    dataset_api_url: str = ""
    db_path: Path = BASE_DIR / "cqa.sqlite3"
    default_checklist_path: Path = BASE_DIR / "checklists" / "default_checklist.json"
    cors_origins: list[str] = ["*"]
    log_level: str = "INFO"

    # LLM: gemini | openai (LM Studio и любой OpenAI-совместимый сервер)
    llm_provider: str = "gemini"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "gemini-3.6-flash"
    llm_reasoning_effort: str = "low"
    llm_min_interval_sec: float = 7.0
    llm_concurrency: int = 1
    llm_retries: int = 2
    llm_timeout_sec: float = 120.0

    # ! На бесплатном тарифе Google использует запросы для обучения — реальные звонки не отправляем
    exclude_channels: list[str] = ["voice call"]

    # Целевой индекс качества на дашборде супервайзера
    cqa_target_score: float = 85.0

    # $ за 1M токенов: {"model": [input, output]}; бесплатный тариф = 0
    llm_prices: dict[str, list[float]] = Field(default_factory=dict)

    @property
    def resolved_base_url(self) -> str:
        if self.llm_base_url:
            return self.llm_base_url
        if self.llm_provider == "gemini":
            return "https://generativelanguage.googleapis.com/v1beta/openai/"
        return "http://localhost:1234/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
