from abc import ABC

from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
from semantic_kernel.functions.kernel_plugin import KernelPlugin

from aletheia.plugins.scratchpad import Scratchpad
from aletheia.session import Session


class BaseAgent(ABC):
    """Abstract base class for all specialist agents.
    
    All specialist agents (Data Fetcher, Pattern Analyzer, Code Inspector,
    Root Cause Analyst) inherit from this class and must implement the
    execute() method.
    
    Attributes:
        config: Agent configuration dictionary
        scratchpad: Scratchpad instance for reading/writing shared state
        llm_provider: LLM provider instance for generating completions
        
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        instructions: str,
        service: ChatCompletionClientBase,
        scratchpad: Scratchpad = None,
        session: Session = None,
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
        if scratchpad:  
            _plugins.append(scratchpad)
        _plugins.extend(plugins or [])

        self.agent = ChatCompletionAgent(
            name=self.name,
            description=description,
            instructions=instructions,
            service=service,
            plugins=_plugins
        )



    
    
    
