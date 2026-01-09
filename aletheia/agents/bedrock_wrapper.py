"""
Bedrock client wrapper that adds response_format support.

This wrapper adds structured output support to Bedrock clients by:
1. Intercepting run_stream calls with response_format parameter
2. Adding JSON schema instructions to the system prompt
3. Parsing and validating the response against the expected schema
"""
import json
import re
from typing import Any, AsyncGenerator, Dict, List, Optional, Type, Union
from pydantic import BaseModel, ValidationError

from agent_framework import ChatMessage, TextContent, Role
from aletheia.utils.logging import log_debug, log_error


class BedrockResponseWrapper:
    """Wrapper for response objects that matches the expected interface."""
    
    def __init__(self, text: str, contents: Optional[List] = None):
        """Initialize response wrapper.
        
        Args:
            text: The response text
            contents: Optional contents list (for usage tracking)
        """
        self.text = text
        self.contents = contents or []


class BedrockResponseFormatWrapper:
    """Wrapper that adds response_format support to Bedrock ChatAgent instances."""
    
    def __init__(self, chat_agent):
        """Initialize the wrapper with a ChatAgent instance.
        
        Args:
            chat_agent: The ChatAgent instance to wrap
        """
        self.chat_agent = chat_agent
        self._original_run_stream = chat_agent.run_stream
        
        # Replace the run_stream method with our wrapper
        chat_agent.run_stream = self._wrapped_run_stream
    
    async def _wrapped_run_stream(
        self, 
        messages: List[ChatMessage], 
        thread=None, 
        response_format: Optional[Type[BaseModel]] = None,
        **kwargs
    ) -> AsyncGenerator[Any, None]:
        """Wrapped run_stream method that handles response_format for Bedrock.
        
        Args:
            messages: List of chat messages
            thread: Optional thread context
            response_format: Optional Pydantic model for structured output
            **kwargs: Additional arguments
            
        Yields:
            Streaming response chunks
        """
        if response_format is None:
            # No response format specified, use original method
            async for chunk in self._original_run_stream(messages, thread=thread, **kwargs):
                yield chunk
            return
        
        log_debug(f"BedrockWrapper: Adding JSON schema instructions for {response_format.__name__}")
        
        # Generate JSON schema from the Pydantic model
        schema = response_format.model_json_schema()
        
        # Create system message with JSON formatting instructions
        json_instructions = self._create_json_instructions(response_format, schema)
        
        # Add the JSON instructions to the messages
        modified_messages = self._add_json_instructions(messages, json_instructions)
        
        # Stream the response and attempt to parse as JSON
        accumulated_text = ""
        last_contents = None
        
        async for chunk in self._original_run_stream(modified_messages, thread=thread, **kwargs):
            if hasattr(chunk, 'text') and chunk.text:
                accumulated_text += chunk.text
                
                # Preserve contents from the original response for usage tracking
                if hasattr(chunk, 'contents'):
                    last_contents = chunk.contents
                
                # Try to parse accumulated text as JSON
                parsed_response = self._try_parse_json(accumulated_text, response_format)
                if parsed_response:
                    # Successfully parsed, yield the structured response
                    structured_chunk = BedrockResponseWrapper(
                        text=json.dumps(parsed_response),
                        contents=last_contents
                    )
                    yield structured_chunk
                    return
                else:
                    # Not yet valid JSON, yield a wrapper with the current chunk
                    wrapped_chunk = BedrockResponseWrapper(
                        text=chunk.text,
                        contents=getattr(chunk, 'contents', [])
                    )
                    yield wrapped_chunk
            else:
                # Yield the original chunk if it doesn't have text
                yield chunk
    
    def _create_json_instructions(self, response_format: Type[BaseModel], schema: Dict) -> str:
        """Create JSON formatting instructions for the model.
        
        Args:
            response_format: The Pydantic model class
            schema: JSON schema generated from the model
            
        Returns:
            Formatted instructions string
        """
        # Get field descriptions from the model
        field_descriptions = {}
        if hasattr(response_format, 'model_fields'):
            for field_name, field_info in response_format.model_fields.items():
                if hasattr(field_info, 'description') and field_info.description:
                    field_descriptions[field_name] = field_info.description
        
        instructions = f"""
CRITICAL: You MUST respond with a valid JSON object that exactly matches this schema. Do not include any text before or after the JSON.

Required JSON Schema for {response_format.__name__}:
{json.dumps(schema, indent=2)}

Field Descriptions:
"""
        
        # Add field descriptions
        for field_name, description in field_descriptions.items():
            instructions += f"- {field_name}: {description}\n"
        
        instructions += """
IMPORTANT FORMATTING RULES:
1. Response must be valid JSON only - no markdown, no explanations, no additional text
2. All required fields must be present
3. Use proper JSON data types (strings in quotes, numbers without quotes, arrays with [], objects with {})
4. Confidence should be a number between 0.0 and 1.0
5. Lists should contain actual items, not empty arrays unless no items exist
6. Ensure all JSON is properly escaped and formatted

Example structure:
{
  "confidence": 0.85,
  "agent": "agent_name",
  "findings": {
    "summary": "Brief summary of findings",
    "details": "Detailed analysis",
    "tool_outputs": [],
    "additional_output": null,
    "skill_used": null,
    "knowledge_searched": false
  },
  "decisions": {
    "approach": "Description of approach",
    "tools_used": ["tool1", "tool2"],
    "skills_loaded": [],
    "rationale": "Reasoning behind decisions",
    "checklist": ["item1", "item2"],
    "additional_output": null
  },
  "next_actions": {
    "steps": ["step1", "step2"],
    "additional_output": null
  },
  "errors": null
}
"""
        return instructions
    
    def _add_json_instructions(self, messages: List[ChatMessage], instructions: str) -> List[ChatMessage]:
        """Add JSON formatting instructions to the message list.
        
        Args:
            messages: Original message list
            instructions: JSON formatting instructions
            
        Returns:
            Modified message list with instructions
        """
        # Create a system message with the JSON instructions
        system_message = ChatMessage(
            role=Role.SYSTEM,
            contents=[TextContent(text=instructions)]
        )
        
        # Insert at the beginning or append to existing system message
        modified_messages = []
        system_message_added = False
        
        for message in messages:
            if message.role == Role.SYSTEM and not system_message_added:
                # Append to existing system message
                existing_content = ""
                for content in message.contents:
                    if hasattr(content, 'text'):
                        existing_content += content.text
                
                combined_content = existing_content + "\n\n" + instructions
                modified_message = ChatMessage(
                    role=Role.SYSTEM,
                    contents=[TextContent(text=combined_content)]
                )
                modified_messages.append(modified_message)
                system_message_added = True
            else:
                modified_messages.append(message)
        
        # If no system message existed, add one at the beginning
        if not system_message_added:
            modified_messages.insert(0, system_message)
        
        return modified_messages
    
    def _try_parse_json(self, text: str, response_format: Type[BaseModel]) -> Optional[Dict]:
        """Attempt to parse accumulated text as JSON and validate against schema.
        
        Args:
            text: Accumulated response text
            response_format: Expected Pydantic model
            
        Returns:
            Parsed and validated JSON dict, or None if parsing fails
        """
        # Clean up the text - remove any markdown formatting or extra text
        cleaned_text = self._extract_json_from_text(text)
        
        if not cleaned_text:
            return None
        
        try:
            # Parse as JSON
            parsed = json.loads(cleaned_text)
            
            # Validate against the Pydantic model
            validated = response_format.model_validate(parsed)
            
            # Return the validated dict
            return validated.model_dump()
            
        except (json.JSONDecodeError, ValidationError) as e:
            log_debug(f"BedrockWrapper: JSON parsing failed: {e}")
            return None
    
    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """Extract JSON from text that might contain markdown or other formatting.
        
        Args:
            text: Raw text that might contain JSON
            
        Returns:
            Extracted JSON string, or None if no valid JSON found
        """
        # Remove markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*$', '', text)
        
        # Try to find JSON object boundaries
        # Look for opening brace and try to find matching closing brace
        start_idx = text.find('{')
        if start_idx == -1:
            return None
        
        # Count braces to find the end of the JSON object
        brace_count = 0
        end_idx = -1
        
        for i in range(start_idx, len(text)):
            if text[i] == '{':
                brace_count += 1
            elif text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        if end_idx == -1:
            # No complete JSON object found
            return None
        
        json_text = text[start_idx:end_idx].strip()
        return json_text if json_text else None


def wrap_bedrock_agent(chat_agent, provider: str) -> None:
    """Wrap a ChatAgent with Bedrock response format support if needed.
    
    Args:
        chat_agent: The ChatAgent instance to potentially wrap
        provider: The LLM provider name ("bedrock", "azure", "openai")
    """
    if provider == "bedrock":
        log_debug("Wrapping ChatAgent with Bedrock response format support")
        BedrockResponseFormatWrapper(chat_agent)
    else:
        log_debug(f"Provider {provider} already supports response_format, no wrapping needed")