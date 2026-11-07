from typing import Literal

from pydantic import BaseModel, Field

AutoSort = Literal["date_asc", "date_desc", "size_asc", "size_desc"]
LLMProfileName = Literal["gemini", "local"]
# * asr — свой транскрипт из аудио (Gemini), original — транскрипт из датасета
CallTranscript = Literal["asr", "original"]
# * Звонки (диалоги с записью) в очереди авто-воркера: вперемешку, сначала или в конце
AutoCalls = Literal["mixed", "first", "last"]


class AppSettings(BaseModel):
    # * auto_mode=false — ручной режим (как раньше), true — воркер сам берёт неоценённые диалоги
    auto_mode: bool = False
    # * date — дата импорта + порядок записи в наборе; size — число реплик в транскрипте
    auto_sort: AutoSort = "date_asc"
    auto_calls: AutoCalls = "mixed"
    auto_dataset: str | None = Field(None, max_length=64)
    llm_profile: LLMProfileName = "gemini"
    call_transcript: CallTranscript = "asr"


class SettingsPatch(BaseModel):
    auto_mode: bool | None = None
    auto_sort: AutoSort | None = None
    auto_calls: AutoCalls | None = None
    auto_dataset: str | None = Field(None, max_length=64)
    llm_profile: LLMProfileName | None = None
    call_transcript: CallTranscript | None = None
