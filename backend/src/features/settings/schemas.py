from typing import Literal

from pydantic import BaseModel, Field

QueueSort = Literal["short_first", "long_first", "newest_first", "oldest_first"]


class AppSettings(BaseModel):
    queue_sort: QueueSort = "short_first"
    only_missing: bool = True
    include_errors: bool = False
    concurrency: int = Field(1, ge=1, le=5)
    request_delay_ms: int = Field(500, ge=0, le=60_000)
    auto_evaluate_on_import: bool = False
    default_group_id: str = Field("DEV", min_length=1, max_length=64)
