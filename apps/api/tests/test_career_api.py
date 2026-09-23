"""Integration coverage for the complete career workflow against a real database."""
from contextlib import contextmanager
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.api.access import session as session_dependency
from app.api.datasets import write_session
from app.application.career import CareerSnapshot
from app.application.import_dataset import import_dataset
from app.domain.ranking import DeterministicRecommendationEngine
from app.infrastructure.database import Base
from app.infrastructure.dataset_loader import load_dataset
from app.infrastructure.models import ActivityHistory, Employee, EmployeeSkill
from app.main import create_app
from test_auth_api import config, login, hr

DATASET = Path(__file__).resolve().parents[3] / 'dataset'


@contextmanager
def workspace(tmp_path, imported=True):
    engine = create_engine('sqlite:///' + str(tmp_path / 'career.sqlite3'))
    Base.metadata.create_all(engine)
    if imported:
        with Session(engine) as db:
            import_dataset(db, load_dataset(DATASET))
    app = create_app(config())
    def sessions():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[session_dependency] = sessions
    app.dependency_overrides[write_session] = sessions
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


@pytest.fixture
def client_and_engine(tmp_path, monkeypatch):
    monkeypatch.setenv('LLM_ENABLED', 'false')
    with workspace(tmp_path) as pair:
        yield pair


def recommended_employee(engine):
    with Session(engine) as db:
        snapshot = CareerSnapshot(db)
        for employee_id in snapshot.employees:
            items = DeterministicRecommendationEngine().rank(snapshot.context(employee_id))
            if len(items) >= 2:
                return employee_id
    raise AssertionError('Expected a fixture employee with at least two recommendations')


def test_employee_completes_activity_and_receives_updated_plan(client_and_engine):
    client, engine = client_and_engine
    employee_id = recommended_employee(engine)
    headers = {**login(client, employee_id), 'Idempotency-Key': 'workflow-first'}
    base = f'/api/v1/employees/{employee_id}'
    trajectory = client.get(base + '/trajectory', headers=headers).json()
    assert trajectory['grades'] == ['Junior', 'Middle', 'Senior', 'Lead']
    recommended = client.post(base + '/recommendations', json={'language': 'ru'}, headers=headers).json()
    assert 1 <= len(recommended) <= 3
    chosen = recommended[0]
    assert chosen['reason'] and chosen['explanation_source'] == 'fallback'
    assert chosen['career_readiness_after'] > chosen['career_readiness_before']
    event = client.get('/api/v1/events/' + chosen['event_id'] + '?employee_id=' + employee_id, headers=headers).json()
    assert event['duration_hours'] > 0
    assert event['preview']['career_readiness_after'] == chosen['career_readiness_after']
    response = client.post(base + '/activities/' + chosen['event_id'] + '/complete', json={}, headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['already_completed'] is False
    assert result['career_readiness_after'] == chosen['career_readiness_after']
    assert result['changes']
    current = client.get(base + '/trajectory', headers=headers).json()
    assert current['career_readiness'] == result['career_readiness_after']
    skills = {s['skill_id']: s['level'] for s in client.get(base + '/skills', headers=headers).json()['items']}
    assert all(skills[item['skill_id']] == item['after'] <= 5 for item in result['changes'])
    history = client.get(base + '/activities?limit=100', headers=headers).json()['items']
    assert any(item['event_id'] == chosen['event_id'] and item['status'] == 'completed' for item in history)
    updated = client.post(base + '/recommendations', json={'language': 'ru'}, headers=headers).json()
    assert chosen['event_id'] not in [item['event_id'] for item in updated]
    assert all(item['career_readiness_before'] == result['career_readiness_after'] for item in updated)
    again = client.post(base + '/activities/' + chosen['event_id'] + '/complete', json={}, headers={**headers, 'Idempotency-Key': 'workflow-repeat'}).json()
    assert again['already_completed'] and again['changes'] == []
    assert again['career_readiness_after'] == result['career_readiness_after']


def test_hr_metrics_match_records_and_access_is_scoped(client_and_engine):
    client, engine = client_and_engine
    employee = login(client)
    admin = hr(client)
    for section in ('dashboard', 'employees', 'skill-gaps', 'activity-stats', 'recommendation-coverage'):
        assert client.get('/api/v1/hr/' + section).status_code == 401
        assert client.get('/api/v1/hr/' + section, headers=employee).status_code == 403
        assert client.get('/api/v1/hr/' + section, headers=admin).status_code == 200
    data = client.get('/api/v1/hr/dashboard', headers=admin).json()
    assert data['employee_count'] == 200
    assert 0 <= data['active_this_month'] <= 200
    with Session(engine) as db:
        assert data['completed_activities'] == db.scalar(select(func.count()).select_from(ActivityHistory).where(ActivityHistory.status == 'completed'))
    people = client.get('/api/v1/hr/employees', headers=admin).json()
    assert len(people) == 200
    assert data['without_recommendations'] == len(client.get('/api/v1/hr/recommendation-coverage', headers=admin).json())
    assert client.get('/api/v1/employees/E0002/trajectory', headers=employee).status_code == 403
    assert client.post('/api/v1/employees/E0002/recommendations', json={}, headers=employee).status_code == 403
    assert client.get('/api/v1/events/EV_001?employee_id=E0002', headers=employee).status_code == 403
    assert client.post('/api/v1/employees/E0001/activities/EV_001/complete', json={}, headers={**admin, 'Idempotency-Key': 'hr-denied'}).status_code == 403


def test_invalid_completion_does_not_change_skills(client_and_engine):
    client, engine = client_and_engine
    headers = {**login(client), 'Idempotency-Key': 'invalid-completion'}
    before = client.get('/api/v1/employees/E0001/skills', headers=headers).json()
    with Session(engine) as db:
        snapshot = CareerSnapshot(db, ['E0001'])
        event_id = next(key for key in snapshot.events if not snapshot.eligible('E0001', key)
                        and not any(row.event_id == key and row.status == 'completed' for row in snapshot.history_rows))
    assert client.post(f'/api/v1/employees/E0001/activities/{event_id}/complete', json={}, headers=headers).status_code == 409
    assert client.post('/api/v1/employees/E0001/activities/missing/complete', json={}, headers=headers).status_code == 404
    assert client.get('/api/v1/employees/E0001/skills', headers=headers).json() == before


def test_initial_http_import_is_idempotent(tmp_path):
    with workspace(tmp_path, imported=False) as (client, engine):
        headers = hr(client)
        files = {name: (name, (DATASET / name).read_bytes()) for name in ('employees.json', 'events.json', 'skills.json', 'activity_history.csv')}
        response = client.post('/api/v1/datasets/import', data={'mode': 'initial'}, files=files, headers=headers)
        assert response.status_code == 200, response.text
        result = response.json()
        assert (result['employees'], result['events'], result['skills']) == (200, 40, 60)
        with Session(engine) as db:
            before = list(db.execute(select(EmployeeSkill.employee_id, EmployeeSkill.skill_id, EmployeeSkill.level)))
        assert client.post('/api/v1/datasets/import', data={'mode': 'initial'}, files=files, headers=headers).json()['status'] == 'unchanged'
        with Session(engine) as db:
            assert list(db.execute(select(EmployeeSkill.employee_id, EmployeeSkill.skill_id, EmployeeSkill.level))) == before
        assert client.post('/api/v1/datasets/import', data={'mode': 'initial'}, files={'employees.json': ('employees.json', b'bad')}, headers=headers).status_code == 422


def jury_files(invalid=False):
    source = json.loads((DATASET / 'employees.json').read_text())
    employee = source['employees'][0]
    employee['employee_id'] = 'JURY-NEW'
    employee['full_name'] = 'Test Jury Profile'
    if invalid:
        employee['skills']['UNKNOWN_SKILL'] = 3
    source['employees'] = [employee]
    header = (DATASET / 'activity_history.csv').read_text().splitlines()[0] + '\n'
    return {'employees.json': ('employees.json', json.dumps(source).encode()),
            'activity_history.csv': ('activity_history.csv', header.encode())}


def test_append_profiles_validates_and_preserves_existing_progress(client_and_engine):
    client, engine = client_and_engine
    headers = hr(client)
    with Session(engine) as db:
        before = list(db.execute(select(EmployeeSkill.employee_id, EmployeeSkill.skill_id, EmployeeSkill.level)))
    denied = client.post('/api/v1/datasets/import', data={'mode': 'append'}, files=jury_files(), headers=login(client))
    assert denied.status_code == 403
    bad = client.post('/api/v1/datasets/import', data={'mode': 'append'}, files=jury_files(invalid=True), headers=headers)
    assert bad.status_code == 422, bad.text
    assert client.get('/api/v1/hr/dashboard', headers=headers).json()['employee_count'] == 200
    response = client.post('/api/v1/datasets/import', data={'mode': 'append'}, files=jury_files(), headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['employees'] == 1
    assert client.get('/api/v1/hr/dashboard', headers=headers).json()['employee_count'] == 201
    repeated = client.post('/api/v1/datasets/import', data={'mode': 'append'}, files=jury_files(), headers=headers)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()['status'] == 'unchanged'
    employee = login(client, 'JURY-NEW')
    assert client.get('/api/v1/employees/JURY-NEW/trajectory', headers=employee).status_code == 200
    assert client.post('/api/v1/employees/JURY-NEW/recommendations', json={}, headers=employee).status_code == 200
    with Session(engine) as db:
        after = list(db.execute(select(EmployeeSkill.employee_id, EmployeeSkill.skill_id, EmployeeSkill.level).where(EmployeeSkill.employee_id != 'JURY-NEW')))
    assert before == after
