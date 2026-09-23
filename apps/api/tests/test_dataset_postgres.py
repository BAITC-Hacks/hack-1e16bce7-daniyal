"""Opt-in integration check; all writes are isolated in a temporary schema."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from fastapi.testclient import TestClient

from app.application.import_dataset import import_dataset
from app.infrastructure.database import Database
from app.infrastructure.dataset_loader import load_dataset
from app.infrastructure.models import Employee, ActivityHistory
from app.config import Settings
from app.main import create_app


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL for PostgreSQL checks")
def test_postgres_migrations_and_concurrent_import(monkeypatch):
    api_root = Path(__file__).resolve().parents[1]
    schema = "test_dataset_" + uuid4().hex
    url = make_url(os.environ["TEST_DATABASE_URL"])
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated_url = url.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", isolated_url)
    config = Config(str(api_root / "alembic.ini"))
    database = Database(isolated_url)
    try:
        command.upgrade(config, "head")
        command.check(config)
        dataset = load_dataset(api_root.parents[1] / "dataset")
        def run_import(_):
            with database.sessions() as session:
                return import_dataset(session, dataset)["status"]
        with ThreadPoolExecutor(max_workers=2) as executor:
            assert sorted(executor.map(run_import, range(2))) == ["imported", "unchanged"]
        with database.sessions() as session:
            assert session.scalar(select(func.count()).select_from(Employee)) == 200
            assert session.scalar(select(func.count()).select_from(ActivityHistory)) == 2743
        settings = Settings(_env_file=None, database_url=isolated_url, demo_auth_enabled=True,
                            jwt_secret="postgres-integration-key-" * 3, demo_hr_password="test-hr-password")
        with TestClient(create_app(settings)) as client:
            employee_token = client.post("/api/v1/auth/demo/employee", json={"employee_id": "E0173"})
            assert employee_token.status_code == 200
            employee_headers = {"Authorization": "Bearer " + employee_token.json()["access_token"]}
            hr_token = client.post("/api/v1/auth/demo/hr", json={"password": "test-hr-password"})
            assert hr_token.status_code == 200
            hr_headers = {"Authorization": "Bearer " + hr_token.json()["access_token"]}
            for suffix in ("", "/skills", "/activities"):
                assert client.get("/api/v1/employees/E0173" + suffix, headers=employee_headers).status_code == 200
                assert client.get("/api/v1/employees/E0001" + suffix, headers=employee_headers).status_code == 403
                assert client.get("/api/v1/employees/E0001" + suffix, headers=hr_headers).status_code == 200
            verify_workflows(client, dataset, hr_headers)
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        command.check(config)
    finally:
        database.close()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def verify_workflows(client, dataset, hr_headers):
    """Exercise real HTTP uploads and completion against the migrated PostgreSQL schema."""
    import json
    from app.domain.progress import apply_skill_effects
    from app.domain.models import SkillEffect
    event = next(e for e in dataset.events.events if not e.mandatory and e.format == "self_paced"
                 and any(s.max_level > e.prerequisites.get(s.skill_id, 0) and s.gain > 0 for s in e.develops_skills))
    person = next(e for e in dataset.employees.employees if e.role in event.target_roles and e.grade in event.target_grades)
    person = person.model_copy(deep=True)
    person.employee_id = "jury-integration"
    person.manager_id = None
    person.skills = dict(event.prerequisites)
    def upload(person):
        return client.post("/api/v1/datasets/import", headers=hr_headers, data={"mode": "append"}, files={
            "employees.json": ("employees.json", json.dumps({"meta": dataset.employees.meta.model_dump(mode="json"),
                "employees": [person.model_dump(mode="json")]}).encode(), "application/json"),
            "activity_history.csv": ("activity_history.csv", b"record_id,employee_id,event_id,date,due_date,status,completion_pct,score,feedback_rating,assigned_by\n", "text/csv")})
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: upload(person), range(2)))
    assert [r.status_code for r in results] == [200, 200]
    assert sorted(r.json()["status"] for r in results) == ["imported", "unchanged"]
    assert len(client.get("/api/v1/hr/employees", headers=hr_headers).json()) == 201
    assert len(client.get("/api/v1/events", headers=hr_headers).json()) == 40
    token = client.post("/api/v1/auth/demo/employee", json={"employee_id": person.employee_id}).json()["access_token"]
    headers = {"Authorization": "Bearer " + token, "Idempotency-Key": "same-concurrent-request"}
    path = f"/api/v1/employees/{person.employee_id}"
    before = {s["skill_id"]: s["level"] for s in client.get(path + "/skills", headers=headers).json()["items"]}
    def complete(_):
        return client.post(path + f"/activities/{event.event_id}/complete", json={}, headers=headers)
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(complete, range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    assert sorted(r.json()["already_completed"] for r in responses) == [False, True]
    assert len({r.json()["record_id"] for r in responses}) == 1
    expected = apply_skill_effects(before, [SkillEffect(**s.model_dump()) for s in event.develops_skills])
    other = person.model_copy(deep=True)
    other.employee_id = "jury-concurrent-append"
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(upload, other), executor.submit(complete, 0)]
        assert all(f.result().status_code == 200 for f in futures)
    assert upload(person).json()["status"] == "unchanged"
    after = {s["skill_id"]: s["level"] for s in client.get(path + "/skills", headers=headers).json()["items"]}
    assert after == expected and after != before
    assert client.get(path + "/activities", headers=headers).json()["total"] == 1
