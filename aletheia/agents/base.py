"""Base agent class for all specialist agents."""

import os
from abc import ABC
from collections.abc import Sequence
from pathlib import Path

import structlog
import yaml
from agent_framework import Agent, AgentSession, FunctionTool, tool
from jinja2 import Template

from aletheia.agents.bedrock_chat_client_wrapper import wrap_bedrock_chat_client
from aletheia.agents.client import LLMClient
from aletheia.agents.deepcopy_patch import patch_deepcopy
from aletheia.agents.middleware import (
    ConsoleFunctionMiddleware,
    LoggingAgentMiddleware,
    LoggingFunctionMiddleware,
)
from aletheia.agents.skills import SkillLoader
from aletheia.engram.tools import Engram
from aletheia.knowledge import KnowledgePlugin, SqliteKnowledge
from aletheia.mcp.mcp import load_mcp_tools
from aletheia.plugins.base import BasePlugin
from aletheia.plugins.dockerscript.dockerscript_plugin import DockerScriptPlugin
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session

logger = structlog.get_logger(__name__)

# Apply the deepcopy patch to handle bound methods in tools
patch_deepcopy()


class AgentInfo(ABC):
    """Holds information about an agent loaded from YAML instructions."""

    def __init__(self, name: str, prompts_dir: Path | None = None):
        self.name = name
        self.identity = ""
        self.guidelines = ""
        package_dir = Path(__file__).parent.parent
        self.prompts_dir = prompts_dir if prompts_dir else (package_dir / "agents")
        self.load()

    def load(self):
        """Load agent instructions from YAML file."""
        instructions_file_name = "instructions.yaml"
        prompt_file = self.prompts_dir / f"{self.name}/{instructions_file_name}"
        with open(prompt_file, encoding="utf-8") as file:
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
        tools: Sequence[FunctionTool] = None,
        render_instructions: bool = True,
        config=None,
        additional_middleware: Sequence = None,
        prompts_dir: Path | None = None,
        engram: Engram | None = None,
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

        if engram:
            _tools.extend(engram.get_tools())

        _tools.extend(tools or [])

        # mcp tools
        self.mcp_tools = []
        mcp_tools = load_mcp_tools(
            agent=self.name,
            config_file=config.mcp_servers_config if config else None,
        )
        self.mcp_tools.extend(mcp_tools)
        _tools.extend(mcp_tools)

        # Loading skills
        _skills = []
        _skill_loaders: list[SkillLoader] = []
        if config is not None:
            skills_directory = self.config.skills_directory
            skill_directories = [skills_directory] if skills_directory else []

            user_skills_dirs = os.getenv("ALETHEIA_USER_SKILLS_DIRS")
            if user_skills_dirs:
                for dir_path in user_skills_dirs.split(os.pathsep):
                    skill_directories.append(dir_path)

            for skill_dir in skill_directories:
                skillloader = SkillLoader(os.path.join(skill_dir, self.name.lower()))
                _skill_loaders.append(skillloader)
                if skillloader.skills:
                    _skills.extend(skillloader.skills)

        # Store skill loaders for runtime reload
        self._skill_loaders = _skill_loaders

        if len(_skills) > 0:
            docker_plugin = DockerScriptPlugin(
                config=config, session=session, scratchpad=scratchpad
            )
            plugins.append(docker_plugin)
            _tools.append(skillloader.get_skill_instructions)
            _tools.append(skillloader.load_file)
            _tools.append(docker_plugin.sandbox_run)

        # Always register list_available_skills for runtime skill discovery
        if _skill_loaders:
            _tools.append(_skill_loaders[0].list_available_skills)

        client = LLMClient(agent_name=self.name)

        # loading custom instructions
        custom_instructions = self.load_custom_instructions()

        # Load soul for orchestrator personality
        soul_content = None
        has_soul = False
        if self.name == "orchestrator":
            soul_content = self.load_soul()
            has_soul = soul_content is not None

        # Adding knowledge
        knowledge_enabled = config.knowledge_enabled if config else True
        if knowledge_enabled:
            knowledge_plugin = KnowledgePlugin(SqliteKnowledge())
            _tools.append(knowledge_plugin.query)

        rendered_instructions = ""
        agent_info = None
        if instructions:
            rendered_instructions = instructions
            if render_instructions:
                template = Template(instructions)
                rendered_instructions = template.render(
                    skills=_skills,
                    plugins=plugins,
                    llm_client=client,
                    custom_instructions=custom_instructions,
                    memory_enabled=(engram is not None),
                    knowledge_enabled=knowledge_enabled,
                    soul=soul_content,
                    has_soul=has_soul,
                )
        else:
            prompt_template = self.load_prompt_template()
            agent_info = AgentInfo(self.name, prompts_dir=prompts_dir)
            rendered_instructions = prompt_template
            if render_instructions:
                template = Template(prompt_template)
                rendered_instructions = template.render(
                    skills=_skills,
                    plugins=plugins,
                    agent_info=agent_info,
                    llm_client=client,
                    custom_instructions=custom_instructions,
                    memory_enabled=(engram is not None),
                    knowledge_enabled=knowledge_enabled,
                    soul=soul_content,
                    has_soul=has_soul,
                )

        # Store template context for hot-reload of skills
        self._render_instructions = render_instructions
        self._instructions_source = instructions if instructions else prompt_template
        self._agent_info = agent_info
        self._render_context = {
            "plugins": plugins,
            "llm_client": client,
            "custom_instructions": custom_instructions,
            "memory_enabled": (engram is not None),
            "knowledge_enabled": knowledge_enabled,
            "soul": soul_content,
            "has_soul": has_soul,
        }

        console_function_middleware = ConsoleFunctionMiddleware()
        logging_agent_middleware = LoggingAgentMiddleware()
        logging_function_middleware = LoggingFunctionMiddleware()

        # Build middleware list
        middleware_list = [
            logging_agent_middleware,
            logging_function_middleware,
            console_function_middleware,
        ]

        # Add any additional middleware passed by caller
        if additional_middleware:
            logger.debug(
                f"[BaseAgent::{self.name}] Adding additional middleware: {additional_middleware}"
            )
            middleware_list.extend(additional_middleware)

        logger.debug(
            f"[BaseAgent::{self.name}] Final middleware list: {middleware_list}"
        )

        # Wrap raw callables as FunctionTool so they serialize for the LLM API
        _wrapped_tools = []
        for t in _tools:
            if isinstance(t, FunctionTool) or not callable(t):
                _wrapped_tools.append(t)
            else:
                _wrapped_tools.append(tool(t))

        # Build context providers for active context management
        from agent_framework import InMemoryHistoryProvider

        from aletheia.context import ContextWindowProvider

        _max_tokens = config.max_context_window if config else 1_000_000
        _reserved = (
            config.context_reserved_ratio
            if config and hasattr(config, "context_reserved_ratio")
            else 0.225
        )
        self._context_provider = ContextWindowProvider(
            max_tokens=_max_tokens,
            reserved_ratio=_reserved,
        )
        _context_providers = [
            InMemoryHistoryProvider(),
            self._context_provider,
        ]

        self.agent = Agent(
            client=client.get_client(),
            instructions=rendered_instructions,
            name=self.name,
            description=description,
            tools=_wrapped_tools,
            middleware=middleware_list,
            default_options={"temperature": config.llm_temperature if config else 0.0},
            context_providers=_context_providers,
        )

        # Enable detailed error messages in verbose mode
        if session and session.get_metadata().verbose:
            fic = getattr(
                self.agent.client,
                "function_invocation_configuration",
                None,
            )
            if fic is not None:
                fic["include_detailed_errors"] = True

        # Wrap with Bedrock response format support if needed
        wrap_bedrock_chat_client(client.get_client(), client.get_provider())

    def reload_skills(self) -> int:
        """Re-scan skills from disk and hot-patch agent instructions.

        Re-reads all skill directories, re-renders the Jinja2 prompt template
        with the updated skills list, and patches the live ChatAgent's
        instructions. The conversation thread is preserved.

        Returns:
            Number of skills found after reload.
        """
        if not self._render_instructions or not self._instructions_source:
            logger.debug(
                f"[BaseAgent::{self.name}] Skipping reload: "
                "render_instructions disabled or no template source"
            )
            return 0

        # Re-scan skills from all loaders
        _skills: list = []
        for loader in self._skill_loaders:
            loader.skills = loader.load_skills()
            _skills.extend(loader.skills)

        # Re-render the prompt template with updated skills
        template = Template(self._instructions_source)
        render_ctx = dict(self._render_context)
        render_ctx["skills"] = _skills
        if self._agent_info:
            render_ctx["agent_info"] = self._agent_info
        new_instructions = template.render(**render_ctx)

        # Hot-patch the live ChatAgent instructions
        self.agent.default_options["instructions"] = new_instructions
        logger.info(
            f"[BaseAgent::{self.name}] Reloaded skills. "
            f"Found {len(_skills)} skills. Instructions updated."
        )

        return len(_skills)

    async def cleanup(self):
        """Clean up MCP tool connections."""
        for mcp_tool in self.mcp_tools:
            if hasattr(mcp_tool, "close"):
                try:
                    await mcp_tool.close()
                except (OSError, RuntimeError):
                    pass  # Ignore cleanup errors

    def load_prompt_template(self) -> str:
        """Load the agent's prompt template from a markdown file."""
        package_dir = Path(__file__).parent.parent
        prompt_template = package_dir / "agents" / "prompt_template.md"
        with open(prompt_template, encoding="utf-8") as file:
            content = file.read()
        return content

    def load_custom_instructions(self):
        """Load custom instructions for the agent from a YAML file."""
        try:
            if self.config is None:
                return None
            if self.config.custom_instructions_dir is None:
                return None
            prompt_file = (
                f"{self.config.custom_instructions_dir}/{self.name}/instructions.md"
            )
            with open(prompt_file, encoding="utf-8") as file:
                content = file.read()
                return content
        except (OSError, FileNotFoundError, IsADirectoryError, PermissionError) as e:
            logger.warning(
                f"BaseAgent::load_custom_instructions:: Error loading custom instructions for agent {self.name}: {e}"
            )
            return None

    def load_soul(self) -> str | None:
        """Load SOUL.md for personality/tone configuration from the config directory."""
        try:
            from aletheia.config import get_config_dir

            soul_file = get_config_dir() / "SOUL.md"
            if soul_file.exists():
                with open(soul_file, encoding="utf-8") as file:
                    return file.read()
            return None
        except (OSError, FileNotFoundError, PermissionError):
            return None
