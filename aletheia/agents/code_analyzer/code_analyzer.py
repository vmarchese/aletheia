
from agent_framework import BaseChatClient

from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.plugins.scratchpad import Scratchpad
from aletheia.plugins.claude_code_plugin import ClaudeCodePlugin
from aletheia.plugins.copilot_plugin import CopilotPlugin
from aletheia.plugins.git_plugin import GitPlugin
from aletheia.utils.logging import log_debug
from aletheia.config import Config, CodeAnalyzerType


class CodeAnalyzer(BaseAgent):
    def __init__(self, 
                 name: str, 
                 config: Config,
                 description: str,
                 instructions: str,
                 service: BaseChatClient,
                 session: Session,
                 scratchpad: Scratchpad):

        log_debug("CodeAnalyzer::__init__:: called")

        log_debug("CodeAnalyzer::__init__:: setup plugins")
        code_plugin = None
        if config.code_analyzer == CodeAnalyzerType.CLAUDE.value:
            log_debug("CodeAnalyzer::__init__:: Using Claude Code Analyzer")
            code_plugin = ClaudeCodePlugin(config=config, session=session)
        elif config.code_analyzer == CodeAnalyzerType.COPILOT.value:
            log_debug("CodeAnalyzer::__init__:: Using Copilot Code Analyzer")
            code_plugin = CopilotPlugin(config=config, session=session)

        git_plugin = GitPlugin(session=session)


        plugins = [code_plugin, git_plugin, scratchpad]

        super().__init__(name=name,
                         description=description,
                         instructions=instructions,
                         service=service,
                         session=session,
                         plugins=plugins)
