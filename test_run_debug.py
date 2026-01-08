#!/usr/bin/env python3
"""
Debug script to trace the run method execution.
"""
import asyncio
from typing import Annotated
from pydantic import Field

from agent_framework import ChatAgent, ChatMessage, ChatOptions
from aletheia.agents.client import LLMClient
from agent_framework._tools import ai_function


@ai_function
def test_tool(message: Annotated[str, Field(description="A test message")]) -> str:
    """A simple test tool that returns the message."""
    print(f"[TEST TOOL] Called with message: {message}")
    return f"Tool received: {message}"


# Monkey patch the ChatAgent run method to add debug output
original_run = ChatAgent.run

async def debug_run(self, messages=None, *, thread=None, tools=None, **kwargs):
    print(f"[DEBUG RUN] Called with tools parameter: {tools}")
    print(f"[DEBUG RUN] Agent chat_options.tools: {self.chat_options.tools}")
    print(f"[DEBUG RUN] kwargs: {list(kwargs.keys())}")
    
    # Call the original run method
    return await original_run(self, messages, thread=thread, tools=tools, **kwargs)

ChatAgent.run = debug_run


async def main():
    print("Debugging run method...")
    
    # Create LLM client
    client = LLMClient()
    bedrock_client = client.get_client()
    
    # Create agent with tool
    agent = ChatAgent(
        chat_client=bedrock_client,
        name="test_agent",
        description="Test agent for tool passing",
        instructions="You are a test agent. Use the test_tool when asked to test something.",
        tools=[test_tool]
    )
    
    print(f"Agent created with tools: {agent.chat_options.tools}")
    
    # Test message - call run without tools parameter
    message = "Please use the test tool with the message 'Hello from test'"
    
    try:
        print("\n=== Calling agent.run() ===")
        response = await agent.run(message)
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())