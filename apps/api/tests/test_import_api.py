import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.access import session as read_session
from app.api.datasets import router, write_session
from app.infrastructure.database import Base
from app.main import create_app
from test_auth_api import config, hr, login

ROOT = Path(__file__).resolve().parents[3] / 'dataset'


@pytest.fixture
def client(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'import.sqlite3'))
    Base.metadata.create_all(engine)
    app = create_app(config())
    if not any(route.path == '/api/v1/datasets/import' for route in app.routes):
        app.include_router(router)
    def sessions():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[read_session] = sessions
    app.dependency_overrides[write_session] = sessions
    with TestClient(app) as client:
        yield client
    engine.dispose()


def initial_files():
    return {name: (name, (ROOT / name).read_bytes()) for name in
            ('employees.json', 'events.json', 'skills.json', 'activity_history.csv')}


def append_files():
    payload = json.loads((ROOT / 'employees.json').read_text())
    person = payload['employees'][0]
    person.update(employee_id='jury-upload', manager_id=None)
    payload['employees'] = [person]
    header = (ROOT / 'activity_history.csv').read_text().splitlines()[0] + '\n'
    return {'employees.json': ('employees.json', json.dumps(payload).encode()),
            'activity_history.csv': ('activity_history.csv', header.encode())}


def upload(client, files, mode='initial', headers=None):
    return client.post('/api/v1/datasets/import', data={'mode': mode}, files=files, headers=headers)


def test_initial_append_and_replays(client):
    headers = hr(client)
    response = upload(client, initial_files(), headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['history_records'] == 2743
    assert upload(client, initial_files(), headers=headers).json()['status'] == 'unchanged'
    appended = upload(client, append_files(), mode='append', headers=headers)
    assert appended.status_code == 200, appended.text
    assert appended.json() == {'status': 'imported', 'employees': 1, 'skills': 0, 'events': 0, 'history_records': 0}
    assert upload(client, append_files(), mode='append', headers=headers).json()['status'] == 'unchanged'
    assert login(client, 'jury-upload')


def test_authorization(client):
    assert upload(client, initial_files()).status_code == 401
    upload(client, initial_files(), headers=hr(client))
    assert upload(client, append_files(), mode='append', headers=login(client)).status_code == 403


@pytest.mark.parametrize('kind', ['json', 'csv', 'missing', 'extra', 'duplicate', 'oversize'])
def test_invalid_upload(client, kind):
    files = initial_files()
    if kind == 'json':
        files['employees.json'] = ('employees.json', b'{')
    elif kind == 'csv':
        files['activity_history.csv'] = ('activity_history.csv', b'bad,header\n')
    elif kind == 'missing':
        del files['skills.json']
    elif kind == 'extra':
        files['extra.json'] = ('extra.json', b'{}')
    elif kind == 'duplicate':
        files = list(files.items()) + [('employees.json', files['employees.json'])]
    else:
        files['employees.json'] = ('employees.json', b' ' * (10 * 1024 * 1024 + 1))
    result = upload(client, files, headers=hr(client))
    assert result.status_code == (413 if kind == 'oversize' else 422), result.text
    assert upload(client, initial_files(), headers=hr(client)).status_code == 200


def test_conflicts_and_missing_initial(client):
    headers = hr(client)
    assert upload(client, append_files(), mode='append', headers=headers).status_code == 409
    assert upload(client, initial_files(), headers=headers).status_code == 200
    files = initial_files()
    changed = json.loads(files['employees.json'][1])
    changed['employees'][0]['full_name'] = 'Changed'
    files['employees.json'] = ('employees.json', json.dumps(changed).encode())
    assert upload(client, files, headers=headers).status_code == 409


def test_malformed_multipart(client):
    result = client.post('/api/v1/datasets/import', headers={**hr(client),
        'Content-Type': 'multipart/form-data; boundary=valid'}, content=b'--wrong\r\ninvalid')
    assert result.status_code == 422
