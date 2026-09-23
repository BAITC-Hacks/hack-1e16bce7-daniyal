"""Read-only employee queries; HTTP and authentication live in the API layer."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.models import ActivityHistory, Employee, EmployeeSkill, Event, Skill


def get_employee(session: Session, employee_id: str):
    return session.get(Employee, employee_id)


def list_employees(session: Session, limit: int, offset: int):
    items = session.scalars(select(Employee).order_by(Employee.employee_id).limit(limit).offset(offset)).all()
    return {"items": items, "total": session.scalar(select(func.count()).select_from(Employee)),
            "limit": limit, "offset": offset}


def employee_skills(session: Session, employee_id: str):
    rows = session.execute(select(Skill, EmployeeSkill).join(EmployeeSkill).where(
        EmployeeSkill.employee_id == employee_id).order_by(Skill.skill_id)).all()
    return {"employee_id": employee_id, "items": [
        {"skill_id": skill.skill_id, "name": skill.name, "type": skill.type,
         "category": skill.category, "description": skill.description,
         "assessed_level": levels.assessed_level, "level": levels.level} for skill, levels in rows]}


def employee_history(session: Session, employee_id: str, limit: int, offset: int):
    rows = session.execute(select(ActivityHistory, Event.title, Event.type).join(Event).where(
        ActivityHistory.employee_id == employee_id).order_by(
        ActivityHistory.date.desc(), ActivityHistory.record_id.desc()).limit(limit).offset(offset)).all()
    fields = ("record_id", "employee_id", "event_id", "date", "due_date", "status",
              "completion_pct", "score", "feedback_rating", "assigned_by",
              "completed_on", "session_date", "simulated")
    return {"items": [{**{field: getattr(row, field) for field in fields},
                       "event_title": title, "event_type": kind} for row, title, kind in rows],
            "total": session.scalar(select(func.count()).select_from(ActivityHistory).where(
                ActivityHistory.employee_id == employee_id)), "limit": limit, "offset": offset}
