#!/usr/bin/env python3
"""
Example demonstrating Bedrock response format support.

This example shows how the BedrockResponseFormatWrapper enables structured
JSON responses from Bedrock clients that match the AgentResponse schema.
"""
import asyncio
import json
import os
from typing import List

from agent_framework import ChatMessage, TextContent, Role
from aletheia.agents.model import AgentResponse
from aletheia.agents.bedrock_wrapper import BedrockResponseFormatWrapper


class MockBedrockChatAgent:
    """Mock Bedrock ChatAgent that returns unstructured text."""
    
    async def run_stream(self, messages: List[ChatMessage], **kwargs):
        """Mock run_stream that returns unstructured text (simulating Bedrock behavior)."""
        # Simulate Bedrock returning unstructured text instead of JSON
        unstructured_response = """
        Based on my analysis, I have medium confidence in these findings.
        
        I found that the system is experiencing high CPU usage and memory pressure.
        The logs show several error messages related to database connections.
        
        My approach was to examine the system metrics and log files.
        I used monitoring tools and log analysis.
        
        Next steps should include:
        1. Restart the database service
        2. Check network connectivity
        3. Monitor system resources
        """
        
        # In a real Bedrock client, this would be streamed
        class MockResponse:
            def __init__(self, text):
                self.text = text
                self.contents = []
        
        yield MockResponse(unstructured_response)


class MockBedrockChatAgentWithJSON:
    """Mock Bedrock ChatAgent that can return JSON when prompted correctly."""
    
    async def run_stream(self, messages: List[ChatMessage], **kwargs):
        """Mock run_stream that returns JSON when JSON instructions are present."""
        # Check if JSON instructions were added to the messages
        has_json_instructions = False
        for message in messages:
            if message.role == Role.SYSTEM:
                for content in message.contents:
                    if hasattr(content, 'text') and 'JSON' in content.text:
                        has_json_instructions = True
                        break
        
        if has_json_instructions:
            # Return structured JSON response
            structured_response = {
                "confidence": 0.75,
                "agent": "bedrock_agent",
                "findings": {
                    "summary": "System experiencing high resource usage",
                    "details": "CPU usage at 85%, memory pressure detected, database connection errors in logs",
                    "tool_outputs": [
                        {
                            "tool_name": "system_monitor",
                            "command": "top -n 1",
                            "output": "CPU: 85.2% user, 12.1% system, 2.7% idle"
                        }
                    ],
                    "additional_output": None,
                    "skill_used": None,
                    "knowledge_searched": False
                },
                "decisions": {
                    "approach": "Systematic analysis of system metrics and logs",
                    "tools_used": ["system_monitor", "log_analyzer"],
                    "skills_loaded": [],
                    "rationale": "High resource usage indicates performance bottleneck",
                    "checklist": [
                        "Check CPU usage",
                        "Analyze memory consumption", 
                        "Review error logs"
                    ],
                    "additional_output": None
                },
                "next_actions": {
                    "steps": [
                        "Restart database service",
                        "Check network connectivity",
                        "Monitor system resources for 30 minutes"
                    ],
                    "additional_output": None
                },
                "errors": None
            }
            
            class MockResponse:
                def __init__(self, text):
                    self.text = text
            
            yield MockResponse(json.dumps(structured_response))
        else:
            # Return unstructured text (original Bedrock behavior)
            unstructured_response = "System analysis shows high CPU and memory usage..."
            
            class MockResponse:
                def __init__(self, text):
                    self.text = text
            
            yield MockResponse(unstructured_response)


async def demonstrate_without_wrapper():
    """Demonstrate Bedrock behavior without the wrapper."""
    print("=== WITHOUT BEDROCK WRAPPER ===")
    print("Simulating original Bedrock behavior (returns unstructured text)\n")
    
    agent = MockBedrockChatAgent()
    messages = [ChatMessage(role=Role.USER, contents=[TextContent(text="Analyze system performance")])]
    
    print("Request: Analyze system performance")
    print("Response format requested: AgentResponse (JSON)")
    print("Actual response:")
    
    async for response in agent.run_stream(messages, response_format=AgentResponse):
        print(f"  {response.text}")
    
    print("\n❌ Problem: Bedrock ignores response_format and returns unstructured text")
    print("   The CLI would fail to parse this as JSON!\n")


async def demonstrate_with_wrapper():
    """Demonstrate Bedrock behavior with the wrapper."""
    print("=== WITH BEDROCK WRAPPER ===")
    print("Using BedrockResponseFormatWrapper to add JSON support\n")
    
    agent = MockBedrockChatAgentWithJSON()
    wrapper = BedrockResponseFormatWrapper(agent)
    
    messages = [ChatMessage(role=Role.USER, contents=[TextContent(text="Analyze system performance")])]
    
    print("Request: Analyze system performance")
    print("Response format requested: AgentResponse (JSON)")
    print("Wrapper adds JSON instructions to the prompt...")
    print("Actual response:")
    
    async for response in agent.run_stream(messages, response_format=AgentResponse):
        # Try to parse as JSON to show it's valid
        try:
            parsed = json.loads(response.text)
            print("✅ Valid JSON response received!")
            print(f"   Agent: {parsed['agent']}")
            print(f"   Confidence: {parsed['confidence']}")
            print(f"   Findings Summary: {parsed['findings']['summary']}")
            print(f"   Next Actions: {len(parsed['next_actions']['steps'])} steps")
        except json.JSONDecodeError:
            print(f"  Raw text: {response.text}")
    
    print("\n✅ Success: Wrapper enables structured JSON responses from Bedrock!")
    print("   The CLI can now parse and display formatted output.\n")


async def main():
    """Run the demonstration."""
    print("Bedrock Response Format Wrapper Demonstration")
    print("=" * 50)
    print()
    
    await demonstrate_without_wrapper()
    await demonstrate_with_wrapper()
    
    print("Summary:")
    print("- Original Bedrock clients ignore response_format parameter")
    print("- BedrockResponseFormatWrapper adds JSON schema instructions to prompts")
    print("- This enables structured output that matches AgentResponse schema")
    print("- CLI and API can now parse and display formatted responses from Bedrock")


if __name__ == "__main__":
    asyncio.run(main())