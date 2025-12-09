import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from aletheia.api import app, investigation_queues
import asyncio

client = TestClient(app)

@pytest.fixture
def clean_queues():
    investigation_queues.clear()
    yield
    investigation_queues.clear()

def test_chat_slash_command_help(clean_queues):
    # We need to mock the background task execution because TestClient runs synchronously 
    # but background tasks might need manual triggering or we just inspect the queue if the endpoint runs logically.
    # However, FastAPI TestClient normally runs background tasks after the response.
    # But our background task `run_command_step` puts things into a queue.
    # Since we can't easily validte async queue with TestClient in sync mode without some tricks,
    # we can trust that `run_command_step` is called if we patch it?
    # Or better, we can actually let it run if we use AsyncClient?
    # For simplicity with TestClient, we can check if the response status is correct, 
    # and then maybe inspect if `run_command_step` was added to background tasks if we could.
    # But a full integration test is better.
    
    # Let's mock `run_command_step` to ensure it's called with correct args
    with patch("aletheia.api.run_command_step") as mock_run_cmd:
        response = client.post("/sessions/test_session/chat", json={"message": "/help"})
        assert response.status_code == 200
        assert response.json()["status"] == "processing_command"
        
        mock_run_cmd.assert_called_once()
        call_args = mock_run_cmd.call_args
        assert call_args[0][0] == "help" # command_name
        assert call_args[0][1] == [] # args

def test_chat_slash_command_invalid(clean_queues):
    with patch("aletheia.api.run_command_step") as mock_run_cmd:
        response = client.post("/sessions/test_session/chat", json={"message": "/invalid"})
        assert response.status_code == 200
        assert response.json()["status"] == "processing_command"
        
        mock_run_cmd.assert_called_once()
        call_args = mock_run_cmd.call_args
        assert call_args[0][0] == "invalid"


# Let's also unit test run_command_step directly since it's async
import pytest
from aletheia.api import run_command_step

@pytest.mark.asyncio
async def test_run_command_step_help():
    queue = asyncio.Queue()
    await run_command_step("help", [], queue, "test_session")
    
    # Check queue items
    item1 = await queue.get()
    assert item1["type"] == "text"
    assert "help" in item1["content"] or "Show this help message" in item1["content"]
    
    item2 = await queue.get()
    assert item2["type"] == "done"

@pytest.mark.asyncio
async def test_run_command_step_unknown():
    queue = asyncio.Queue()
    await run_command_step("foobar", [], queue, "test_session")
    
    item1 = await queue.get()
    assert item1["type"] == "error"
    assert "Unknown command" in item1["content"]

