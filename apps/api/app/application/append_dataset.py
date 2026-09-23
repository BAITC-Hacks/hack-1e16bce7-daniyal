"""Append jury profiles atomically without replacing existing employee progress."""
from collections import defaultdict
import hashlib
import json

from sqlalchemy import select, text

from app.application.dataset import Dataset, Employees
from app.application.import_dataset import DatasetConflict
from app.domain.models import SkillEffect
from app.domain.progress import apply_skill_effects
from app.infrastructure import models as db


def append_dataset(session, incoming: Employees, history):
    fingerprint = hashlib.sha256(json.dumps({'employees': incoming.model_dump(mode='json'),
        'history': [row.model_dump(mode='json') for row in history]}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    with session.begin():
        if session.get_bind().dialect.name == 'postgresql':
            session.execute(text('SELECT pg_advisory_xact_lock(731924180)'))
        state = session.get(db.DatasetState, 1)
        if state is None:
            raise DatasetConflict('Load the initial dataset before adding profiles')
        receipt = session.get(db.DatasetImportBatch, fingerprint)
        if receipt:
            return {'status': 'unchanged', **receipt.counts}
        employees = {row.employee_id: row for row in session.scalars(select(db.Employee))}
        skills = session.scalars(select(db.Skill)).all()
        assessed = defaultdict(dict)
        for row in session.scalars(select(db.EmployeeSkill)):
            assessed[row.employee_id][row.skill_id] = row.assessed_level
        def profile(row):
            return {column.name: getattr(row, column.name) for column in db.Employee.__table__.columns} | {'skills': assessed[row.employee_id]}
        incoming_ids = {row.employee_id for row in incoming.employees}
        if any(row.employee_id not in incoming_ids for row in history):
            raise ValueError('History must belong to the uploaded employee profiles')
        new = []
        for row in incoming.employees:
            if row.employee_id in employees:
                raise DatasetConflict(f'{row.employee_id}: existing profile cannot be overwritten')
            new.append(row)
        # Validate against the actual catalog and managers already in the database.
        requirements = defaultdict(dict)
        critical = defaultdict(list)
        for row in session.scalars(select(db.GradeRequirement)):
            requirements[(row.role, row.grade)][row.skill_id] = row.required_level
            if row.critical:
                critical[(row.role, row.grade)].append(row.skill_id)
        catalog = {'meta': state.source_meta, 'proficiency_scale': state.proficiency_scale,
            'skills': [{column.name: getattr(row, column.name) for column in db.Skill.__table__.columns} for row in skills],
            'role_profiles': [{'role': row.role, 'grade': row.grade, 'required_skills': requirements[(row.role, row.grade)],
                'critical_skills': critical[(row.role, row.grade)]} for row in session.scalars(select(db.RoleGrade))]}
        effects, prerequisites = defaultdict(list), defaultdict(dict)
        for row in session.scalars(select(db.EventSkill)):
            effects[row.event_id].append({'skill_id': row.skill_id, 'gain': row.gain, 'max_level': row.max_level})
        for row in session.scalars(select(db.EventPrerequisite)):
            prerequisites[row.event_id][row.skill_id] = row.required_level
        event_rows = [{column.name: getattr(row, column.name) for column in db.Event.__table__.columns if column.name != 'repeatable'}
            | {'develops_skills': effects[row.event_id], 'prerequisites': prerequisites[row.event_id]}
            for row in session.scalars(select(db.Event))]
        Dataset(catalog=catalog, events={'meta': state.source_meta, 'events': event_rows},
            employees={'meta': incoming.meta, 'employees': [profile(row) for row in employees.values()
                if row.employee_id not in incoming_ids] + [row.model_dump() for row in incoming.employees]}, history=history)
        new_ids = {row.employee_id for row in new}
        fresh_history = []
        for row in history:
            stored = session.get(db.ActivityHistory, row.record_id)
            if stored:
                if any(getattr(stored, field) != value for field, value in row.model_dump().items()):
                    raise DatasetConflict(f'{row.record_id}: existing history cannot be overwritten')
            elif row.employee_id not in new_ids:
                raise DatasetConflict(f'{row.employee_id}: additional history is only allowed with a new profile')
            else:
                fresh_history.append(row)
        # Insert employees first so new profiles can reference newly supplied leads.
        for row in new:
            session.add(db.Employee(**row.model_dump(exclude={'skills', 'manager_id'}), manager_id=None))
        session.flush()
        for row in new:
            session.get(db.Employee, row.employee_id).manager_id = row.manager_id
            before = {skill.skill_id: row.skills.get(skill.skill_id, 0) for skill in skills}
            current = dict(before)
            for activity in sorted((item for item in fresh_history if item.employee_id == row.employee_id), key=lambda item: (item.date, item.record_id)):
                if activity.status == 'completed' and activity.date > row.last_review_date:
                    current = apply_skill_effects(current, [SkillEffect(**effect) for effect in effects[activity.event_id]])
            session.add_all(db.EmployeeSkill(employee_id=row.employee_id, skill_id=key, assessed_level=before[key], level=level)
                            for key, level in current.items())
        session.add_all(db.ActivityHistory(**row.model_dump(), effects_applied=row.status == 'completed') for row in fresh_history)
        counts = {'employees': len(new), 'events': 0, 'skills': 0, 'history_records': len(fresh_history)}
        session.add(db.DatasetImportBatch(fingerprint=fingerprint, counts=counts))
    return {'status': 'imported', **counts}
