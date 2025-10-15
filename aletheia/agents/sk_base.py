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
from abc import abstractmethod
from typing import Any, Dict, List, Optional

from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion, OpenAIChatPromptExecutionSettings
from semantic_kernel.contents import ChatHistory, ChatMessageContent

from aletheia.scratchpad import Scratchpad
from aletheia.llm.prompts import get_system_prompt


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
        
        Lazy initialization of the kernel with OpenAI chat completion service.
        The service is configured based on agent-specific or default LLM config.
        
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
            
            # Determine model and credentials
            model = agent_config.get("model") or llm_config.get("default_model", "gpt-4o")
            api_key = llm_config.get("api_key") or None
            
            # Create kernel
            self._kernel = Kernel()
            
            # Add OpenAI chat completion service
            service = OpenAIChatCompletion(
                service_id="default",
                ai_model_id=model,
                api_key=api_key
            )
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
        settings: Optional[Dict[str, Any]] = None
    ) -> str:
        """Invoke the SK agent with a user message (async).
        
        This method sends a message to the SK ChatCompletionAgent and returns
        the response. It handles automatic function calling if plugins are
        configured with FunctionChoiceBehavior.Auto().
        
        Args:
            user_message: User message to send to the agent
            settings: Optional execution settings for the agent
        
        Returns:
            Agent's response as string
        
        Raises:
            Exception: If agent invocation fails
        """
        # Add user message to history
        self.chat_history.add_user_message(user_message)
        
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
        response = await self.agent.invoke(
            history=self.chat_history,
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
        
        # Add response to history
        self.chat_history.add_assistant_message(response_text)
        
        return response_text
    
    def invoke(
        self,
        user_message: str,
        settings: Optional[Dict[str, Any]] = None
    ) -> str:
        """Invoke the SK agent with a user message (synchronous wrapper).
        
        This is a synchronous wrapper around invoke_async() for compatibility
        with existing synchronous code.
        
        Args:
            user_message: User message to send to the agent
            settings: Optional execution settings for the agent
        
        Returns:
            Agent's response as string
        """
        return asyncio.run(self.invoke_async(user_message, settings))
    
    def read_scratchpad(self, section: str) -> Optional[Any]:
        """Read a section from the scratchpad.
        
        Args:
            section: Section name to read
        
        Returns:
            Section data if it exists, None otherwise
        """
        return self.scratchpad.read_section(section)
    
    def write_scratchpad(self, section: str, data: Any) -> None:
        """Write data to a scratchpad section.
        
        Args:
            section: Section name to write
            data: Data to write to the section
        """
        self.scratchpad.write_section(section, data)
        self.scratchpad.save()
    
    def append_scratchpad(self, section: str, data: Any) -> None:
        """Append data to a scratchpad section.
        
        Args:
            section: Section name to append to
            data: Data to append to the section
        """
        self.scratchpad.append_to_section(section, data)
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
