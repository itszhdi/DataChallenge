from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from src.features.datasets.utils import normalize_transcript


class Record(BaseModel):
    # ** Строго проверяем только id и то, что транскрипт — список; реплики нормализуются, а не отбраковываются
    conversation_id: str = Field(min_length=1)
    channel: str | None = None
    language: str | None = None
    transcript: list[Any]
    audio_url: str | None = None

    @field_validator("conversation_id", "channel", "language", "audio_url", mode="before")
    @classmethod
    def to_str(cls, v: Any) -> Any:
        if v is None or isinstance(v, str):
            return v.strip() if isinstance(v, str) else v
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return str(v)
        return None

    @field_validator("transcript", mode="after")
    @classmethod
    def normalize(cls, v: list[Any]) -> list[dict[str, Any]]:
        return normalize_transcript(v)


class ImportRequest(BaseModel):
    group_id: str | None = Field(None, min_length=1, max_length=64)
    # * Полная ссылка (если организаторы дали другой URL); иначе берётся DATASET_API_URL + group_id
    url: str | None = Field(None, pattern=r"^https://")

    @model_validator(mode="after")
    def check_source(self) -> "ImportRequest":
        if not self.group_id and not self.url:
            raise ValueError("нужен group_id или url")
        return self


class ImportResult(BaseModel):
    dataset: str
    imported: int
    skipped: int
    errors: list[str] = []
    warnings: list[str] = []
