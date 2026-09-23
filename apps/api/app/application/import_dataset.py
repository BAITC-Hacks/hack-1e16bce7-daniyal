"""Atomic initial import. Re-importing the same source never replays gains."""
import hashlib
import json

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.application.dataset import Dataset, GRADES
from app.domain.models import SkillEffect
from app.domain.progress import apply_skill_effects
from app.infrastructure import models as db


class DatasetConflict(ValueError):
    pass


def import_dataset(session: Session, dataset: Dataset) -> dict:
    """Caller supplies a fresh session; this service owns the transaction.

    Changed snapshots are rejected rather than overwriting runtime progress.
    PostgreSQL advisory lock serializes imports, including the first one.
    """
    fingerprint = hashlib.sha256(json.dumps(dataset.model_dump(mode="json"),
                                            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    counts = {"skills": len(dataset.catalog.skills), "employees": len(dataset.employees.employees),
              "events": len(dataset.events.events), "history": len(dataset.history)}
    with session.begin():
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("SELECT pg_advisory_xact_lock(731924180)"))
        state = session.get(db.DatasetState, 1)
        if state:
            if state.fingerprint != fingerprint:
                raise DatasetConflict("Database already contains a different snapshot; no data changed")
            return {"status": "unchanged", **counts}
        for model in (db.Skill, db.Employee, db.Event, db.RoleGrade, db.ActivityHistory):
            if session.scalar(select(func.count()).select_from(model)):
                raise DatasetConflict("Database is not empty and has no import marker; no data changed")
        session.add_all(db.Skill(**skill.model_dump()) for skill in dataset.catalog.skills)
        session.flush()
        # Insert grades with null successors, then link them after all keys exist.
        session.add_all(db.RoleGrade(role=p.role, grade=p.grade) for p in dataset.catalog.role_profiles)
        session.flush()
        for p in dataset.catalog.role_profiles:
            index = GRADES.index(p.grade)
            successor = GRADES[index + 1] if index + 1 < len(GRADES) else None
            session.execute(update(db.RoleGrade).where(db.RoleGrade.role == p.role, db.RoleGrade.grade == p.grade)
                            .values(next_grade=successor))
            session.add_all(db.GradeRequirement(role=p.role, grade=p.grade, skill_id=skill,
                            required_level=level, critical=skill in p.critical_skills)
                            for skill, level in p.required_skills.items())
        for e in dataset.employees.employees:
            session.add(db.Employee(**e.model_dump(exclude={"skills", "manager_id"}), manager_id=None))
        session.flush()
        for e in dataset.employees.employees:
            session.execute(update(db.Employee).where(db.Employee.employee_id == e.employee_id)
                            .values(manager_id=e.manager_id))
        for e in dataset.events.events:
            values = e.model_dump(exclude={"develops_skills", "prerequisites", "upcoming_sessions"})
            session.add(db.Event(**values, upcoming_sessions=[d.isoformat() for d in e.upcoming_sessions],
                                 repeatable=e.event_id == "EV_036"))
        session.flush()
        for e in dataset.events.events:
            session.add_all(db.EventSkill(event_id=e.event_id, **effect.model_dump()) for effect in e.develops_skills)
            session.add_all(db.EventPrerequisite(event_id=e.event_id, skill_id=skill, required_level=level)
                            for skill, level in e.prerequisites.items())
        employees = {e.employee_id: e for e in dataset.employees.employees}
        events = {e.event_id: e for e in dataset.events.events}
        assessed = {e.employee_id: {s.skill_id: e.skills.get(s.skill_id, 0) for s in dataset.catalog.skills}
                    for e in employees.values()}
        current = {key: dict(levels) for key, levels in assessed.items()}
        for h in sorted(dataset.history, key=lambda h: (h.date, h.record_id)):
            if h.status == "completed" and h.date > employees[h.employee_id].last_review_date:
                current[h.employee_id] = apply_skill_effects(current[h.employee_id],
                    [SkillEffect(**effect.model_dump()) for effect in events[h.event_id].develops_skills])
            # Earlier completions are already included in the assessment baseline.
            session.add(db.ActivityHistory(**h.model_dump(), effects_applied=h.status == "completed"))
        for employee_id, levels in current.items():
            session.add_all(db.EmployeeSkill(employee_id=employee_id, skill_id=skill,
                assessed_level=assessed[employee_id][skill], level=level) for skill, level in levels.items())
        session.add(db.DatasetState(id=1, fingerprint=fingerprint, as_of_date=dataset.catalog.meta.as_of_date,
                    source_meta=dataset.catalog.meta.model_dump(mode="json"),
                    proficiency_scale=dataset.catalog.proficiency_scale))
    return {"status": "imported", **counts}
