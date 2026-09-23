"""Read-only dataset adapter for AI demos/evaluation; never imports or writes a database."""
import csv
from dataclasses import dataclass
from datetime import date, datetime, time
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, StrictInt, field_validator

from app.domain.models import (Employee, Event, GradeRequirement, Participation,
                               RecommendationContext, SkillEffect)
from app.domain.progress import apply_skill_effects

GRADE_ORDER = ("Junior", "Middle", "Senior", "Lead")  # Dataset README contract.


class GoalRow(BaseModel):
    target_role: str
    target_grade: str


class EmployeeRow(BaseModel):
    employee_id: str = Field(min_length=1)
    role: str
    grade: str
    tenure_months: StrictInt = Field(ge=0)
    skills: dict[str, StrictInt]
    preferred_language: Literal["ru", "kk", "en"] = "ru"
    last_review_date: date
    career_goal: GoalRow | None = None

    @field_validator("skills")
    @classmethod
    def levels(cls, value):
        if any(not key or not 0 <= level <= 5 for key, level in value.items()):
            raise ValueError("invalid skills")
        return value


class EffectRow(BaseModel):
    skill_id: str
    gain: StrictInt = Field(ge=0, le=5)
    max_level: StrictInt = Field(ge=0, le=5)


class EventRow(BaseModel):
    event_id: str = Field(min_length=1)
    title: str
    type: str
    format: Literal["online", "offline", "self_paced"]
    mandatory: bool
    target_roles: list[str]
    target_grades: list[str]
    develops_skills: list[EffectRow]
    prerequisites: dict[str, StrictInt]
    upcoming_sessions: list[date]


class RequirementRow(BaseModel):
    role: str
    grade: str
    required_skills: dict[str, StrictInt]
    critical_skills: list[str]


class HistoryRow(BaseModel):
    record_id: str = Field(min_length=1)
    employee_id: str
    event_id: str
    date: date
    status: Literal["completed", "in_progress", "dropped", "no_show", "declined", "overdue"]


def _unique(rows, key):
    result = {}
    for row in rows:
        identifier = key(row)
        if identifier in result:
            raise ValueError(f"duplicate dataset ID: {identifier}")
        result[identifier] = row
    return result


@dataclass(frozen=True)
class DatasetSnapshot:
    as_of: date
    employees: dict[str, EmployeeRow]
    events: dict[str, Event]
    requirements: dict[tuple[str, str], GradeRequirement]
    history: tuple[Participation, ...]
    skill_names: dict[str, str]

    @classmethod
    def load(cls, directory: str | Path) -> "DatasetSnapshot":
        directory = Path(directory)
        def read(name):
            with (directory / name).open(encoding="utf-8-sig") as handle:
                return json.load(handle)
        skill_data, employee_data, event_data = (read(name) for name in ("skills.json", "employees.json", "events.json"))
        as_of = date.fromisoformat(skill_data["meta"]["as_of_date"])
        if any(date.fromisoformat(data["meta"]["as_of_date"]) != as_of for data in (employee_data, event_data)):
            raise ValueError("dataset snapshot dates must match")
        catalog = _unique(skill_data["skills"], lambda row: row["skill_id"])
        names = {key: row["name"] for key, row in catalog.items()}
        employees = _unique([EmployeeRow.model_validate(row) for row in employee_data["employees"]], lambda row: row.employee_id)
        event_rows = _unique([EventRow.model_validate(row) for row in event_data["events"]], lambda row: row.event_id)
        requirements = _unique([RequirementRow.model_validate(row) for row in skill_data["role_profiles"]], lambda row: (row.role, row.grade))
        def check_skills(values):
            if not set(values) <= names.keys():
                raise ValueError("unknown skill reference")
            if any(type(value) is not int or not 0 <= value <= 5 for value in values.values()):
                raise ValueError("invalid skill level")
        events = {}
        for key, row in event_rows.items():
            check_skills(row.prerequisites)
            effects = tuple(SkillEffect(item.skill_id, item.gain, item.max_level) for item in row.develops_skills)
            if len({item.skill_id for item in effects}) != len(effects):
                raise ValueError("duplicate skill effects")
            if any(item.skill_id not in names for item in effects):
                raise ValueError("unknown effect skill")
            events[key] = Event(key, row.title, row.type, tuple(row.target_roles), tuple(row.target_grades), effects,
                                row.mandatory, row.prerequisites, row.format, tuple(row.upcoming_sessions), key == "EV_036")
        targets = {}
        for key, row in requirements.items():
            check_skills(row.required_skills)
            if row.grade not in GRADE_ORDER or not set(row.critical_skills) <= row.required_skills.keys():
                raise ValueError("invalid grade requirements")
            position = GRADE_ORDER.index(row.grade)
            next_grade = GRADE_ORDER[position + 1] if position + 1 < len(GRADE_ORDER) else None
            targets[key] = GradeRequirement(row.role, row.grade, next_grade, row.required_skills, tuple(row.critical_skills))
        for row in employees.values():
            check_skills(row.skills)
            if (row.role, row.grade) not in targets or row.last_review_date > as_of:
                raise ValueError("invalid employee grade or review date")
            if row.career_goal and (row.career_goal.target_role, row.career_goal.target_grade) not in targets:
                raise ValueError("unknown career goal")
        with (directory / "activity_history.csv").open(encoding="utf-8-sig", newline="") as handle:
            rows = _unique([HistoryRow.model_validate(row) for row in csv.DictReader(handle)], lambda row: row.record_id)
        history = []
        for row in rows.values():
            if row.employee_id not in employees or row.event_id not in events or row.date > as_of:
                raise ValueError("invalid history reference or future participation")
            history.append(Participation(row.record_id, row.employee_id, row.event_id, row.status,
                                         datetime.combine(row.date, time.min)))
        return cls(as_of, employees, events, targets,
                   tuple(sorted(history, key=lambda row: (row.occurred_at, row.participation_id))), names)

    def context_for(self, employee_id: str, locale: str | None = None) -> RecommendationContext:
        row = self.employees[employee_id]
        language = locale or row.preferred_language
        if language not in ("ru", "kk", "en"):
            raise ValueError("unsupported locale")
        history = tuple(item for item in self.history if item.employee_id == employee_id)
        # This reconstruction is for RAW assessment snapshots only. The DB service passes
        # already materialized current skills directly and must not replay history again.
        skills = {key: row.skills.get(key, 0) for key in self.skill_names}
        seen_completed = set()
        for item in history:
            if item.status != "completed":
                continue
            event = self.events[item.event_id]
            if item.event_id in seen_completed and not event.repeatable and not (event.mandatory and not event.effects):
                raise ValueError("non-repeatable event completed more than once")
            seen_completed.add(item.event_id)
            if item.occurred_at.date() > row.last_review_date:
                skills = apply_skill_effects(skills, event.effects)
        if row.career_goal:
            target = self.requirements[(row.career_goal.target_role, row.career_goal.target_grade)]
        else:
            next_grade = self.requirements[(row.role, row.grade)].next_grade
            target = self.requirements[(row.role, next_grade)] if next_grade else None
        return RecommendationContext(
            Employee(row.employee_id, row.role, row.grade, row.tenure_months, skills), target,
            history, tuple(self.events.values()), language, self.as_of,
        )
