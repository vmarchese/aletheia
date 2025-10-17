"""
Unit tests for CLI commands.
"""
import getpass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from aletheia.cli import app
from aletheia.session import Session, SessionError, SessionExistsError, SessionNotFoundError

runner = CliRunner()


class TestVersionCommand:
    """Tests for version command."""

    def test_version_displays_version(self):
        """Test version command displays version."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "Aletheia" in result.stdout
        assert "version" in result.stdout
        assert "0.1.0" in result.stdout


class TestSessionOpenCommand:
    """Tests for session open command."""

    @patch("aletheia.cli._start_investigation")
    @patch("aletheia.cli.Session.create")
    @patch("aletheia.cli.getpass.getpass")
    def test_session_open_basic(self, mock_getpass, mock_create, mock_start_investigation):
        """Test basic session creation."""
        # Mock password input
        mock_getpass.side_effect = ["test-password", "test-password"]

        # Mock session creation
        mock_metadata = MagicMock()
        mock_metadata.name = "session-1234"
        mock_metadata.mode = "guided"
        
        mock_session = MagicMock()
        mock_session.session_id = "INC-1234"
        mock_session.session_path = Path("/home/user/.aletheia/sessions/INC-1234")
        mock_session.get_metadata.return_value = mock_metadata
        mock_create.return_value = mock_session

        result = runner.invoke(app, ["session", "open"])

        assert result.exit_code == 0
        assert "INC-1234" in result.stdout
        assert "created" in result.stdout
        mock_create.assert_called_once_with(name=None, password="test-password", mode="guided")
        mock_start_investigation.assert_called_once()

    @patch("aletheia.cli._start_investigation")
    @patch("aletheia.cli.Session.create")
    @patch("aletheia.cli.getpass.getpass")
    def test_session_open_with_name(self, mock_getpass, mock_create, mock_start_investigation):
        """Test session creation with name."""
        mock_getpass.side_effect = ["test-password", "test-password"]

        mock_metadata = MagicMock()
        mock_metadata.name = "production-outage"
        mock_metadata.mode = "guided"
        
        mock_session = MagicMock()
        mock_session.session_id = "INC-5678"
        mock_session.session_path = Path("/home/user/.aletheia/sessions/INC-5678")
        mock_session.get_metadata.return_value = mock_metadata
        mock_create.return_value = mock_session

        result = runner.invoke(
            app, ["session", "open", "--name", "production-outage"]
        )

        assert result.exit_code == 0
        assert "INC-5678" in result.stdout
        assert "production-outage" in result.stdout
        mock_create.assert_called_once_with(
            name="production-outage", password="test-password", mode="guided"
        )
        mock_start_investigation.assert_called_once()

    @patch("aletheia.cli._start_investigation")
    @patch("aletheia.cli.Session.create")
    @patch("aletheia.cli.getpass.getpass")
    def test_session_open_with_mode(self, mock_getpass, mock_create, mock_start_investigation):
        """Test session creation with conversational mode."""
        mock_getpass.side_effect = ["test-password", "test-password"]

        mock_metadata = MagicMock()
        mock_metadata.name = "session-abcd"
        mock_metadata.mode = "conversational"
        
        mock_session = MagicMock()
        mock_session.session_id = "INC-ABCD"
        mock_session.session_path = Path("/home/user/.aletheia/sessions/INC-ABCD")
        mock_session.get_metadata.return_value = mock_metadata
        mock_create.return_value = mock_session

        result = runner.invoke(
            app, ["session", "open", "--mode", "conversational"]
        )

        assert result.exit_code == 0
        mock_create.assert_called_once_with(
            name=None, mode="conversational", password="test-password"
        )
        mock_start_investigation.assert_called_once()

    @patch("aletheia.cli.getpass.getpass")
    def test_session_open_invalid_mode(self, mock_getpass):
        """Test session creation with invalid mode."""
        mock_getpass.side_effect = ["test-password", "test-password"]

        result = runner.invoke(app, ["session", "open", "--mode", "invalid"])

        assert result.exit_code == 1
        assert "Error" in result.stderr
        assert "guided" in result.stderr or "conversational" in result.stderr

    @patch("aletheia.cli.getpass.getpass")
    def test_session_open_password_mismatch(self, mock_getpass):
        """Test session creation with password mismatch."""
        mock_getpass.side_effect = ["password1", "password2"]

        result = runner.invoke(app, ["session", "open"])

        assert result.exit_code == 1
        assert "Error" in result.stderr
        assert "do not match" in result.stderr

    @patch("aletheia.cli.getpass.getpass")
    def test_session_open_empty_password(self, mock_getpass):
        """Test session creation with empty password."""
        mock_getpass.side_effect = ["", ""]

        result = runner.invoke(app, ["session", "open"])

        assert result.exit_code == 1
        assert "Error" in result.stderr
        assert "cannot be empty" in result.stderr

    @patch("aletheia.cli.Session.create")
    @patch("aletheia.cli.getpass.getpass")
    def test_session_open_already_exists(self, mock_getpass, mock_create):
        """Test session creation when session already exists."""
        mock_getpass.side_effect = ["test-password", "test-password"]
        mock_create.side_effect = FileExistsError("Session INC-1234 already exists")

        result = runner.invoke(app, ["session", "open"])

        assert result.exit_code == 1
        assert "Error" in result.stderr
        assert "already exists" in result.stderr


class TestSessionListCommand:
    """Tests for session list command."""

    @patch("aletheia.cli.Session.list_sessions")
    def test_session_list_empty(self, mock_list):
        """Test listing when no sessions exist."""
        mock_list.return_value = []

        result = runner.invoke(app, ["session", "list"])

        assert result.exit_code == 0
        assert "No sessions found" in result.stdout

    @patch("aletheia.cli.Session.list_sessions")
    def test_session_list_with_sessions(self, mock_list):
        """Test listing with existing sessions."""
        mock_list.return_value = [
            {
                "id": "INC-1234",
                "path": "/Users/test/.aletheia/sessions/INC-1234",
                "created": "2025-10-14T10:00:00.123456",
            },
            {
                "id": "INC-5678",
                "path": "/Users/test/.aletheia/sessions/INC-5678",
                "created": "2025-10-14T11:00:00.123456",
            },
        ]

        result = runner.invoke(app, ["session", "list"])

        assert result.exit_code == 0
        assert "INC-1234" in result.stdout
        assert "INC-5678" in result.stdout

    @patch("aletheia.cli.Session.list_sessions")
    def test_session_list_error(self, mock_list):
        """Test listing with error."""
        mock_list.side_effect = Exception("Test error")

        result = runner.invoke(app, ["session", "list"])

        assert result.exit_code == 1
        assert "Error" in result.stderr


class TestSessionResumeCommand:
    """Tests for session resume command."""

    @patch("aletheia.cli.Session.resume")
    @patch("aletheia.cli.getpass.getpass")
    @patch("aletheia.cli._start_investigation")
    def test_session_resume_basic(self, mock_start_investigation, mock_getpass, mock_resume):
        """Test resuming a session."""
        mock_getpass.return_value = "test-password"

        mock_metadata = MagicMock()
        mock_metadata.name = "production-outage"
        mock_metadata.mode = "guided"
        
        mock_session = MagicMock()
        mock_session.session_id = "INC-1234"
        mock_session.get_metadata.return_value = mock_metadata
        mock_resume.return_value = mock_session

        result = runner.invoke(app, ["session", "resume", "INC-1234"])

        assert result.exit_code == 0
        assert "INC-1234" in result.stdout
        assert "resumed" in result.stdout
        assert "production-outage" in result.stdout
        mock_resume.assert_called_once_with(session_id="INC-1234", password="test-password")
        mock_start_investigation.assert_called_once()

    @patch("aletheia.cli.getpass.getpass")
    def test_session_resume_empty_password(self, mock_getpass):
        """Test resuming with empty password."""
        mock_getpass.return_value = ""

        result = runner.invoke(app, ["session", "resume", "INC-1234"])

        assert result.exit_code == 1
        assert "Error" in result.stderr

    @patch("aletheia.cli.Session.resume")
    @patch("aletheia.cli.getpass.getpass")
    def test_session_resume_not_found(self, mock_getpass, mock_resume):
        """Test resuming non-existent session."""
        mock_getpass.return_value = "test-password"
        mock_resume.side_effect = FileNotFoundError("Session INC-9999 not found")

        result = runner.invoke(app, ["session", "resume", "INC-9999"])

        assert result.exit_code == 1
        assert "Error" in result.stderr

    @patch("aletheia.cli.Session.resume")
    @patch("aletheia.cli.getpass.getpass")
    def test_session_resume_wrong_password(self, mock_getpass, mock_resume):
        """Test resuming with wrong password."""
        mock_getpass.return_value = "wrong-password"
        mock_resume.side_effect = ValueError("Invalid password")

        result = runner.invoke(app, ["session", "resume", "INC-1234"])

        assert result.exit_code == 1
        assert "Error" in result.stderr


class TestSessionDeleteCommand:
    """Tests for session delete command."""

    @patch("aletheia.cli.Session.delete")
    def test_session_delete_with_yes_flag(self, mock_delete):
        """Test deleting session with --yes flag."""
        result = runner.invoke(app, ["session", "delete", "INC-1234", "--yes"])

        assert result.exit_code == 0
        assert "deleted" in result.stdout
        mock_delete.assert_called_once_with("INC-1234")

    @patch("aletheia.cli.Session.delete")
    def test_session_delete_with_confirmation(self, mock_delete):
        """Test deleting session with confirmation."""
        result = runner.invoke(app, ["session", "delete", "INC-1234"], input="y\n")

        assert result.exit_code == 0
        assert "deleted" in result.stdout
        mock_delete.assert_called_once_with("INC-1234")

    def test_session_delete_cancelled(self):
        """Test cancelling session deletion."""
        result = runner.invoke(app, ["session", "delete", "INC-1234"], input="n\n")

        assert result.exit_code == 0
        assert "cancelled" in result.stdout

    @patch("aletheia.cli.Session.delete")
    def test_session_delete_not_found(self, mock_delete):
        """Test deleting non-existent session."""
        mock_delete.side_effect = FileNotFoundError("Session not found")

        result = runner.invoke(app, ["session", "delete", "INC-9999", "--yes"])

        assert result.exit_code == 1
        assert "Error" in result.stderr


class TestSessionExportCommand:
    """Tests for session export command."""

    @patch("aletheia.cli.Session.resume")
    @patch("aletheia.cli.getpass.getpass")
    def test_session_export_basic(self, mock_getpass, mock_resume):
        """Test exporting a session."""
        mock_getpass.return_value = "test-password"

        mock_session = MagicMock()
        mock_session.session_id = "INC-1234"
        output_path = Path("/tmp/INC-1234.tar.gz.enc")
        mock_session.export.return_value = output_path
        mock_resume.return_value = mock_session

        result = runner.invoke(app, ["session", "export", "INC-1234"])

        assert result.exit_code == 0
        assert "exported" in result.stdout
        assert str(output_path) in result.stdout
        mock_session.export.assert_called_once_with(output_path=None)

    @patch("aletheia.cli.Session.resume")
    @patch("aletheia.cli.getpass.getpass")
    def test_session_export_with_output_path(self, mock_getpass, mock_resume):
        """Test exporting with custom output path."""
        mock_getpass.return_value = "test-password"

        mock_session = MagicMock()
        mock_session.session_id = "INC-1234"
        output_path = Path("/custom/path/export.enc")
        mock_session.export.return_value = output_path
        mock_resume.return_value = mock_session

        result = runner.invoke(
            app, ["session", "export", "INC-1234", "--output", "/custom/path/export.enc"]
        )

        assert result.exit_code == 0
        assert "exported" in result.stdout
        mock_session.export.assert_called_once()

    @patch("aletheia.cli.Session.resume")
    @patch("aletheia.cli.getpass.getpass")
    def test_session_export_wrong_password(self, mock_getpass, mock_resume):
        """Test export with wrong password."""
        mock_getpass.return_value = "wrong-password"
        mock_resume.side_effect = ValueError("Invalid password")

        result = runner.invoke(app, ["session", "export", "INC-1234"])

        assert result.exit_code == 1
        assert "Error" in result.stderr


class TestSessionImportCommand:
    """Tests for session import command."""

    @patch("aletheia.cli.Session.import_session")
    @patch("aletheia.cli.getpass.getpass")
    @patch("pathlib.Path.exists")
    def test_session_import_basic(self, mock_exists, mock_getpass, mock_import):
        """Test importing a session."""
        mock_exists.return_value = True
        mock_getpass.return_value = "test-password"

        mock_session = MagicMock()
        mock_session.session_id = "INC-1234"
        mock_session.session_path = Path("/home/user/.aletheia/sessions/INC-1234")
        mock_metadata = MagicMock()
        mock_metadata.name = "imported-session"
        mock_metadata.mode = "guided"
        mock_session.get_metadata.return_value = mock_metadata
        mock_import.return_value = mock_session

        result = runner.invoke(app, ["session", "import", "/path/to/archive.tar.gz.enc"])

        assert result.exit_code == 0
        assert "imported" in result.stdout
        assert "INC-1234" in result.stdout
        mock_import.assert_called_once()

    @patch("pathlib.Path.exists")
    def test_session_import_file_not_found(self, mock_exists):
        """Test importing non-existent file."""
        mock_exists.return_value = False

        result = runner.invoke(app, ["session", "import", "/path/to/nonexistent.tar.gz.enc"])

        assert result.exit_code == 1
        assert "Error" in result.stderr

    @patch("aletheia.cli.Session.import_session")
    @patch("aletheia.cli.getpass.getpass")
    @patch("pathlib.Path.exists")
    def test_session_import_already_exists(self, mock_exists, mock_getpass, mock_import):
        """Test importing when session already exists."""
        mock_exists.return_value = True
        mock_getpass.return_value = "test-password"
        mock_import.side_effect = FileExistsError("Session INC-1234 already exists")

        result = runner.invoke(app, ["session", "import", "/path/to/archive.tar.gz.enc"])

        assert result.exit_code == 1
        assert "Error" in result.stderr

    @patch("aletheia.cli.Session.import_session")
    @patch("aletheia.cli.getpass.getpass")
    @patch("pathlib.Path.exists")
    def test_session_import_wrong_password(self, mock_exists, mock_getpass, mock_import):
        """Test import with wrong password."""
        mock_exists.return_value = True
        mock_getpass.return_value = "wrong-password"
        mock_import.side_effect = ValueError("Invalid password")

        result = runner.invoke(app, ["session", "import", "/path/to/archive.tar.gz.enc"])

        assert result.exit_code == 1
        assert "Error" in result.stderr

    @patch("aletheia.cli.getpass.getpass")
    @patch("pathlib.Path.exists")
    def test_session_import_empty_password(self, mock_exists, mock_getpass):
        """Test import with empty password."""
        mock_exists.return_value = True
        mock_getpass.return_value = ""

        result = runner.invoke(app, ["session", "import", "/path/to/archive.tar.gz.enc"])

        assert result.exit_code == 1
        assert "Error" in result.stderr
