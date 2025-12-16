"""
Bedrock-compatible LLM client for Aletheia.
"""
import os
import json
import boto3
from typing import Dict, Any, Optional, AsyncIterable, MutableSequence
from collections.abc import Sequence
from agent_framework._clients import BaseChatClient
from agent_framework._types import ChatMessage, ChatOptions, ChatResponse, ChatResponseUpdate
from datetime import datetime


class BedrockChatClient(BaseChatClient):
    """Bedrock Chat client that implements the BaseChatClient interface."""
    
    def __init__(self, model_id: str, region: str = "us-east-1"):
        super().__init__()
        self.model_id = model_id
        self.region = region
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=region)
    
    async def _inner_get_response(
        self,
        *,
        messages: MutableSequence[ChatMessage],
        chat_options: ChatOptions,
        **kwargs: Any,
    ) -> ChatResponse:
        """Get a single response from Bedrock."""
        try:
            # Convert messages to Bedrock format
            bedrock_messages = self._convert_messages_to_bedrock(messages)
            
            # Prepare Bedrock request
            max_tokens = getattr(chat_options, 'max_tokens', None)
            if max_tokens is None:
                max_tokens = 4000
            else:
                max_tokens = int(max_tokens)
            
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": bedrock_messages['messages']
            }
            
            if bedrock_messages['system']:
                body["system"] = bedrock_messages['system']
                
            # Call Bedrock
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body)
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            
            # Convert to ChatResponse format
            return self._create_chat_response(response_body)
            
        except Exception as ex:
            from agent_framework.exceptions import ServiceResponseException
            raise ServiceResponseException(
                f"Bedrock service failed to complete the prompt: {ex}",
                inner_exception=ex,
            ) from ex
    
    async def _inner_get_streaming_response(
        self,
        *,
        messages: MutableSequence[ChatMessage],
        chat_options: ChatOptions,
        **kwargs: Any,
    ) -> AsyncIterable[ChatResponseUpdate]:
        """Get streaming response from Bedrock (fallback to non-streaming)."""
        # Bedrock doesn't support streaming in the same way, so we'll simulate it
        response = await self._inner_get_response(messages=messages, chat_options=chat_options, **kwargs)
        
        # Convert ChatResponse to ChatResponseUpdate
        from agent_framework._types import Role, TextContent
        
        if response.messages and response.messages[0].contents:
            for content in response.messages[0].contents:
                if hasattr(content, 'text'):
                    yield ChatResponseUpdate(
                        role=Role.ASSISTANT,
                        contents=[content],
                        model_id=response.model_id,
                        response_id=response.response_id,
                        message_id=response.response_id,
                        created_at=response.created_at,
                        finish_reason=response.finish_reason
                    )
    
    def _convert_messages_to_bedrock(self, messages: Sequence[ChatMessage]) -> Dict[str, Any]:
        """Convert ChatMessage objects to Bedrock format."""
        system_message = ""
        user_messages = []
        
        for msg in messages:
            role = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)
            
            # Extract text content from message
            content_text = ""
            for content in msg.contents:
                if hasattr(content, 'text'):
                    content_text += content.text
                elif hasattr(content, 'to_dict'):
                    content_dict = content.to_dict()
                    if 'text' in content_dict:
                        content_text += content_dict['text']
            
            if role == 'system':
                system_message += content_text
            elif role in ['user', 'assistant']:
                user_messages.append({"role": role, "content": content_text})
        
        return {
            "system": system_message,
            "messages": user_messages
        }
    
    def _create_chat_response(self, bedrock_response: Dict[str, Any]) -> ChatResponse:
        """Convert Bedrock response to ChatResponse format."""
        from agent_framework._types import TextContent, FinishReason, UsageDetails
        
        # Extract content
        content = bedrock_response.get('content', [])
        text_content = ""
        if content and len(content) > 0:
            text_content = content[0].get('text', '')
        
        # Create message
        message = ChatMessage(
            role="assistant",
            contents=[TextContent(text=text_content)]
        )
        
        # Create usage details
        usage = bedrock_response.get('usage', {})
        usage_details = UsageDetails(
            input_token_count=usage.get('input_tokens', 0),
            output_token_count=usage.get('output_tokens', 0),
            total_token_count=usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
        )
        
        return ChatResponse(
            response_id=f"bedrock-{hash(str(bedrock_response))}",
            created_at=datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            usage_details=usage_details,
            messages=[message],
            model_id=self.model_id,
            finish_reason=FinishReason(value="stop")
        )
    
    def service_url(self) -> str:
        """Get the URL of the service."""
        return f"https://bedrock-runtime.{self.region}.amazonaws.com"

