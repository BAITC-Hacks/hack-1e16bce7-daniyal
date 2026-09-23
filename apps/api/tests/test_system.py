from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        yield client


def test_health_does_not_require_database(client):
    with patch.object(client.app.state.database, "check", side_effect=AssertionError("must not connect")):
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "stage": "foundation"}


def test_readiness_checks_database(client):
    with patch.object(client.app.state.database, "check") as check:
        response = client.get("/api/v1/ready")
    check.assert_called_once_with()
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_readiness_hides_connection_details(client):
    error = OperationalError("SELECT 1", {}, Exception("password=private-secret"))
    with patch.object(client.app.state.database, "check", side_effect=error):
        response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
    assert "private-secret" not in response.text
