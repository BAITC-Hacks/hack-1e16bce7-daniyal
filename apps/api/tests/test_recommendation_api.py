import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.application.import_dataset import import_dataset
from app.domain.ranking import DeterministicRecommendationEngine
from app.infrastructure.ai_dataset import DatasetSnapshot
from app.infrastructure.database import Base
from app.infrastructure.dataset_loader import load_dataset
from app.infrastructure.explanations import ExplanationResult, TemplateExplanationProvider
from app.infrastructure.models import EmployeeSkill
from app.infrastructure.recommendation_context import load_context
from app.main import create_app
from test_auth_api import config, hr, login

DATASET = Path(__file__).resolve().parents[3] / "dataset"


@pytest.fixture(scope="module")
def database():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as session:
        import_dataset(session, load_dataset(DATASET))
    yield SimpleNamespace(sessions=sessions, close=lambda: None)
    engine.dispose()


def test_database_ranking_matches_dataset_without_replaying_gains(database):
    snapshot = DatasetSnapshot.load(DATASET)
    engine = DeterministicRecommendationEngine()
    with database.sessions() as session:
        for employee_id in snapshot.employees:
            actual, names = load_context(session, employee_id, "ru")
            expected = snapshot.context_for(employee_id, "ru")
            assert actual.employee.skills == expected.employee.skills
            assert engine.rank(actual) == engine.rank(expected)
            assert names == snapshot.skill_names
        row = session.get(EmployeeSkill, ("E0028", next(iter(names))))
        row.level = (row.level + 1) % 6
        session.flush()
        changed, _ = load_context(session, "E0028", "ru")
        assert changed.employee.skills[row.skill_id] == row.level
        session.rollback()


@pytest.fixture
def client(database, monkeypatch):
    monkeypatch.setenv('LLM_ENABLED', 'false')
    with patch("app.main.Database", return_value=database):
        with TestClient(create_app(config())) as client:
            client.headers.update(hr(client))
            yield client


def test_employee_list_and_live_provider_metadata(client):
    response = client.get("/api/v1/employees")
    assert response.status_code == 200
    assert len(response.json()["employees"]) == 200
    assert response.headers["cache-control"] == "no-store"
    class Provider:
        async def explain_with_metadata(self, context):
            assert context.locale == "kk"
            return ExplanationResult(await TemplateExplanationProvider().explain(context), "ollama")
    client.app.state.explanations = Provider()
    response = client.post("/api/v1/recommendations", json={"employee_id": "E0028", "locale": "kk"})
    assert response.status_code == 200
    body = response.json()
    assert body["explanation_source"] == "ollama" and body["fallback_reason"] is None
    assert 1 <= len(body["recommendations"]) <= 3
    assert all(row["title"] and row["explanation"] for row in body["recommendations"])


def test_unknown_employee_invalid_locale_and_busy_model(client):
    assert client.post("/api/v1/recommendations", json={"employee_id": "UNKNOWN"}).status_code == 404
    assert not client.app.state.inference_slot.locked()
    assert client.post("/api/v1/recommendations", json={"employee_id": "E0028", "locale": "xx"}).status_code == 422
    client.app.state.inference_slot = asyncio.Semaphore(0)
    assert client.post("/api/v1/recommendations", json={"employee_id": "E0028"}).status_code == 429


def test_fallback_is_never_reported_as_live_ai(client):
    class Provider:
        async def explain_with_metadata(self, context):
            return ExplanationResult(await TemplateExplanationProvider().explain(context), "template", "timeout")
    client.app.state.explanations = Provider()
    body = client.post("/api/v1/recommendations", json={"employee_id": "E0028"}).json()
    assert body["explanation_source"] == "template" and body["fallback_reason"] == "timeout"


def test_recommendations_preserve_session_and_employee_access_rules(client):
    body = {"employee_id": "E0028", "locale": "ru"}
    anonymous = {"Authorization": ""}
    assert client.get("/api/v1/employees", headers=anonymous).status_code == 401
    assert client.post("/api/v1/recommendations", json=body, headers=anonymous).status_code == 401
    employee = login(client, "E0028")
    response = client.get("/api/v1/employees", headers=employee)
    assert [row["employee_id"] for row in response.json()["employees"]] == ["E0028"]
    assert client.post("/api/v1/recommendations", json=body, headers=employee).status_code == 200
    body["employee_id"] = "E0001"
    assert client.post("/api/v1/recommendations", json=body, headers=employee).status_code == 403
    assert not client.app.state.inference_slot.locked()
    client.app.state.settings.demo_auth_enabled = False
    assert client.get("/api/v1/employees", headers=employee).status_code == 401
    assert client.post("/api/v1/recommendations", json=body, headers=employee).status_code == 401
