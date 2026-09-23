"""Internal contracts; dataset field mapping belongs in the import adapter."""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class SkillEffect:
    skill_id: str
    gain: int
    max_level: int

    def __post_init__(self) -> None:
        if not self.skill_id:
            raise ValueError("skill_id is required")
        if type(self.gain) is not int or not 0 <= self.gain <= 5:
            raise ValueError("gain must be an integer between 0 and 5")
        if type(self.max_level) is not int or not 0 <= self.max_level <= 5:
            raise ValueError("max_level must be an integer between 0 and 5")


@dataclass(frozen=True)
class Employee:
    employee_id: str
    role: str
    grade: str
    tenure_months: int
    skills: dict[str, int]


@dataclass(frozen=True)
class Event:
    event_id: str
    title: str
    event_type: str
    audience_roles: tuple[str, ...]
    audience_grades: tuple[str, ...]
    effects: tuple[SkillEffect, ...]


@dataclass(frozen=True)
class Participation:
    participation_id: str
    employee_id: str
    event_id: str
    status: Literal["completed", "missed", "declined", "registered"]
    occurred_at: datetime


@dataclass(frozen=True)
class GradeRequirement:
    role: str
    grade: str
    next_grade: str | None
    required_skills: dict[str, int]


@dataclass(frozen=True)
class RecommendationContext:
    employee: Employee
    target: GradeRequirement
    history: tuple[Participation, ...]
    candidates: tuple[Event, ...]
    locale: Literal["ru", "kk", "en"]


@dataclass(frozen=True)
class Recommendation:
    event_id: str
    explanation: str
    target_grade: str
    skill_gaps: dict[str, int]
    history_ids: tuple[str, ...]
    expected_gains: dict[str, int]


@dataclass(frozen=True)
class RankedRecommendation:
    event_id: str
    score: float
    target_grade: str
    skill_gaps: dict[str, int]
    expected_gains: dict[str, int]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class ExplanationContext:
    """Facts to serialize as explanation JSON; no employee identity needed."""

    locale: Literal["ru", "kk", "en"]
    recommendations: tuple[RankedRecommendation, ...]
