import pytest
from fastapi.testclient import TestClient
from app.api.main import app
from app.config import config
import os

client = TestClient(app)

@pytest.fixture
def mock_env_setup(monkeypatch):
    monkeypatch.setenv("API_KEY_REQUIRED", "false")
    monkeypatch.setenv("ENCRYPTION_KEY", "test_key_must_be_32_bytes_long_exact!!")

def test_health_check(mock_env_setup):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in ["healthy", "degraded"]
    assert "components" in response.json()

def test_list_runs(mock_env_setup):
    response = client.get("/runs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_application_defaults(mock_env_setup):
    response = client.get("/application-defaults")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)
