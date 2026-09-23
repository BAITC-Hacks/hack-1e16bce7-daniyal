from datetime import date

import pytest
from sqlalchemy import select, func

from app.application.append_dataset import append_dataset
from app.application.dataset import Employees, HistoryRecord
from app.application.import_dataset import DatasetConflict, import_dataset
from app.infrastructure import models as db
from test_dataset import dataset, session


@pytest.fixture
def incoming(dataset):
    person = dataset.employees.employees[0].model_copy(deep=True)
    person.employee_id = "jury-42"
    person.manager_id = None
    person.skills = {}
    person.last_review_date = date(2026, 9, 1)
    return Employees(meta=dataset.employees.meta, employees=[person])


def record(dataset, incoming, day="2026-09-02", identifier="jury-history"):
    return HistoryRecord(record_id=identifier, employee_id=incoming.employees[0].employee_id,
                         event_id=next(e for e in dataset.events.events if e.develops_skills).event_id, date=day, due_date=None,
                         status="completed", completion_pct=100, score=None, feedback_rating=None, assigned_by="hr")


def test_append_replay_preserves_runtime_progress(dataset, session, incoming):
    import_dataset(session, dataset)
    h = record(dataset, incoming)
    result = append_dataset(session, incoming, [h])
    assert result == {"status": "imported", "employees": 1, "events": 0, "skills": 0, "history_records": 1}
    skill_id = next(e for e in dataset.events.events if e.develops_skills).develops_skills[0].skill_id
    stored = session.get(db.EmployeeSkill, ("jury-42", skill_id))
    assert stored.assessed_level == 0
    assert stored.level == min(next(e for e in dataset.events.events if e.develops_skills).develops_skills[0].gain,
                               next(e for e in dataset.events.events if e.develops_skills).develops_skills[0].max_level)
    stored.level = 5
    session.get(db.ActivityHistory, h.record_id).score = 99
    session.commit()
    assert append_dataset(session, incoming, [h])["status"] == "unchanged"
    assert session.get(db.EmployeeSkill, ("jury-42", skill_id)).level == 5
    assert session.get(db.ActivityHistory, h.record_id).score == 99


def test_append_existing_manager_and_review_boundary(dataset, session, incoming):
    import_dataset(session, dataset)
    original = next(e for e in dataset.employees.employees if e.manager_id)
    person = original.model_copy(deep=True)
    person.employee_id = "jury-42"
    person.skills = {}
    incoming.employees = [person]
    h = record(dataset, incoming, day=person.last_review_date.isoformat())
    append_dataset(session, incoming, [h])
    assert session.get(db.Employee, "jury-42").manager_id == original.manager_id
    assert session.scalar(select(func.sum(db.EmployeeSkill.level)).where(db.EmployeeSkill.employee_id == "jury-42")) == 0
    assert session.get(db.ActivityHistory, h.record_id).effects_applied


@pytest.mark.parametrize("change", ["existing", "history_collision", "old_history", "metadata", "manager", "skill", "future"])
def test_append_invalid_is_atomic(dataset, session, incoming, change):
    import_dataset(session, dataset)
    h = record(dataset, incoming)
    if change == "existing":
        incoming.employees[0].employee_id = dataset.employees.employees[0].employee_id
        h.employee_id = incoming.employees[0].employee_id
    elif change == "history_collision":
        h.record_id = dataset.history[0].record_id
    elif change == "old_history":
        h.employee_id = dataset.employees.employees[0].employee_id
    elif change == "metadata":
        incoming.meta = incoming.meta.model_copy(update={"version": "other"})
    elif change == "manager":
        incoming.employees[0].manager_id = "missing"
    elif change == "skill":
        incoming.employees[0].skills = {"missing": 1}
    else:
        h.date = incoming.meta.as_of_date
    with pytest.raises(ValueError):
        append_dataset(session, incoming, [h])
    assert session.scalar(select(func.count()).select_from(db.Employee)) == 200
    assert session.scalar(select(func.count()).select_from(db.DatasetImportBatch)) == 0


def test_append_requires_initial_dataset(session, incoming):
    with pytest.raises(DatasetConflict):
        append_dataset(session, incoming, [])
