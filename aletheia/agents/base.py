"""Base agent class for all specialist agents.

DEPRECATION WARNING:
    This custom BaseAgent class is deprecated and maintained only for backward
    compatibility during the Semantic Kernel migration. New agents should inherit
    from `aletheia.agents.sk_base.SKBaseAgent` instead.
    
    Migration Guide: See MIGRATION_SK.md for detailed migration instructions.
    
    Timeline:
    - v1.0 (current): Both patterns supported via feature flags
    - v1.1 (planned): SK becomes default, custom patterns deprecated
    - v2.0 (future): Custom patterns removed entirely

This module provides the abstract base class that all specialist agents must inherit from.
It provides common functionality for:
- Reading and writing to the scratchpad
- Accessing LLM providers
- Standardized execution interface

For new development, use SKBaseAgent which provides:
- Automatic function calling via plugins
- Built-in Semantic Kernel orchestration support
- Better testability with SK mocking patterns
- Multi-agent coordination via HandoffOrchestration
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from aletheia.llm.provider import LLMProvider, LLMFactory
from aletheia.scratchpad import Scratchpad


class BaseAgent(ABC):
    """Abstract base class for all specialist agents.
    
    DEPRECATED: Use `aletheia.agents.sk_base.SKBaseAgent` for new agents.
    This class is maintained for backward compatibility only.
    
    All specialist agents (Data Fetcher, Pattern Analyzer, Code Inspector,
    Root Cause Analyst) inherit from this class and must implement the
    execute() method.
    
    Attributes:
        config: Agent configuration dictionary
        scratchpad: Scratchpad instance for reading/writing shared state
        llm_provider: LLM provider instance for generating completions
        
    See Also:
        aletheia.agents.sk_base.SKBaseAgent: Modern SK-based agent foundation
        MIGRATION_SK.md: Detailed migration guide from BaseAgent to SKBaseAgent
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        scratchpad: Scratchpad,
        agent_name: Optional[str] = None
    ):
        """Initialize the base agent.
        
        Args:
            config: Configuration dictionary containing LLM and agent settings
            scratchpad: Scratchpad instance for agent communication
            agent_name: Optional agent name for LLM config lookup (defaults to class name)
        
        Raises:
            ValueError: If required configuration is missing
        """
        self.config = config
        self.scratchpad = scratchpad
        self.agent_name = agent_name or self.__class__.__name__.lower().replace("agent", "")
        
        # Validate configuration
        self._validate_config()
        
        # Initialize LLM provider (lazy - only when needed)
        self._llm_provider: Optional[LLMProvider] = None
    
    def _validate_config(self) -> None:
        """Validate that required configuration is present.
        
        Raises:
            ValueError: If required configuration is missing
        """
        if "llm" not in self.config:
            raise ValueError("Missing 'llm' configuration")
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the agent's main task.
        
        This method must be implemented by all subclasses. It performs the
        agent's specific work and returns results.
        
        Args:
            **kwargs: Agent-specific parameters
        
        Returns:
            Dictionary containing execution results
        
        Raises:
            NotImplementedError: If not implemented by subclass
        """
        pass
    
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
    
    def get_llm(self) -> LLMProvider:
        """Get the LLM provider for this agent.
        
        Lazy loads the LLM provider on first access. Uses agent-specific
        configuration if available, otherwise uses default configuration.
        
        Returns:
            LLM provider instance
        
        Raises:
            ValueError: If LLM configuration is invalid
        """
        if self._llm_provider is None:
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
            
            # Add Azure OpenAI configuration if present
            if llm_config.get("use_azure"):
                provider_config["use_azure"] = True
                provider_config["azure_deployment"] = agent_config.get("azure_deployment") or llm_config.get("azure_deployment")
                provider_config["azure_endpoint"] = agent_config.get("azure_endpoint") or llm_config.get("azure_endpoint")
                if "azure_api_version" in llm_config or "azure_api_version" in agent_config:
                    provider_config["azure_api_version"] = agent_config.get("azure_api_version") or llm_config.get("azure_api_version")
            
            self._llm_provider = LLMFactory.create_provider(provider_config)
        
        return self._llm_provider
    
    def __repr__(self) -> str:
        """Return string representation of the agent."""
        return f"{self.__class__.__name__}(agent_name='{self.agent_name}')"
