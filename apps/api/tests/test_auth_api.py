from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.access import session as session_dependency
from app.application.import_dataset import import_dataset
from app.auth.tokens import AUDIENCE, ISSUER
from app.config import Settings
from app.infrastructure.database import Base
from app.infrastructure.dataset_loader import load_dataset
from app.main import create_app

SECRET = 'test-signing-key-' * 4
PASSWORD = 'HR-test-password-қауіпсіз'


def config(**changes):
    return Settings(_env_file=None, demo_auth_enabled=True, jwt_secret=SECRET,
                    demo_hr_password=PASSWORD, **changes)


@pytest.fixture(scope='module')
def engine(tmp_path_factory):
    engine = create_engine('sqlite:///' + str(tmp_path_factory.mktemp('api') / 'dataset.sqlite3'))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        import_dataset(session, load_dataset(Path(__file__).resolve().parents[3] / 'dataset'))
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine):
    app = create_app(config())
    def sessions():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[session_dependency] = sessions
    with TestClient(app) as client:
        yield client


def login(client, employee_id='E0001'):
    response = client.post('/api/v1/auth/demo/employee', json={'employee_id': employee_id})
    assert response.status_code == 200
    assert response.json()['expires_in'] == 3600
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


def hr(client):
    response = client.post('/api/v1/auth/demo/hr', json={'password': PASSWORD})
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


def test_login_and_profile(client):
    headers = login(client, 'E0173')
    assert client.get('/api/v1/auth/me', headers=headers).json() == {'role': 'employee', 'employee_id': 'E0173'}
    result = client.get('/api/v1/employees/E0173', headers=headers)
    assert result.status_code == 200
    assert result.json()['employee_id'] == 'E0173'
    assert result.headers['cache-control'] == 'no-store'
    assert set(result.json()) == {'employee_id', 'full_name', 'role', 'grade', 'department', 'manager_id',
        'hire_date', 'tenure_months', 'work_format', 'preferred_language', 'career_goal', 'last_review_date'}
    assert client.get('/api/v1/auth/me', headers=hr(client)).json() == {'role': 'hr', 'employee_id': None}


@pytest.mark.parametrize('suffix', ['', '/skills', '/activities'])
def test_access_matrix(client, suffix):
    path = '/api/v1/employees/E0002' + suffix
    assert client.get(path).status_code == 401
    assert client.get(path, headers=login(client)).status_code == 403
    assert client.get(path, headers=login(client, 'E0002')).status_code == 200
    assert client.get(path, headers=hr(client)).status_code == 200
    missing = '/api/v1/employees/missing' + suffix
    assert client.get(missing, headers=login(client)).status_code == 403
    assert client.get(missing, headers=hr(client)).status_code == 404


def test_public_list_pagination_and_validation(client):
    page = client.get('/api/v1/auth/demo/employees?limit=2&offset=1').json()
    assert page['total'] == 200
    assert [e['employee_id'] for e in page['items']] == ['E0002', 'E0003']
    assert set(page['items'][0]) == {'employee_id', 'full_name', 'role', 'grade'}
    assert client.get('/api/v1/auth/demo/employees?offset=200').json()['items'] == []
    for query in ['limit=0', 'limit=101', 'offset=-1']:
        assert client.get('/api/v1/auth/demo/employees?' + query).status_code == 422
        assert client.get('/api/v1/employees/E0001/activities?' + query, headers=login(client)).status_code == 422


def test_skills_and_history_match_storage(client, engine):
    from app.infrastructure.models import EmployeeSkill, ActivityHistory
    headers = login(client)
    skills = client.get('/api/v1/employees/E0001/skills', headers=headers).json()['items']
    assert len(skills) == 60
    assert [s['skill_id'] for s in skills] == sorted(s['skill_id'] for s in skills)
    with Session(engine) as session:
        for skill in skills:
            stored = session.get(EmployeeSkill, ('E0001', skill['skill_id']))
            assert (skill['assessed_level'], skill['level']) == (stored.assessed_level, stored.level)
        history = client.get('/api/v1/employees/E0001/activities?limit=100', headers=headers).json()
        items = history['items']
        assert len(items) == history['total'] > 0
        assert [(h['date'], h['record_id']) for h in items] == sorted(
            [(h['date'], h['record_id']) for h in items], reverse=True)
        for item in items:
            stored = session.get(ActivityHistory, item['record_id'])
            assert item['status'] == stored.status
            assert item['completion_pct'] == stored.completion_pct
            assert item['event_title']
            assert 'effects_applied' not in item
    page = client.get('/api/v1/employees/E0001/activities?limit=2&offset=1', headers=headers).json()
    assert page['items'] == items[1:3]
    assert client.get('/api/v1/employees/E0001/activities?offset=10000', headers=headers).json()['items'] == []


def test_invalid_login_and_secret_not_echoed(client):
    assert client.post('/api/v1/auth/demo/hr', json={'password': 'wrong'}).status_code == 401
    assert client.post('/api/v1/auth/demo/employee', json={'employee_id': 'missing'}).status_code == 404
    result = client.post('/api/v1/auth/demo/hr', json={'password': 'sensitive', 'role': 'hr'})
    assert result.status_code == 422
    assert 'sensitive' not in result.text
    assert client.post('/api/v1/auth/demo/employee', json={'employee_id': 'E0001', 'role': 'hr'}).status_code == 422


@pytest.mark.parametrize('change', ['expired', 'signature', 'algorithm', 'iss', 'aud', 'role', 'subject',
    'missing-sub', 'missing-role', 'missing-iat', 'missing-exp', 'missing-iss', 'missing-aud', 'deleted', 'future', 'malformed'])
def test_bad_tokens(client, change):
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {'sub': 'employee:E0001', 'role': 'employee', 'iat': now, 'exp': now + 3600,
              'iss': ISSUER, 'aud': AUDIENCE}
    key, algorithm = SECRET, 'HS256'
    if change == 'expired':
        claims.update(iat=now - 7200, exp=now - 3600)
    elif change == 'signature':
        key = 'different-signing-key-' * 4
    elif change == 'algorithm':
        algorithm = 'HS384'
    elif change in ('iss', 'aud'):
        claims[change] = 'wrong'
    elif change == 'role':
        claims['role'] = 'hr'
    elif change == 'subject':
        claims['sub'] = 'demo:hr'
    elif change.startswith('missing-'):
        del claims[change.removeprefix('missing-')]
    elif change == 'deleted':
        claims['sub'] = 'employee:missing'
    elif change == 'future':
        claims['iat'] = now + 100
    token = jwt.encode(claims, key, algorithm=algorithm) if change != 'malformed' else 'garbage'
    response = client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + token})
    assert response.status_code == 401
    assert response.headers['www-authenticate'] == 'Bearer'
    assert response.headers['cache-control'] == 'no-store'


def test_disabled_mode_rejects_old_tokens(client):
    headers = login(client)
    client.app.state.settings.demo_auth_enabled = False
    assert client.get('/api/v1/auth/demo/employees').status_code == 404
    assert client.post('/api/v1/auth/demo/hr', json={'password': PASSWORD}).status_code == 404
    assert client.post('/api/v1/auth/demo/employee', json={'employee_id': 'E0001'}).status_code == 404
    assert client.get('/api/v1/auth/me', headers=headers).status_code == 401
    assert client.get('/api/v1/health').status_code == 200


@pytest.mark.parametrize('field', ['jwt_secret', 'demo_hr_password'])
def test_missing_secrets_fail_startup(field):
    settings = config()
    from pydantic import SecretStr
    setattr(settings, field, SecretStr(''))
    with pytest.raises(ValueError, match=field.upper()):
        with TestClient(create_app(settings)):
            pass


def test_database_errors_are_redacted(client):
    with patch('app.application.employees.list_employees', side_effect=OperationalError(
            'private SQL', {}, Exception('password=private'))):
        response = client.get('/api/v1/auth/demo/employees')
    assert response.status_code == 503
    assert response.json() == {'detail': 'Database unavailable'}
    assert response.headers['cache-control'] == 'no-store'


def test_additional_employee_without_history(client, engine):
    from sqlalchemy import delete
    from app.infrastructure.models import Employee
    employee_id = 'jury-profile-new'
    with Session(engine) as session:
        original = session.get(Employee, 'E0001')
        values = {column.name: getattr(original, column.name) for column in Employee.__table__.columns
                  if column.name != 'employee_id'}
        session.add(Employee(employee_id=employee_id, **values))
        session.commit()
    try:
        headers = login(client, employee_id)
        assert client.get('/api/v1/employees/' + employee_id, headers=headers).status_code == 200
        response = client.get('/api/v1/employees/' + employee_id + '/activities', headers=headers)
        assert response.json() == {'items': [], 'total': 0, 'limit': 50, 'offset': 0}
    finally:
        with Session(engine) as session:
            session.execute(delete(Employee).where(Employee.employee_id == employee_id))
            session.commit()
