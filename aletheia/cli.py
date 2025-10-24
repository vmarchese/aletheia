"""
Command-line interface for Aletheia.

Main entry point for the Aletheia CLI application.
"""
import os
import typer
import asyncio
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
import getpass

from semantic_kernel.contents.chat_history import ChatMessageContent
from semantic_kernel.contents import ChatMessageContent, FunctionCallContent, FunctionResultContent
from semantic_kernel.agents import ChatHistoryAgentThread
from semantic_kernel.connectors.ai.completion_usage import CompletionUsage

from aletheia.session import Session
from aletheia.config import load_config
from aletheia.llm.service import LLMService
from aletheia.agents.orchestrator import OrchestratorAgent
from aletheia.agents.pattern_analyzer import PatternAnalyzerAgent
from aletheia.agents.kubernetes_data_fetcher import KubernetesDataFetcher
from aletheia.agents.prometheus_data_fetcher import PrometheusDataFetcher
from aletheia.agents.log_file_data_fetcher import LogFileDataFetcher
from aletheia.agents.pcap_file_data_fetcher import PCAPFileDataFetcher
from aletheia.scratchpad import Scratchpad
from aletheia.utils import set_verbose_commands, enable_trace_logging
from aletheia.llm.prompts.loader import Loader
from aletheia.agents.entrypoint import Orchestrator
from aletheia.agents.history import ConversationHistory
from aletheia.utils.logging import log_debug

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

demo_app = typer.Typer(
    name="demo",
    help="Run demo mode with pre-recorded scenarios",
)

app.add_typer(session_app, name="session")
app.add_typer(demo_app, name="demo")

console = Console()


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

        # get LLM Service
        llm_service = LLMService(config=config)
        
        # Initialize orchestrator
        orchestrator = OrchestratorAgent( 
            name="orchestrator",
            description="Orchestrator agent managing the investigation workflow",
            instructions=prompt_loader.load("orchestrator", "instructions"),
            service = llm_service.client,
            session=session,
            scratchpad=scratchpad
        )
        
        # Initialize and register specialist agents
        kubernetes_fetcher = KubernetesDataFetcher(name="kubernetes_data_fetcher",
                                                   config=config,
                                                   description="Kubernetes Data Fetcher Agent for collecting Kubernetes logs and pod information.",
                                                   instructions=prompt_loader.load("kubernetes_data_fetcher", "instructions"),
                                                   service=llm_service.client,
                                                   session=session,
                                                   scratchpad=scratchpad) 

        log_file_fetcher = LogFileDataFetcher(name="log_file_data_fetcher",
                                              config=config,
                                              description="Log File Data Fetcher Agent for collecting logs from log files.",
                                              instructions=prompt_loader.load("log_file_data_fetcher", "instructions"),
                                              service=llm_service.client,
                                              session=session,
                                              scratchpad=scratchpad)

        pcap_file_fetcher = PCAPFileDataFetcher(name="pcap_file_data_fetcher",
                                              config=config,
                                              description="PCAP File Data Fetcher Agent for collecting packets from PCAP files.",
                                              instructions=prompt_loader.load("pcap_file_data_fetcher", "instructions"),
                                              service=llm_service.client,
                                              session=session,
                                              scratchpad=scratchpad)                                              

        prometheus_fetcher = PrometheusDataFetcher(name="prometheus_data_fetcher",
                                                   config=config,
                                                   description="Prometheus Data Fetcher Agent for collecting Prometheus metrics.",
                                                   instructions=prompt_loader.load("prometheus_data_fetcher", "instructions"),
                                                   service=llm_service.client,
                                                   session=session,
                                                   scratchpad=scratchpad)
        pattern_analyzer = PatternAnalyzerAgent(name="pattern_analyzer",
                                                description="Pattern Analyzer Agent for analyzing collected data patterns.",
                                                instructions=prompt_loader.load("pattern_analyzer", "instructions"),
                                                service=llm_service.client,
                                                session=session,
                                                scratchpad=scratchpad)

        # Creating orchestration
        """
        orchestration = AletheiaHandoffOrchestration(
            session=session,
            orchestration_agent=orchestrator,
            kubernetes_fetcher_agent=kubernetes_fetcher,
            prometheus_fetcher_agent=prometheus_fetcher,
            pattern_analyzer_agent=pattern_analyzer,
            log_file_data_fetcher_agent=log_file_fetcher,
            console=console
        )
        
        # Start investigation in conversational mode
        console.print(f"\n[cyan]Starting conversational investigation...[/cyan]\n")
        runtime = orchestration.start_runtime()

        # Ask user for the problem to investigate
        problem = typer.prompt("Describe the issue to investigate")
        if not problem or not problem.strip():
            console.print("[yellow]No problem description provided. Aborting investigation.[/yellow]")
            return

        result = await orchestration.orchestration_handoffs.invoke(
            runtime = runtime,
            task = problem,
        )
        value = await result.get()
        console.print(f"\n[bold green]Investigation Result:[/bold green]\n{value}\n")   
        """
        entry = Orchestrator( 
            name="orchestrator",
            description="Orchestrator agent managing the investigation workflow",
            instructions=prompt_loader.load("orchestrator", "instructions"),
            service = llm_service.client,
            session=session,
            kubernetes_fetcher_agent=kubernetes_fetcher,
            prometheus_fetcher_agent=prometheus_fetcher,
            pattern_analyzer_agent=pattern_analyzer,
            log_file_data_fetcher_agent=log_file_fetcher,
            pcap_file_fetcher_agent=pcap_file_fetcher,
            scratchpad=scratchpad
        )
        

        chatting = True
        chat_history = ConversationHistory()
        completion_usage = CompletionUsage()

        thread: ChatHistoryAgentThread = None
        while chatting:
            console.print(f"\n[cyan]You can ask questions about the investigation or type 'exit' to end the session.[/cyan]\n")
            user_input = Prompt.ask(f"\n[[bold yellow]{session.session_id}[/bold yellow]] [bold yellow]👤 Your input[/bold yellow]")
            if user_input.lower() in ['exit', 'quit']:
                chatting = False
                console.print("\n[cyan]Ending the investigation session.[/cyan]\n")
                break
            chat_history.add_message(ChatMessageContent(role="user", content=user_input))

            log_debug(f"cli::start_investigation - Sending input to orchestrator agent{chat_history.to_prompt()}")
            console.print(f"[[bold yellow]{session.session_id}[/bold yellow]] [bold green]🤖 Thinking...[/bold green]\n")
            full_response = ""
            async for response in entry.agent.invoke_stream(
                messages=chat_history.to_prompt(),
                on_intermediate_message=handle_intermediate_steps,
                thread=thread
            ):
                if response:
                    full_response += str(response.content)
                    console.print(f"{response.content}", end="")
                if response.metadata.get("usage"):
                    completion_usage += response.metadata["usage"]
                thread = response.thread
            chat_history.add_message(ChatMessageContent(role="assistant", content=full_response))
            console.print("\n\n")
            console.print(f"[grey89]({completion_usage.completion_tokens} tokens used)[/grey89]\n")
            """
            response = await entry.agent.invoke(
                messages=chat_history.to_prompt(),
                on_intermediate_message=lambda msg: console.print(f"[[bold yellow]{session.session_id}[/bold yellow]] [bold green]🤖 Thinking...[/bold green]\n{msg}\n"),
            )
            if response:
                chat_history.add_message(response.content)
                console.print(f"\n[[bold yellow]{session.session_id}[/bold yellow]] [bold green]🤖 Response:[/bold green]\n{response}\n")
            """



             


        
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Investigation interrupted. Session saved.[/yellow]")
        # Save scratchpad before exiting
        scratchpad.save()
    except Exception as e:
        console.print(f"[red]Error during investigation: {e}[/red]")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

async def handle_intermediate_steps(message: ChatMessageContent) -> None:
    for item in message.items or []:
        if isinstance(item, FunctionCallContent):
            log_debug(f"<Function Call:> {item.name} with arguments: {item.arguments}")
        elif isinstance(item, FunctionResultContent):
            log_debug("<Function Result:> {item.result} for function: {item.name}")
        else:
            log_debug("{message.role}: {message.content}")


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
        
        table = Table(title="Aletheia Sessions")
        table.add_column("Session ID", style="magenta")
        table.add_column("Created", style="yellow")
        table.add_column("Path", style="cyan")
        
        for session_data in sessions:
            table.add_row(
                session_data["id"],
                session_data["created"],
                session_data["path"],
            )
        
        console.print(table)
    except Exception as e:
        typer.echo(f"Error listing sessions: {e}", err=True)
        raise typer.Exit(1)


@session_app.command("resume")
def session_resume(
    session_id: str = typer.Argument(..., help="Session ID to resume"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show all external commands and their output"),
    very_verbose: bool = typer.Option(False, "--very-verbose", "-vv", help="Enable trace logging with prompts, commands, and full details"),
    unsafe: bool = typer.Option(False, "--unsafe", help="Session uses plaintext storage (skips encryption)"),
) -> None:
    """Resume an existing troubleshooting session."""
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
        console.print("[bold red]⚠️  WARNING: --unsafe mode enabled - session uses PLAINTEXT storage![/bold red]\n")
    
    # Get password (skip in unsafe mode)
    password = None
    if not unsafe:
        password = getpass.getpass("Enter session password: ")
        if not password:
            typer.echo("Error: Password cannot be empty", err=True)
            raise typer.Exit(1)
    
    try:
        session = Session.resume(session_id=session_id, password=password, unsafe=unsafe)
        metadata = session.get_metadata()
        
        # Enable trace logging if very-verbose mode or if session was created with verbose
        if very_verbose or metadata.verbose:
            enable_trace_logging(session.session_path)
            console.print(f"[dim]Trace log: {session.session_path / 'aletheia_trace.log'}[/dim]\n")
        
        console.print(f"[green]Session '{metadata.name}' resumed successfully![/green]")
        console.print(f"Session ID: {session.session_id}")
        
        # Resume investigation workflow
        asyncio.run(_start_investigation(session, console))
        
    except FileNotFoundError:
        typer.echo(f"Error: Session '{session_id}' not found", err=True)
        raise typer.Exit(1)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error resuming session: {e}", err=True)
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
        Session.delete(session_id)
        console.print(f"[green]Session '{session_id}' deleted successfully![/green]")
    except FileNotFoundError:
        typer.echo(f"Error: Session '{session_id}' not found", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error deleting session: {e}", err=True)
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
    
    try:
        session = Session.resume(session_id=session_id, password=password, unsafe=unsafe)
        export_path = session.export(output_path=output)
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


@session_app.command("import")
def session_import(
    archive_path: Path = typer.Argument(..., help="Path to session archive"),
    unsafe: bool = typer.Option(False, "--unsafe", help="Archive uses plaintext storage (skips encryption)"),
) -> None:
    """Import a troubleshooting session."""
    if not archive_path.exists():
        typer.echo(f"Error: Archive file '{archive_path}' not found", err=True)
        raise typer.Exit(1)
    
    # Warn about unsafe mode
    if unsafe:
        console.print("[bold red]⚠️  WARNING: --unsafe mode enabled - archive uses PLAINTEXT storage![/bold red]\n")
    
    # Get password (skip in unsafe mode)
    password = None
    if not unsafe:
        password = getpass.getpass("Enter session password: ")
        if not password:
            typer.echo("Error: Password cannot be empty", err=True)
            raise typer.Exit(1)
    
    try:
        session = Session.import_session(archive_path=archive_path, password=password, unsafe=unsafe)
        metadata = session.get_metadata()
        console.print(f"[green]Session imported successfully![/green]")
        console.print(f"Session ID: {session.session_id}")
        console.print(f"Session Name: {metadata.name}")
    except FileExistsError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error importing session: {e}", err=True)
        raise typer.Exit(1)


@session_app.command("view")
def session_view(
    session_id: str = typer.Argument(..., help="Session ID to view"),
    format: str = typer.Option("yaml", "--format", "-f", help="Output format (yaml or json)"),
    unsafe: bool = typer.Option(False, "--unsafe", help="Session uses plaintext storage (skips encryption)"),
) -> None:
    """View scratchpad contents of a session."""
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
        # Resume session to decrypt
        session = Session.resume(session_id=session_id, password=password, unsafe=unsafe)
        
        # Load scratchpad
        scratchpad_file = session.scratchpad_file
        if not scratchpad_file.exists():
            console.print("[yellow]No scratchpad data found for this session[/yellow]")
            return
        
        scratchpad = Scratchpad.load(
            session_dir=session.session_path,
            encryption_key=session._get_key()
        )
        
        # Display metadata
        metadata = session.get_metadata()
        console.print(f"\n[bold cyan]Session: {metadata.name or session_id}[/bold cyan]")
        console.print(f"Status: {metadata.status}")
        console.print(f"Created: {metadata.created}")
        console.print(f"Updated: {metadata.updated}")
        
        # Display scratchpad contents
        console.print(f"\n[bold cyan]Scratchpad Contents:[/bold cyan]\n")
        
        if format.lower() == "json":
            import json
            data = scratchpad.to_dict()
            console.print(json.dumps(data, indent=2))
        else:
            # YAML format (default)
            yaml_output = scratchpad.to_yaml()
            console.print(yaml_output)
        
        # Summary statistics
        console.print(f"\n[dim]Sections: {scratchpad.section_count}[/dim]")
        if scratchpad.updated_at:
            console.print(f"[dim]Last updated: {scratchpad.updated_at.isoformat()}[/dim]")
        
    except FileNotFoundError:
        typer.echo(f"Error: Session '{session_id}' not found", err=True)
        raise typer.Exit(1)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error viewing session: {e}", err=True)
        raise typer.Exit(1)


@demo_app.command("list")
def demo_list() -> None:
    """List available demo scenarios."""
    from aletheia.demo.scenario import DEMO_SCENARIOS
    
    table = Table(title="Available Demo Scenarios")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Description", style="white")
    
    for scenario_id, scenario in DEMO_SCENARIOS.items():
        table.add_row(
            scenario_id,
            scenario.name,
            scenario.description[:80] + "..." if len(scenario.description) > 80 else scenario.description,
        )
    
    console.print(table)
    console.print("\n[dim]Run a demo with: aletheia demo run <scenario_id>[/dim]")


@demo_app.command("run")
def demo_run(
    scenario: str = typer.Argument(..., help="Demo scenario ID to run"),
) -> None:
    """Run a demo investigation scenario with pre-recorded data."""
    from aletheia.demo.scenario import DEMO_SCENARIOS
    from aletheia.demo.orchestrator import run_demo
    from tempfile import TemporaryDirectory
    
    # Validate scenario
    if scenario not in DEMO_SCENARIOS:
        available = ", ".join(DEMO_SCENARIOS.keys())
        typer.echo(f"Error: Unknown scenario '{scenario}'. Available: {available}", err=True)
        typer.echo("Run 'aletheia demo list' to see all scenarios.", err=True)
        raise typer.Exit(1)
    
    try:
        # Load configuration
        config = load_config()
        
        # Create temporary scratchpad (demo doesn't persist)
        with TemporaryDirectory() as temp_dir:
            # Use a simple key for demo mode (no sensitive data)
            demo_key = b"demo_mode_key_32_bytes_length_"
            scratchpad = Scratchpad(
                session_dir=Path(temp_dir),
                encryption_key=demo_key
            )
            
            # Run demo investigation
            console.print("[cyan]Starting demo mode...[/cyan]\n")
            result = asyncio.run(run_demo(scenario, config, scratchpad))
            
            # Display completion status
            if result["status"] == "completed":
                console.print("\n[green]✓ Demo investigation completed![/green]")
                console.print("\n[dim]Note: Demo data is not persisted. Run a real session with 'aletheia session open' for actual investigations.[/dim]")
            elif result["status"] == "cancelled":
                console.print("\n[yellow]Demo cancelled by user[/yellow]")
            else:
                console.print(f"\n[yellow]Demo ended with status: {result['status']}[/yellow]")
                
    except Exception as e:
        typer.echo(f"Error running demo: {e}", err=True)
        raise typer.Exit(1)

def show_banner():
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
