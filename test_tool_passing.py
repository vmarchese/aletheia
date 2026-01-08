#!/usr/bin/env python3
"""
Test script to verify tools are being passed to Bedrock client.
"""
import asyncio
import os
from typing import Annotated
from pydantic import Field

from agent_framework import ChatAgent, ChatMessage
from aletheia.agents.client import LLMClient
from agent_framework._tools import ai_function


@ai_function
def test_tool(message: Annotated[str, Field(description="A test message")]) -> str:
    """A simple test tool that returns the message."""
    print(f"[TEST TOOL] Called with message: {message}")
    return f"Tool received: {message}"


async def main():
    print("Testing tool passing to Bedrock...")
    
    # Create LLM client
    client = LLMClient()
    print(f"Provider: {client.provider}")
    print(f"Model: {client.model}")
    
    # Create agent with tool
    agent = ChatAgent(
        chat_client=client.get_client(),
        name="test_agent",
        description="Test agent for tool passing",
        instructions="You are a test agent. Use the test_tool when asked to test something.",
        tools=[test_tool]
    )
    
    print(f"Agent created with {len(agent.chat_options.tools or [])} tools")
    
    # Test message
    message = "Please use the test tool with the message 'Hello from test'"
    
    try:
        response = await agent.run(message)
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())