from typing import Literal

from pydantic import BaseModel, Field

# * Порядок очереди — общий для пакетной оценки и авто-воркера: по длине (число реплик) или по дате импорта
QueueSort = Literal["short_first", "long_first", "newest_first", "oldest_first"]
LLMProfileName = Literal["gemini", "luna", "local"]
# * asr — свой транскрипт из аудио (Gemini), original — транскрипт из датасета
CallTranscript = Literal["asr", "original"]
# * Звонки (диалоги с записью) в очереди авто-воркера: вперемешку, сначала или в конце
AutoCalls = Literal["mixed", "first", "last"]


class AppSettings(BaseModel):
    queue_sort: QueueSort = "short_first"
    only_missing: bool = True
    include_errors: bool = False
    concurrency: int = Field(1, ge=1, le=5)
    # ** Пауза между запросами к модели; для профиля не опускается ниже его *_MIN_INTERVAL_SEC (лимиты Gemini free)
    request_delay_ms: int = Field(500, ge=0, le=60_000)
    auto_evaluate_on_import: bool = False
    default_group_id: str = Field("DEV", min_length=1, max_length=64)
    # * auto_mode=false — ручной режим, true — воркер сам берёт неоценённые диалоги
    auto_mode: bool = False
    auto_calls: AutoCalls = "mixed"
    auto_dataset: str | None = Field(None, max_length=64)
    llm_profile: LLMProfileName = "gemini"
    call_transcript: CallTranscript = "asr"


class SettingsPatch(BaseModel):
    # * Частичное обновление: PUT от фронта присылает весь объект, PATCH — только изменённые поля
    queue_sort: QueueSort | None = None
    only_missing: bool | None = None
    include_errors: bool | None = None
    concurrency: int | None = Field(None, ge=1, le=5)
    request_delay_ms: int | None = Field(None, ge=0, le=60_000)
    auto_evaluate_on_import: bool | None = None
    default_group_id: str | None = Field(None, min_length=1, max_length=64)
    auto_mode: bool | None = None
    auto_calls: AutoCalls | None = None
    auto_dataset: str | None = Field(None, max_length=64)
    llm_profile: LLMProfileName | None = None
    call_transcript: CallTranscript | None = None
