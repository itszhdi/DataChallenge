from pydantic import BaseModel, Field


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
    group_id: str = Field(min_length=1, max_length=64)


class ImportResult(BaseModel):
    dataset: str
    imported: int
    skipped: int
    errors: list[str] = []
