"""
Command-line interface for Aletheia.

Main entry point for the Aletheia CLI application.
"""

import asyncio
import getpass
import json
import os
import random
import shutil
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

import typer
from agent_framework import (
    AgentThread,
    ChatMessage,
    Role,
    TextContent,
    UsageContent,
    UsageDetails,
)
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import FormattedText
from rich.live import Live
from rich.markdown import Markdown
from rich.table import Table

# from agent_framework.observability import setup_observability
from aletheia import __version__
from aletheia.agents.aws.aws import AWSAgent
from aletheia.agents.aws_amp.amp_prometheus import AWSAMPAgent
from aletheia.agents.azure.azure import AzureAgent
from aletheia.agents.base import BaseAgent
from aletheia.agents.code_analyzer.code_analyzer import CodeAnalyzer
from aletheia.agents.entrypoint import Orchestrator
from aletheia.agents.instructions_loader import Loader
from aletheia.agents.kubernetes_data_fetcher.kubernetes_data_fetcher import (
    KubernetesDataFetcher,
)
from aletheia.agents.loader import load_user_agents
from aletheia.agents.log_file_data_fetcher.log_file_data_fetcher import (
    LogFileDataFetcher,
)
from aletheia.agents.model import AgentResponse, Timeline
from aletheia.agents.network.network import NetworkAgent
from aletheia.agents.pcap_file_data_fetcher.pcap_file_data_fetcher import (
    PCAPFileDataFetcher,
)
from aletheia.agents.security.security import SecurityAgent
from aletheia.agents.sysdiag.sysdiag import SysDiagAgent
from aletheia.agents.timeline.timeline_agent import TimelineAgent
from aletheia.commands import COMMANDS, AgentsInfo, expand_custom_command
from aletheia.completion import CommandCompleter
from aletheia.config import Config, get_config_dir, load_config
from aletheia.console import get_console_wrapper
from aletheia.encryption import DecryptionError, decrypt_file
from aletheia.engram.tools import Engram
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session, SessionNotFoundError
from aletheia.utils import enable_trace_logging, set_verbose_commands
from aletheia.utils.logging import log_debug

THINKING_MESSAGES = [
    "🕺 Galavanting...",
    "🧠 Confabulating...",
    "🫣 Unhiding...",
    "🧶 Byte-braiding...",
    "😌 Panic-taming...",
    "🚶‍♂️ Perambulating...",
    "🔮 Divining...",
    "🕵️‍♀️ Unconcealing...",
    "📏 Metric-massaging...",
    "🦘 Log-leaping...",
    "📡 Packet-probing...",
    "⛏️ Metric-mining...",
    "🤠 Log-lassoing...",
    "🧭 Trace-traversing...",
    "⚓ Data-dredging...",
    "🚀 Warming up the stream...",
    "🤔 Thinking deep thoughts...",
    "✨ Summoning Markdown magic...",
    "🧠 Crunching ideas...",
    "📡 Connecting to the source...",
    "🧵 Weaving words together...",
    "🔮 Consulting the language spirits...",
    "⚙️ Calibrating cleverness...",
    "📖 Turning pages of possibility...",
    "💫 Spinning semantic silk...",
    "🪄 Casting formatting spells...",
    "🔍 Inspecting thought packets...",
    "🧩 Reassembling syntax fragments...",
    "🌩️ Charging the neural flux...",
    "🎭 Rehearsing replies...",
    "💡 Illuminating markdown mysteries...",
    "📈 Optimizing verbosity coefficients...",
    "🛰️ Aligning thought satellites...",
]


def banner_callback():
    """Show banner on app start."""
    show_banner()


app = typer.Typer(
    name="aletheia",
    help="AI-powered troubleshooting tool for SREs",
    add_completion=False,
    callback=banner_callback,
)

session_app = typer.Typer(
    name="session",
    help="Manage troubleshooting sessions",
)

knowledge_app = typer.Typer(
    name="knowledge",
    help="Manage knowledge base",
)

telegram_app = typer.Typer(
    name="telegram",
    help="Telegram bot server commands",
)

app.add_typer(session_app, name="session")
app.add_typer(knowledge_app, name="knowledge")
app.add_typer(telegram_app, name="telegram")


console = get_console_wrapper().get_console()

THINKING_INTERVAL = 2.0  # seconds

# setup_observability()


def _build_plugins(
    config: Config,
    prompt_loader: Loader,
    session: Session,
    scratchpad: Scratchpad,
    additional_middleware=None,
    engram: Engram | None = None,
) -> tuple[list[BaseAgent], list[BaseAgent]]:
    """Build and return the list of available agent plugins.

    Args:
        additional_middleware: Optional middleware to add to all agents

    Returns:
        Tuple of (tool_list, agent_instances) where tool_list contains the tools for orchestrator
        and agent_instances contains actual agent objects for cleanup.
    """
    # Currently, plugins are built directly in the _start_investigation function.
    # This function can be expanded in the future to dynamically load plugins.

    plugins = []
    agent_instances = []

    kubernetes_fetcher = KubernetesDataFetcher(
        name="kubernetes_data_fetcher",
        config=config,
        description="Kubernetes Data Fetcher Agent for collecting Kubernetes logs and pod information.",
        session=session,
        scratchpad=scratchpad,
        additional_middleware=additional_middleware,
        engram=engram,
    )
    agent_instances.append(kubernetes_fetcher)
    plugins.append(kubernetes_fetcher.agent.as_tool())

    log_file_fetcher = LogFileDataFetcher(
        name="log_file_data_fetcher",
        config=config,
        description="Log File Data Fetcher Agent for collecting logs from log files.",
        session=session,
        scratchpad=scratchpad,
        additional_middleware=additional_middleware,
        engram=engram,
    )
    agent_instances.append(log_file_fetcher)
    plugins.append(log_file_fetcher.agent.as_tool())

    sysdiag_agent = SysDiagAgent(
        name="sysdiag",
        config=config,
        description="SysDiag Agent for system diagnostics and troubleshooting.",
        session=session,
        scratchpad=scratchpad,
        additional_middleware=additional_middleware,
        engram=engram,
    )
    agent_instances.append(sysdiag_agent)
    plugins.append(sysdiag_agent.agent.as_tool())

    pcap_file_fetcher = PCAPFileDataFetcher(
        name="pcap_file_data_fetcher",
        config=config,
        description="PCAP File Data Fetcher Agent for collecting packets from PCAP files.",
        session=session,
        scratchpad=scratchpad,
        additional_middleware=additional_middleware,
        engram=engram,
    )
    agent_instances.append(pcap_file_fetcher)
    plugins.append(pcap_file_fetcher.agent.as_tool())

    aws_amp_agent = AWSAMPAgent(
        name="aws_amp",
        config=config,
        description="AWS Managed Prometheus Agent for fetching AWS Managed Prometheus related data.",
        session=session,
        scratchpad=scratchpad,
        additional_middleware=additional_middleware,
        engram=engram,
    )
    agent_instances.append(aws_amp_agent)
    plugins.append(aws_amp_agent.agent.as_tool())

    aws_agent = AWSAgent(
        name="aws",
        config=config,
        description="AWS Agent for fetching AWS related data using AWS CLI.",
        session=session,
        scratchpad=scratchpad,
        additional_middleware=additional_middleware,
        engram=engram,
    )
    agent_instances.append(aws_agent)
    plugins.append(aws_agent.agent.as_tool())

    azure_agent = AzureAgent(
        name="azure",
        config=config,
        description="Azure Agent for fetching Azure related data using Azure CLI.",
        session=session,
        scratchpad=scratchpad,
        additional_middleware=additional_middleware,
        engram=engram,
    )
    agent_instances.append(azure_agent)
    plugins.append(azure_agent.agent.as_tool())

    network_agent = NetworkAgent(
        name="network",
        config=config,
        description="Network Agent for fetching TCP Network related data.",
        session=session,
        scratchpad=scratchpad,
        additional_middleware=additional_middleware,
        engram=engram,
    )
    agent_instances.append(network_agent)
    plugins.append(network_agent.agent.as_tool())

    security_agent = SecurityAgent(
        name="security",
        config=config,
        description="Security Agent for performing security testing and analysis.",
        session=session,
        scratchpad=scratchpad,
        additional_middleware=additional_middleware,
        engram=engram,
    )
    plugins.append(security_agent.agent.as_tool())

    if config.code_analyzer is not None and config.code_analyzer.strip() != "":
        code_analyzer = CodeAnalyzer(
            name=f"{config.code_analyzer}_code_analyzer",
            config=config,
            description="Claude Code Analyzer Agent for analyzing code repositories using Claude.",
            instructions=prompt_loader.load(
                "code_analyzer", "instructions", prefix=config.code_analyzer.lower()
            ),
            session=session,
            scratchpad=scratchpad,
            additional_middleware=additional_middleware,
            engram=engram,
        )
        agent_instances.append(code_analyzer)
        plugins.append(code_analyzer.agent.as_tool())

    # Load user-defined agents
    if config.user_agents_enabled:
        user_tools, user_instances = load_user_agents(
            agents_directory=config.user_agents_directory,
            config=config,
            session=session,
            scratchpad=scratchpad,
            additional_middleware=additional_middleware,
            engram=engram,
        )
        plugins.extend(user_tools)
        agent_instances.extend(user_instances)

    # Filter out disabled agents
    if config.disabled_agents:
        plugins = [p for p in plugins if p.name not in config.disabled_agents]

    COMMANDS["agents"] = AgentsInfo(agents=plugins)

    return plugins, agent_instances


async def show_thinking_animation(live, stop_event):
    """Show thinking animation until stop_event is set."""
    while not stop_event.is_set():
        msg = random.choice(THINKING_MESSAGES)
        md = f"[grey82 i]{msg}[/grey82 i]"
        live.update(md)
        await asyncio.sleep(1)


async def init_orchestrator(
    session: Session, config: Config, engram: Engram | None = None
) -> Orchestrator:
    """Initialize orchestrator for a session.

    This is a reusable function for CLI, Telegram, and API modes.

    Args:
        session: Active session
        config: Aletheia configuration
        engram: Optional Engram memory instance

    Returns:
        Initialized Orchestrator instance with thread
    """
    prompt_loader = Loader()

    # Initialize scratchpad with session directory and encryption key
    scratchpad = Scratchpad(
        session_dir=session.session_path, encryption_key=session.get_key()
    )
    session.scratchpad = scratchpad

    # Build plugins
    tools, agent_instances = _build_plugins(
        config=config,
        prompt_loader=prompt_loader,
        session=session,
        scratchpad=scratchpad,
        engram=engram,
    )

    # Create orchestrator
    orchestrator = Orchestrator(
        name="orchestrator",
        description="Orchestrator agent managing the investigation workflow",
        instructions=prompt_loader.load("orchestrator", "instructions"),
        session=session,
        sub_agents=tools,
        scratchpad=scratchpad,
        config=config,
        engram=engram,
    )

    # Initialize thread
    orchestrator.thread = orchestrator.agent.get_new_thread()

    # Store for cleanup
    orchestrator.sub_agent_instances = agent_instances

    return orchestrator


async def _start_investigation(
    session: Session, enable_memory: bool = True
) -> None:
    """
    Start the investigation workflow for a session.

    Args:
        session: Active session to investigate
        enable_memory: Whether to enable Engram memory
    """

    engram_instance: Engram | None = None
    try:
        # Load configuration
        config = load_config()

        # Initialize Engram memory
        if enable_memory:
            engram_instance = Engram(identity=str(get_config_dir()))
            engram_instance.start_watcher()

        # Initialize orchestrator using helper function
        entry = await init_orchestrator(session, config, engram=engram_instance)

        chatting = True

        completion_usage = UsageDetails()

        thread: AgentThread = entry.thread

        # Initialize prompt_toolkit session with command completion
        completer = CommandCompleter(config)
        prompt_session: PromptSession[str] = PromptSession(
            completer=completer,
            complete_while_typing=True,
        )

        try:
            while chatting:
                console.print("[cyan]" + "─" * console.width + "[/cyan]")
                console.print(
                    "[i cyan]You can ask questions about the investigation or type 'exit' to end the session. Type '/help' for help.[/i cyan]\n"
                )

                # Use prompt_toolkit for input with command completion
                # Use formatted text for colored prompt
                prompt_formatted = FormattedText(
                    [
                        ("", "\n["),
                        ("bold ansiyellow", session.session_id),
                        ("", "] "),
                        ("bold ansigreen", "👤 YOU"),
                        ("", " "),
                    ]
                )

                user_input = await prompt_session.prompt_async(prompt_formatted)

                # Skip empty input
                if not user_input or not user_input.strip():
                    continue

                if user_input.lower() in ["exit", "quit"]:
                    chatting = False
                    console.print("\n[cyan]Ending the investigation session.[/cyan]\n")
                    break
                elif user_input.strip().startswith("/"):
                    # Try to expand custom command first
                    expanded_message, was_expanded = expand_custom_command(
                        user_input, config
                    )

                    if was_expanded:
                        # Custom command was expanded, use the expanded message for chat
                        user_input = expanded_message
                    else:
                        # Not a custom command, check if it's a built-in command
                        command = user_input.strip()[1:]
                        if command in COMMANDS:
                            COMMANDS[command].execute(
                                console,
                                completion_usage=completion_usage,
                                config=config,
                            )
                            continue

                # Start thinking animation in a background thread
                stop_event = asyncio.Event()

                full_response = ""
                try:
                    # Print header with horizontal line ONCE at the start
                    console.print(
                        f"\n[[bold yellow]{session.session_id}[/bold yellow]] [bold cyan]🤖 Aletheia[/bold cyan]"
                    )
                    console.print("[cyan]" + "─" * 80 + "[/cyan]")

                    json_buffer = ""
                    current_agent_name = "Orchestrator"  # Default
                    parsed_response = None
                    parsed_successfully = False  # Track if JSON parsing ever succeeded

                    with Live("", console=console, refresh_per_second=5) as live:
                        _ = asyncio.create_task(
                            show_thinking_animation(live, stop_event)
                        )

                        async for response in entry.agent.run_stream(
                            messages=[
                                ChatMessage(
                                    role="user", contents=[TextContent(text=user_input)]
                                )
                            ],
                            thread=thread,
                            response_format=AgentResponse,
                        ):
                            if response and str(response.text) != "":
                                if not stop_event.is_set():
                                    stop_event.set()
                                    await asyncio.sleep(
                                        0.1
                                    )  # Give animation time to stop

                                full_response += str(response.text)
                                json_buffer += response.text

                                # Try to parse as structured JSON
                                try:
                                    # First try direct parsing (works for Sonnet)
                                    parsed_response = json.loads(json_buffer)
                                    parsed_successfully = True  # Mark successful parse
                                except json.JSONDecodeError:
                                    # If that fails, try to extract JSON from mixed content (for Haiku)
                                    try:
                                        import re

                                        # Look for JSON object in the buffer (handles text before/after JSON)
                                        json_match = re.search(
                                            r"\{.*\}", json_buffer, re.DOTALL
                                        )
                                        if json_match:
                                            parsed_response = json.loads(
                                                json_match.group(0)
                                            )
                                            parsed_successfully = True
                                        else:
                                            # No JSON found yet, continue buffering
                                            raise json.JSONDecodeError(
                                                "No JSON found", json_buffer, 0
                                            )
                                    except (json.JSONDecodeError, AttributeError):
                                        # Not yet complete JSON, continue buffering
                                        parsed_response = None

                                # Only process if we successfully parsed
                                if parsed_response is not None:
                                    parsed_successfully = True  # Mark successful parse
                                    # Successfully parsed structured response
                                    display_parts = []

                                    # Agent and confidence
                                    if "agent" in parsed_response:
                                        current_agent_name = parsed_response["agent"]
                                    if "confidence" in parsed_response:
                                        confidence_pct = int(
                                            parsed_response["confidence"] * 100
                                        )
                                        display_parts.append(
                                            f"**Agent:** {current_agent_name} | **Confidence:** {confidence_pct}%\n"
                                        )
                                    else:
                                        display_parts.append(
                                            f"**Agent:** {current_agent_name}\n"
                                        )

                                    # Findings
                                    if "findings" in parsed_response:
                                        findings = parsed_response["findings"]
                                        display_parts.append("\n## 🔍 Findings\n")
                                        if (
                                            "summary" in findings
                                            and findings["summary"]
                                        ):
                                            display_parts.append(
                                                f"**Summary:** {findings['summary']}\n\n"
                                            )
                                        if (
                                            "details" in findings
                                            and findings["details"]
                                        ):
                                            display_parts.append(
                                                f"{findings['details']}\n\n"
                                            )
                                        if (
                                            "tool_outputs" in findings
                                            and findings["tool_outputs"]
                                        ):
                                            display_parts.append("**Tool Outputs:**\n")
                                            for tool_output in findings["tool_outputs"]:
                                                display_parts.append(
                                                    f"\n*{tool_output['tool_name']}*\n"
                                                )
                                                display_parts.append(
                                                    f"Command: `{tool_output['command']}`\n"
                                                )
                                                display_parts.append(
                                                    f"```\n{tool_output['output']}\n```\n"
                                                )
                                        if (
                                            "additional_output" in findings
                                            and findings["additional_output"]
                                        ):
                                            display_parts.append(
                                                f"**Additional Output:**\n{findings['additional_output']}\n\n"
                                            )

                                    # Decisions
                                    if "decisions" in parsed_response:
                                        decisions = parsed_response["decisions"]
                                        display_parts.append("\n## 🎯 Decisions\n")
                                        if (
                                            "approach" in decisions
                                            and decisions["approach"]
                                        ):
                                            display_parts.append(
                                                f"**Approach:** {decisions['approach']}\n\n"
                                            )
                                        if (
                                            "tools_used" in decisions
                                            and decisions["tools_used"]
                                        ):
                                            display_parts.append(
                                                f"**Tools Used:** {', '.join(decisions['tools_used'])}\n\n"
                                            )
                                        if (
                                            "skills_loaded" in decisions
                                            and decisions["skills_loaded"]
                                        ):
                                            display_parts.append(
                                                f"**Skills Loaded:** {', '.join(decisions['skills_loaded'])}\n\n"
                                            )
                                        if (
                                            "rationale" in decisions
                                            and decisions["rationale"]
                                        ):
                                            display_parts.append(
                                                f"**Rationale:** {decisions['rationale']}\n\n"
                                            )
                                        if (
                                            "checklist" in decisions
                                            and decisions["checklist"]
                                        ):
                                            display_parts.append("**Checklist:**\n")
                                            for item in decisions["checklist"]:
                                                display_parts.append(f"- {item}\n")
                                            display_parts.append("\n")
                                        if (
                                            "additional_output" in decisions
                                            and decisions["additional_output"]
                                        ):
                                            display_parts.append(
                                                f"**Additional Output:**\n{decisions['additional_output']}\n\n"
                                            )

                                    # Next Actions
                                    if "next_actions" in parsed_response:
                                        next_actions = parsed_response["next_actions"]
                                        display_parts.append("\n## 📋 Next Actions\n")
                                        if (
                                            "steps" in next_actions
                                            and next_actions["steps"]
                                        ):
                                            for i, step in enumerate(
                                                next_actions["steps"], 1
                                            ):
                                                display_parts.append(f"{i}. {step}\n")
                                            display_parts.append("\n")
                                        if (
                                            "additional_output" in next_actions
                                            and next_actions["additional_output"]
                                        ):
                                            display_parts.append(
                                                f"**Additional Output:**\n{next_actions['additional_output']}\n\n"
                                            )

                                    # Errors
                                    if (
                                        "errors" in parsed_response
                                        and parsed_response["errors"]
                                    ):
                                        display_parts.append("\n## ⚠️ Errors\n")
                                        for error in parsed_response["errors"]:
                                            display_parts.append(f"- {error}\n")
                                        display_parts.append("\n")

                                    display_text = "".join(display_parts)
                                    live.update(Markdown(display_text))

                            if response and response.contents:
                                for content in response.contents:
                                    if isinstance(content, UsageContent):
                                        completion_usage += content.details

                    # Fallback: If JSON parsing never succeeded, render raw buffer
                    if not parsed_successfully and json_buffer and json_buffer.strip():
                        console.print(
                            "\n[yellow]⚠️ Structured parsing failed, showing raw response:[/yellow]\n"
                        )
                        # Try to extract text content from partial JSON or render as-is
                        fallback_text = json_buffer
                        # If it looks like JSON, try to extract string values
                        if json_buffer.strip().startswith("{"):
                            try:
                                # Attempt to extract readable text from partial JSON
                                import re

                                # Extract text from string fields
                                text_matches = re.findall(
                                    r'"(?:summary|details|approach|rationale)":\s*"([^"]*)"',
                                    json_buffer,
                                )
                                if text_matches:
                                    fallback_text = "\n\n".join(text_matches)
                            except Exception:
                                pass  # Use raw buffer if extraction fails
                        console.print(Markdown(fallback_text))

                    log_debug(f"complete response:{json_buffer}")
                    # Print final usage for this turn
                    if completion_usage:
                        console.print(
                            f"_[dim]Usage: {completion_usage.total_token_count} (In: {completion_usage.input_token_count}, Out: {completion_usage.output_token_count})[/dim]_",
                            style="dim",
                        )

                finally:
                    if stop_event and not stop_event.is_set():
                        stop_event.set()
        finally:
            # Clean up agent resources before exiting
            try:
                await entry.cleanup()
            except Exception:
                pass  # Ignore cleanup errors

            # Clean up all sub-agents
            for agent in getattr(entry, "sub_agent_instances", []):
                try:
                    await agent.cleanup()
                except Exception:
                    pass  # Ignore cleanup errors

        # evaluate total session cost
        COMMANDS["cost"].execute(
            console, completion_usage=completion_usage, config=config
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]Investigation interrupted. Session saved.[/yellow]")
        # Save scratchpad before exiting
        if session.scratchpad:
            session.scratchpad.save()
    except Exception as e:
        console.print(f"[red]Error during investigation: {e}[/red]")
        typer.echo(f"Error: {e}", err=True)
        # Print full traceback for debugging
        import traceback

        traceback.print_exc()
        raise typer.Exit(1)
    finally:
        if engram_instance is not None:
            engram_instance.stop_watcher()


def safe_md(s: str) -> str:
    """Ensure that Markdown code fences are properly closed."""
    fences = s.count("```")
    return s + ("\n```" if fences % 2 else "")


@app.command()
def version() -> None:
    """Display the version of Aletheia."""
    typer.echo(f"Aletheia version {__version__}")


@session_app.command("open")
def session_open(
    name: str | None = typer.Option(None, "--name", "-n", help="Session name"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show all external commands and their output"
    ),
    very_verbose: bool = typer.Option(
        False,
        "--very-verbose",
        "-vv",
        help="Enable trace logging with prompts, commands, and full details",
    ),
    unsafe: bool = typer.Option(
        False,
        "--unsafe",
        help="Use plaintext storage (skips encryption - NOT RECOMMENDED)",
    ),
    enable_memory: bool = typer.Option(
        True,
        "--enable-memory/--disable-memory",
        help="Enable or disable Engram memory",
    ),
) -> None:
    """Open a new troubleshooting session in conversational mode."""
    # Enable very-verbose mode (implies verbose)
    if very_verbose:
        verbose = True

    # Enable verbose command output if requested
    if verbose:
        set_verbose_commands(True)
        console.print(
            "[dim]Verbose mode enabled - all external commands will be shown[/dim]\n"
        )

    if very_verbose:
        console.print(
            "[dim]Very-verbose mode (-vv) enabled - full trace logging with prompts and details[/dim]\n"
        )

    # Warn about unsafe mode
    if unsafe:
        console.print(
            "[bold red]⚠️  WARNING: --unsafe mode enabled - data will be stored in PLAINTEXT without encryption![/bold red]"
        )
        console.print(
            "[red]This mode should ONLY be used for testing purposes.[/red]\n"
        )

    # Get password (skip in unsafe mode)
    password = None
    if not unsafe:
        password = getpass.getpass("Enter password: ")
        if not password:
            typer.echo("Error: Password cannot be empty", err=True)
            raise typer.Exit(1)

        # Confirm password
        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            typer.echo("Error: Passwords do not match", err=True)
            raise typer.Exit(1)

    try:
        session = Session.create(
            name=name,
            password=password,
            verbose=very_verbose,
            unsafe=unsafe,
        )

        # Enable trace logging if very-verbose mode
        # Enable trace logging if very-verbose mode
        if very_verbose:
            console.print(
                f"[dim]Trace log: {session.session_path / 'aletheia_trace.log'}[/dim]\n"
            )

        console.print(
            f"[green]Session '{session.session_id}' created successfully![/green]"
        )
        console.print(f"Session ID: {session.session_id}")

        # Start investigation workflow
        asyncio.run(_start_investigation(session, enable_memory=enable_memory))

    except FileExistsError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error creating session: {e}", err=True)
        raise typer.Exit(1)


@session_app.command("list")
def session_list() -> None:
    """List all troubleshooting sessions."""
    try:
        sessions = Session.list_sessions()

        if not sessions:
            console.print("[yellow]No sessions found[/yellow]")
            return

        console.print()
        table = Table(title="Aletheia Sessions")
        table.add_column("Session ID", style="magenta")
        table.add_column("Name", style="green")
        table.add_column("Created", style="yellow")
        table.add_column("Path", style="cyan")
        table.add_column("Unsafe", style="cyan")

        for session_data in sessions:
            table.add_row(
                session_data["id"],
                session_data.get("name") or "",
                session_data["created"],
                session_data["path"],
                str(session_data["unsafe"]),
            )

        console.print(table)
    except Exception as e:
        typer.echo(f"Error listing sessions: {e}", err=True)
        raise typer.Exit(1)


@session_app.command("delete")
def session_delete(
    session_id: str = typer.Argument(..., help="Session ID to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Delete a troubleshooting session."""
    if not yes:
        confirm = typer.confirm(
            f"Are you sure you want to delete session '{session_id}'?"
        )
        if not confirm:
            console.print("[yellow]Deletion cancelled[/yellow]")
            return

    try:
        # Directly construct Session and call delete
        session = Session(session_id=session_id)
        session.delete()
        console.print(f"[green]Session '{session_id}' deleted successfully![/green]")
    except SessionNotFoundError as exc:
        typer.echo(f"Error: Session '{session_id}' not found", err=True)
        raise typer.Exit(1) from exc
    except Exception as e:
        typer.echo(f"Error deleting session: {e}", err=True)
        raise typer.Exit(1)


@session_app.command("resume")
def session_resume(
    session_id: str = typer.Argument(..., help="Session ID to resume"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show all external commands and their output"
    ),
    very_verbose: bool = typer.Option(
        False,
        "--very-verbose",
        "-vv",
        help="Enable trace logging with prompts, commands, and full details",
    ),
    unsafe: bool = typer.Option(
        False, "--unsafe", help="Session uses plaintext storage (skips encryption)"
    ),
    enable_memory: bool = typer.Option(
        True,
        "--enable-memory/--disable-memory",
        help="Enable or disable Engram memory",
    ),
) -> None:
    """Resume an existing troubleshooting session."""
    # Enable very-verbose mode (implies verbose)
    if very_verbose:
        verbose = True

    # Enable verbose command output if requested
    if verbose:
        set_verbose_commands(True)
        console.print(
            "[dim]Verbose mode enabled - all external commands will be shown[/dim]\n"
        )

    if very_verbose:
        console.print(
            "[dim]Very-verbose mode (-vv) enabled - full trace logging with prompts and details[/dim]\n"
        )

    # Warn about unsafe mode
    if unsafe:
        console.print(
            "[bold red]⚠️  WARNING: --unsafe mode enabled - session uses PLAINTEXT storage![/bold red]\n"
        )

    # Get password (skip in unsafe mode)
    password = None
    if not unsafe:
        password = getpass.getpass("Enter session password: ")
        if not password:
            typer.echo("Error: Password cannot be empty", err=True)
            raise typer.Exit(1)

    try:
        session = Session.resume(
            session_id=session_id, password=password, unsafe=unsafe
        )

        # Enable trace logging if very-verbose mode
        if very_verbose:
            enable_trace_logging(session.session_path)
            console.print(
                f"[dim]Trace log: {session.session_path / 'aletheia_trace.log'}[/dim]\n"
            )

        console.print(
            f"[green]Session '{session.session_id}' resumed successfully![/green]"
        )
        console.print(f"Session ID: {session.session_id}")

        # Start investigation workflow
        asyncio.run(_start_investigation(session, enable_memory=enable_memory))

    except SessionNotFoundError as exc:
        typer.echo(f"Error: Session '{session_id}' not found", err=True)
        raise typer.Exit(1) from exc
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error resuming session: {e}", err=True)
        raise typer.Exit(1)


@session_app.command("timeline")
def session_timeline(
    session_id: str = typer.Argument(..., help="Session ID to export"),
    unsafe: bool = typer.Option(
        False, "--unsafe", help="Session uses plaintext storage (skips encryption)"
    ),
) -> None:
    """prints a session timeline"""
    # Warn about unsafe mode
    if unsafe:
        console.print(
            "[bold red]⚠️  WARNING: --unsafe mode enabled - session uses PLAINTEXT storage![/bold red]\n"
        )

    # Get password (skip in unsafe mode)
    password = None
    if not unsafe:
        password = getpass.getpass("Enter session password: ")
        if not password:
            typer.echo("Error: Password cannot be empty", err=True)
            raise typer.Exit(1)

    try:
        # Load configuration
        # Resume session to access metadata
        session = Session.resume(
            session_id=session_id, password=password, unsafe=unsafe
        )

        # Load scratchpad
        scratchpad_file = session.scratchpad_file
        if not scratchpad_file.exists():
            console.print("[yellow]No scratchpad data found for this session[/yellow]")
            return

        scratchpad = Scratchpad(
            session_dir=session.session_path, encryption_key=session.get_key()
        )

        # Display scratchpad contents (raw journal)
        journal_content = scratchpad.read_scratchpad()

        prompt_loader = Loader()

        timeline_agent = TimelineAgent(
            name="timeline_agent",
            instructions=prompt_loader.load("timeline", "json_instructions"),
            description="Timeline Agent for generating session timeline",
        )

        message = ChatMessage(
            role=Role.USER,
            contents=[TextContent(text=f"""
                                       Generate a timeline of the following troubleshooting session scratchpad data:\n\n{journal_content}\n\n
                                       """)],
        )
        response = asyncio.run(
            timeline_agent.agent.run(message, response_format=Timeline)
        )

        if response:
            try:
                timeline_data = json.loads(str(response.text))

                table = Table(title=f"Session Timeline: {session_id}")
                table.add_column("Time", style="cyan", no_wrap=True)
                table.add_column("Type", style="magenta")
                table.add_column("Content", style="white")

                # Handle both Timeline model format and legacy format
                entries = (
                    timeline_data.get("entries", timeline_data)
                    if isinstance(timeline_data, dict)
                    else timeline_data
                )

                for event in entries:
                    timestamp = event.get("timestamp", "")
                    # Support both 'entry_type' (TimelineEntry model) and 'type' (legacy)
                    event_type = event.get("entry_type", event.get("type", "INFO"))
                    # Support both 'content' (TimelineEntry model) and 'description' (legacy)
                    content = event.get("content", event.get("description", ""))

                    # Color code types
                    type_style = (
                        "green"
                        if event_type.upper() == "ACTION"
                        else (
                            "yellow"
                            if event_type.upper() == "OBSERVATION"
                            else "blue" if event_type.upper() == "DECISION" else "white"
                        )
                    )

                    table.add_row(
                        timestamp, f"[{type_style}]{event_type}[/{type_style}]", content
                    )

                console.print(table)

            except json.JSONDecodeError:
                console.print(f"\n{response.text}\n")

    except FileNotFoundError as fne:
        typer.echo(f"Error: Session '{session_id}' not found {fne}", err=True)
        raise typer.Exit(1)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error exporting session: {e}", err=True)
        raise typer.Exit(1)


@session_app.command("export")
def session_export(
    session_id: str = typer.Argument(..., help="Session ID to export"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file path"),
    unsafe: bool = typer.Option(
        False, "--unsafe", help="Session uses plaintext storage (skips encryption)"
    ),
) -> None:
    """Export a troubleshooting session."""
    # Warn about unsafe mode
    if unsafe:
        console.print(
            "[bold red]⚠️  WARNING: --unsafe mode enabled - session uses PLAINTEXT storage![/bold red]\n"
        )

    # Get password (skip in unsafe mode)
    password = None
    if not unsafe:
        password = getpass.getpass("Enter session password: ")
        if not password:
            typer.echo("Error: Password cannot be empty", err=True)
            raise typer.Exit(1)

    try:
        session = Session.resume(
            session_id=session_id, password=password, unsafe=unsafe
        )
        session_dir = session.session_path

        # Prepare output zip path
        zip_name = f"{session_id}.zip"
        export_path = output or Path(zip_name)

        # Create a temporary directory to hold decrypted files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            # Copy all files from session_dir to tmpdir, decrypting if needed
            key = session.get_key() if not unsafe else None
            for root, _, files in os.walk(session_dir):
                rel_root = Path(root).relative_to(session_dir)
                for file in files:
                    src_file = Path(root) / file
                    rel_file = rel_root / file
                    dest_file = tmpdir_path / rel_file
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    # Decrypt all files if encrypted session
                    if key:
                        # Try to decrypt, if fails fallback to copy
                        try:
                            decrypt_file(src_file, key, dest_file)
                        except (OSError, DecryptionError):
                            shutil.copy2(src_file, dest_file)
                    else:
                        shutil.copy2(src_file, dest_file)

            # Create zip file from tmpdir
            with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for foldername, _, filenames in os.walk(tmpdir_path):
                    for filename in filenames:
                        file_path = Path(foldername) / filename
                        arcname = file_path.relative_to(tmpdir_path)
                        zipf.write(file_path, arcname)

        console.print("[green]Session exported successfully![/green]")
        console.print(f"Export file: {export_path}")
    except FileNotFoundError as exc:
        typer.echo(f"Error: Session '{session_id}' not found", err=True)
        raise typer.Exit(1) from exc
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e
    except Exception as e:
        typer.echo(f"Error exporting session: {e}", err=True)
        raise typer.Exit(1) from e


@session_app.command("view")
def session_view(
    session_id: str = typer.Argument(..., help="Session ID to view"),
    unsafe: bool = typer.Option(
        False, "--unsafe", help="Session uses plaintext storage (skips encryption)"
    ),
) -> None:
    """View scratchpad contents of a session, and list files in the data directory."""
    # Warn about unsafe mode
    if unsafe:
        console.print(
            "[bold red]⚠️  WARNING: --unsafe mode enabled - session uses PLAINTEXT storage![/bold red]\n"
        )
    password = None
    if not unsafe:
        password = getpass.getpass("Enter session password: ")
        if not password:
            typer.echo("Error: Password cannot be empty", err=True)
            raise typer.Exit(1)

    try:
        # Resume session to access metadata
        session = Session.resume(
            session_id=session_id, password=password, unsafe=unsafe
        )
        metadata = session.get_metadata()

        # Load scratchpad
        scratchpad_file = session.scratchpad_file
        if not scratchpad_file.exists():
            console.print("[yellow]No scratchpad data found for this session[/yellow]")
            return

        scratchpad = Scratchpad(
            session_dir=session.session_path, encryption_key=session.get_key()
        )

        # Display metadata
        console.print(
            f"\n[bold cyan]Session: {metadata.name or session_id}[/bold cyan]"
        )
        console.print(f"Status: {metadata.status}")
        console.print(f"Created: {metadata.created}")
        console.print(f"Updated: {metadata.updated}")

        # Display scratchpad contents (raw journal)
        console.print("\n[bold cyan]Scratchpad Contents:[/bold cyan]\n")
        journal_content = scratchpad.read_scratchpad()
        if not journal_content.strip():
            console.print("[dim](Scratchpad is empty)[/dim]")
        else:
            console.print(Markdown(journal_content))

        # List files in the session's data directory (recursively)
        data_dir = session.session_path / "data"
        console.print("\n[bold cyan]Data Directory Files:[/bold cyan]")
        if data_dir.exists() and data_dir.is_dir():
            all_files = []
            for root, _, files in os.walk(data_dir):
                for file in files:
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(data_dir)
                    all_files.append(rel_path)
            if all_files:
                # Build a tree structure for pretty printing
                def tree():
                    return defaultdict(tree)

                file_tree = tree()
                for rel_path in all_files:
                    parts = rel_path.parts
                    node = file_tree
                    for part in parts[:-1]:
                        node = node[part]
                    node[parts[-1]] = None  # File leaf

                def print_tree(node, prefix="", depth=0):
                    for key in sorted(node.keys()):
                        indent = "  " * depth
                        if node[key] is None:
                            console.print(f"{indent}- {key}")
                        else:
                            console.print(f"{indent}- {key}/")
                            print_tree(node[key], prefix + key + "/", depth + 1)

                print_tree(file_tree)
            else:
                console.print("[dim](No files in data directory)[/dim]")
        else:
            console.print("[dim](No data directory found)[/dim]")

    except FileNotFoundError as exc:
        typer.echo(f"Error: Session '{session_id}' not found", err=True)
        raise typer.Exit(1) from exc
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e
    except Exception as e:
        typer.echo(f"Error viewing session: {e}", err=True)
        raise typer.Exit(1) from e


def show_banner() -> None:
    """Display the Aletheia banner."""
    banner_path = os.path.join(os.path.dirname(__file__), "banner.txt")
    try:
        with open(banner_path, encoding="utf-8") as f:
            console.print(f.read())
    except OSError:
        # Ignore file read errors (banner is optional)
        pass


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind the server to"),
    port: int = typer.Option(8000, help="Port to bind the server to"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
    enable_memory: bool = typer.Option(
        True,
        "--enable-memory/--disable-memory",
        help="Enable or disable Engram memory",
    ),
) -> None:
    """Start the Aletheia REST API server."""
    try:
        import uvicorn

        # Pass memory flag to API module
        import aletheia.api as api_module

        api_module.MEMORY_ENABLED = enable_memory

        get_console_wrapper().disable_output_functions()
        console = get_console_wrapper().get_console()

        console.print(
            f"[green]Starting Aletheia API server on http://{host}:{port}[/green]"
        )
        uvicorn.run("aletheia.api:app", host=host, port=port, reload=reload)
    except ImportError:
        console.print(
            "[red]Error: 'uvicorn' not found. Please install it with 'pip install uvicorn'.[/red]"
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error starting server: {e}[/red]")
        raise typer.Exit(1)


@knowledge_app.command("add")
def knowledge_add(
    id: str = typer.Argument(..., help="Document ID"),
    path: str = typer.Argument(..., help="Markdown document path"),
    metadata: str | None = typer.Option(
        None, "--metadata", "-m", help="Metadata as JSON string"
    ),
) -> None:
    """Add a document to the knowledge base."""
    try:
        from aletheia.knowledge import ChromaKnowledge

        knowledge = ChromaKnowledge()

        meta_dict = {}
        if metadata:
            try:
                meta_dict = json.loads(metadata)
            except json.JSONDecodeError as jde:
                console.print(f"[red]Error parsing metadata JSON: {jde}[/red]")
                raise typer.Exit(1)
        meta_dict["source_path"] = path

        log_debug(
            f"Adding document ID '{id}' from path '{path}' with metadata: {meta_dict}"
        )
        knowledge.add_document_from_markdown_file(
            id=id, file_path=path, metadata=meta_dict
        )
        console.print(
            f"[green]Document '{id}' added to knowledge base successfully![/green]"
        )
    except Exception as e:
        console.print(f"[red]Error adding document: {e}[/red]")
        raise typer.Exit(1)


@knowledge_app.command("delete")
def knowledge_delete(
    id: str = typer.Argument(..., help="Document ID to delete"),
) -> None:
    """Delete a document from the knowledge base."""
    try:
        from aletheia.knowledge import ChromaKnowledge

        knowledge = ChromaKnowledge()

        log_debug(f"Deleting document ID '{id}' from knowledge base")
        knowledge.delete_document(id=id)
        console.print(
            f"[green]Document '{id}' deleted from knowledge base successfully![/green]"
        )
    except Exception as e:
        console.print(f"[red]Error deleting document: {e}[/red]")
        raise typer.Exit(1)


@knowledge_app.command("list")
def knowledge_list() -> None:
    """List all documents in the knowledge base."""
    try:
        from aletheia.knowledge import ChromaKnowledge

        knowledge = ChromaKnowledge()

        ids, documents = knowledge.list_documents()
        if not documents:
            console.print("[yellow]No documents found in the knowledge base[/yellow]")
            return

        console.print()
        table = Table(title="Knowledge Base Documents")
        table.add_column("Document ID", style="magenta")
        table.add_column("Content Preview", style="green")

        for i, doc in enumerate(documents):
            id = ids[i]
            preview = (doc[:75] + "...") if len(doc) > 75 else doc
            table.add_row(id, preview)

        console.print(table)
    except Exception as e:
        console.print(f"[red]Error listing documents: {e}[/red]")
        raise typer.Exit(1)


@telegram_app.command("serve")
def telegram_serve(
    token: str = typer.Option(
        None, "--token", help="Bot token (overrides config/env var)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
    enable_memory: bool = typer.Option(
        True,
        "--enable-memory/--disable-memory",
        help="Enable or disable Engram memory",
    ),
) -> None:
    """Start the Telegram bot server with polling.

    The bot will start polling for messages from Telegram users.
    All sessions created via Telegram use unsafe mode (plaintext storage).

    Configuration:
    - Bot token: --token flag, ALETHEIA_TELEGRAM_BOT_TOKEN env var, or config.yaml
    - Allowed users: ALETHEIA_TELEGRAM_ALLOWED_USERS env var or config.yaml

    Security Note: Telegram is not end-to-end encrypted. Messages can be read
    by Telegram server administrators. Use the allowlist to restrict access.
    """
    from aletheia.telegram.bot import run_telegram_bot

    # Print security disclaimer
    console.print("[bold red]⚠️  SECURITY NOTICE[/bold red]")
    console.print(
        "[yellow]Telegram is not encrypted end-to-end. "
        "Your messages can be read by Telegram server administrators. "
        "Avoid sharing sensitive data.[/yellow]\n"
    )

    # Load configuration
    config = load_config()
    bot_token = token or config.telegram_bot_token

    if not bot_token:
        console.print(
            "[red]Error: Bot token not configured.[/red]\n"
            "\nSet the token using one of:\n"
            "  1. --token flag: aletheia telegram serve --token YOUR_TOKEN\n"
            "  2. Environment variable: export ALETHEIA_TELEGRAM_BOT_TOKEN=YOUR_TOKEN\n"
            "  3. Config file: Add 'telegram_bot_token: YOUR_TOKEN' to ~/.config/aletheia/config.yaml"
        )
        raise typer.Exit(1)

    # Check allowlist configuration
    if not config.telegram_allowed_users:
        console.print(
            "[yellow]⚠️  Warning: No allowed users configured.[/yellow]\n"
            "[yellow]All Telegram users can access the bot.[/yellow]\n"
            "\nTo restrict access, set allowed users:\n"
            "  1. Environment variable: export ALETHEIA_TELEGRAM_ALLOWED_USERS=123456789,987654321\n"
            "  2. Config file: Add 'telegram_allowed_users: [123456789, 987654321]' to config.yaml\n"
        )

    console.print("[green]Starting Telegram bot with polling...[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    # Run the bot
    try:
        asyncio.run(run_telegram_bot(bot_token, config, verbose, enable_memory=enable_memory))
    except KeyboardInterrupt:
        console.print("\n[cyan]Bot stopped.[/cyan]")


@telegram_app.command("allowed-users")
def telegram_allowed_users() -> None:
    """Show configured allowed Telegram users.

    Displays the list of Telegram user IDs that are authorized to access the bot.
    If the list is empty, all users can access the bot (not recommended).
    """
    config = load_config()

    if not config.telegram_allowed_users:
        console.print("[yellow]No allowed users configured[/yellow]")
        console.print("\nAll Telegram users can currently access the bot.")
        console.print("\nTo add allowed users:")
        console.print("  1. Edit config.yaml:")
        console.print("     telegram_allowed_users: [123456789, 987654321]")
        console.print("\n  2. Or set environment variable:")
        console.print("     export ALETHEIA_TELEGRAM_ALLOWED_USERS=123456789,987654321")
        console.print("\nTo find your Telegram user ID:")
        console.print("  1. Message @userinfobot on Telegram")
        console.print("  2. The bot will reply with your user ID")
        return

    console.print()
    table = Table(title="Allowed Telegram Users")
    table.add_column("User ID", style="cyan", no_wrap=True)
    table.add_column("Index", style="dim")

    for idx, user_id in enumerate(config.telegram_allowed_users, 1):
        table.add_row(str(user_id), str(idx))

    console.print(table)
    console.print(
        f"\n[green]Total: {len(config.telegram_allowed_users)} user(s)[/green]"
    )


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
