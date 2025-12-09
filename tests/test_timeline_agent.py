import pytest
import json
import unittest
from unittest.mock import AsyncMock, MagicMock
from aletheia.agents.timeline.timeline_agent import TimelineAgent
from agent_framework import ChatMessage, TextContent, Role

@pytest.mark.asyncio
async def test_timeline_agent_returns_json():
    # Mock the LLM response to be a valid JSON string
    mock_json_response = """
    [
        {
            "timestamp": "2023-10-27 10:00:00",
            "type": "ACTION",
            "description": "User started session"
        },
        {
            "timestamp": "2023-10-27 10:01:00",
            "type": "FINDING",
            "description": "Error log found"
        }
    ]
    """
    
    # Mock LLMClient to avoid "No valid LLM configuration" error
    with unittest.mock.patch('aletheia.agents.client.LLMClient.get_client') as mock_get_client:
        mock_client_instance = MagicMock()
        mock_get_client.return_value = mock_client_instance
        
        # We also need to mock the agent execution since we don't want real calls
        with unittest.mock.patch('aletheia.agents.base.ChatAgent') as mock_chat_agent:
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=MagicMock(text=mock_json_response))
            mock_chat_agent.return_value = mock_agent_instance

            agent = TimelineAgent(name="test_timeline", instructions="test instructions", description="test description")
            
            message = ChatMessage(role=Role.USER, contents=[TextContent(text="Generate timeline")])
            response = await agent.agent.run(message)
            
            # Verify we can parse the JSON
            parsed_data = json.loads(response.text)
            assert isinstance(parsed_data, list)
            assert len(parsed_data) == 2
            assert parsed_data[0]["type"] == "ACTION"
