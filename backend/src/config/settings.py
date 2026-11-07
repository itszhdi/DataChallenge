from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class LLMProfile:
    name: str
    provider: str
    api_key: str
    base_url: str
    model: str
    reasoning_effort: str
    min_interval_sec: float
    concurrency: int
    retries: int
    timeout_sec: float
    # * 0 — без ограничения длины ответа
    max_tokens: int = 0
    # * Повторять ли запрос после таймаута (локальной модели повтор почти никогда не помогает)
    retry_on_timeout: bool = True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # ** URL организаторов уже содержит подпись sig — хранить только в .env
    dataset_api_url: str = ""
    db_path: Path = BASE_DIR / "cqa.sqlite3"
    default_checklist_path: Path = BASE_DIR / "checklists" / "default_checklist.json"
    # * Куда сохраняются выгрузки результатов (POST /api/export/save)
    results_dir: Path = BASE_DIR.parent / "results"
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

    # * Локальная модель (LM Studio): второй профиль, переключается в /api/settings на лету
    local_llm_base_url: str = "http://localhost:1234/v1"
    local_llm_api_key: str = "lm-studio"
    local_llm_model: str = ""
    # ! Qwen3.5 по умолчанию «размышляет» тысячами токенов до JSON; LM Studio отключает это только через reasoning_effort=none
    local_llm_reasoning_effort: str = "none"
    local_llm_max_tokens: int = 3000
    local_llm_min_interval_sec: float = 0.0
    local_llm_concurrency: int = 1
    local_llm_retries: int = 2
    local_llm_timeout_sec: float = 600.0
    # * Профиль по умолчанию, пока его не сменили в настройках: gemini | local
    default_llm_profile: str = "gemini"
    worker_interval_sec: float = 5.0

    # * Каналы, которые не отправляются в модель (по умолчанию все разрешены: данные банка можно использовать)
    exclude_channels: list[str] = []

    # * Распознавание звонков через Gemini (аудио → транскрипт с ролями); ключ и адрес — из LLM_*
    transcribe_model: str = "gemini-3.8-flash"
    transcribe_reasoning_effort: str = "low"
    transcribe_timeout_sec: float = 600.0
    transcribe_max_audio_mb: float = 20.0

    # $ за 1M токенов: {"model": [input, output]}; бесплатный тариф = 0
    llm_prices: dict[str, list[float]] = Field(default_factory=dict)

    @property
    def resolved_base_url(self) -> str:
        if self.llm_base_url:
            return self.llm_base_url
        if self.llm_provider == "gemini":
            return "https://generativelanguage.googleapis.com/v1beta/openai/"
        return "http://localhost:1234/v1"


    def llm_profiles(self) -> dict[str, LLMProfile]:
        # ** Профиль gemini — это основной LLM_* (может быть и openai-совместимым), local — LOCAL_LLM_*
        return {
            "gemini": LLMProfile(
                "gemini", self.llm_provider, self.llm_api_key, self.resolved_base_url, self.llm_model,
                self.llm_reasoning_effort, self.llm_min_interval_sec, self.llm_concurrency, self.llm_retries, self.llm_timeout_sec,
            ),
            "local": LLMProfile(
                "local", "openai", self.local_llm_api_key, self.local_llm_base_url, self.local_llm_model,
                self.local_llm_reasoning_effort, self.local_llm_min_interval_sec, self.local_llm_concurrency,
                self.local_llm_retries, self.local_llm_timeout_sec, self.local_llm_max_tokens, False,
            ),
        }


    def transcribe_profile(self) -> LLMProfile:
        gemini = self.llm_profiles()["gemini"]
        return replace(
            gemini, name="transcribe", provider="gemini", model=self.transcribe_model,
            reasoning_effort=self.transcribe_reasoning_effort, timeout_sec=self.transcribe_timeout_sec, retries=1,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
