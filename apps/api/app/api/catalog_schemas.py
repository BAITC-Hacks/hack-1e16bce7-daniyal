"""Read contracts shared by the HR directory and activity catalog."""
import datetime as dt

from pydantic import BaseModel, ConfigDict


class HREmployee(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    employee_id: str
    full_name: str
    role: str
    grade: str
    tenure_months: int
    department: str
    career_readiness: float | None = None


class EventEffect(BaseModel):
    skill_id: str
    name: str
    gain: int
    max_level: int


class PreviewSkill(BaseModel):
    skill_id: str
    name: str
    current_level: int
    required_level: int | None
    predicted_level: int


class EventPreview(BaseModel):
    skills: list[PreviewSkill]
    career_readiness_before: float | None
    career_readiness_after: float | None


class CatalogEvent(BaseModel):
    event_id: str
    title: str
    description: str
    type: str
    format: str
    duration_hours: float
    mandatory: bool
    repeatable: bool
    target_roles: list[str]
    target_grades: list[str]
    upcoming_sessions: list[dt.date]
    prerequisites: dict[str, int]
    develops_skills: list[EventEffect]

    preview: EventPreview | None = None
