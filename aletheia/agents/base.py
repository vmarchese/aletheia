from abc import ABC
from typing import Sequence

from agent_framework import ChatAgent, BaseChatClient, ChatMessageStore, ToolProtocol
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential   

#from semantic_kernel.agents import ChatCompletionAgent
#from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
#from semantic_kernel.functions.kernel_plugin import KernelPlugin

from aletheia.plugins.scratchpad import Scratchpad
from aletheia.session import Session
from aletheia.agents.middleware import LoggingFunctionMiddleware, LoggingAgentMiddleware, LoggingChatMiddleware
from aletheia.agents.chat_message_store import ChatMessageStoreSingleton


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
        service: BaseChatClient,
        scratchpad: Scratchpad = None,
        session: Session = None,
        tools: Sequence[ToolProtocol] = None
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
        _tools = []
        if scratchpad:  
            _tools.append(scratchpad)
        _tools.extend(tools or [])

        
        """
        self.agent = ChatAgent(
            name=self.name,
            description=description,
            instructions=instructions,
            chat_client=service,
            tools=_tools,
            chat_store=create_message_store() if chat_store_enabled else None
        )
        """

        logging_middleware = LoggingFunctionMiddleware()
        logging_agent_middleware = LoggingAgentMiddleware()
        logging_chat_middleware = LoggingChatMiddleware()
        """
        self.agent = AzureOpenAIChatClient(credential=AzureCliCredential()).create_agent(
            name=self.name,
            description=description,
            instructions=instructions,
            tools=_tools,
            chat_message_store_factory=ChatMessageStoreSingleton.get_instance
#            middleware=[logging_middleware, logging_agent_middleware, logging_chat_middleware]
        )
        """
        self.agent = ChatAgent(
            name=self.name,
            description=description,
            instructions=instructions,
            chat_client=AzureOpenAIChatClient(credential=AzureCliCredential()),
            tools=_tools,
            chat_store=ChatMessageStoreSingleton.get_instance
        )






    
    
    
