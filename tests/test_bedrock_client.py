"""
Tests for BedrockChatClient with Converse API integration.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError, EndpointConnectionError, ConnectTimeoutError

from agent_framework._types import ChatMessage, ChatOptions, Role, TextContent
from aletheia.agents.bedrock_client import BedrockChatClient


class TestBedrockChatClient:
    """Test cases for BedrockChatClient."""

    def setup_method(self):
        """Set up test fixtures."""
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        self.region = "us-east-1"
        
        # Mock boto3 client
        with patch('boto3.client') as mock_boto3:
            self.mock_bedrock_client = Mock()
            mock_boto3.return_value = self.mock_bedrock_client
            self.client = BedrockChatClient(model_id=self.model_id, region=self.region)

    @pytest.mark.asyncio
    async def test_inner_get_response_basic(self):
        """Test basic non-streaming response functionality."""
        # Arrange
        messages = [
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello")])
        ]
        chat_options = ChatOptions(max_tokens=1000, temperature=0.5)
        
        # Mock Converse API response
        mock_response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Hello! How can I help you?"}]
                }
            },
            "stopReason": "end_turn",
            "usage": {
                "inputTokens": 5,
                "outputTokens": 8,
                "totalTokens": 13
            }
        }
        self.mock_bedrock_client.converse.return_value = mock_response
        
        # Act
        response = await self.client._inner_get_response(
            messages=messages, 
            chat_options=chat_options
        )
        
        # Assert
        assert response.model_id == self.model_id
        assert len(response.messages) == 1
        assert response.messages[0].role == Role.ASSISTANT
        assert len(response.messages[0].contents) == 1
        assert response.messages[0].contents[0].text == "Hello! How can I help you?"
        assert response.usage_details.input_token_count == 5
        assert response.usage_details.output_token_count == 8
        assert response.usage_details.total_token_count == 13
        
        # Verify Converse API was called with correct parameters
        self.mock_bedrock_client.converse.assert_called_once()
        call_args = self.mock_bedrock_client.converse.call_args[1]
        assert call_args["modelId"] == self.model_id
        assert "messages" in call_args
        assert "inferenceConfig" in call_args
        assert call_args["inferenceConfig"]["maxTokens"] == 1000
        assert call_args["inferenceConfig"]["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_inner_get_response_with_system_message(self):
        """Test response with system message."""
        # Arrange
        messages = [
            ChatMessage(role=Role.SYSTEM, contents=[TextContent(text="You are a helpful assistant.")]),
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello")])
        ]
        chat_options = ChatOptions(max_tokens=1000)
        
        # Mock Converse API response
        mock_response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Hello! How can I help you?"}]
                }
            },
            "stopReason": "end_turn",
            "usage": {
                "inputTokens": 10,
                "outputTokens": 8,
                "totalTokens": 18
            }
        }
        self.mock_bedrock_client.converse.return_value = mock_response
        
        # Act
        response = await self.client._inner_get_response(
            messages=messages, 
            chat_options=chat_options
        )
        
        # Assert
        assert response.model_id == self.model_id
        
        # Verify system message was included in the call
        call_args = self.mock_bedrock_client.converse.call_args[1]
        assert "system" in call_args
        assert len(call_args["system"]) == 1
        assert call_args["system"][0]["text"] == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_inner_get_response_validation_error(self):
        """Test handling of ValidationException."""
        # Arrange
        messages = [
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello")])
        ]
        chat_options = ChatOptions()
        
        # Mock ClientError
        error_response = {
            'Error': {
                'Code': 'ValidationException',
                'Message': 'Invalid model ID'
            }
        }
        self.mock_bedrock_client.converse.side_effect = ClientError(
            error_response, 'converse'
        )
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await self.client._inner_get_response(
                messages=messages, 
                chat_options=chat_options
            )
        
        assert "Bedrock Converse API validation error" in str(exc_info.value)
        assert "Invalid model ID" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_inner_get_response_access_denied_error(self):
        """Test handling of AccessDeniedException."""
        # Arrange
        messages = [
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello")])
        ]
        chat_options = ChatOptions()
        
        # Mock ClientError
        error_response = {
            'Error': {
                'Code': 'AccessDeniedException',
                'Message': 'Access denied to model'
            }
        }
        self.mock_bedrock_client.converse.side_effect = ClientError(
            error_response, 'converse'
        )
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await self.client._inner_get_response(
                messages=messages, 
                chat_options=chat_options
            )
        
        assert "Bedrock Converse API access denied" in str(exc_info.value)
        assert "Access denied to model" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_inner_get_response_throttling_error(self):
        """Test handling of ThrottlingException."""
        # Arrange
        messages = [
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello")])
        ]
        chat_options = ChatOptions()
        
        # Mock ClientError
        error_response = {
            'Error': {
                'Code': 'ThrottlingException',
                'Message': 'Request rate exceeded'
            }
        }
        self.mock_bedrock_client.converse.side_effect = ClientError(
            error_response, 'converse'
        )
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await self.client._inner_get_response(
                messages=messages, 
                chat_options=chat_options
            )
        
        assert "Bedrock Converse API throttling" in str(exc_info.value)
        assert "Request rate exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_inner_get_response_service_quota_exceeded_error(self):
        """Test handling of ServiceQuotaExceededException."""
        # Arrange
        messages = [
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello")])
        ]
        chat_options = ChatOptions()
        
        # Mock ClientError
        error_response = {
            'Error': {
                'Code': 'ServiceQuotaExceededException',
                'Message': 'Service quota exceeded for model requests'
            }
        }
        self.mock_bedrock_client.converse.side_effect = ClientError(
            error_response, 'converse'
        )
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await self.client._inner_get_response(
                messages=messages, 
                chat_options=chat_options
            )
        
        assert "Bedrock Converse API quota exceeded" in str(exc_info.value)
        assert "Service quota exceeded for model requests" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_inner_get_response_internal_server_error(self):
        """Test handling of InternalServerException."""
        # Arrange
        messages = [
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello")])
        ]
        chat_options = ChatOptions()
        
        # Mock ClientError
        error_response = {
            'Error': {
                'Code': 'InternalServerException',
                'Message': 'Internal server error occurred'
            }
        }
        self.mock_bedrock_client.converse.side_effect = ClientError(
            error_response, 'converse'
        )
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await self.client._inner_get_response(
                messages=messages, 
                chat_options=chat_options
            )
        
        assert "Bedrock Converse API internal error" in str(exc_info.value)
        assert "Internal server error occurred" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_inner_get_response_generic_client_error(self):
        """Test handling of generic ClientError."""
        # Arrange
        messages = [
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello")])
        ]
        chat_options = ChatOptions()
        
        # Mock ClientError
        error_response = {
            'Error': {
                'Code': 'UnknownException',
                'Message': 'Unknown error occurred'
            }
        }
        self.mock_bedrock_client.converse.side_effect = ClientError(
            error_response, 'converse'
        )
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await self.client._inner_get_response(
                messages=messages, 
                chat_options=chat_options
            )
        
        assert "Bedrock Converse API error (UnknownException)" in str(exc_info.value)
        assert "Unknown error occurred" in str(exc_info.value)

    def test_build_inference_config(self):
        """Test inference config building."""
        # Test with supported parameters
        chat_options = ChatOptions(
            max_tokens=2000,
            temperature=0.7
        )
        # Mock additional attributes that might not be in ChatOptions
        chat_options.top_p = 0.9
        chat_options.stop_sequences = ["STOP", "END"]
        
        config = self.client._build_inference_config(chat_options)
        
        assert config["maxTokens"] == 2000
        assert config["temperature"] == 0.7
        assert config["topP"] == 0.9
        assert config["stopSequences"] == ["STOP", "END"]

    def test_build_inference_config_defaults(self):
        """Test inference config with defaults."""
        chat_options = ChatOptions()
        
        config = self.client._build_inference_config(chat_options)
        
        assert config["maxTokens"] == 4000  # Default value
        assert "temperature" not in config
        assert "topP" not in config
        assert "stopSequences" not in config

    def test_build_additional_model_fields(self):
        """Test additional model fields building."""
        # Create a mock ChatOptions with top_k
        chat_options = Mock()
        chat_options.top_k = 200
        
        fields = self.client._build_additional_model_fields(chat_options)
        
        assert fields["top_k"] == 200

    def test_build_additional_model_fields_empty(self):
        """Test additional model fields when no fields are set."""
        chat_options = ChatOptions()
        
        fields = self.client._build_additional_model_fields(chat_options)
        
        assert fields == {}

    def test_service_url(self):
        """Test service URL generation."""
        url = self.client.service_url()
        assert url == f"https://bedrock-runtime.{self.region}.amazonaws.com"

    @pytest.mark.asyncio
    async def test_inner_get_streaming_response_basic(self):
        """Test basic streaming response functionality."""
        # Arrange
        messages = [
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello")])
        ]
        chat_options = ChatOptions(max_tokens=1000, temperature=0.5)
        
        # Mock streaming events
        mock_events = [
            {"contentBlockStart": {"start": {"text": ""}, "contentBlockIndex": 0}},
            {"contentBlockDelta": {"delta": {"text": "Hello"}, "contentBlockIndex": 0}},
            {"contentBlockDelta": {"delta": {"text": "! How"}, "contentBlockIndex": 0}},
            {"contentBlockDelta": {"delta": {"text": " can I help?"}, "contentBlockIndex": 0}},
            {"messageStop": {"stopReason": "end_turn"}},
            {"metadata": {"usage": {"inputTokens": 5, "outputTokens": 8, "totalTokens": 13}}}
        ]
        
        # Mock Converse Stream API response
        mock_stream_response = {
            "stream": iter(mock_events)
        }
        self.mock_bedrock_client.converse_stream.return_value = mock_stream_response
        
        # Act
        updates = []
        async for update in self.client._inner_get_streaming_response(
            messages=messages, 
            chat_options=chat_options
        ):
            updates.append(update)
        
        # Assert
        assert len(updates) == 4  # 3 content deltas + 1 message stop (metadata doesn't yield)
        
        # Check content deltas
        assert updates[0].contents[0].text == "Hello"
        assert updates[1].contents[0].text == "! How"
        assert updates[2].contents[0].text == " can I help?"
        
        # Check message stop
        assert updates[3].finish_reason is not None
        assert len(updates[3].contents) == 0
        
        # Verify all updates have correct metadata
        for update in updates:
            assert update.model_id == self.model_id
            assert update.response_id.startswith("converse-stream-")
            assert update.role == Role.ASSISTANT
        
        # Verify Converse Stream API was called with correct parameters
        self.mock_bedrock_client.converse_stream.assert_called_once()
        call_args = self.mock_bedrock_client.converse_stream.call_args[1]
        assert call_args["modelId"] == self.model_id
        assert "messages" in call_args
        assert "inferenceConfig" in call_args
        assert call_args["inferenceConfig"]["maxTokens"] == 1000
        assert call_args["inferenceConfig"]["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_inner_get_streaming_response_validation_error(self):
        """Test handling of ValidationException in streaming."""
        # Arrange
        messages = [
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello")])
        ]
        chat_options = ChatOptions()
        
        # Mock ClientError
        error_response = {
            'Error': {
                'Code': 'ValidationException',
                'Message': 'Invalid streaming request'
            }
        }
        self.mock_bedrock_client.converse_stream.side_effect = ClientError(
            error_response, 'converse_stream'
        )
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            async for _ in self.client._inner_get_streaming_response(
                messages=messages, 
                chat_options=chat_options
            ):
                pass
        
        assert "Bedrock Converse API validation error" in str(exc_info.value)
        assert "Invalid streaming request" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_inner_get_streaming_response_access_denied_error(self):
        """Test handling of AccessDeniedException in streaming."""
        # Arrange
        messages = [
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello")])
        ]
        chat_options = ChatOptions()
        
        # Mock ClientError
        error_response = {
            'Error': {
                'Code': 'AccessDeniedException',
                'Message': 'Access denied to streaming model'
            }
        }
        self.mock_bedrock_client.converse_stream.side_effect = ClientError(
            error_response, 'converse_stream'
        )
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            async for _ in self.client._inner_get_streaming_response(
                messages=messages, 
                chat_options=chat_options
            ):
                pass
        
        assert "Bedrock Converse API access denied" in str(exc_info.value)
        assert "Access denied to streaming model" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_inner_get_streaming_response_throttling_error(self):
        """Test handling of ThrottlingException in streaming."""
        # Arrange
        messages = [
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello")])
        ]
        chat_options = ChatOptions()
        
        # Mock ClientError
        error_response = {
            'Error': {
                'Code': 'ThrottlingException',
                'Message': 'Streaming request rate exceeded'
            }
        }
        self.mock_bedrock_client.converse_stream.side_effect = ClientError(
            error_response, 'converse_stream'
        )
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            async for _ in self.client._inner_get_streaming_response(
                messages=messages, 
                chat_options=chat_options
            ):
                pass
        
        assert "Bedrock Converse API throttling" in str(exc_info.value)
        assert "Streaming request rate exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_inner_get_response_network_error_with_retry(self):
        """Test handling of network errors with retry logic."""
        # Arrange
        messages = [
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello")])
        ]
        chat_options = ChatOptions()
        
        # Mock network error that succeeds on second attempt
        mock_response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Hello! How can I help you?"}]
                }
            },
            "stopReason": "end_turn",
            "usage": {
                "inputTokens": 5,
                "outputTokens": 8,
                "totalTokens": 13
            }
        }
        
        # First call fails with network error, second succeeds
        self.mock_bedrock_client.converse.side_effect = [
            EndpointConnectionError(endpoint_url="https://bedrock-runtime.us-east-1.amazonaws.com"),
            mock_response
        ]
        
        # Act
        response = await self.client._inner_get_response(
            messages=messages, 
            chat_options=chat_options
        )
        
        # Assert
        assert response.model_id == self.model_id
        assert len(response.messages) == 1
        assert response.messages[0].contents[0].text == "Hello! How can I help you?"
        
        # Verify converse was called twice (first failed, second succeeded)
        assert self.mock_bedrock_client.converse.call_count == 2

    @pytest.mark.asyncio
    async def test_inner_get_response_network_error_exhausted_retries(self):
        """Test handling of network errors when all retries are exhausted."""
        # Arrange
        messages = [
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello")])
        ]
        chat_options = ChatOptions()
        
        # Mock network error that always fails
        self.mock_bedrock_client.converse.side_effect = EndpointConnectionError(
            endpoint_url="https://bedrock-runtime.us-east-1.amazonaws.com"
        )
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await self.client._inner_get_response(
                messages=messages, 
                chat_options=chat_options
            )
        
        assert "Bedrock Converse API network error after 3 retries" in str(exc_info.value)
        
        # Verify converse was called 4 times (initial + 3 retries)
        assert self.mock_bedrock_client.converse.call_count == 4

    @pytest.mark.asyncio
    async def test_inner_get_streaming_response_network_error_with_retry(self):
        """Test handling of network errors with retry logic in streaming."""
        # Arrange
        messages = [
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello")])
        ]
        chat_options = ChatOptions()
        
        # Mock streaming events
        mock_events = [
            {"contentBlockDelta": {"delta": {"text": "Hello"}, "contentBlockIndex": 0}},
            {"messageStop": {"stopReason": "end_turn"}}
        ]
        
        # Mock streaming response that succeeds on second attempt
        mock_stream_response = {
            "stream": iter(mock_events)
        }
        
        # First call fails with network error, second succeeds
        self.mock_bedrock_client.converse_stream.side_effect = [
            ConnectTimeoutError(endpoint_url="https://bedrock-runtime.us-east-1.amazonaws.com"),
            mock_stream_response
        ]
        
        # Act
        updates = []
        async for update in self.client._inner_get_streaming_response(
            messages=messages, 
            chat_options=chat_options
        ):
            updates.append(update)
        
        # Assert
        assert len(updates) == 2  # 1 content delta + 1 message stop
        assert updates[0].contents[0].text == "Hello"
        
        # Verify converse_stream was called twice (first failed, second succeeded)
        assert self.mock_bedrock_client.converse_stream.call_count == 2