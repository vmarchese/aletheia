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

from abc import ABC

from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
from semantic_kernel.functions.kernel_plugin import KernelPlugin

from aletheia.scratchpad import Scratchpad
from aletheia.session import Session


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
        name: str,
        description: str,
        instructions: str,
        service: ChatCompletionClientBase,
        session: Session,
        scratchpad: Scratchpad,
        plugins: list[KernelPlugin] = None,
    ):
        """Initialize the base agent.
        
        Args:
            scratchpad: Scratchpad instance for agent communication
            agent_name: Optional agent name for LLM config lookup (defaults to class name)
        
        Raises:
            ValueError: If required configuration is missing
        """
        self.scratchpad = scratchpad
        self.name = name
        self.description = description
        self.session = session  
        _plugins = []
        _plugins.append(scratchpad)
        _plugins.extend(plugins or [])

        self.agent = ChatCompletionAgent(
            name=self.name,
            description=description,
            instructions=instructions,
            service=service,
            plugins=_plugins
        )



    
    
    
