"""Validated contracts for the supplied JSON/CSV dataset, independent of SQL."""
import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Level = Annotated[int, Field(strict=True, ge=0, le=5)]
Identifier = Annotated[str, Field(min_length=1, max_length=200)]
Grade = Literal["Junior", "Middle", "Senior", "Lead"]
GRADES = ("Junior", "Middle", "Senior", "Lead")
Status = Literal["completed", "in_progress", "dropped", "no_show", "declined", "overdue"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Meta(Contract):
    dataset: str
    version: str
    as_of_date: dt.date


class Skill(Contract):
    skill_id: Identifier
    name: Identifier
    type: Literal["hard", "soft"]
    category: Identifier
    description: str


class RoleProfile(Contract):
    role: Identifier
    grade: Grade
    required_skills: dict[Identifier, Level]
    critical_skills: list[Identifier]


class SkillCatalog(Contract):
    meta: Meta
    proficiency_scale: dict[str, str]
    skills: list[Skill] = Field(min_length=1)
    role_profiles: list[RoleProfile] = Field(min_length=1)


class CareerGoal(Contract):
    target_role: Identifier
    target_grade: Grade


class Employee(Contract):
    employee_id: Identifier
    full_name: Identifier
    department: Identifier
    role: Identifier
    grade: Grade
    manager_id: Identifier | None
    hire_date: dt.date
    tenure_months: int = Field(strict=True, ge=0)
    work_format: Literal["office", "hybrid", "remote"]
    preferred_language: Literal["ru", "kk", "en"]
    career_goal: CareerGoal | None
    skills: dict[Identifier, Level]
    last_review_date: dt.date


class Employees(Contract):
    meta: Meta
    employees: list[Employee]


class Effect(Contract):
    skill_id: Identifier
    gain: Level
    max_level: Level


class Event(Contract):
    event_id: Identifier
    title: Identifier
    description: str
    type: Literal["compliance", "onboarding", "course", "workshop", "mentoring", "certification", "meetup"]
    format: Literal["online", "offline", "self_paced"]
    duration_hours: float = Field(gt=0, allow_inf_nan=False)
    mandatory: bool = Field(strict=True)
    target_roles: list[Identifier]
    target_grades: list[Grade]
    develops_skills: list[Effect]
    prerequisites: dict[Identifier, Level]
    upcoming_sessions: list[dt.date]


class Events(Contract):
    meta: Meta
    events: list[Event]


class HistoryRecord(Contract):
    record_id: Identifier
    employee_id: Identifier
    event_id: Identifier
    date: dt.date
    due_date: dt.date | None
    status: Status
    completion_pct: int = Field(strict=True, ge=0, le=100)
    score: Annotated[int, Field(strict=True, ge=0, le=100)] | None
    feedback_rating: Annotated[int, Field(strict=True, ge=1, le=5)] | None
    assigned_by: Literal["self", "manager", "hr"]

    @model_validator(mode="after")
    def consistent_status(self):
        limits = {"completed": (100, 100), "in_progress": (0, 95), "dropped": (5, 95),
                  "no_show": (0, 0), "declined": (0, 0), "overdue": (0, 95)}
        low, high = limits[self.status]
        if not low <= self.completion_pct <= high:
            raise ValueError(f"{self.record_id}: completion_pct conflicts with {self.status}")
        return self


def unique(values, label):
    values = list(values)
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {label}")
    return set(values)


class Dataset(Contract):
    catalog: SkillCatalog
    employees: Employees
    events: Events
    history: list[HistoryRecord]

    @model_validator(mode="after")
    def references(self):
        if not self.catalog.meta == self.employees.meta == self.events.meta:
            raise ValueError("dataset metadata must match across JSON files")
        if set(self.catalog.proficiency_scale) != {str(i) for i in range(6)}:
            raise ValueError("proficiency_scale must describe levels 0–5")
        skills = unique((s.skill_id for s in self.catalog.skills), "skill_id")
        employees = {e.employee_id: e for e in self.employees.employees}
        unique((e.employee_id for e in self.employees.employees), "employee_id")
        events = {e.event_id: e for e in self.events.events}
        unique((e.event_id for e in self.events.events), "event_id")
        unique((h.record_id for h in self.history), "record_id")
        profiles = unique(((p.role, p.grade) for p in self.catalog.role_profiles), "role/grade")
        roles = {role for role, grade in profiles}

        def require(condition, message):
            if not condition:
                raise ValueError(message)

        for role in roles:
            require(all((role, grade) in profiles for grade in GRADES), f"{role}: incomplete grade path")
        for p in self.catalog.role_profiles:
            require(set(p.required_skills) <= skills, f"{p.role}/{p.grade}: unknown required skill")
            require(set(p.critical_skills) <= set(p.required_skills), f"{p.role}/{p.grade}: unknown critical skill")
            unique(p.critical_skills, "critical skill")
        for e in employees.values():
            require((e.role, e.grade) in profiles, f"{e.employee_id}: unknown role/grade")
            require(set(e.skills) <= skills, f"{e.employee_id}: unknown skill")
            require(e.hire_date <= e.last_review_date <= self.catalog.meta.as_of_date, f"{e.employee_id}: invalid review date")
            if e.manager_id:
                manager = employees.get(e.manager_id)
                require(manager is not None and manager.grade == "Lead" and manager.department == e.department
                        and manager.employee_id != e.employee_id, f"{e.employee_id}: invalid manager")
            if e.career_goal:
                require((e.career_goal.target_role, e.career_goal.target_grade) in profiles, f"{e.employee_id}: unknown career goal")
        for e in events.values():
            require(set(e.target_roles) <= roles, f"{e.event_id}: unknown target role")
            unique((s.skill_id for s in e.develops_skills), f"{e.event_id} effect")
            require({s.skill_id for s in e.develops_skills} | set(e.prerequisites) <= skills, f"{e.event_id}: unknown skill")
            require(all(d >= self.catalog.meta.as_of_date for d in e.upcoming_sessions), f"{e.event_id}: past upcoming session")
            require(e.format != "self_paced" or not e.upcoming_sessions, f"{e.event_id}: self_paced sessions")
        for h in self.history:
            require(h.employee_id in employees, f"{h.record_id}: unknown employee")
            require(h.event_id in events, f"{h.record_id}: unknown event")
            require(h.date < self.catalog.meta.as_of_date, f"{h.record_id}: history after snapshot")
            event = events[h.event_id]
            require(h.due_date is None or event.mandatory, f"{h.record_id}: optional event has due_date")
            require(h.status != "overdue" or (event.mandatory and h.due_date is not None
                    and h.due_date < self.catalog.meta.as_of_date), f"{h.record_id}: invalid overdue status")
            require(h.status != "no_show" or event.format != "self_paced", f"{h.record_id}: self_paced no_show")
        return self
