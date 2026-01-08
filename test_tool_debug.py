#!/usr/bin/env python3
"""
Debug script to see what's happening with tools in ChatOptions.
"""
import asyncio
import os
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


async def main():
    print("Debugging tool passing...")
    
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
    
    print(f"Agent chat_options.tools: {agent.chat_options.tools}")
    print(f"Agent chat_options.tools length: {len(agent.chat_options.tools or [])}")
    
    # Create the same ChatOptions that would be created in run()
    new_chat_options = ChatOptions(
        model_id=None,
        conversation_id=None,
        frequency_penalty=None,
        logit_bias=None,
        max_tokens=None,
        metadata=None,
        presence_penalty=None,
        response_format=None,
        seed=None,
        stop=None,
        store=None,
        temperature=None,
        tool_choice=None,
        tools=[test_tool],  # This is final_tools from the run method
        top_p=None,
        user=None,
        additional_properties={},
    )
    
    print(f"New chat_options.tools: {new_chat_options.tools}")
    print(f"New chat_options.tools length: {len(new_chat_options.tools or [])}")
    
    # Test the & operator
    merged = agent.chat_options & new_chat_options
    print(f"Merged chat_options.tools: {merged.tools}")
    print(f"Merged chat_options.tools length: {len(merged.tools or [])}")
    
    # Test what happens when tools=None in new options
    empty_chat_options = ChatOptions(
        model_id=None,
        conversation_id=None,
        frequency_penalty=None,
        logit_bias=None,
        max_tokens=None,
        metadata=None,
        presence_penalty=None,
        response_format=None,
        seed=None,
        stop=None,
        store=None,
        temperature=None,
        tool_choice=None,
        tools=None,  # This might be what's happening
        top_p=None,
        user=None,
        additional_properties={},
    )
    
    print(f"Empty chat_options.tools: {empty_chat_options.tools}")
    
    # Test the & operator with empty tools
    merged_empty = agent.chat_options & empty_chat_options
    print(f"Merged with empty tools: {merged_empty.tools}")
    print(f"Merged with empty tools length: {len(merged_empty.tools or [])}")


if __name__ == "__main__":
    asyncio.run(main())