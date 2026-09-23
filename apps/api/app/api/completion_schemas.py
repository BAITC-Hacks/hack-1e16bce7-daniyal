import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: str | None = Field(default=None, min_length=1)
    session_date: dt.date | None = None

    @model_validator(mode="after")
    def exclusive_target(self):
        if self.record_id is not None and self.session_date is not None:
            raise ValueError("Choose record_id or session_date, not both")
        return self


class SkillChange(BaseModel):
    skill_id: str
    name: str
    before: int
    after: int


class CompletionResponse(BaseModel):
    event_id: str
    record_id: str
    already_completed: bool
    changes: list[SkillChange]
    career_readiness_before: float | None = None
    career_readiness_after: float | None = None
