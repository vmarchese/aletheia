"""Semantic Kernel-based agent foundation.

This module provides the SK-based base class for all specialist agents using
Semantic Kernel's ChatCompletionAgent framework. This is the future-proof
foundation for agent implementations with plugin support and orchestration.

Key features:
- Uses SK's ChatCompletionAgent as base
- Automatic plugin invocation via FunctionChoiceBehavior.Auto()
- Maintains scratchpad compatibility
- Kernel management per agent
"""

import asyncio
import os
from abc import abstractmethod
from typing import Any, Dict, List, Optional

from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion, AzureChatCompletion, OpenAIChatPromptExecutionSettings
from semantic_kernel.contents import ChatHistory, ChatMessageContent

from aletheia.scratchpad import Scratchpad
from aletheia.llm.prompts import get_system_prompt
from aletheia.utils.logging import (
    is_trace_enabled, 
    log_prompt, 
    log_prompt_response,
    log_operation_start,
    log_operation_complete,
    log_scratchpad_operation,
    log_llm_invocation
)


class SKBaseAgent:
    """Semantic Kernel-based base agent for all specialist agents.
    
    This class wraps SK's ChatCompletionAgent to provide a foundation for
    all specialist agents while maintaining compatibility with the existing
    scratchpad-based architecture.
    
    Agents inherit from this class to gain:
    - Automatic plugin function calling (via FunctionChoiceBehavior.Auto())
    - Kernel management with chat completion service
    - Scratchpad read/write operations
    - Structured agent execution pattern
    
    Attributes:
        config: Agent configuration dictionary
        scratchpad: Scratchpad instance for shared state
        agent_name: Name of the agent (used for prompts and config)
        kernel: Semantic Kernel instance with chat service
        agent: SK ChatCompletionAgent instance
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        scratchpad: Scratchpad,
        agent_name: Optional[str] = None
    ):
        """Initialize the SK-based agent.
        
        Args:
            config: Configuration dictionary containing LLM and agent settings
            scratchpad: Scratchpad instance for agent communication
            agent_name: Optional agent name for config lookup (defaults to class name)
        
        Raises:
            ValueError: If required configuration is missing
        """
        self.config = config
        self.scratchpad = scratchpad
        self.agent_name = agent_name or self.__class__.__name__.lower().replace("agent", "")
        
        # Validate configuration
        self._validate_config()
        
        # Initialize kernel and agent (lazy - only when needed)
        self._kernel: Optional[Kernel] = None
        self._agent: Optional[ChatCompletionAgent] = None
        self._chat_history: Optional[ChatHistory] = None
    
    def _validate_config(self) -> None:
        """Validate that required configuration is present.
        
        Raises:
            ValueError: If required configuration is missing
        """
        if "llm" not in self.config:
            raise ValueError("Missing 'llm' configuration")
    
    @property
    def kernel(self) -> Kernel:
        """Get or create the Semantic Kernel instance.
        
        Lazy initialization of the kernel with OpenAI or Azure chat completion service.
        The service is configured based on agent-specific or default LLM config.
        
        Supports both standard OpenAI and Azure OpenAI Services:
        - If use_azure=True, uses AzureChatCompletion
        - Otherwise, uses OpenAIChatCompletion
        
        Returns:
            Configured Semantic Kernel instance
        """
        if self._kernel is None:
            # Get configuration
            llm_config = self.config.get("llm", {})
            agents_config = llm_config.get("agents", {})
            
            # Check for exact agent name match first, then try without common suffixes
            agent_config = agents_config.get(self.agent_name, {})
            if not agent_config:
                # Try alternative names (e.g., datafetcher vs data_fetcher)
                for key in agents_config:
                    if key.replace("_", "") == self.agent_name.replace("_", ""):
                        agent_config = agents_config[key]
                        break
            
            # Determine if using Azure OpenAI (agent-specific overrides default)
            use_azure = agent_config.get("use_azure", llm_config.get("use_azure", False))
            
            # Create kernel
            self._kernel = Kernel()
            
            if use_azure:
                # Azure OpenAI configuration
                azure_deployment = agent_config.get("azure_deployment") or llm_config.get("azure_deployment")
                azure_endpoint = agent_config.get("azure_endpoint") or llm_config.get("azure_endpoint")
                azure_api_version = agent_config.get("azure_api_version") or llm_config.get("azure_api_version")
                
                # Get API key from environment variable or config
                api_key_env = llm_config.get("api_key_env", "OPENAI_API_KEY")
                api_key = llm_config.get("api_key") or os.getenv(api_key_env)
                
                # Validate required Azure fields
                if not azure_deployment:
                    raise ValueError(f"Azure deployment name required when use_azure=True (agent: {self.agent_name})")
                if not azure_endpoint:
                    raise ValueError(f"Azure endpoint required when use_azure=True (agent: {self.agent_name})")
                
                # Create Azure chat completion service
                service_kwargs = {
                    "service_id": "default",
                    "deployment_name": azure_deployment,
                    "endpoint": azure_endpoint,
                    "api_key": api_key,
                }
                if azure_api_version is not None:
                    service_kwargs["api_version"] = azure_api_version
                
                service = AzureChatCompletion(**service_kwargs)
            else:
                # Standard OpenAI configuration
                model = agent_config.get("model") or llm_config.get("default_model", "gpt-4o")
                
                # Get API key from environment variable or config
                api_key_env = llm_config.get("api_key_env", "OPENAI_API_KEY")
                api_key = llm_config.get("api_key") or os.getenv(api_key_env)
                
                # Agent-specific base_url takes precedence over default
                base_url = agent_config.get("base_url") or llm_config.get("base_url") or None
                
                # Create OpenAI chat completion service
                service_kwargs = {
                    "service_id": "default",
                    "ai_model_id": model,
                    "api_key": api_key,
                }
                if base_url is not None:
                    service_kwargs["base_url"] = base_url
                
                service = OpenAIChatCompletion(**service_kwargs)
            
            self._kernel.add_service(service)
        
        return self._kernel
    
    @property
    def agent(self) -> ChatCompletionAgent:
        """Get or create the ChatCompletionAgent instance.
        
        Lazy initialization of the SK ChatCompletionAgent with:
        - System instructions from prompts
        - Kernel with chat completion service
        - Auto function calling behavior
        
        Returns:
            Configured ChatCompletionAgent instance
        """
        if self._agent is None:
            # Get system instructions
            instructions = get_system_prompt(self.agent_name)
            
            # Create ChatCompletionAgent
            self._agent = ChatCompletionAgent(
                service_id="default",
                kernel=self.kernel,
                name=self.agent_name,
                instructions=instructions,
            )
        
        return self._agent
    
    @property
    def chat_history(self) -> ChatHistory:
        """Get or create the chat history for this agent.
        
        Returns:
            ChatHistory instance for conversation tracking
        """
        if self._chat_history is None:
            self._chat_history = ChatHistory()
        return self._chat_history
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the agent's main task.
        
        This method must be implemented by all subclasses. It performs the
        agent's specific work and returns results.
        
        Subclasses can use invoke() to interact with the SK agent.
        
        Args:
            **kwargs: Agent-specific parameters
        
        Returns:
            Dictionary containing execution results
        
        Raises:
            NotImplementedError: If not implemented by subclass
        """
        pass
    
    async def invoke_async(
        self,
        user_message: str,
        settings: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """Invoke the SK agent with a user message (async).
        
        This method sends a message to the SK ChatCompletionAgent and returns
        the response. It handles automatic function calling if plugins are
        configured with FunctionChoiceBehavior.Auto().
        
        Args:
            user_message: User message to send to the agent
            settings: Optional execution settings for the agent
            system_prompt: Optional custom system prompt (overrides default)
        
        Returns:
            Agent's response as string
        
        Raises:
            Exception: If agent invocation fails
        """
        # Get model name for logging
        llm_config = self.config.get("llm", {})
        agents_config = llm_config.get("agents", {})
        agent_config = agents_config.get(self.agent_name, {})
        model = agent_config.get("model") or llm_config.get("default_model", "gpt-4o")
        
        # Create custom agent if system_prompt is provided
        if system_prompt:
            custom_agent = ChatCompletionAgent(
                service_id="default",
                kernel=self.kernel,
                name=self.agent_name,
                instructions=system_prompt,
            )
            agent_to_use = custom_agent
            # Create fresh chat history for custom prompt
            chat_history = ChatHistory()
        else:
            agent_to_use = self.agent
            chat_history = self.chat_history
        
        # Log prompt if trace logging is enabled
        if is_trace_enabled():
            # Estimate tokens (rough approximation: 4 chars per token)
            prompt_tokens = len(user_message) // 4
            prompt_summary = user_message[:100].replace('\n', ' ')
            log_llm_invocation(
                agent_name=self.agent_name,
                model=model,
                prompt_summary=prompt_summary,
                estimated_tokens=prompt_tokens
            )
            log_prompt(
                agent_name=self.agent_name,
                prompt=user_message,
                model=model,
                prompt_tokens=prompt_tokens
            )
        
        # Add user message to history
        chat_history.add_user_message(user_message)
        
        # Configure settings with auto function calling
        if settings is None:
            settings = {}
        
        # Create execution settings
        exec_settings = OpenAIChatPromptExecutionSettings(
            temperature=settings.get("temperature", 0.7),
            max_tokens=settings.get("max_tokens", None),
            function_choice_behavior=FunctionChoiceBehavior.Auto()
        )
        
        # Invoke agent
        response = await agent_to_use.invoke(
            history=chat_history,
            settings=exec_settings
        )
        
        # Extract response content
        if isinstance(response, list):
            # Multiple messages returned
            response_text = "\n".join([msg.content for msg in response if hasattr(msg, 'content')])
        elif hasattr(response, 'content'):
            response_text = response.content
        else:
            response_text = str(response)
        
        # Log response if trace logging is enabled
        if is_trace_enabled():
            # Estimate tokens for response
            completion_tokens = len(response_text) // 4
            total_tokens = prompt_tokens + completion_tokens if 'prompt_tokens' in locals() else None
            log_prompt_response(
                agent_name=self.agent_name,
                response=response_text,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
        
        # Add response to history (only if using default agent)
        if not system_prompt:
            chat_history.add_assistant_message(response_text)
        
        return response_text
    
    def invoke(
        self,
        user_message: str,
        settings: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """Invoke the SK agent with a user message (synchronous wrapper).
        
        This is a synchronous wrapper around invoke_async() for compatibility
        with existing synchronous code.
        
        Args:
            user_message: User message to send to the agent
            settings: Optional execution settings for the agent
            system_prompt: Optional custom system prompt (overrides default)
        
        Returns:
            Agent's response as string
        """
        return asyncio.run(self.invoke_async(user_message, settings, system_prompt))
    
    def read_scratchpad(self, section: str) -> Optional[Any]:
        """Read a section from the scratchpad.
        
        Args:
            section: Section name to read
        
        Returns:
            Section data, or None if section doesn't exist
        """
        data = self.scratchpad.read_section(section)
        
        # Log scratchpad read operation
        if is_trace_enabled() and data is not None:
            data_summary = str(data)[:100] if data else None
            log_scratchpad_operation(
                operation="READ",
                section=section,
                agent_name=self.agent_name,
                data_summary=data_summary
            )
        
        return data
    
    def write_scratchpad(self, section: str, data: Any) -> None:
        """Write data to a scratchpad section.
        
        Args:
            section: Section name to write
            data: Data to write to the section
        """
        self.scratchpad.write_section(section, data)
        self.scratchpad.save()
        
        # Log scratchpad write operation
        if is_trace_enabled():
            data_summary = str(data)[:100] if data else None
            log_scratchpad_operation(
                operation="WRITE",
                section=section,
                agent_name=self.agent_name,
                data_summary=data_summary
            )
    
    def append_scratchpad(self, section: str, data: Any) -> None:
        """Append data to a scratchpad section.
        
        Args:
            section: Section name to append to
            data: Data to append to the section
        """
        self.scratchpad.append_to_section(section, data)
        
        # Log scratchpad append operation
        if is_trace_enabled():
            data_summary = str(data)[:100] if data else None
            log_scratchpad_operation(
                operation="APPEND",
                section=section,
                agent_name=self.agent_name,
                data_summary=data_summary
            )
        self.scratchpad.save()
    
    def reset_chat_history(self) -> None:
        """Reset the chat history for this agent.
        
        Useful when starting a new task or clearing context.
        """
        self._chat_history = None
    
    def get_llm(self):
        """Get an LLM provider for legacy compatibility.
        
        This method provides backward compatibility with code that expects
        the old BaseAgent's get_llm() method. It returns an LLMProvider
        that wraps the SK chat service.
        
        Note: New code should use invoke() instead of calling LLM directly.
        
        Returns:
            LLMProvider instance for backward compatibility
        """
        from aletheia.llm.provider import LLMFactory
        
        if not hasattr(self, '_llm_provider') or self._llm_provider is None:
            llm_config = self.config.get("llm", {})
            
            # Try to get agent-specific configuration
            agents_config = llm_config.get("agents", {})
            agent_config = agents_config.get(self.agent_name, {})
            
            # Merge with default configuration
            provider_config = {
                "model": agent_config.get("model") or llm_config.get("default_model", "gpt-4o"),
                "api_key_env": llm_config.get("api_key_env", "OPENAI_API_KEY"),
            }
            
            # Add optional configuration
            if "api_key" in llm_config:
                provider_config["api_key"] = llm_config["api_key"]
            if "base_url" in agent_config:
                provider_config["base_url"] = agent_config["base_url"]
            if "timeout" in agent_config:
                provider_config["timeout"] = agent_config["timeout"]
            
            self._llm_provider = LLMFactory.create_provider(provider_config)
        
        return self._llm_provider
    
    def __repr__(self) -> str:
        """Return string representation of the agent."""
        return f"{self.__class__.__name__}(agent_name='{self.agent_name}')"
