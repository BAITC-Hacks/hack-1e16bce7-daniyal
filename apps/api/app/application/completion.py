"""Atomic completion of a participation, including explicit demo simulation."""
import datetime as dt
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.domain.models import SkillEffect
from app.domain.progress import apply_skill_effects
from app.infrastructure import models as db


class CompletionError(ValueError):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(message)


def complete_activity(session: Session, employee_id: str, event_id: str,
                      payload: dict, key: str, *, include_readiness: bool = False) -> dict:
    with session.begin():
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("SELECT pg_advisory_xact_lock(731924180)"))
        employee = session.scalar(select(db.Employee).where(
            db.Employee.employee_id == employee_id).with_for_update())
        if employee is None:
            raise CompletionError(404, "Employee not found")
        receipt = session.get(db.CompletionReceipt, (employee_id, key))
        if receipt:
            if receipt.event_id != event_id or receipt.request_payload != payload:
                raise CompletionError(409, "Idempotency key already used for a different request")
            return {**receipt.result, "already_completed": True}
        event = session.get(db.Event, event_id)
        if event is None:
            raise CompletionError(404, "Event not found")
        state = session.get(db.DatasetState, 1)
        if state is None:
            raise CompletionError(409, "Dataset has not been imported")
        today = state.as_of_date
        records = list(session.scalars(select(db.ActivityHistory).where(
            db.ActivityHistory.employee_id == employee_id,
            db.ActivityHistory.event_id == event_id).order_by(db.ActivityHistory.record_id)))
        record_id = payload.get("record_id")
        session_date = dt.date.fromisoformat(payload["session_date"]) if payload.get("session_date") else None
        if event.repeatable and not record_id and not session_date:
            raise CompletionError(422, "Repeatable activity requires record_id or session_date")
        record = None
        if record_id:
            record = next((row for row in records if row.record_id == record_id), None)
            if record is None:
                raise CompletionError(404, "Participation not found")
        elif session_date:
            if event.format == "self_paced":
                raise CompletionError(422, "Self-paced activity has no session date")
            matching = [row for row in records if (row.session_date or row.date) == session_date]
            record = next((row for row in matching if row.status == "completed"), None)
            if record is None:
                active = [row for row in matching if row.status in ("in_progress", "overdue")]
                if len(active) > 1:
                    raise CompletionError(409, "Choose an explicit participation record")
                record = active[0] if active else None
        else:
            active = [row for row in records if row.status in ("in_progress", "overdue")]
            if len(active) > 1:
                raise CompletionError(409, "Choose an explicit participation record")
            record = active[0] if active else None
        completed = next((row for row in records if row.status == "completed" and (
            not event.repeatable or (record is not None and
                (row.session_date or row.date) == (record.session_date or record.date)))), None)
        if completed is not None:
            record = completed
        levels = list(session.scalars(select(db.EmployeeSkill).where(
            db.EmployeeSkill.employee_id == employee_id)))
        current = {row.skill_id: row.level for row in levels}
        readiness_before = None
        target = None
        if include_readiness:
            from app.application.career import CareerSnapshot
            from app.domain.ranking import career_readiness
            context = CareerSnapshot(session, [employee_id]).context(employee_id)
            target = context.target
            readiness_before = career_readiness(current, target)
        changes = []
        already_completed = record is not None and record.status == "completed"
        if not already_completed:
            if record is not None and record.status not in ("in_progress", "overdue"):
                raise CompletionError(409, "This participation cannot be completed; start a new attempt")
            if record is None:
                if event.mandatory:
                    raise CompletionError(409, "Mandatory activity requires an existing assignment")
                if employee.role not in event.target_roles or employee.grade not in event.target_grades:
                    raise CompletionError(409, "Employee does not match the event audience")
                prerequisites = session.scalars(select(db.EventPrerequisite).where(
                    db.EventPrerequisite.event_id == event_id))
                if any(current.get(p.skill_id, 0) < p.required_level for p in prerequisites):
                    raise CompletionError(409, "Event prerequisites are not met")
                if event.format != "self_paced" and session_date is None and not event.repeatable:
                    upcoming = [dt.date.fromisoformat(day) for day in event.upcoming_sessions
                                if dt.date.fromisoformat(day) >= today]
                    session_date = min(upcoming) if upcoming else None
                if event.format != "self_paced" and (session_date is None or
                        session_date.isoformat() not in event.upcoming_sessions):
                    raise CompletionError(422, "Choose a listed session date")
                record = db.ActivityHistory(record_id="runtime_" + uuid4().hex,
                    employee_id=employee_id, event_id=event_id, date=today,
                    session_date=session_date, due_date=None, status="in_progress", completion_pct=0,
                    score=None, feedback_rating=None, assigned_by="self", effects_applied=False,
                    simulated=False)
                session.add(record)
            if record.effects_applied:
                raise CompletionError(409, "Participation effects were already applied")
            effects = [SkillEffect(row.skill_id, row.gain, row.max_level) for row in
                       session.scalars(select(db.EventSkill).where(db.EventSkill.event_id == event_id))]
            updated = apply_skill_effects(current, effects)
            names = dict(session.execute(select(db.Skill.skill_id, db.Skill.name)).all())
            changes = [{"skill_id": skill, "name": names[skill], "before": current[skill], "after": updated[skill]}
                       for skill in sorted(updated) if updated[skill] != current[skill]]
            for level in levels:
                level.level = updated[level.skill_id]
            record.status = "completed"
            record.completion_pct = 100
            record.effects_applied = True
            record.completed_on = today
            record.simulated = (record.session_date or record.date) > today
        result = {"event_id": event_id, "record_id": record.record_id,
                  "already_completed": already_completed, "changes": changes,
                  "career_readiness_before": readiness_before,
                  "career_readiness_after": career_readiness({row.skill_id: row.level for row in levels}, target) if include_readiness else None}
        session.flush()
        session.add(db.CompletionReceipt(employee_id=employee_id, idempotency_key=key,
            event_id=event_id, request_payload=payload, record_id=record.record_id, result=result))
    return result
