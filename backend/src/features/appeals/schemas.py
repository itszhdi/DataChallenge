from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AppealCreate(BaseModel):
    criterion_id: str
    comment: str = Field(min_length=1, max_length=2000)


class AppealResolve(BaseModel):
    decision: Literal["upheld", "changed"]
    reason: str = Field(min_length=1, max_length=2000)
    value: int | None = None
    na: bool = False

    @model_validator(mode="after")
    def check_changed(self) -> "AppealResolve":
        if self.decision == "changed" and self.value is None and not self.na:
            raise ValueError("для decision=changed нужно value или na=true")
        return self
