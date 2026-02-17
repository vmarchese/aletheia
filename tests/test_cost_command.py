import pytest
from unittest.mock import MagicMock, patch
from aletheia.api import run_agent_step, run_command_step, active_investigations
from agent_framework import AgentSession, Content, UsageDetails
import asyncio


# Mock Orchestrator
class MockOrchestrator:
    def __init__(self):
        self.agent = MagicMock()
        self.completion_usage = {
            "input_token_count": 0, "output_token_count": 0
        }
        self.agent_session = AgentSession()


@pytest.mark.asyncio
async def test_usage_tracking():
    # Setup
    orchestrator = MockOrchestrator()
    queue = asyncio.Queue()

    # Mock stream response with usage
    async def mock_stream(*args, **kwargs):
        # Yield a text response
        yield MagicMock(
            text="Hello",
            contents=[Content.from_text("Hello")],
        )
        # Yield a usage response
        usage = UsageDetails(
            input_token_count=10, output_token_count=5
        )
        yield MagicMock(
            text="",
            contents=[Content.from_usage(usage)],
        )

    orchestrator.agent.run_stream = mock_stream

    # Run agent step
    await run_agent_step(orchestrator, "hi", queue)

    # Verify usage updated
    assert orchestrator.completion_usage["input_token_count"] == 10
    assert orchestrator.completion_usage["output_token_count"] == 5


@pytest.mark.asyncio
@patch("aletheia.api.load_config")
async def test_cost_command_with_usage(mock_load_config):
    # Setup
    session_id = "test_session_cost"
    orchestrator = MockOrchestrator()
    # Pre-populate usage
    orchestrator.completion_usage = {
        "input_token_count": 100, "output_token_count": 50
    }
    active_investigations[session_id] = orchestrator

    # Mock config
    mock_config = MagicMock()
    mock_config.cost_per_input_token = 0.001
    mock_config.cost_per_output_token = 0.002
    mock_load_config.return_value = mock_config

    queue = asyncio.Queue()

    # Run cost command
    await run_command_step("cost", [], queue, session_id)

    # Verify output
    item = await queue.get()
    assert item["type"] == "text"
    output = item["content"]

    # Check if calculation is correct in output
    # Total cost = 100*0.001 + 50*0.002 = 0.1 + 0.1 = 0.2
    assert "0.200000" in output
    assert "150" in output  # Total tokens
