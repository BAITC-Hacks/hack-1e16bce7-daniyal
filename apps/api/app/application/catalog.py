"""Read catalog data without calculating employee eligibility or readiness."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models import Employee, Event, EventPrerequisite, EventSkill, Skill


def hr_employees(session: Session):
    return session.scalars(select(Employee).order_by(Employee.employee_id)).all()


def catalog_events(session: Session, event_id: str | None = None):
    query = select(Event).order_by(Event.event_id)
    if event_id is not None:
        query = query.where(Event.event_id == event_id)
    events = session.scalars(query).all()
    if not events:
        return []
    ids = [event.event_id for event in events]
    effects = {identifier: [] for identifier in ids}
    requirements = {identifier: {} for identifier in ids}
    for effect, name in session.execute(
        select(EventSkill, Skill.name).join(Skill).where(EventSkill.event_id.in_(ids))
        .order_by(EventSkill.event_id, EventSkill.skill_id)
    ):
        effects[effect.event_id].append({"skill_id": effect.skill_id, "name": name,
                                       "gain": effect.gain, "max_level": effect.max_level})
    for prerequisite in session.scalars(
        select(EventPrerequisite).where(EventPrerequisite.event_id.in_(ids))
        .order_by(EventPrerequisite.event_id, EventPrerequisite.skill_id)
    ):
        requirements[prerequisite.event_id][prerequisite.skill_id] = prerequisite.required_level
    fields = ("event_id", "title", "description", "type", "format", "duration_hours",
              "mandatory", "repeatable", "target_roles", "target_grades", "upcoming_sessions")
    return [{**{field: getattr(event, field) for field in fields},
             "prerequisites": requirements[event.event_id],
             "develops_skills": effects[event.event_id]} for event in events]
