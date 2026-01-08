"""
Bedrock-compatible LLM client for Aletheia.
"""
from collections.abc import AsyncIterable, MutableSequence
from datetime import datetime
from typing import Any, Dict, List, Optional
import asyncio
from functools import wraps

import boto3
from agent_framework._clients import BaseChatClient
from agent_framework._types import (
    ChatMessage,
    ChatOptions,
    ChatResponse,
    ChatResponseUpdate,
    FunctionCallContent,
    Role,
)
from agent_framework import use_function_invocation
from botocore.exceptions import ClientError, EndpointConnectionError, ConnectTimeoutError

from .bedrock_response_processor import ConverseResponseProcessor
from .bedrock_tool_converter import ConverseMessageConverter


@use_function_invocation
class BedrockChatClient(BaseChatClient):
    """Bedrock Chat client that implements the BaseChatClient interface."""

    def __init__(self, model_id: str, region: str = "us-east-1"):
        super().__init__()
        self.model_id = model_id
        self.region = region
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=region)
        self.message_converter = ConverseMessageConverter()
        self.response_processor = ConverseResponseProcessor()
        
        # Instance-level attributes for tool support
        self._supports_tools = True
        self._supports_function_calling = True
        self._supports_function_invoking = True
        self._function_invoking_supported = True
        
        # This is the key attribute the agent framework checks for
        self.__function_invoking_chat_client__ = True
        
        # Apply our custom wrapper to fix the framework bug
        self._apply_tool_fix_wrapper()

    def _apply_tool_fix_wrapper(self):
        """Apply a custom wrapper to fix the framework's tool passing bug."""
        
        # Wrap the _inner_get_response method directly
        original_inner_get_response = self._inner_get_response
        
        async def fixed_inner_get_response(*, messages, chat_options, **kwargs):
            # Fix the tools parameter if it's None but chat_options has tools
            tools = kwargs.get("tools")
            if not tools and chat_options and isinstance(chat_options, ChatOptions):
                if chat_options.tools:
                            kwargs["tools"] = chat_options.tools
            
            return await original_inner_get_response(messages=messages, chat_options=chat_options, **kwargs)
        
        self._inner_get_response = fixed_inner_get_response
        
        # Wrap the _inner_get_streaming_response method directly
        original_inner_get_streaming_response = self._inner_get_streaming_response
        
        async def fixed_inner_get_streaming_response(*, messages, chat_options, **kwargs):
            # Fix the tools parameter if it's None but chat_options has tools
            tools = kwargs.get("tools")
            if not tools and chat_options and isinstance(chat_options, ChatOptions):
                if chat_options.tools:
                    kwargs["tools"] = chat_options.tools
            
            # Return the async generator, not await it
            async for update in original_inner_get_streaming_response(messages=messages, chat_options=chat_options, **kwargs):
                yield update
        
        self._inner_get_streaming_response = fixed_inner_get_streaming_response

    @property
    def supports_tools(self) -> bool:
        """Indicate that this client supports tool/function calling."""
        return True

    @property
    def supports_function_calling(self) -> bool:
        """Indicate that this client supports function calling."""
        return True

    def supports_tool_calling(self) -> bool:
        """Indicate that this client supports tool calling."""
        return True

    def supports_function_invoking(self) -> bool:
        """Indicate that this client supports function invoking."""
        return True

    @property
    def supports_function_invoking(self) -> bool:
        """Indicate that this client supports function invoking."""
        return True

    @property
    def function_invoking_supported(self) -> bool:
        """Indicate that this client supports function invoking."""
        return True

    def can_invoke_functions(self) -> bool:
        """Check if this client can invoke functions."""
        return True

    def get_supported_call_formats(self) -> List[str]:
        """Return the supported call formats for this client."""
        return ["function_calling", "tool_calling", "function_invoking"]

    def get_capabilities(self) -> Dict[str, Any]:
        """Return the capabilities of this client."""
        return {
            "supports_tools": True,
            "supports_function_calling": True,
            "supports_function_invoking": True,
            "supports_streaming": True,
            "supports_tool_choice": True
        }

    def __getattribute__(self, name: str) -> Any:
        """Override to log all attribute access."""
        return super().__getattribute__(name)

    def _update_agent_name(self, agent_name: str) -> None:
        """Update the agent name for this client."""
        # Store the agent name if needed for logging or other purposes
        self._agent_name = agent_name

    def __getattr__(self, name: str) -> Any:
        """Handle dynamic attribute access for tool support checks."""
        # Handle any attribute that contains keywords related to tool/function support
        if any(keyword in name.lower() for keyword in ['support', 'tool', 'function', 'invoke', 'call']):
            # Return True for any attribute that suggests tool/function support
            return True
        
        # Handle other method calls that might be expected
        if name.startswith('_'):
            return None
            
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    async def _inner_get_response(
        self,
        *,
        messages: MutableSequence[ChatMessage],
        chat_options: ChatOptions,
        tools: Optional[List[Any]] = None,
        tool_choice: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Get a single response from Bedrock using Converse API."""
        # Ensure tool support is declared
        if not hasattr(self, '_tool_support_declared'):
            self._tool_support_declared = True
            
        try:
            # Use tools from parameters or kwargs
            if tools is None:
                tools = kwargs.get('tools', [])
            if tool_choice is None:
                tool_choice = kwargs.get('tool_choice', None)
            
            # Convert messages to Converse format
            converse_messages = self.message_converter.convert_to_converse_format(messages)

            # Build inference configuration
            inference_config = self._build_inference_config(chat_options)

            # Build additional model request fields
            additional_fields = self._build_additional_model_fields(chat_options)

            # Prepare Converse API request
            request_params = {
                "modelId": self.model_id,
                "messages": converse_messages["messages"],
                "inferenceConfig": inference_config
            }

            # Add system messages if present
            if converse_messages["system"]:
                request_params["system"] = converse_messages["system"]

            # Add additional model fields if present
            if additional_fields:
                request_params["additionalModelRequestFields"] = additional_fields

            # Add tool configuration if tools are provided
            if tools:
                tool_config = self._build_tool_config(tools, tool_choice)
                if tool_config:
                    request_params["toolConfig"] = tool_config

            # Call Bedrock Converse API with retry logic for network issues
            response = await self._call_converse_with_retry(**request_params)

            # Convert to ChatResponse format using response processor
            return self.response_processor.create_chat_response(response, self.model_id)

        except ClientError as e:
            self._handle_converse_api_error(e)
        except Exception as ex:
            from agent_framework.exceptions import ServiceResponseException
            raise ServiceResponseException(
                f"Bedrock Converse API failed: {ex}",
                inner_exception=ex,
            ) from ex

    async def _inner_get_streaming_response(
        self,
        *,
        messages: MutableSequence[ChatMessage],
        chat_options: ChatOptions,
        tools: Optional[List[Any]] = None,
        tool_choice: Optional[Any] = None,
        **kwargs: Any,
    ) -> AsyncIterable[ChatResponseUpdate]:
        """Get streaming response from Bedrock using Converse Stream API."""
        
        # Use tools from parameters or kwargs
        if tools is None:
            tools = kwargs.get('tools', [])
        if tool_choice is None:
            tool_choice = kwargs.get('tool_choice', None)
        
        # If tools are provided, fall back to non-streaming mode for tool calls
        # This is because tool calls require complete response processing
        if tools:
            # Call the non-streaming method and convert to streaming format
            complete_response = await self._inner_get_response(
                messages=messages,
                chat_options=chat_options,
                tools=tools,
                tool_choice=tool_choice,
                **kwargs
            )
            
            # Convert the complete response to streaming format
            # Yield the message content as streaming updates
            for message in complete_response.messages:
                for content in message.contents:
                    if hasattr(content, 'text') and content.text:
                        yield ChatResponseUpdate(
                            role=message.role,
                            contents=[content],
                            model_id=complete_response.model_id,
                            response_id=complete_response.response_id,
                            message_id=complete_response.response_id,  # Use response_id as message_id
                            created_at=complete_response.created_at,
                            finish_reason=None
                        )
                    elif isinstance(content, FunctionCallContent):
                        # Yield tool calls as streaming updates
                        yield ChatResponseUpdate(
                            role=message.role,
                            contents=[content],
                            model_id=complete_response.model_id,
                            response_id=complete_response.response_id,
                            message_id=complete_response.response_id,
                            created_at=complete_response.created_at,
                            finish_reason=None
                        )
            
            # Yield final update with finish reason
            final_update = ChatResponseUpdate(
                role=Role.ASSISTANT,
                contents=[],
                model_id=complete_response.model_id,
                response_id=complete_response.response_id,
                message_id=complete_response.response_id,
                created_at=complete_response.created_at,
                finish_reason=complete_response.finish_reason
            )
            
            yield final_update
            return
        
        # Continue with normal streaming for non-tool responses
        try:
            # Convert messages to Converse format
            converse_messages = self.message_converter.convert_to_converse_format(messages)

            # Build inference configuration
            inference_config = self._build_inference_config(chat_options)

            # Build additional model request fields
            additional_fields = self._build_additional_model_fields(chat_options)

            # Prepare Converse Stream API request
            request_params = {
                "modelId": self.model_id,
                "messages": converse_messages["messages"],
                "inferenceConfig": inference_config
            }

            # Add system messages if present
            if converse_messages["system"]:
                request_params["system"] = converse_messages["system"]

            # Add additional model fields if present
            if additional_fields:
                request_params["additionalModelRequestFields"] = additional_fields

            # Call Bedrock Converse Stream API with retry logic for network issues
            response = await self._call_converse_stream_with_retry(**request_params)

            # Process streaming events
            async for update in self._process_stream_events(response["stream"]):
                yield update

        except ClientError as e:
            self._handle_converse_api_error(e)
        except Exception as ex:
            from agent_framework.exceptions import ServiceResponseException
            raise ServiceResponseException(
                f"Bedrock Converse Stream API failed: {ex}",
                inner_exception=ex,
            ) from ex

    async def _process_stream_events(self, event_stream) -> AsyncIterable[ChatResponseUpdate]:
        """
        Process streaming events from Converse Stream API.

        Args:
            event_stream: Event stream from Bedrock Converse Stream API

        Yields:
            ChatResponseUpdate objects for content deltas and completion events
        """
        response_id = f"converse-stream-{hash(str(datetime.now()))}"
        message_id = response_id
        created_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        for event in event_stream:
            # Handle contentBlockDelta events - yield incremental content
            if "contentBlockDelta" in event:
                delta = event["contentBlockDelta"]["delta"]
                
                if "text" in delta:
                    # Regular text content
                    update = self.response_processor.process_streaming_event(event)
                    if update:
                        # Set the response metadata
                        update.model_id = self.model_id
                        update.response_id = response_id
                        update.message_id = message_id
                        update.created_at = created_at
                        yield update

            # Handle messageStop events - yield completion with finish reason
            elif "messageStop" in event:
                stop_reason = event["messageStop"].get("stopReason", "end_turn")
                finish_reason = self.response_processor._map_stop_reason_to_finish_reason(stop_reason)
                
                # Create the final response update
                final_update = ChatResponseUpdate(
                    role=Role.ASSISTANT,
                    contents=[],
                    model_id=self.model_id,
                    response_id=response_id,
                    message_id=message_id,
                    created_at=created_at,
                    finish_reason=finish_reason
                )
                
                yield final_update

            # Handle metadata events - contains final usage statistics
            elif "metadata" in event:
                # For now, we don't yield a separate update for metadata
                # The usage information could be logged or tracked separately
                # but ChatResponseUpdate doesn't support usage_details parameter
                continue

    def _build_inference_config(self, chat_options: ChatOptions) -> dict[str, Any]:
        """
        Build inference configuration for Converse API.

        Args:
            chat_options: Chat options containing inference parameters

        Returns:
            Dictionary with inference configuration parameters
        """
        inference_config = {}

        # Handle max_tokens
        max_tokens = getattr(chat_options, 'max_tokens', None)
        if max_tokens is not None:
            inference_config["maxTokens"] = int(max_tokens)
        else:
            inference_config["maxTokens"] = 4000

        # Handle temperature
        temperature = getattr(chat_options, 'temperature', None)
        if temperature is not None:
            inference_config["temperature"] = float(temperature)

        # Handle top_p
        top_p = getattr(chat_options, 'top_p', None)
        if top_p is not None:
            inference_config["topP"] = float(top_p)

        # Handle stop sequences
        stop_sequences = getattr(chat_options, 'stop_sequences', None)
        if stop_sequences is not None:
            inference_config["stopSequences"] = list(stop_sequences)

        return inference_config

    def _build_additional_model_fields(self, chat_options: ChatOptions) -> dict[str, Any]:
        """
        Build additional model request fields for Converse API.

        Args:
            chat_options: Chat options containing model-specific parameters

        Returns:
            Dictionary with additional model-specific parameters
        """
        additional_fields = {}

        # Handle top_k (model-specific parameter)
        top_k = getattr(chat_options, 'top_k', None)
        if top_k is not None:
            additional_fields["top_k"] = int(top_k)

        return additional_fields

    def _build_tool_config(self, tools: List[Any], tool_choice: Any = None) -> Optional[Dict[str, Any]]:
        """
        Build tool configuration for Converse API.

        Args:
            tools: List of ToolProtocol objects
            tool_choice: Tool choice parameter

        Returns:
            Dictionary with tool configuration for Converse API, or None if no valid tools
        """
        if not tools:
            return None

        # Convert tools to Converse format
        tool_definitions = self.message_converter.convert_tools_to_converse_format(tools)
        
        if not tool_definitions:
            return None

        tool_config = {
            "tools": tool_definitions
        }

        # Add tool choice - if not specified, default to "auto" to encourage tool usage
        if tool_choice is not None:
            tool_choice_config = self.message_converter.convert_tool_choice_to_converse_format(tool_choice)
            tool_config["toolChoice"] = tool_choice_config
        else:
            # Default to "auto" to encourage the model to use tools when appropriate
            tool_config["toolChoice"] = {"auto": {}}

        return tool_config

    def _handle_converse_api_error(self, error: ClientError) -> None:
        """
        Handle Converse API specific errors.

        Args:
            error: ClientError from boto3

        Raises:
            ServiceResponseException: With descriptive error message
        """
        from agent_framework.exceptions import ServiceResponseException

        error_code = error.response['Error']['Code']
        error_message = error.response['Error']['Message']

        if error_code == 'ValidationException':
            raise ServiceResponseException(
                f"Bedrock Converse API validation error: {error_message}. "
                f"Please check your model ID, message format, or request parameters.",
                inner_exception=error,
            ) from error
        elif error_code == 'AccessDeniedException':
            raise ServiceResponseException(
                f"Bedrock Converse API access denied: {error_message}. "
                f"Please check your AWS credentials and model access permissions.",
                inner_exception=error,
            ) from error
        elif error_code == 'ThrottlingException':
            raise ServiceResponseException(
                f"Bedrock Converse API throttling: {error_message}. "
                f"Request rate exceeded, please retry with exponential backoff.",
                inner_exception=error,
            ) from error
        elif error_code == 'ServiceQuotaExceededException':
            raise ServiceResponseException(
                f"Bedrock Converse API quota exceeded: {error_message}. "
                f"Service limits have been exceeded.",
                inner_exception=error,
            ) from error
        elif error_code == 'InternalServerException':
            raise ServiceResponseException(
                f"Bedrock Converse API internal error: {error_message}. "
                f"AWS service encountered an internal error.",
                inner_exception=error,
            ) from error
        else:
            # Handle other ClientError types
            raise ServiceResponseException(
                f"Bedrock Converse API error ({error_code}): {error_message}",
                inner_exception=error,
            ) from error
    def service_url(self) -> str:
        """Get the URL of the service."""
        return f"https://bedrock-runtime.{self.region}.amazonaws.com"

    async def _call_converse_with_retry(self, **request_params) -> dict[str, Any]:
        """
        Call Bedrock Converse API with retry logic for network issues.
        
        Args:
            **request_params: Parameters to pass to the converse API
            
        Returns:
            Response from the Converse API
            
        Raises:
            ServiceResponseException: If all retries are exhausted
        """
        max_retries = 3
        base_delay = 1.0  # Start with 1 second
        
        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                return self.bedrock_client.converse(**request_params)
            except (EndpointConnectionError, ConnectTimeoutError, ConnectionError) as e:
                if attempt == max_retries:
                    # Last attempt failed, raise ServiceResponseException
                    from agent_framework.exceptions import ServiceResponseException
                    raise ServiceResponseException(
                        f"Bedrock Converse API network error after {max_retries} retries: {e}",
                        inner_exception=e,
                    ) from e
                
                # Calculate exponential backoff delay
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
            except ClientError:
                # Don't retry ClientError exceptions (validation, access denied, etc.)
                # Let them bubble up to be handled by _handle_converse_api_error
                raise

    async def _call_converse_stream_with_retry(self, **request_params) -> dict[str, Any]:
        """
        Call Bedrock Converse Stream API with retry logic for network issues.
        
        Args:
            **request_params: Parameters to pass to the converse_stream API
            
        Returns:
            Response from the Converse Stream API
            
        Raises:
            ServiceResponseException: If all retries are exhausted
        """
        max_retries = 3
        base_delay = 1.0  # Start with 1 second
        
        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                return self.bedrock_client.converse_stream(**request_params)
            except (EndpointConnectionError, ConnectTimeoutError, ConnectionError) as e:
                if attempt == max_retries:
                    # Last attempt failed, raise ServiceResponseException
                    from agent_framework.exceptions import ServiceResponseException
                    raise ServiceResponseException(
                        f"Bedrock Converse Stream API network error after {max_retries} retries: {e}",
                        inner_exception=e,
                    ) from e
                
                # Calculate exponential backoff delay
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
            except ClientError:
                # Don't retry ClientError exceptions (validation, access denied, etc.)
                # Let them bubble up to be handled by _handle_converse_api_error
                raise

