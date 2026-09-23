from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.access import session as session_dependency
from app.api.catalog import router
from app.application.import_dataset import import_dataset
from app.auth.models import Role
from app.auth.tokens import Principal, issue_token
from app.config import Settings
from app.infrastructure.database import Base
from app.infrastructure.dataset_loader import load_dataset
from app.infrastructure.models import Employee, Event
from app.main import create_app


@pytest.fixture(scope="module")
def dataset():
    return load_dataset(Path(__file__).resolve().parents[3] / "dataset")


@pytest.fixture(scope="module")
def engine(tmp_path_factory, dataset):
    engine = create_engine("sqlite:///" + str(tmp_path_factory.mktemp("catalog") / "test.db"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        import_dataset(session, dataset)
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine):
    settings = Settings(_env_file=None, demo_auth_enabled=True,
                        jwt_secret="catalog-test-secret-" * 4, demo_hr_password="catalog-test-password")
    app = create_app(settings)
    # Keep this module independently testable while the coordinator connects routers.
    if not any(route.path == "/api/v1/events" for route in app.routes):
        app.include_router(router)
    def sessions():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[session_dependency] = sessions
    with TestClient(app) as result:
        yield result


def headers(client, employee_id=None):
    principal = Principal(Role.EMPLOYEE, employee_id) if employee_id else Principal(Role.HR)
    return {"Authorization": "Bearer " + issue_token(client.app.state.settings, principal)}


@pytest.mark.parametrize("path", ["/hr/employees", "/events", "/events/EV_001"])
def test_access(client, path):
    url = "/api/v1" + path
    assert client.get(url).status_code == 401
    assert client.get(url, headers={"Authorization": "Bearer broken"}).status_code == 401
    response = client.get(url, headers=headers(client))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert client.get(url, headers=headers(client, "E0001")).status_code == (
        403 if path == "/hr/employees" else 200)


def test_hr_directory_matches_dataset(client, dataset, engine):
    actual = client.get("/api/v1/hr/employees", headers=headers(client)).json()
    expected = [{**employee.model_dump(include={"employee_id", "full_name", "role", "grade",
                                                "tenure_months", "department"}),
                 "career_readiness": None} for employee in dataset.employees.employees]
    assert actual == sorted(expected, key=lambda employee: employee["employee_id"])
    with Session(engine) as session:
        employee = session.scalar(select(Employee).where(Employee.role == "HR Business Partner"))
        assert employee is not None
        employee_id = employee.employee_id
    assert client.get("/api/v1/hr/employees", headers=headers(client, employee_id)).status_code == 403


def test_catalog_matches_source_and_details(client, dataset, engine):
    auth = headers(client, "E0001")
    actual = client.get("/api/v1/events", headers=auth).json()
    names = {skill.skill_id: skill.name for skill in dataset.catalog.skills}
    assert [event["event_id"] for event in actual] == sorted(event.event_id for event in dataset.events.events)
    source = {event.event_id: event for event in dataset.events.events}
    with Session(engine) as session:
        repeatable = dict(session.execute(select(Event.event_id, Event.repeatable)).all())
    for event in actual:
        expected = source[event["event_id"]].model_dump(mode="json")
        expected["develops_skills"] = sorted(
            [{**effect, "name": names[effect["skill_id"]]} for effect in expected["develops_skills"]],
            key=lambda effect: effect["skill_id"])
        expected["repeatable"] = repeatable[event["event_id"]]
        assert event == expected
        detail = client.get("/api/v1/events/" + event["event_id"], headers=auth)
        assert detail.status_code == 200
        assert detail.json() == event
    assert client.get("/api/v1/events/missing", headers=auth).status_code == 404


def test_empty_catalog_and_directory(client, tmp_path):
    empty_engine = create_engine("sqlite:///" + str(tmp_path / "empty.db"))
    Base.metadata.create_all(empty_engine)
    def sessions():
        with Session(empty_engine) as session:
            yield session
    client.app.dependency_overrides[session_dependency] = sessions
    try:
        for path in ["hr/employees", "events"]:
            response = client.get("/api/v1/" + path, headers=headers(client))
            assert response.status_code == 200
            assert response.json() == []
        assert client.get("/api/v1/events/missing", headers=headers(client)).status_code == 404
    finally:
        empty_engine.dispose()


@pytest.mark.parametrize("path,query", [("hr/employees", "hr_employees"),
                                      ("events", "catalog_events")])
def test_database_errors_are_sanitized(client, path, query):
    with patch("app.application.catalog." + query,
               side_effect=OperationalError("sensitive SQL", {}, Exception("sensitive server"))):
        response = client.get("/api/v1/" + path, headers=headers(client))
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_business_route_registrations_are_unique():
    from collections import Counter
    from app.main import create_app
    app = create_app()
    routes = Counter((method, route.path) for route in app.routes
                     for method in getattr(route, 'methods', []) if route.path.startswith('/api/v1/'))
    assert not {key: count for key, count in routes.items() if count > 1}
