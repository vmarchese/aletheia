#!/usr/bin/env python3
"""
Comprehensive tests for Bedrock tool use functionality.

Tests tool definition conversion, tool call response processing,
tool result handling, and end-to-end tool use scenarios with mocked AWS responses.
"""

import json
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, List

from agent_framework._types import ChatMessage, Role, TextContent, FunctionCallContent, FunctionResultContent
from agent_framework._tools import ToolProtocol

from aletheia.agents.bedrock_client import BedrockChatClient
from aletheia.agents.bedrock_tool_converter import ConverseMessageConverter
from aletheia.agents.bedrock_response_processor import ConverseResponseProcessor


class MockKubernetesTool(ToolProtocol):
    """Mock Kubernetes tool for testing."""
    
    @property
    def name(self) -> str:
        return "list_kubernetes_pods"
    
    @property
    def description(self) -> str:
        return "List Kubernetes pods in a namespace"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace to list pods from",
                    "default": "default"
                }
            },
            "required": []
        }
    
    def execute(self, **kwargs) -> str:
        namespace = kwargs.get('namespace', 'default')
        return f"Found 3 pods in namespace '{namespace}': pod1, pod2, pod3"


class MockSystemTool(ToolProtocol):
    """Mock system tool for testing."""
    
    @property
    def name(self) -> str:
        return "get_system_info"
    
    @property
    def description(self) -> str:
        return "Get system information"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "info_type": {
                    "type": "string",
                    "enum": ["cpu", "memory", "disk"],
                    "description": "Type of system information to retrieve"
                }
            },
            "required": ["info_type"]
        }
    
    def execute(self, **kwargs) -> str:
        info_type = kwargs.get('info_type', 'cpu')
        return f"System {info_type} usage: 45%"


class TestToolDefinitionConversion:
    """Test tool definition conversion to Bedrock format."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.converter = ConverseMessageConverter()
        self.kubernetes_tool = MockKubernetesTool()
        self.system_tool = MockSystemTool()
    
    def test_single_tool_conversion(self):
        """Test converting a single tool to Bedrock format."""
        tools = [self.kubernetes_tool]
        tool_definitions = self.converter.convert_tools_to_converse_format(tools)
        
        assert tool_definitions is not None
        assert len(tool_definitions) == 1
        
        bedrock_tool = tool_definitions[0]
        assert "toolSpec" in bedrock_tool
        
        tool_spec = bedrock_tool["toolSpec"]
        assert tool_spec["name"] == "list_kubernetes_pods"
        assert tool_spec["description"] == "List Kubernetes pods in a namespace"
        assert "inputSchema" in tool_spec
        assert "json" in tool_spec["inputSchema"]
        
        schema = tool_spec["inputSchema"]["json"]
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "namespace" in schema["properties"]
    
    def test_multiple_tools_conversion(self):
        """Test converting multiple tools to Bedrock format."""
        tools = [self.kubernetes_tool, self.system_tool]
        tool_definitions = self.converter.convert_tools_to_converse_format(tools)
        
        assert tool_definitions is not None
        assert len(tool_definitions) == 2
        
        tool_names = [tool["toolSpec"]["name"] for tool in tool_definitions]
        assert "list_kubernetes_pods" in tool_names
        assert "get_system_info" in tool_names
    
    def test_tool_choice_auto(self):
        """Test tool choice configuration with 'auto'."""
        tool_choice_config = self.converter.convert_tool_choice_to_converse_format("auto")
        
        assert "auto" in tool_choice_config
        assert tool_choice_config["auto"] == {}
    
    def test_tool_choice_any(self):
        """Test tool choice configuration with 'any'."""
        tool_choice_config = self.converter.convert_tool_choice_to_converse_format("any")
        
        assert "any" in tool_choice_config
        assert tool_choice_config["any"] == {}
    
    def test_tool_choice_specific_tool(self):
        """Test tool choice configuration with specific tool name."""
        tool_choice_config = self.converter.convert_tool_choice_to_converse_format({"name": "list_kubernetes_pods"})
        
        assert "tool" in tool_choice_config
        assert tool_choice_config["tool"]["name"] == "list_kubernetes_pods"
    
    def test_empty_tools_list(self):
        """Test handling empty tools list."""
        tool_definitions = self.converter.convert_tools_to_converse_format([])
        assert tool_definitions == []
    
    def test_none_tools(self):
        """Test handling None tools."""
        # This should raise an error or be handled gracefully
        try:
            tool_definitions = self.converter.convert_tools_to_converse_format(None)
            # If it doesn't raise an error, it should return an empty list
            assert tool_definitions == []
        except (TypeError, AttributeError):
            # It's acceptable for this to raise an error
            pass


class TestToolCallResponseProcessing:
    """Test processing tool calls from Bedrock responses."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = ConverseResponseProcessor()
    
    def test_tool_use_response_processing(self):
        """Test processing a response with tool use."""
        mock_response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "text": "I'll help you list the pods in your namespace."
                        },
                        {
                            "toolUse": {
                                "toolUseId": "tool_123",
                                "name": "list_kubernetes_pods",
                                "input": {
                                    "namespace": "production"
                                }
                            }
                        }
                    ]
                }
            },
            "stopReason": "tool_use",
            "usage": {
                "inputTokens": 50,
                "outputTokens": 25,
                "totalTokens": 75
            }
        }
        
        chat_response = self.processor.create_chat_response(mock_response, "test-model")
        
        # Check basic response structure - text should be in first content
        text_contents = [c for c in chat_response.messages[0].contents if hasattr(c, 'text')]
        assert len(text_contents) == 1
        assert text_contents[0].text == "I'll help you list the pods in your namespace."
        
        # Check tool call details - should be FunctionCallContent
        from agent_framework._types import FunctionCallContent
        tool_calls = [c for c in chat_response.messages[0].contents if isinstance(c, FunctionCallContent)]
        assert len(tool_calls) == 1
        
        tool_call = tool_calls[0]
        assert tool_call.call_id == "tool_123"
        assert tool_call.name == "list_kubernetes_pods"
        assert tool_call.arguments == {"namespace": "production"}
        
        # Check finish reason
        assert chat_response.finish_reason.value == "tool_calls"
    
    def test_multiple_tool_calls_response(self):
        """Test processing a response with multiple tool calls."""
        mock_response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tool_1",
                                "name": "list_kubernetes_pods",
                                "input": {"namespace": "default"}
                            }
                        },
                        {
                            "toolUse": {
                                "toolUseId": "tool_2",
                                "name": "get_system_info",
                                "input": {"info_type": "memory"}
                            }
                        }
                    ]
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 60, "outputTokens": 30, "totalTokens": 90}
        }
        
        chat_response = self.processor.create_chat_response(mock_response, "test-model")
        
        # Check tool calls - should be FunctionCallContent objects
        from agent_framework._types import FunctionCallContent
        tool_calls = [c for c in chat_response.messages[0].contents if isinstance(c, FunctionCallContent)]
        assert len(tool_calls) == 2
        assert tool_calls[0].call_id == "tool_1"
        assert tool_calls[1].call_id == "tool_2"
        assert chat_response.finish_reason.value == "tool_calls"
    
    def test_text_and_tool_use_response(self):
        """Test processing a response with both text and tool use."""
        mock_response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "text": "Let me check the system status for you."
                        },
                        {
                            "toolUse": {
                                "toolUseId": "tool_456",
                                "name": "get_system_info",
                                "input": {"info_type": "cpu"}
                            }
                        }
                    ]
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 40, "outputTokens": 20, "totalTokens": 60}
        }
        
        chat_response = self.processor.create_chat_response(mock_response, "test-model")
        
        # Check text content
        text_contents = [c for c in chat_response.messages[0].contents if hasattr(c, 'text')]
        assert len(text_contents) == 1
        assert text_contents[0].text == "Let me check the system status for you."
        
        # Check tool calls
        from agent_framework._types import FunctionCallContent
        tool_calls = [c for c in chat_response.messages[0].contents if isinstance(c, FunctionCallContent)]
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "get_system_info"


class TestToolResultHandling:
    """Test handling tool results in multi-turn conversations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.converter = ConverseMessageConverter()
    
    def test_tool_result_message_conversion(self):
        """Test converting tool result messages to Bedrock format."""
        messages = [
            ChatMessage(
                role=Role.USER,
                contents=[TextContent(text="List pods in production namespace")]
            ),
            ChatMessage(
                role=Role.ASSISTANT,
                contents=[
                    TextContent(text="I'll list the pods for you."),
                    FunctionCallContent(
                        call_id="tool_123",
                        name="list_kubernetes_pods",
                        arguments='{"namespace": "production"}'
                    )
                ]
            ),
            ChatMessage(
                role=Role.USER,
                contents=[
                    FunctionResultContent(
                        call_id="tool_123",
                        result="Found 3 pods in namespace 'production': web-1, web-2, db-1"
                    )
                ]
            )
        ]
        
        bedrock_format = self.converter.convert_to_converse_format(messages)
        bedrock_messages = bedrock_format["messages"]
        
        # Should have 3 messages: user, assistant, user (with tool result)
        assert len(bedrock_messages) == 3
        
        # Check tool result message
        tool_result_msg = bedrock_messages[2]
        assert tool_result_msg["role"] == "user"
        assert len(tool_result_msg["content"]) == 1
        assert "toolResult" in tool_result_msg["content"][0]
        
        tool_result = tool_result_msg["content"][0]["toolResult"]
        assert tool_result["toolUseId"] == "tool_123"
        assert "Found 3 pods" in tool_result["content"][0]["text"]
    
    def test_multiple_tool_results_conversion(self):
        """Test converting multiple tool results."""
        messages = [
            ChatMessage(
                role=Role.ASSISTANT,
                contents=[
                    FunctionCallContent(call_id="tool_1", name="tool1", arguments="{}"),
                    FunctionCallContent(call_id="tool_2", name="tool2", arguments="{}")
                ]
            ),
            ChatMessage(
                role=Role.USER,
                contents=[
                    FunctionResultContent(call_id="tool_1", result="Result 1"),
                    FunctionResultContent(call_id="tool_2", result="Result 2")
                ]
            )
        ]
        
        bedrock_format = self.converter.convert_to_converse_format(messages)
        bedrock_messages = bedrock_format["messages"]
        
        # Should have 2 messages: assistant + user (with tool results)
        assert len(bedrock_messages) == 2
        
        user_msg = bedrock_messages[1]
        assert user_msg["role"] == "user"
        assert len(user_msg["content"]) == 2  # Two tool results
        
        # Check both tool results are present
        tool_ids = [content["toolResult"]["toolUseId"] for content in user_msg["content"]]
        assert "tool_1" in tool_ids
        assert "tool_2" in tool_ids


class TestEndToEndToolUse:
    """Test end-to-end tool use scenarios with mocked AWS responses."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = BedrockChatClient(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            region="us-east-1"
        )
        self.tools = [MockKubernetesTool(), MockSystemTool()]
    
    @pytest.mark.asyncio
    @patch.object(BedrockChatClient, '_call_converse_with_retry')
    async def test_complete_tool_use_flow(self, mock_converse):
        """Test complete tool use flow with mocked Bedrock responses."""
        # Mock response with tool use
        mock_converse.return_value = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "text": "I'll check the pods in your namespace."
                        },
                        {
                            "toolUse": {
                                "toolUseId": "tool_123",
                                "name": "list_kubernetes_pods",
                                "input": {"namespace": "default"}
                            }
                        }
                    ]
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 50, "outputTokens": 25, "totalTokens": 75}
        }
        
        messages = [
            ChatMessage(
                role=Role.USER, 
                contents=[TextContent(text="Show me the pods in default namespace")]
            )
        ]
        
        from agent_framework._types import ChatOptions
        chat_options = ChatOptions(tools=self.tools)
        
        # Test the actual method that would be called
        response = await self.client._inner_get_response(
            messages=messages, 
            chat_options=chat_options,
            tools=self.tools
        )
        
        # Verify the response structure
        assert response.finish_reason.value == "tool_calls"
        assert len(response.messages) == 1
        
        # Check that we have both text and tool call content
        message = response.messages[0]
        text_contents = [c for c in message.contents if hasattr(c, 'text')]
        tool_calls = [c for c in message.contents if isinstance(c, FunctionCallContent)]
        
        assert len(text_contents) == 1
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "list_kubernetes_pods"
        
        # Verify the API call was made with correct parameters
        mock_converse.assert_called_once()
        call_args = mock_converse.call_args[1]
        
        assert call_args["modelId"] == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert "toolConfig" in call_args
        assert len(call_args["toolConfig"]["tools"]) == 2  # Both tools provided
    
    @pytest.mark.asyncio
    async def test_no_tools_provided(self):
        """Test behavior when no tools are provided."""
        with patch.object(self.client, '_call_converse_with_retry') as mock_converse:
            mock_converse.return_value = {
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [{"text": "Regular response without tools."}]
                    }
                },
                "stopReason": "end_turn",
                "usage": {"inputTokens": 20, "outputTokens": 10, "totalTokens": 30}
            }
            
            messages = [ChatMessage(role=Role.USER, contents=[TextContent(text="Hello")])]
            from agent_framework._types import ChatOptions
            chat_options = ChatOptions()
            
            response = await self.client._inner_get_response(
                messages=messages, 
                chat_options=chat_options,
                tools=None
            )
            
            # Verify no tool config was sent
            call_args = mock_converse.call_args[1]
            assert "toolConfig" not in call_args
            
            # Verify response content
            assert len(response.messages[0].contents) == 1
            assert response.messages[0].contents[0].text == "Regular response without tools."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])