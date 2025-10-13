"""Test CLI basic functionality."""
from typer.testing import CliRunner
from aletheia.cli import app

runner = CliRunner()


def test_version_command() -> None:
    """Test that version command works."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Aletheia version" in result.stdout


def test_session_command() -> None:
    """Test that session command works."""
    result = runner.invoke(app, ["session"])
    assert result.exit_code == 0
    assert "coming soon" in result.stdout.lower()
