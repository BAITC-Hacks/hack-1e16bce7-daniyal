import datetime as dt
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.application.completion import CompletionError, complete_activity
from app.application.import_dataset import import_dataset
from app.infrastructure.database import Base
from app.infrastructure.dataset_loader import load_dataset
from app.infrastructure import models as db


@pytest.fixture
def engine(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "completion.db"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        import_dataset(session, load_dataset(Path(__file__).resolve().parents[3] / "dataset"))
    with Session(engine) as session, session.begin():
        employee = session.get(db.Employee, "E0001")
        skill = session.scalar(select(db.EmployeeSkill).where(db.EmployeeSkill.employee_id == "E0001"))
        skill.level = 0
        session.add(db.Event(event_id="test_event", title="Test", description="Test",
            type="course", format="self_paced", duration_hours=1, mandatory=False,
            repeatable=False, target_roles=[employee.role], target_grades=[employee.grade], upcoming_sessions=[]))
        session.flush()
        session.add(db.EventSkill(event_id="test_event", skill_id=skill.skill_id, gain=1, max_level=5))
    yield engine
    engine.dispose()


def complete(engine, key="first", payload=None, event="test_event"):
    with Session(engine) as session:
        return complete_activity(session, "E0001", event,
                                 payload or {"record_id": None, "session_date": None}, key)


def test_completion_repeat_and_key_conflict(engine):
    result = complete(engine)
    assert result["changes"][0]["before"] == 0
    assert result["changes"][0]["after"] == 1
    assert result["career_readiness_after"] is None
    assert complete(engine)["already_completed"]
    second = complete(engine, key="another")
    assert second["already_completed"] and second["changes"] == []
    assert second["record_id"] == result["record_id"]
    with pytest.raises(CompletionError, match="different request"):
        complete(engine, payload={"record_id": result["record_id"], "session_date": None})
    with Session(engine) as session:
        row = session.get(db.ActivityHistory, result["record_id"])
        assert row.completed_on == dt.date(2026, 10, 1)
        assert not row.simulated
        assert row.effects_applied


def test_repeatable_sessions_and_simulation(engine):
    with Session(engine) as session, session.begin():
        event = session.get(db.Event, "test_event")
        event.repeatable = True
        event.format = "online"
        event.upcoming_sessions = ["2026-10-10", "2026-10-20"]
    with pytest.raises(CompletionError, match="requires"):
        complete(engine)
    first = complete(engine, payload={"record_id": None, "session_date": "2026-10-10"})
    duplicate = complete(engine, key="different", payload={"record_id": None, "session_date": "2026-10-10"})
    assert duplicate["already_completed"]
    second = complete(engine, key="next", payload={"record_id": None, "session_date": "2026-10-20"})
    assert second["changes"][0]["after"] == 2
    with Session(engine) as session:
        row = session.get(db.ActivityHistory, first["record_id"])
        assert row.date == dt.date(2026, 10, 1)
        assert row.session_date == dt.date(2026, 10, 10)
        assert row.simulated


def test_nonrepeatable_selects_nearest_future_session(engine):
    with Session(engine) as session, session.begin():
        event = session.get(db.Event, "test_event")
        event.format = "online"
        event.upcoming_sessions = ["2026-10-20", "2026-09-20", "2026-10-10"]
    result = complete(engine)
    with Session(engine) as session:
        row = session.get(db.ActivityHistory, result["record_id"])
        assert row.session_date == dt.date(2026, 10, 10)
        assert row.simulated


def test_existing_assignment_retains_source_fields(engine):
    with Session(engine) as session, session.begin():
        event = session.get(db.Event, "test_event")
        event.mandatory = True
        event.target_roles = []
        session.add(db.ActivityHistory(record_id="assignment", employee_id="E0001", event_id="test_event",
            date=dt.date(2026, 9, 1), due_date=dt.date(2026, 9, 20), status="overdue",
            completion_pct=40, assigned_by="hr", score=None, feedback_rating=None, effects_applied=False))
    complete(engine, payload={"record_id": "assignment", "session_date": None})
    with Session(engine) as session:
        row = session.get(db.ActivityHistory, "assignment")
        assert row.date == dt.date(2026, 9, 1)
        assert row.due_date == dt.date(2026, 9, 20)
        assert row.assigned_by == "hr"
        assert row.completion_pct == 100


def test_rejects_missing_assignment_and_bad_prerequisites(engine):
    with Session(engine) as session, session.begin():
        session.get(db.Event, "test_event").mandatory = True
    with pytest.raises(CompletionError, match="existing assignment"):
        complete(engine)
    with Session(engine) as session, session.begin():
        session.get(db.Event, "test_event").mandatory = False
        skill = session.scalar(select(db.EventSkill).where(db.EventSkill.event_id == "test_event"))
        session.add(db.EventPrerequisite(event_id="test_event", skill_id=skill.skill_id, required_level=3))
    with pytest.raises(CompletionError, match="prerequisites"):
        complete(engine)


def test_invalid_effect_rolls_back_new_history(engine, monkeypatch):
    def fail(*args):
        raise ValueError("broken effect")
    monkeypatch.setattr("app.application.completion.apply_skill_effects", fail)
    with pytest.raises(ValueError, match="broken effect"):
        complete(engine)
    with Session(engine) as session:
        assert session.scalar(select(db.ActivityHistory).where(db.ActivityHistory.event_id == "test_event")) is None
        assert session.get(db.CompletionReceipt, ("E0001", "first")) is None


def test_imported_completed_never_replays(engine):
    with Session(engine) as session:
        row = session.scalar(select(db.ActivityHistory).join(db.Event).where(
            db.ActivityHistory.employee_id == "E0001", db.ActivityHistory.status == "completed",
            db.Event.repeatable.is_(False)))
        event = row.event_id
        record_id = row.record_id
    result = complete(engine, event=event, payload={"record_id": record_id, "session_date": None})
    assert result["already_completed"] and result["changes"] == []


def test_completion_http_authorization_and_validation(engine):
    from fastapi.testclient import TestClient
    from app.api.access import session as session_dependency
    from app.api.completion import router
    from app.main import create_app
    from test_auth_api import config, hr, login

    app = create_app(config())
    if not any(getattr(route, "path", "").endswith("/complete") for route in app.routes):
        app.include_router(router)
    def sessions():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[session_dependency] = sessions
    path = "/api/v1/employees/E0001/activities/test_event/complete"
    with TestClient(app) as client:
        headers = {**login(client), "Idempotency-Key": "http-first"}
        assert client.post(path, json={}).status_code == 401
        assert client.post(path, json={}, headers=login(client)).status_code == 422
        assert client.post(path, json={}, headers={**hr(client), "Idempotency-Key": "hr"}).status_code == 403
        assert client.post(path.replace("E0001", "E0002"), json={}, headers=headers).status_code == 403
        assert client.post(path, json={"record_id": "x", "session_date": "2026-10-10"}, headers=headers).status_code == 422
        assert client.post(path, json={}, headers=headers).status_code == 200
        assert client.post(path, json={}, headers=headers).json()["already_completed"]


def test_postgres_concurrent_completion(monkeypatch):
    import os
    from concurrent.futures import ThreadPoolExecutor
    from uuid import uuid4
    from sqlalchemy import text
    from sqlalchemy.engine import make_url

    if not os.getenv("TEST_DATABASE_URL"):
        pytest.skip("Set TEST_DATABASE_URL for PostgreSQL concurrency checks")
    url = make_url(os.environ["TEST_DATABASE_URL"])
    admin = create_engine(url)
    schema = "test_completion_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url.update_query_dict({"options": f"-csearch_path={schema}"}))
    try:
        Base.metadata.create_all(engine)
        dataset = load_dataset(Path(__file__).resolve().parents[3] / "dataset")
        with Session(engine) as session:
            import_dataset(session, dataset)
        with Session(engine) as session, session.begin():
            employee = session.get(db.Employee, "E0001")
            skill = session.scalar(select(db.EmployeeSkill).where(db.EmployeeSkill.employee_id == "E0001"))
            skill_id = skill.skill_id
            skill.level = 0
            for event_id in ("test_event", "second_event"):
                session.add(db.Event(event_id=event_id, title="Test", description="Test", type="course",
                    format="self_paced", duration_hours=1, mandatory=False, repeatable=False,
                    target_roles=[employee.role], target_grades=[employee.grade], upcoming_sessions=[]))
            session.flush()
            for event_id in ("test_event", "second_event"):
                session.add(db.EventSkill(event_id=event_id, skill_id=skill_id, gain=1, max_level=5))
        def run(index):
            if index == 3:
                with Session(engine) as session:
                    return import_dataset(session, dataset)
            return complete(engine, key=str(index), event="second_event" if index == 2 else "test_event")
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(run, range(4)))
        assert sorted(row["already_completed"] for row in results[:2]) == [False, True]
        assert results[3]["status"] == "unchanged"
        with Session(engine) as session:
            assert session.get(db.EmployeeSkill, ("E0001", skill_id)).level == 2
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
