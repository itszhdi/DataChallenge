from typing import Literal

from pydantic import BaseModel


class EvaluateRequest(BaseModel):
    conversation_id: str


class BatchRequest(BaseModel):
    conversation_ids: list[str] | None = None
    dataset: str | None = None
    mode: Literal["evaluate", "reapply"] = "evaluate"
    only_missing: bool = False
