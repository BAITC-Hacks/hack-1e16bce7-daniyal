from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.application.dataset import Dataset
from app.application.import_dataset import DatasetConflict, import_dataset
from app.infrastructure.database import Base
from app.infrastructure.dataset_loader import load_dataset
from app.infrastructure import models as db


@pytest.fixture(scope="module")
def dataset():
    return load_dataset(Path(__file__).resolve().parents[3] / "dataset")


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_official_dataset_import_and_idempotency(dataset, session):
    assert import_dataset(session, dataset) == {
        "status": "imported", "skills": 60, "employees": 200, "events": 40, "history": 2743}
    assert import_dataset(session, dataset)["status"] == "unchanged"
    assert session.scalar(select(func.count()).select_from(db.ActivityHistory)) == 2743
    assert session.scalar(select(func.count()).select_from(db.EmployeeSkill)) == 12000
    assert session.get(db.RoleGrade, ("Backend Engineer", "Middle")).next_grade == "Senior"
    assert session.get(db.RoleGrade, ("Backend Engineer", "Lead")).next_grade is None
    assert session.get(db.Event, "EV_036").repeatable is True
    assert session.scalar(select(func.count()).select_from(db.EmployeeSkill).where(
        db.EmployeeSkill.level > db.EmployeeSkill.assessed_level)) > 0


@pytest.mark.parametrize("mutation", [
    lambda d: d["employees"]["employees"][0]["skills"].update(UNKNOWN=1),
    lambda d: d["employees"]["employees"][0]["skills"].update(SK_PYTHON=6),
    lambda d: d["employees"]["employees"][0]["skills"].update(SK_PYTHON=True),
    lambda d: d["history"][0].update(employee_id="missing"),
    lambda d: d["history"][0].update(event_id="missing"),
    lambda d: d["history"][0].update(status="missed"),
    lambda d: d["history"][0].update(completion_pct=50),
    lambda d: d["history"].append(d["history"][0]),
    lambda d: d["events"]["events"][0].update(develops_skills=[
        {"skill_id": "SK_PYTHON", "gain": 1, "max_level": 5}] * 2),
    lambda d: d["employees"]["employees"][0].update(manager_id="missing"),
])
def test_invalid_dataset_rejected(dataset, mutation):
    payload = dataset.model_dump(mode="json")
    mutation(payload)
    with pytest.raises(ValidationError):
        Dataset.model_validate(payload)


def test_changed_snapshot_does_not_overwrite_progress(dataset, session):
    import_dataset(session, dataset)
    changed = deepcopy(dataset)
    changed.employees.employees[0].full_name = "Changed"
    with pytest.raises(DatasetConflict):
        import_dataset(session, changed)
    assert session.get(db.Employee, dataset.employees.employees[0].employee_id).full_name != "Changed"


def test_failure_rolls_back_entire_import(dataset, session, monkeypatch):
    def fail(*args):
        raise RuntimeError("effect failure")
    monkeypatch.setattr("app.application.import_dataset.apply_skill_effects", fail)
    with pytest.raises(RuntimeError, match="effect failure"):
        import_dataset(session, dataset)
    assert session.scalar(select(func.count()).select_from(db.Skill)) == 0
    assert session.scalar(select(func.count()).select_from(db.Employee)) == 0
    assert session.get(db.DatasetState, 1) is None


def test_review_boundary_missing_skill_and_replay_order(dataset, session):
    payload = dataset.model_dump(mode="json")
    employee = payload["employees"]["employees"][0]
    employee["skills"] = {}
    employee["last_review_date"] = "2026-09-01"
    activity = payload["events"]["events"][0]
    activity["develops_skills"] = [{"skill_id": "SK_PYTHON", "gain": 1, "max_level": 5}]
    payload["history"] = [{"record_id": f"TEST{i}", "employee_id": employee["employee_id"],
        "event_id": activity["event_id"], "date": day, "due_date": None, "status": status,
        "completion_pct": 100 if status == "completed" else 50, "score": None,
        "feedback_rating": None, "assigned_by": "hr"}
        for i, (day, status) in enumerate([
            ("2026-08-31", "completed"), ("2026-09-01", "completed"),
            ("2026-09-02", "completed"), ("2026-09-03", "in_progress")])]
    import_dataset(session, Dataset.model_validate(payload))
    skill = session.get(db.EmployeeSkill, (employee["employee_id"], "SK_PYTHON"))
    assert (skill.assessed_level, skill.level) == (0, 1)
    assert session.get(db.ActivityHistory, "TEST0").effects_applied
    assert not session.get(db.ActivityHistory, "TEST3").effects_applied
    session.rollback()
    assert import_dataset(session, Dataset.model_validate(payload))["status"] == "unchanged"
    assert session.get(db.EmployeeSkill, (employee["employee_id"], "SK_PYTHON")).level == 1
