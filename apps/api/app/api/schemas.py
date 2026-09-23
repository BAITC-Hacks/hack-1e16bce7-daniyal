import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.application.dataset import CareerGoal, Status
from app.auth.models import Role


class EmployeeLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: str = Field(min_length=1, max_length=200)


class HRLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: SecretStr = Field(min_length=1, max_length=1024)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = 3600


class IdentityResponse(BaseModel):
    role: Role
    employee_id: str | None


class EmployeeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    employee_id: str
    full_name: str
    role: str
    grade: str


class EmployeeProfile(EmployeeSummary):
    department: str
    manager_id: str | None
    hire_date: dt.date
    tenure_months: int
    work_format: str
    preferred_language: str
    career_goal: CareerGoal | None
    last_review_date: dt.date


class EmployeePage(BaseModel):
    items: list[EmployeeSummary]
    total: int
    limit: int
    offset: int


class SkillResponse(BaseModel):
    skill_id: str
    name: str
    type: Literal["hard", "soft"]
    category: str
    description: str
    assessed_level: int
    level: int


class EmployeeSkills(BaseModel):
    employee_id: str
    items: list[SkillResponse]


class ActivityResponse(BaseModel):
    record_id: str
    employee_id: str
    event_id: str
    date: dt.date
    due_date: dt.date | None
    status: Status
    completion_pct: int
    score: int | None
    feedback_rating: int | None
    assigned_by: Literal["self", "manager", "hr"]
    event_title: str
    event_type: str


class ActivityPage(BaseModel):
    items: list[ActivityResponse]
    total: int
    limit: int
    offset: int
