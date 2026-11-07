from pydantic import BaseModel, Field, model_validator


class Message(BaseModel):
    timestamp: str | None = None
    speaker: str
    text: str = ""


class Record(BaseModel):
    conversation_id: str
    channel: str | None = None
    language: str | None = None
    transcript: list[Message]
    audio_url: str | None = None


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
