from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ScaleStep(BaseModel):
    value: int
    description: str = ""


class Criterion(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")
    section: str
    title: str = Field(min_length=1)
    type: Literal["binary", "scale", "flag"]
    weight: float = Field(ge=0)
    na_allowed: bool = False
    na_condition: str = ""
    rule: str = ""
    scale: list[ScaleStep] = []
    guidance: str = ""
    examples_pass: list[str] = []
    examples_fail: list[str] = []
    flag_types: list[str] = []

    @model_validator(mode="after")
    def check_consistency(self) -> "Criterion":
        if self.type == "scale":
            values = [s.value for s in self.scale]
            if len(values) < 2 or len(set(values)) != len(values):
                raise ValueError(f"{self.id}: у шкалы должно быть ≥2 различных ступеней")
            if max(values) <= 0:
                raise ValueError(f"{self.id}: верхняя ступень шкалы должна быть > 0")
        if self.na_allowed and not self.na_condition.strip():
            raise ValueError(f"{self.id}: при na_allowed нужно условие N/A (na_condition)")
        if self.type != "scale" and not self.rule.strip():
            raise ValueError(f"{self.id}: нужно правило (rule)")
        return self


class Section(BaseModel):
    id: str
    title: str


class ChecklistData(BaseModel):
    name: str = "Чек-лист"
    settings: dict[str, Any] = Field(default_factory=lambda: {"first_response_threshold_sec": 180, "rounding": 2})
    sections: list[Section] = []
    criteria: list[Criterion] = Field(min_length=1)

    @model_validator(mode="after")
    def check_ids(self) -> "ChecklistData":
        ids = [c.id for c in self.criteria]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"повторяющиеся id критериев: {sorted(dupes)}")
        # * Секции, которых нет в списке, добавляем автоматически, чтобы UI мог просто указать название
        known = {s.id for s in self.sections}
        for c in self.criteria:
            if c.section not in known:
                self.sections.append(Section(id=c.section, title=c.section))
                known.add(c.section)
        return self


class SaveChecklistRequest(BaseModel):
    data: ChecklistData
    comment: str = ""


class WeightsRequest(BaseModel):
    weights: dict[str, float]
    reapply_all: bool = True
    comment: str = ""
