"""
Command-line interface for Aletheia.

Main entry point for the Aletheia CLI application.
"""
import sys
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
import getpass

from aletheia.session import Session

app = typer.Typer(
    name="aletheia",
    help="AI-powered troubleshooting tool for SREs",
    add_completion=False,
)

session_app = typer.Typer(
    name="session",
    help="Manage troubleshooting sessions",
)

app.add_typer(session_app, name="session")

console = Console()


@app.command()
def version() -> None:
    """Display the version of Aletheia."""
    from aletheia import __version__
    typer.echo(f"Aletheia version {__version__}")


@session_app.command("open")
def session_open(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Session name"),
    mode: str = typer.Option("guided", "--mode", "-m", help="Session mode (guided or conversational)"),
) -> None:
    """Open a new troubleshooting session."""
    if mode not in ["guided", "conversational"]:
        typer.echo("Error: Mode must be 'guided' or 'conversational'", err=True)
        raise typer.Exit(1)
    
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
            mode=mode,
        )
        console.print(f"[green]Session '{session.name}' created successfully![/green]")
        console.print(f"Session ID: {session.session_id}")
        console.print(f"Mode: {session.mode}")
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
        table.add_column("Name", style="cyan")
        table.add_column("Session ID", style="magenta")
        table.add_column("Mode", style="green")
        table.add_column("Created", style="yellow")
        
        for session_data in sessions:
            table.add_row(
                session_data["name"],
                session_data["session_id"],
                session_data["mode"],
                session_data["created_at"],
            )
        
        console.print(table)
    except Exception as e:
        typer.echo(f"Error listing sessions: {e}", err=True)
        raise typer.Exit(1)


@session_app.command("resume")
def session_resume(
    session_id: str = typer.Argument(..., help="Session ID to resume"),
) -> None:
    """Resume an existing troubleshooting session."""
    # Get password
    password = getpass.getpass("Enter session password: ")
    if not password:
        typer.echo("Error: Password cannot be empty", err=True)
        raise typer.Exit(1)
    
    try:
        session = Session.resume(session_id=session_id, password=password)
        console.print(f"[green]Session '{session.name}' resumed successfully![/green]")
        console.print(f"Session ID: {session.session_id}")
        console.print(f"Mode: {session.mode}")
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
        console.print(f"[green]Session imported successfully![/green]")
        console.print(f"Session ID: {session.session_id}")
        console.print(f"Session Name: {session.name}")
    except FileExistsError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error importing session: {e}", err=True)
        raise typer.Exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
