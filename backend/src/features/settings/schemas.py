from typing import Literal

from pydantic import BaseModel, Field

AutoSort = Literal["date_asc", "date_desc", "size_asc", "size_desc"]
LLMProfileName = Literal["gemini", "local"]


class AppSettings(BaseModel):
    # * auto_mode=false — ручной режим (как раньше), true — воркер сам берёт неоценённые диалоги
    auto_mode: bool = False
    # * date — дата импорта + порядок записи в наборе; size — число реплик в транскрипте
    auto_sort: AutoSort = "date_asc"
    auto_dataset: str | None = Field(None, max_length=64)
    llm_profile: LLMProfileName = "gemini"


class SettingsPatch(BaseModel):
    auto_mode: bool | None = None
    auto_sort: AutoSort | None = None
    auto_dataset: str | None = Field(None, max_length=64)
    llm_profile: LLMProfileName | None = None
