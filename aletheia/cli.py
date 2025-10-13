"""
Command-line interface for Aletheia.

Main entry point for the Aletheia CLI application.
"""
import typer
from typing import Optional

app = typer.Typer(
    name="aletheia",
    help="AI-powered troubleshooting tool for SREs",
    add_completion=False,
)


@app.command()
def version() -> None:
    """Display the version of Aletheia."""
    from aletheia import __version__
    typer.echo(f"Aletheia version {__version__}")


@app.command()
def session() -> None:
    """Manage troubleshooting sessions."""
    typer.echo("Session management coming soon...")


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
