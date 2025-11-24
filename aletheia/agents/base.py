"""Base agent class for all specialist agents."""
import os
from abc import ABC
from typing import Sequence
from pathlib import Path
from jinja2 import Template

import yaml

from agent_framework import ChatAgent, ToolProtocol
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential

from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session
from aletheia.agents.middleware import LoggingAgentMiddleware, LoggingFunctionMiddleware
from aletheia.agents.chat_message_store import ChatMessageStoreSingleton
from aletheia.plugins.base import BasePlugin
from aletheia.agents.skills import SkillLoader


class AgentInfo(ABC):
    def __init__(self,
                 name: str):
        self.name = name
        self.identity = ""
        self.guidelines = ""
        package_dir = Path(__file__).parent.parent
        self.prompts_dir = package_dir / "agents"        
        self.load()

    def load(self):
        """Load agent instructions from YAML file."""
        instructions_file_name = "instructions.yaml"
        prompt_file = self.prompts_dir / f"{self.name}/{instructions_file_name}"
        with open(prompt_file, 'r', encoding="utf-8") as file:
            content = file.read()        
            instructions = yaml.safe_load(content)
            self.name = str(instructions.get("agent").get("name"))
            self.identity = str(instructions.get("agent").get("identity"))
            self.guidelines = str(instructions.get("agent").get("guidelines"))


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
        instructions: str = None,
        scratchpad: Scratchpad = None,
        session: Session = None,
        plugins: Sequence[BasePlugin] = None,
        tools: Sequence[ToolProtocol] = None,
        render_instructions: bool = True,
        config=None,
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
        if plugins:
            for plugin in plugins:
                _tools.extend(plugin.get_tools())

        if scratchpad:
            _tools.append(scratchpad.get_tools())

        _tools.extend(tools or [])

        # Loading skills
        skills = []
        if config and config.skills_directory:
            skillloader = SkillLoader(os.path.join(config.skills_directory, self.name.lower()))
            skills = skillloader.skills
            _tools.append(skillloader.load_skill)

        # prompt template
        rendered_instructions = ""
        if instructions:
            rendered_instructions = instructions
            if render_instructions:
                template = Template(instructions)
                rendered_instructions = template.render(plugins=plugins, skills=skills)
        else: 
            prompt_template = self.load_prompt_template()

            agent_info = AgentInfo(self.name)
            rendered_instructions = prompt_template
            if render_instructions:
                template = Template(prompt_template)
                rendered_instructions = template.render(plugins=plugins, skills=skills, agent_info=agent_info)

        logging_agent_middleware = LoggingAgentMiddleware()
        logging_function_middleware = LoggingFunctionMiddleware()

        self.agent = ChatAgent(
            name=self.name,
            description=description,
            instructions=rendered_instructions,
            chat_client=AzureOpenAIChatClient(credential=AzureCliCredential()),
            tools=_tools,
            chat_store=ChatMessageStoreSingleton.get_instance,
            middleware=[logging_agent_middleware, logging_function_middleware],
            temperature=0.2
        )

    def load_prompt_template(self) -> str:
        """Load the agent's prompt template from a markdown file."""
        package_dir = Path(__file__).parent.parent
        prompt_template = package_dir / "agents" / "prompt_template.md"
        with open(prompt_template, 'r', encoding="utf-8") as file:
            content = file.read()
        return content
