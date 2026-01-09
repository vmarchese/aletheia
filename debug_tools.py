#!/usr/bin/env python3
"""
Debug script to test tool passing to Bedrock client directly.
"""
import os
import asyncio
from agent_framework import ChatMessage, TextContent, Role, ChatOptions
from agent_framework_bedrock import BedrockChatClient

class MockTool:
    """Mock tool for testing."""
    
    def __init__(self, name: str):
        self.__name__ = name
        self.name = name
        self.description = f"Mock tool {name}"
        
    def __call__(self, **kwargs):
        return f"Mock result from {self.name}"

async def test_bedrock_tools():
    """Test if tools are passed correctly to Bedrock client."""
    
    # Create Bedrock client
    model_id = os.environ.get("ALETHEIA_OPENAI_MODEL", "anthropic.claude-3-sonnet-20240229-v1:0")
    endpoint = os.environ.get("ALETHEIA_OPENAI_ENDPOINT", "")
    region = endpoint.split(".")[1] if "." in endpoint else "us-east-1"
    
    client = BedrockChatClient(model_id=model_id, region=region)
    
    # Create mock tools
    tools = [MockTool("test_tool_1"), MockTool("test_tool_2")]
    
    # Create test message
    messages = [
        ChatMessage(role=Role.USER, contents=[TextContent(text="Hello, can you use tools?")])
    ]
    
    chat_options = ChatOptions()
    
    print("Testing direct tool passing to BedrockChatClient...")
    print(f"Tools: {[tool.name for tool in tools]}")
    
    try:
        # Test streaming response with tools
        print("\n=== Testing Streaming Response ===")
        async for update in client._inner_get_streaming_response(
            messages=messages,
            chat_options=chat_options,
            tools=tools
        ):
            print(f"Streaming update: {update}")
            break  # Just test the first update
            
    except Exception as e:
        print(f"Streaming test failed: {e}")
    
    try:
        # Test non-streaming response with tools
        print("\n=== Testing Non-Streaming Response ===")
        response = await client._inner_get_response(
            messages=messages,
            chat_options=chat_options,
            tools=tools
        )
        print(f"Non-streaming response: {response}")
        
    except Exception as e:
        print(f"Non-streaming test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_bedrock_tools())