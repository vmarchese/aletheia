from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase

from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.scratchpad import Scratchpad
from aletheia.plugins.claude_code_plugin import ClaudeCodePlugin
from aletheia.utils.logging import log_debug
from aletheia.config import Config


class ClaudeCodeAnalyzer(BaseAgent):
    def __init__(self, 
                 name: str, 
                 config: Config,
                 description: str,
                 instructions: str,
                 service: ChatCompletionClientBase,
                 session: Session,
                 scratchpad: Scratchpad):

        log_debug("ClaudeCodeAnalyzer::__init__:: called")

        log_debug("ClaudeCodeAnalyzer::__init__:: setup plugins")
        claude_code_plugin = ClaudeCodePlugin(config=config, session=session)


        super().__init__(name=name,
                         description=description,
                         instructions=instructions,
                         service=service,
                         session=session,
                         scratchpad=scratchpad,
                         plugins=[claude_code_plugin])        
    