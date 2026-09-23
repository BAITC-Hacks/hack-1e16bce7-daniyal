"""Persistent dataset entities. JSON columns retain source arrays and metadata."""
import datetime as dt

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, ForeignKey, ForeignKeyConstraint, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class DatasetState(Base):
    __tablename__ = "dataset_state"
    id: Mapped[int] = mapped_column(primary_key=True)
    as_of_date: Mapped[dt.date] = mapped_column(Date)
    fingerprint: Mapped[str] = mapped_column(String(64))
    source_meta: Mapped[dict] = mapped_column(JSON)
    proficiency_scale: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (CheckConstraint("id = 1"),)


class Skill(Base):
    __tablename__ = "skills"
    skill_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str]
    type: Mapped[str]
    category: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    __table_args__ = (CheckConstraint("type IN ('hard', 'soft')"),)


class RoleGrade(Base):
    __tablename__ = "role_grades"
    role: Mapped[str] = mapped_column(String, primary_key=True)
    grade: Mapped[str] = mapped_column(String, primary_key=True)
    next_grade: Mapped[str | None]
    __table_args__ = (ForeignKeyConstraint(["role", "next_grade"], ["role_grades.role", "role_grades.grade"]),)


class GradeRequirement(Base):
    __tablename__ = "grade_requirements"
    role: Mapped[str] = mapped_column(String, primary_key=True)
    grade: Mapped[str] = mapped_column(String, primary_key=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.skill_id"), primary_key=True)
    required_level: Mapped[int]
    critical: Mapped[bool] = mapped_column(Boolean)
    __table_args__ = (
        ForeignKeyConstraint(["role", "grade"], ["role_grades.role", "role_grades.grade"]),
        CheckConstraint("required_level BETWEEN 0 AND 5"),
    )


class Employee(Base):
    __tablename__ = "employees"
    employee_id: Mapped[str] = mapped_column(String, primary_key=True)
    full_name: Mapped[str]
    department: Mapped[str]
    role: Mapped[str]
    grade: Mapped[str]
    manager_id: Mapped[str | None] = mapped_column(ForeignKey("employees.employee_id"))
    hire_date: Mapped[dt.date] = mapped_column(Date)
    tenure_months: Mapped[int]
    work_format: Mapped[str]
    preferred_language: Mapped[str]
    career_goal: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_review_date: Mapped[dt.date] = mapped_column(Date)
    __table_args__ = (
        ForeignKeyConstraint(["role", "grade"], ["role_grades.role", "role_grades.grade"]),
        CheckConstraint("tenure_months >= 0"),
        CheckConstraint("work_format IN ('office', 'hybrid', 'remote')"),
        CheckConstraint("preferred_language IN ('ru', 'kk', 'en')"),
    )


class EmployeeSkill(Base):
    __tablename__ = "employee_skills"
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), primary_key=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.skill_id"), primary_key=True)
    assessed_level: Mapped[int]
    level: Mapped[int]
    __table_args__ = (
        CheckConstraint("level BETWEEN 0 AND 5"),
        CheckConstraint("assessed_level BETWEEN 0 AND 5"),
    )


class Event(Base):
    __tablename__ = "events"
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    type: Mapped[str]
    format: Mapped[str]
    duration_hours: Mapped[float]
    mandatory: Mapped[bool]
    repeatable: Mapped[bool] = mapped_column(default=False)
    target_roles: Mapped[list] = mapped_column(JSON)
    target_grades: Mapped[list] = mapped_column(JSON)
    upcoming_sessions: Mapped[list] = mapped_column(JSON)
    __table_args__ = (
        CheckConstraint("duration_hours > 0"),
        CheckConstraint("format IN ('online', 'offline', 'self_paced')"),
    )


class EventSkill(Base):
    __tablename__ = "event_skills"
    event_id: Mapped[str] = mapped_column(ForeignKey("events.event_id"), primary_key=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.skill_id"), primary_key=True)
    gain: Mapped[int]
    max_level: Mapped[int]
    __table_args__ = (CheckConstraint("gain BETWEEN 0 AND 5"), CheckConstraint("max_level BETWEEN 0 AND 5"))


class EventPrerequisite(Base):
    __tablename__ = "event_prerequisites"
    event_id: Mapped[str] = mapped_column(ForeignKey("events.event_id"), primary_key=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.skill_id"), primary_key=True)
    required_level: Mapped[int]
    __table_args__ = (CheckConstraint("required_level BETWEEN 0 AND 5"),)


class ActivityHistory(Base):
    __tablename__ = "activity_history"
    record_id: Mapped[str] = mapped_column(String, primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.event_id"), index=True)
    date: Mapped[dt.date] = mapped_column(Date)
    due_date: Mapped[dt.date | None] = mapped_column(Date)
    status: Mapped[str]
    completion_pct: Mapped[int]
    score: Mapped[int | None]
    feedback_rating: Mapped[int | None]
    assigned_by: Mapped[str]
    effects_applied: Mapped[bool] = mapped_column(default=False)
    completed_on: Mapped[dt.date | None] = mapped_column(Date)
    simulated: Mapped[bool] = mapped_column(default=False, server_default=false())
    session_date: Mapped[dt.date | None] = mapped_column(Date)
    __table_args__ = (
        CheckConstraint("status IN ('completed', 'in_progress', 'dropped', 'no_show', 'declined', 'overdue')"),
        CheckConstraint("completion_pct BETWEEN 0 AND 100"),
        CheckConstraint("score BETWEEN 0 AND 100"),
        CheckConstraint("feedback_rating BETWEEN 1 AND 5"),
        CheckConstraint("assigned_by IN ('self', 'manager', 'hr')"),
    )


class DatasetImportBatch(Base):
    __tablename__ = "dataset_import_batches"
    fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    counts: Mapped[dict] = mapped_column(JSON)


class CompletionReceipt(Base):
    __tablename__ = "completion_receipts"
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.event_id"))
    request_payload: Mapped[dict] = mapped_column(JSON)
    record_id: Mapped[str] = mapped_column(ForeignKey("activity_history.record_id"))
    result: Mapped[dict] = mapped_column(JSON)
