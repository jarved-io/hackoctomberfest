"""Tests for the GET /health endpoint."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_contains_status_ok():
    data = client.get("/health").json()
    assert data["status"] == "ok"


def test_health_contains_service_name():
    data = client.get("/health").json()
    assert data["service"] == "api-hallucination-firewall"


def test_health_contains_version():
    data = client.get("/health").json()
    assert "version" in data


def test_health_does_not_expose_secrets():
    """Health must not leak env vars, paths, or credentials."""
    data = client.get("/health").json()
    text = str(data).lower()
    for forbidden in ("password", "secret", "/users/", "home", ".env"):
        assert forbidden not in text
