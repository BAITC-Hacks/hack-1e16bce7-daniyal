"""Read the imported database without replaying already applied skill gains."""
from collections import defaultdict
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import models as domain
from app.infrastructure import models as db


def load_context(session: Session, employee_id: str, locale: str):
    state = session.get(db.DatasetState, 1)
    if state is None:
        raise ValueError("dataset_not_loaded")
    employee = session.get(db.Employee, employee_id)
    if employee is None:
        raise KeyError(employee_id)
    names = dict(session.execute(select(db.Skill.skill_id, db.Skill.name)).all())
    # These levels already include completed activities, unlike raw dataset assessments.
    levels = dict(session.execute(select(db.EmployeeSkill.skill_id, db.EmployeeSkill.level).where(
        db.EmployeeSkill.employee_id == employee_id)).all())
    target = None
    target_role = employee.role
    if employee.career_goal:
        target_role = employee.career_goal["target_role"]
        target_grade = employee.career_goal["target_grade"]
    else:
        current = session.get(db.RoleGrade, (employee.role, employee.grade))
        target_grade = current.next_grade if current else None
    if target_grade:
        role_grade = session.get(db.RoleGrade, (target_role, target_grade))
        requirements = session.scalars(select(db.GradeRequirement).where(
            db.GradeRequirement.role == target_role, db.GradeRequirement.grade == target_grade)).all()
        if role_grade is None:
            raise ValueError("invalid_target")
        target = domain.GradeRequirement(target_role, target_grade, role_grade.next_grade,
            {row.skill_id: row.required_level for row in requirements},
            tuple(row.skill_id for row in requirements if row.critical))
    effects = defaultdict(list)
    for row in session.scalars(select(db.EventSkill)):
        effects[row.event_id].append(domain.SkillEffect(row.skill_id, row.gain, row.max_level))
    prerequisites = defaultdict(dict)
    for row in session.scalars(select(db.EventPrerequisite)):
        prerequisites[row.event_id][row.skill_id] = row.required_level
    events = tuple(domain.Event(row.event_id, row.title, row.type, tuple(row.target_roles),
        tuple(row.target_grades), tuple(effects[row.event_id]), row.mandatory,
        prerequisites[row.event_id], row.format,
        tuple(date.fromisoformat(day) for day in row.upcoming_sessions), row.repeatable)
        for row in session.scalars(select(db.Event).order_by(db.Event.event_id)))
    history = tuple(domain.Participation(row.record_id, row.employee_id, row.event_id, row.status,
        datetime.combine(row.date, time.min)) for row in session.scalars(select(db.ActivityHistory).where(
            db.ActivityHistory.employee_id == employee_id).order_by(db.ActivityHistory.date, db.ActivityHistory.record_id)))
    context = domain.RecommendationContext(
        domain.Employee(employee_id, employee.role, employee.grade, employee.tenure_months, levels),
        target, history, events, locale, state.as_of_date,
    )
    return context, names
