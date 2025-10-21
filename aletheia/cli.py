"""
Command-line interface for Aletheia.

Main entry point for the Aletheia CLI application.
"""
import sys
import typer
import asyncio
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
import getpass

from aletheia.session import Session
from aletheia.config import ConfigLoader
from aletheia.agents.orchestrator import OrchestratorAgent
from aletheia.agents.data_fetcher import DataFetcherAgent
from aletheia.agents.pattern_analyzer import PatternAnalyzerAgent
from aletheia.agents.code_inspector import CodeInspectorAgent
from aletheia.agents.root_cause_analyst import RootCauseAnalystAgent
from aletheia.scratchpad import Scratchpad
from aletheia.utils import set_verbose_commands, enable_trace_logging, disable_trace_logging

app = typer.Typer(
    name="aletheia",
    help="AI-powered troubleshooting tool for SREs",
    add_completion=False,
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


def _start_investigation(session: Session, console: Console) -> None:
    """
    Start the investigation workflow for a session.
    
    Args:
        session: Active session to investigate
        console: Rich console for output
    """
    try:
        # Load configuration
        config_loader = ConfigLoader()
        config_model = config_loader.load()
        
        # Convert Pydantic model to dictionary for agents
        config = config_model.model_dump()
        
        # Initialize scratchpad with session directory and encryption key
        scratchpad_file = session.scratchpad_file
        
        # Load existing scratchpad if it exists, otherwise create new one
        if scratchpad_file.exists():
            scratchpad = Scratchpad.load(
                session_dir=session.session_path,
                encryption_key=session._get_key()
            )
        else:
            scratchpad = Scratchpad(
                session_dir=session.session_path,
                encryption_key=session._get_key()
            )
        
        # Initialize orchestrator
        orchestrator = OrchestratorAgent(
            config=config,
            scratchpad=scratchpad
        )
        
        # Initialize and register specialist agents
        data_fetcher = DataFetcherAgent(config=config, scratchpad=scratchpad)
        pattern_analyzer = PatternAnalyzerAgent(config=config, scratchpad=scratchpad)
        code_inspector = CodeInspectorAgent(config=config, scratchpad=scratchpad)
        root_cause_analyst = RootCauseAnalystAgent(config=config, scratchpad=scratchpad)
        
        orchestrator.register_agent("data_fetcher", data_fetcher)
        orchestrator.register_agent("pattern_analyzer", pattern_analyzer)
        orchestrator.register_agent("code_inspector", code_inspector)
        orchestrator.register_agent("root_cause_analyst", root_cause_analyst)
        
        # Start investigation in conversational mode
        console.print(f"\n[cyan]Starting conversational investigation...[/cyan]\n")
        result = orchestrator.execute()
        
        # Display completion message
        if result.get("status") == "completed":
            console.print("\n[green]✓ Investigation completed successfully![/green]")
        else:
            console.print(f"\n[yellow]Investigation ended with status: {result.get('status')}[/yellow]")
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Investigation interrupted. Session saved.[/yellow]")
        # Save scratchpad before exiting
        scratchpad.save()
    except Exception as e:
        console.print(f"[red]Error during investigation: {e}[/red]")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


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
    
    # Get password
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
        )
        
        # Enable trace logging if very-verbose mode
        if very_verbose:
            enable_trace_logging(session.session_path)
            console.print(f"[dim]Trace log: {session.session_path / 'aletheia_trace.log'}[/dim]\n")
        
        metadata = session.get_metadata()
        console.print(f"[green]Session '{metadata.name}' created successfully![/green]")
        console.print(f"Session ID: {session.session_id}")
        
        # Start investigation workflow
        _start_investigation(session, console)
        
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
    
    # Get password
    password = getpass.getpass("Enter session password: ")
    if not password:
        typer.echo("Error: Password cannot be empty", err=True)
        raise typer.Exit(1)
    
    try:
        session = Session.resume(session_id=session_id, password=password)
        metadata = session.get_metadata()
        
        # Enable trace logging if very-verbose mode or if session was created with verbose
        if very_verbose or metadata.verbose:
            enable_trace_logging(session.session_path)
            console.print(f"[dim]Trace log: {session.session_path / 'aletheia_trace.log'}[/dim]\n")
        
        console.print(f"[green]Session '{metadata.name}' resumed successfully![/green]")
        console.print(f"Session ID: {session.session_id}")
        
        # Resume investigation workflow
        _start_investigation(session, console)
        
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
) -> None:
    """Export a troubleshooting session."""
    # Get password
    password = getpass.getpass("Enter session password: ")
    if not password:
        typer.echo("Error: Password cannot be empty", err=True)
        raise typer.Exit(1)
    
    try:
        session = Session.resume(session_id=session_id, password=password)
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
) -> None:
    """Import a troubleshooting session."""
    if not archive_path.exists():
        typer.echo(f"Error: Archive file '{archive_path}' not found", err=True)
        raise typer.Exit(1)
    
    # Get password
    password = getpass.getpass("Enter session password: ")
    if not password:
        typer.echo("Error: Password cannot be empty", err=True)
        raise typer.Exit(1)
    
    try:
        session = Session.import_session(archive_path=archive_path, password=password)
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
) -> None:
    """View scratchpad contents of a session."""
    # Get password
    password = getpass.getpass("Enter session password: ")
    if not password:
        typer.echo("Error: Password cannot be empty", err=True)
        raise typer.Exit(1)
    
    try:
        # Resume session to decrypt
        session = Session.resume(session_id=session_id, password=password)
        
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
        config_loader = ConfigLoader()
        config_model = config_loader.load()
        config = config_model.model_dump()
        
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


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
