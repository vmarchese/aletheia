import os
import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from unittest.mock import patch, MagicMock

from aletheia.api import app
from aletheia.session import Session

client = TestClient(app)

@pytest.fixture
def temp_session_dir():
    # Create a temporary directory for sessions
    temp_dir = tempfile.mkdtemp()
    original_session_dir = Session.DEFAULT_SESSION_DIR
    Session.DEFAULT_SESSION_DIR = Path(temp_dir)
    yield Path(temp_dir)
    # Cleanup
    shutil.rmtree(temp_dir)
    Session.DEFAULT_SESSION_DIR = original_session_dir

def test_list_sessions_empty(temp_session_dir):
    response = client.get("/sessions")
    assert response.status_code == 200
    assert response.json() == []

def test_create_session(temp_session_dir):
    response = client.post("/sessions", json={"name": "Test Session", "password": "test", "unsafe": False})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Session"
    assert "id" in data
    
    # Verify it exists in list
    response = client.get("/sessions")
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == data["id"]

def test_create_session_unsafe(temp_session_dir):
    response = client.post("/sessions", json={"name": "Unsafe Session", "unsafe": True})
    assert response.status_code == 200
    data = response.json()
    assert data["unsafe"] is True
    
    # Verify metadata file is json (not encrypted)
    session_dir = temp_session_dir / data["id"]
    assert (session_dir / "metadata.json").exists()

def test_get_session_metadata(temp_session_dir):
    # Create session first
    create_resp = client.post("/sessions", json={"name": "Metadata Test", "unsafe": True})
    session_id = create_resp.json()["id"]
    
    response = client.get(f"/sessions/{session_id}")
    assert response.status_code == 200
    assert response.json()["id"] == session_id
    assert response.json()["name"] == "Metadata Test"

def test_delete_session(temp_session_dir):
    create_resp = client.post("/sessions", json={"name": "Delete Test", "unsafe": True})
    session_id = create_resp.json()["id"]
    
    response = client.delete(f"/sessions/{session_id}")
    assert response.status_code == 200
    
    # Verify it's gone
    response = client.get("/sessions")
    assert len(response.json()) == 0

def test_export_session(temp_session_dir):
    create_resp = client.post("/sessions", json={"name": "Export Test", "unsafe": True})
    session_id = create_resp.json()["id"]
    
    response = client.get(f"/sessions/{session_id}/export?unsafe=true")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/gzip"

@patch("aletheia.api.get_or_create_orchestrator")
def test_chat_session(mock_get_orch, temp_session_dir):
    # Mock orchestrator
    mock_orch = MagicMock()
    mock_get_orch.return_value = mock_orch
    
    create_resp = client.post("/sessions", json={"name": "Chat Test", "unsafe": True})
    session_id = create_resp.json()["id"]
    
    response = client.post(f"/sessions/{session_id}/chat?unsafe=true", json={"message": "Hello"})
    assert response.status_code == 200
    assert response.json()["status"] == "processing"

def test_read_root(temp_session_dir):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<title>Aletheia - AI Troubleshooting</title>" in response.text

