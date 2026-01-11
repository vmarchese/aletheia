"""Base agent class for all specialist agents."""
import os
from abc import ABC
from typing import Sequence
from pathlib import Path
from jinja2 import Template

import yaml

from agent_framework import ChatAgent, ToolProtocol

from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session
from aletheia.agents.middleware import LoggingAgentMiddleware, LoggingFunctionMiddleware, ConsoleFunctionMiddleware
from aletheia.agents.chat_message_store import ChatMessageStoreSingleton
from aletheia.plugins.base import BasePlugin
from aletheia.plugins.dockerscript.dockerscript_plugin import DockerScriptPlugin
from aletheia.agents.skills import SkillLoader
from aletheia.agents.client import LLMClient
from aletheia.mcp.mcp import load_mcp_tools
from aletheia.utils.logging import log_error, log_debug
from aletheia.knowledge import KnowledgePlugin, ChromaKnowledge
from aletheia.agents.bedrock_wrapper import wrap_bedrock_agent


class AgentInfo(ABC):
    """Holds information about an agent loaded from YAML instructions."""
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
        additional_middleware: Sequence = None,
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
        self.config = config
        _tools = []
        if plugins:
            for plugin in plugins:
                plugin_tools = plugin.get_tools()
                _tools.extend(plugin_tools)

        if scratchpad:
            scratchpad_tools = scratchpad.get_tools()
            _tools.append(scratchpad_tools)

        _tools.extend(tools or [])

        # mcp tools
        self.mcp_tools = []
        if config and config.mcp_servers_yaml:
            mcp_tools = load_mcp_tools(agent=self.name, yaml_file=config.mcp_servers_yaml)
            self.mcp_tools.extend(mcp_tools)
            _tools.extend(mcp_tools)

        # Loading skills
        _skills = []
        if config is not None:
            skills_directory = self.config.skills_directory
            skill_directories = [skills_directory] if skills_directory else []

            user_skills_dirs = os.getenv("ALETHEIA_USER_SKILLS_DIRS")
            if user_skills_dirs:
                for dir_path in user_skills_dirs.split(os.pathsep):
                    skill_directories.append(dir_path)

            for skill_dir in skill_directories:
                skillloader = SkillLoader(os.path.join(skill_dir, self.name.lower()))
                if skillloader.skills:
                    _skills.extend(skillloader.skills)

        if len(_skills) > 0:
            docker_plugin = DockerScriptPlugin(config=config, session=session, scratchpad=scratchpad)
            plugins.append(docker_plugin)
            _tools.append(skillloader.get_skill_instructions)
            _tools.append(docker_plugin.sandbox_run)

        client = LLMClient(agent_name=self.name)            

        # loading custom instructions
        custom_instructions = self.load_custom_instructions()

        rendered_instructions = ""
        if instructions:
            rendered_instructions = instructions
            if render_instructions:
                template = Template(instructions)
                rendered_instructions = template.render(skills=_skills, plugins=plugins, llm_client=client, custom_instructions=custom_instructions)
        else:
            prompt_template = self.load_prompt_template()
            agent_info = AgentInfo(self.name)
            rendered_instructions = prompt_template
            if render_instructions:
                template = Template(prompt_template)
                rendered_instructions = template.render(skills=_skills, plugins=plugins, agent_info=agent_info, llm_client=client, custom_instructions=custom_instructions)

        console_function_middleware = ConsoleFunctionMiddleware()
        logging_agent_middleware = LoggingAgentMiddleware()
        logging_function_middleware = LoggingFunctionMiddleware()

        ## Adding knowledge
        knowledge_plugin = KnowledgePlugin(ChromaKnowledge())
        _tools.append(knowledge_plugin.query)

        # Build middleware list
        middleware_list = [
            logging_agent_middleware,
            logging_function_middleware,
            console_function_middleware
        ]

        # Add any additional middleware passed by caller
        if additional_middleware:
            log_debug(f"[BaseAgent::{self.name}] Adding additional middleware: {additional_middleware}")
            middleware_list.extend(additional_middleware)

        log_debug(f"[BaseAgent::{self.name}] Final middleware list: {middleware_list}")

        self.agent = ChatAgent(
            name=self.name,
            description=description,
            instructions=rendered_instructions,
            chat_client=client.get_client(),
            tools=_tools,
            chat_store=ChatMessageStoreSingleton.get_instance,
            middleware=middleware_list,
            temperature=config.llm_temperature if config else 0.0
        )

        # Wrap with Bedrock response format support if needed
        wrap_bedrock_agent(self.agent, client.get_provider())

    async def cleanup(self):
        """Clean up MCP tool connections."""
        for mcp_tool in self.mcp_tools:
            if hasattr(mcp_tool, 'close'):
                try:
                    await mcp_tool.close()
                except (OSError, RuntimeError):
                    pass  # Ignore cleanup errors

    def load_prompt_template(self) -> str:
        """Load the agent's prompt template from a markdown file."""
        package_dir = Path(__file__).parent.parent
        prompt_template = package_dir / "agents" / "prompt_template.md"
        with open(prompt_template, 'r', encoding="utf-8") as file:
            content = file.read()
        return content

    def load_custom_instructions(self):
        """Load custom instructions for the agent from a YAML file."""
        try:
            if self.config is None:
                return None
            if self.config.custom_instructions_dir is None:
                return None 
            prompt_file = f"{self.config.custom_instructions_dir}/{self.name}/instructions.md"
            with open(prompt_file, 'r', encoding="utf-8") as file:
                content = file.read()
                return content
        except (OSError, FileNotFoundError, IsADirectoryError, PermissionError) as e:
            log_error(f"BaseAgent::load_custom_instructions:: Error loading custom instructions for agent {self.name}: {e}")
            return None
