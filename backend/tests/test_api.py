"""
Tests for API endpoints — uses FastAPI TestClient.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "2.0.0"


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "name" in response.json()


@patch("app.api.v1.runs.get_supabase_client")
def test_create_run_no_supabase(mock_supa):
    """Run creation should succeed and return run_id even without Supabase."""
    mock_supa.return_value = None
    with patch("app.api.v1.runs.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        response = client.post("/api/v1/runs", json={
            "topic": "AI in business",
            "platforms": ["instagram"]
        })
    assert response.status_code == 200
    assert "run_id" in response.json()["data"]


@patch("app.api.v1.ingest.get_supabase_client")
def test_ingest_webhook_compat(mock_supa):
    mock_supa.return_value = None
    response = client.post("/webhook/kelvin6k/ingest", json={
        "source": "document",
        "filename": "test.pdf",
        "storage_path": "test-id/test.pdf",
        "brand_id": "brand_atlas"
    })
    assert response.status_code == 200
    assert response.json()["ok"] is True


@patch("app.api.v1.runs.get_supabase_client")
def test_run_now_webhook_compat(mock_supa):
    mock_supa.return_value = None
    with patch("app.api.v1.runs.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        response = client.post("/webhook/kelvin6k/run-now", json={
            "brand_id": "brand_atlas",
            "platforms": ["instagram", "linkedin"]
        })
    assert response.status_code == 200
    assert "run_id" in response.json()["data"]


@patch("app.api.webhooks.get_supabase_client")
def test_approval_action_webhook_compat(mock_supa):
    mock_supa.return_value = None
    response = client.post("/webhook/kelvin6k/approval-action", json={
        "draft_id": "draft_123",
        "action": "reject",
        "feedback": None,
        "decided_by": "user"
    })
    assert response.status_code == 200
