"""
Command-line interface for Aletheia.

Main entry point for the Aletheia CLI application.
"""
import os
import sys
import typer
import asyncio
import threading
import time
import random
import sys
import getpass
import time
import random
import threading

from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.live import Live


from agent_framework import (
    AgentThread,
    ChatMessage,
    TextContent,
    UsageContent,
    UsageDetails,
    Role
)

from aletheia.agents.base import BaseAgent
from aletheia.session import Session, SessionNotFoundError
from aletheia.config import load_config
from aletheia.llm.service import LLMService
from aletheia.agents.kubernetes_data_fetcher.kubernetes_data_fetcher import KubernetesDataFetcher
from aletheia.agents.prometheus_data_fetcher.prometheus_data_fetcher import PrometheusDataFetcher
from aletheia.agents.log_file_data_fetcher.log_file_data_fetcher import LogFileDataFetcher
from aletheia.agents.pcap_file_data_fetcher.pcap_file_data_fetcher import PCAPFileDataFetcher
from aletheia.agents.network.network import NetworkAgent
from aletheia.agents.aws.aws import AWSAgent
from aletheia.agents.azure.azure import AzureAgent
from aletheia.agents.timeline.timeline_agent import TimelineAgent
from aletheia.agents.code_analyzer.code_analyzer import CodeAnalyzer
from aletheia.plugins.scratchpad import Scratchpad
from aletheia.utils import set_verbose_commands, enable_trace_logging
from aletheia.agents.instructions_loader import Loader
from aletheia.agents.entrypoint import Orchestrator
from aletheia.agents.history import ConversationHistory
from aletheia.utils.logging import log_debug
from aletheia.config import Config

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

def banner_callback(ctx: typer.Context):
    show_banner()

app = typer.Typer(
    name="aletheia",
    help="AI-powered troubleshooting tool for SREs",
    add_completion=False,
    callback=banner_callback
)

session_app = typer.Typer(
    name="session",
    help="Manage troubleshooting sessions",
)

app.add_typer(session_app, name="session")

console = Console()

thinking_interval = 2.0  # seconds


def _build_plugins(config: Config,
                   prompt_loader: Loader,
                   llm_service: LLMService,
                   session: Session,
                   scratchpad: Scratchpad) -> List[BaseAgent]:
    """Build and return the list of available agent plugins."""
    # Currently, plugins are built directly in the _start_investigation function.
    # This function can be expanded in the future to dynamically load plugins.

    plugins = []

    kubernetes_fetcher = KubernetesDataFetcher(name="kubernetes_data_fetcher",
                                                   config=config,
                                                   description="Kubernetes Data Fetcher Agent for collecting Kubernetes logs and pod information.",
                                                   instructions=prompt_loader.load("kubernetes_data_fetcher", "instructions"),
                                                   service=llm_service.client,
                                                   session=session,
                                                   scratchpad=scratchpad)     
    plugins.append(kubernetes_fetcher.agent.as_tool())

    log_file_fetcher = LogFileDataFetcher(name="log_file_data_fetcher",
                                        config=config,
                                        description="Log File Data Fetcher Agent for collecting logs from log files.",
                                        instructions=prompt_loader.load("log_file_data_fetcher", "instructions"),
                                        service=llm_service.client,
                                        session=session,
                                        scratchpad=scratchpad)
    plugins.append(log_file_fetcher.agent.as_tool())

    pcap_file_fetcher = PCAPFileDataFetcher(name="pcap_file_data_fetcher",
                                        config=config,
                                        description="PCAP File Data Fetcher Agent for collecting packets from PCAP files.",
                                        instructions=prompt_loader.load("pcap_file_data_fetcher", "instructions"),
                                        service=llm_service.client,
                                        session=session,
                                        scratchpad=scratchpad)                                              
    plugins.append(pcap_file_fetcher.agent.as_tool())

    prometheus_fetcher = PrometheusDataFetcher(name="prometheus_data_fetcher",
                                            config=config,
                                            description="Prometheus Data Fetcher Agent for collecting Prometheus metrics.",
                                            instructions=prompt_loader.load("prometheus_data_fetcher", "instructions"),
                                            service=llm_service.client,
                                            session=session,
                                            scratchpad=scratchpad)
    plugins.append(prometheus_fetcher.agent.as_tool())

    aws_agent = AWSAgent(name="aws",
                         config=config,
                         description="AWS Agent for fetching AWS related data using AWS CLI.",
                         instructions=prompt_loader.load("aws", "instructions"),
                         service=llm_service.client,
                         session=session,
                         scratchpad=scratchpad)
    plugins.append(aws_agent.agent.as_tool())    

    azure_agent = AzureAgent(name="azure",
                              config=config,
                              description="Azure Agent for fetching Azure related data using Azure CLI.",
                              instructions=prompt_loader.load("azure", "instructions"),
                              service=llm_service.client,
                              session=session,
                         scratchpad=scratchpad)
    plugins.append(azure_agent.agent.as_tool())        

    network_agent = NetworkAgent(name="network",  
                                config=config,
                                description="Network Agent for fetching TCP Network related data.",
                                instructions=prompt_loader.load("network", "instructions"),
                                service=llm_service.client,
                                session=session,
                                scratchpad=scratchpad)
    plugins.append(network_agent.agent.as_tool())
    
    if config.code_analyzer is not None and config.code_analyzer.strip() != "":
        code_analyzer = CodeAnalyzer(name=f"{config.code_analyzer}_code_analyzer",
                                    config=config,
                                    description="Claude Code Analyzer Agent for analyzing code repositories using Claude.",
                                    instructions=prompt_loader.load("code_analyzer", "instructions", prefix=config.code_analyzer.lower()),
                                    service=llm_service.client,
                                    session=session,
                                    scratchpad=scratchpad)                                                   
        plugins.append(code_analyzer.agent.as_tool())

    return plugins


async def show_thinking_animation(live, stop_event):
    while not stop_event.is_set():
        msg = random.choice(THINKING_MESSAGES)
        live.update(f"[dim cyan]{msg}[/dim cyan]")
        live.refresh()
        await asyncio.sleep(1)



async def _start_investigation(session: Session, console: Console) -> None:

    """
    Start the investigation workflow for a session.
    
    Args:
        session: Active session to investigate
        console: Rich console for output
    """

    try:
        # Load configuration
        config= load_config()
        
        # Prompt loader
        prompt_loader = Loader()
        # Initialize scratchpad with session directory and encryption key
        scratchpad_file = session.scratchpad_file
        
        # Load existing scratchpad if it exists, otherwise create new one
        scratchpad = Scratchpad(
                session_dir=session.session_path,
                encryption_key=session._get_key()
        )
        session.scratchpad = scratchpad

        # get LLM Service
        llm_service = LLMService(config=config)
        

        entry = Orchestrator(
            name="orchestrator",
            description="Orchestrator agent managing the investigation workflow",
            instructions=prompt_loader.load("orchestrator", "instructions"),
            service = llm_service.client,
            session=session,
            sub_agents=_build_plugins(config=config,
                                      prompt_loader=prompt_loader,
                                      llm_service=llm_service,
                                      session=session,
                                      scratchpad=scratchpad),
            scratchpad=scratchpad
        )
        

        chatting = True
        chat_history = ConversationHistory()
        completion_usage = UsageDetails()

        thread: AgentThread = entry.agent.get_new_thread()
        

        while chatting:
            console.print("[cyan]" + "─" * console.width + "[/cyan]")
            console.print(f"[i cyan]You can ask questions about the investigation or type 'exit' to end the session.[/i cyan]\n")
            user_input = Prompt.ask(f"\n[[bold yellow]{session.session_id}[/bold yellow]] [bold green]👤 YOU[/bold green]")
            if user_input.lower() in ['exit', 'quit']:
                chatting = False
                console.print("\n[cyan]Ending the investigation session.[/cyan]\n")
                break


            # Start thinking animation in a background thread
            stop_event = asyncio.Event()

            full_response = ""
            try:
                # Print header with horizontal line ONCE at the start
                console.print(f"\n[[bold yellow]{session.session_id}[/bold yellow]] [bold cyan]🤖 Aletheia[/bold cyan]")
                console.print("[cyan]" + "─" * console.width + "[/cyan]")

                buf=""
                with Live("", console=console, refresh_per_second=4, auto_refresh=False) as live:

                    waiter = asyncio.create_task(show_thinking_animation(live, stop_event))

                    async for response in entry.agent.run_stream(
                        messages=[ChatMessage(role="user", contents=[TextContent(text=user_input)])],
                        thread=thread
                    ):
                        if response and str(response.text) != "":
                            if not stop_event.is_set():
                                stop_event.set()
                                await asyncio.sleep(0.2)  # Give animation time to stop
                                # Clear the live display
                                live.update("")
                                live.refresh()

                            full_response += str(response.text)
                            buf+=response.text
                            live.update(Markdown(safe_md(buf)))
                            live.refresh()

                        if response and response.contents:
                            for content in response.contents:
                                if isinstance(content, UsageContent ):
                                    completion_usage += content.details
            finally:
                if stop_event and not stop_event.is_set():
                    stop_event.set()


        # evaluate total session cost
        input_token = completion_usage.input_token_count
        output_token = completion_usage.output_token_count
        total_tokens = input_token + output_token
        total_cost = (input_token * config.cost_per_input_token) + (output_token * config.cost_per_output_token)
        cost_table = "| Metric | Total | Input | Output |\n"
        cost_table += "|--------|-------|-------|--------|\n"
        cost_table += f"| Tokens | {total_tokens} | {input_token} | {output_token} |\n"
        cost_table += f"| Cost (€) | €{total_cost:.6f} | €{input_token * config.cost_per_input_token:.6f} | €{output_token * config.cost_per_output_token:.6f} |\n"
        console.print(Markdown(cost_table))
#        console.print(f"[bold cyan]Session completed.[/bold cyan] Total tokens used: [bold]{total_tokens}[/bold] (Input: [bold]{input_token}[/bold], Output: [bold]{output_token}[/bold]).")
#        console.print(f"[bold cyan]Estimated session cost:[/bold cyan] €[bold]{total_cost:.6f}[/bold] (Input: €[bold]{input_token * config.cost_per_input_token:.6f}[/bold], Output: €[bold]{output_token * config.cost_per_output_token:.6f}[/bold])\n")

            
    except KeyboardInterrupt:
        console.print("\n[yellow]Investigation interrupted. Session saved.[/yellow]")
        # Save scratchpad before exiting
        scratchpad.save()
    except Exception as e:
        console.print(f"[red]Error during investigation: {e}[/red]")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

def safe_md(s: str) -> str:
        fences = s.count("```")
        return s + ("\n```" if fences % 2 else "")



@app.command()
def version() -> None:
    """Display the version of Aletheia."""
    from aletheia import __version__
    typer.echo(f"Aletheia version {__version__}")


@session_app.command("open")
def session_open(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Session name"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show all external commands and their output"),
    very_verbose: bool = typer.Option(False, "--very-verbose", "-vv", help="Enable trace logging with prompts, commands, and full details"),
    unsafe: bool = typer.Option(False, "--unsafe", help="Use plaintext storage (skips encryption - NOT RECOMMENDED)"),
) -> None:
    """Open a new troubleshooting session in conversational mode."""
    # Enable very-verbose mode (implies verbose)
    if very_verbose:
        verbose = True
    
    # Enable verbose command output if requested
    if verbose:
        set_verbose_commands(True)
        console.print("[dim]Verbose mode enabled - all external commands will be shown[/dim]\n")
    
    if very_verbose:
        console.print("[dim]Very-verbose mode (-vv) enabled - full trace logging with prompts and details[/dim]\n")
    
    # Warn about unsafe mode
    if unsafe:
        console.print("[bold red]⚠️  WARNING: --unsafe mode enabled - data will be stored in PLAINTEXT without encryption![/bold red]")
        console.print("[red]This mode should ONLY be used for testing purposes.[/red]\n")
    
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
        if very_verbose:
            enable_trace_logging(session.session_path)
            console.print(f"[dim]Trace log: {session.session_path / 'aletheia_trace.log'}[/dim]\n")
        
        metadata = session.get_metadata()
        console.print(f"[green]Session '{session.session_id}' created successfully![/green]")
        console.print(f"Session ID: {session.session_id}")
        
        # Start investigation workflow
        asyncio.run(_start_investigation(session, console))
        
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
        table.add_column("Created", style="yellow")
        table.add_column("Path", style="cyan")
        table.add_column("Unsafe", style="cyan")
        
        for session_data in sessions:
            table.add_row(
                session_data["id"],
                session_data["created"],
                session_data["path"],
                session_data["unsafe"]
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
        confirm = typer.confirm(f"Are you sure you want to delete session '{session_id}'?")
        if not confirm:
            console.print("[yellow]Deletion cancelled[/yellow]")
            return
    
    try:
        # Directly construct Session and call delete
        session = Session(session_id=session_id)
        session.delete()
        console.print(f"[green]Session '{session_id}' deleted successfully![/green]")
    except SessionNotFoundError:
        typer.echo(f"Error: Session '{session_id}' not found", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error deleting session: {e}", err=True)
        raise typer.Exit(1)

@session_app.command("timeline")
def session_timeline(
    session_id: str = typer.Argument(..., help="Session ID to export"),
    unsafe: bool = typer.Option(False, "--unsafe", help="Session uses plaintext storage (skips encryption)"),
) -> None:
    """prints a session timeline"""
    # Warn about unsafe mode
    if unsafe:
        console.print("[bold red]⚠️  WARNING: --unsafe mode enabled - session uses PLAINTEXT storage![/bold red]\n")
    
    # Get password (skip in unsafe mode)
    password = None
    if not unsafe:
        password = getpass.getpass("Enter session password: ")
        if not password:
            typer.echo("Error: Password cannot be empty", err=True)
            raise typer.Exit(1)
    
    try:
        # Load configuration
        config= load_config()
        # Resume session to access metadata
        session = Session.resume(session_id=session_id, password=password, unsafe=unsafe)
        metadata = session.get_metadata()

        # Load scratchpad
        scratchpad_file = session.scratchpad_file
        if not scratchpad_file.exists():
            console.print("[yellow]No scratchpad data found for this session[/yellow]")
            return

        scratchpad = Scratchpad(
            session_dir=session.session_path,
            encryption_key=session._get_key()
        )

        # Display scratchpad contents (raw journal)
        journal_content = scratchpad.read_scratchpad()        

        prompt_loader = Loader()        
        # get LLM Service
        llm_service = LLMService(config=config)        

        timeline_agent = TimelineAgent(name="timeline_agent", 
                                       instructions=prompt_loader.load("timeline", "instructions"),
                                       description="Timeline Agent for generating session timeline",
                                       service=llm_service.client)

        message = ChatMessage(role=Role.USER, contents=[TextContent(text=f"""   
                                       Generate a timeline of the following troubleshooting session scratchpad data:\n\n{journal_content}\n\n
                                       The timeline should summarize key actions, findings, and next steps in chronological order.
                                       The output should be in the following format:
                                       - [Time/Step]: Short description of action or finding
                                       No additional commentary is needed.
                                       """)])
        response = asyncio.run(timeline_agent.agent.run(message))
        if response:
            console.print(f"\n{response}\n")






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
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    unsafe: bool = typer.Option(False, "--unsafe", help="Session uses plaintext storage (skips encryption)"),
) -> None:
    """Export a troubleshooting session."""
    # Warn about unsafe mode
    if unsafe:
        console.print("[bold red]⚠️  WARNING: --unsafe mode enabled - session uses PLAINTEXT storage![/bold red]\n")
    
    # Get password (skip in unsafe mode)
    password = None
    if not unsafe:
        password = getpass.getpass("Enter session password: ")
        if not password:
            typer.echo("Error: Password cannot be empty", err=True)
            raise typer.Exit(1)
    
    import zipfile
    import tempfile
    import shutil

    try:
        session = Session.resume(session_id=session_id, password=password, unsafe=unsafe)
        session_dir = session.session_path

        # Prepare output zip path
        zip_name = f"{session_id}.zip"
        export_path = output or Path(zip_name)

        # Create a temporary directory to hold decrypted files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            # Copy all files from session_dir to tmpdir, decrypting if needed
            from aletheia.encryption import decrypt_file
            key = session._get_key() if not unsafe else None
            for root, dirs, files in os.walk(session_dir):
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
                        except Exception:
                            shutil.copy2(src_file, dest_file)
                    else:
                        shutil.copy2(src_file, dest_file)

            # Create zip file from tmpdir
            with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for foldername, subfolders, filenames in os.walk(tmpdir_path):
                    for filename in filenames:
                        file_path = Path(foldername) / filename
                        arcname = file_path.relative_to(tmpdir_path)
                        zipf.write(file_path, arcname)

        console.print(f"[green]Session exported successfully![/green]")
        console.print(f"Export file: {export_path}")
    except FileNotFoundError:
        typer.echo(f"Error: Session '{session_id}' not found", err=True)
        raise typer.Exit(1)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error exporting session: {e}", err=True)
        raise typer.Exit(1)


@session_app.command("view")
def session_view(
    session_id: str = typer.Argument(..., help="Session ID to view"),
    unsafe: bool = typer.Option(False, "--unsafe", help="Session uses plaintext storage (skips encryption)"),
) -> None:
    """View scratchpad contents of a session, and list files in the data directory."""
    # Warn about unsafe mode
    if unsafe:
        console.print("[bold red]⚠️  WARNING: --unsafe mode enabled - session uses PLAINTEXT storage![/bold red]\n")
    password = None
    if not unsafe:
        password = getpass.getpass("Enter session password: ")
        if not password:
            typer.echo("Error: Password cannot be empty", err=True)
            raise typer.Exit(1)         
    
    try:
        # Resume session to access metadata
        session = Session.resume(session_id=session_id, password=password, unsafe=unsafe)
        metadata = session.get_metadata()

        # Load scratchpad
        scratchpad_file = session.scratchpad_file
        if not scratchpad_file.exists():
            console.print("[yellow]No scratchpad data found for this session[/yellow]")
            return

        scratchpad = Scratchpad(
            session_dir=session.session_path,
            encryption_key=session._get_key()
        )

        # Display metadata
        console.print(f"\n[bold cyan]Session: {metadata.name or session_id}[/bold cyan]")
        console.print(f"Status: {metadata.status}")
        console.print(f"Created: {metadata.created}")
        console.print(f"Updated: {metadata.updated}")

        # Display scratchpad contents (raw journal)
        console.print(f"\n[bold cyan]Scratchpad Contents:[/bold cyan]\n")
        journal_content = scratchpad.read_scratchpad()
        if not journal_content.strip():
            console.print("[dim](Scratchpad is empty)[/dim]")
        else:
            from rich.markdown import Markdown
            console.print(Markdown(journal_content))

        # List files in the session's data directory (recursively)
        data_dir = session.session_path / "data"
        console.print(f"\n[bold cyan]Data Directory Files:[/bold cyan]")
        if data_dir.exists() and data_dir.is_dir():
            all_files = []
            for root, dirs, files in os.walk(data_dir):
                for file in files:
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(data_dir)
                    all_files.append(rel_path)
            if all_files:
                # Build a tree structure for pretty printing
                from collections import defaultdict
                tree = lambda: defaultdict(tree)
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

    except FileNotFoundError:
        typer.echo(f"Error: Session '{session_id}' not found", err=True)
        raise typer.Exit(1)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error viewing session: {e}", err=True)
        raise typer.Exit(1)


def show_banner(verbose: bool = False) -> None:
    banner_path = os.path.join(os.path.dirname(__file__), "banner.txt")
    try:
        with open(banner_path, "r", encoding="utf-8") as f:
            console.print(f.read())

    except Exception:
        pass

def main() -> None:
    """Main entry point for the CLI."""
    app()

if __name__ == "__main__":
    main()
