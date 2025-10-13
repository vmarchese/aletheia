"""
Unit tests for session management module.
"""

import json
import shutil
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from aletheia.session import (
    Session,
    SessionError,
    SessionExistsError,
    SessionMetadata,
    SessionNotFoundError,
)


@pytest.fixture
def temp_session_dir(tmp_path):
    """Provide a temporary session directory."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    yield session_dir
    # Cleanup
    if session_dir.exists():
        shutil.rmtree(session_dir)


@pytest.fixture
def test_password():
    """Provide a test password."""
    return "test-password-123"


class TestSessionMetadata:
    """Tests for SessionMetadata dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        metadata = SessionMetadata(
            id="INC-TEST",
            name="Test Session",
            created="2025-01-01T00:00:00",
            updated="2025-01-01T00:00:00",
            status="active",
            salt="dGVzdHNhbHQ=",
            mode="guided",
        )

        result = metadata.to_dict()

        assert result["id"] == "INC-TEST"
        assert result["name"] == "Test Session"
        assert result["status"] == "active"
        assert result["mode"] == "guided"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "id": "INC-TEST",
            "name": "Test Session",
            "created": "2025-01-01T00:00:00",
            "updated": "2025-01-01T00:00:00",
            "status": "active",
            "salt": "dGVzdHNhbHQ=",
            "mode": "guided",
        }

        metadata = SessionMetadata.from_dict(data)

        assert metadata.id == "INC-TEST"
        assert metadata.name == "Test Session"
        assert metadata.status == "active"
        assert metadata.mode == "guided"


class TestSessionCreation:
    """Tests for session creation."""

    def test_create_session(self, temp_session_dir, test_password):
        """Test creating a new session."""
        session = Session.create(
            name="Test Session",
            mode="guided",
            password=test_password,
            session_dir=temp_session_dir,
        )

        assert session.session_id.startswith("INC-")
        assert session.session_path.exists()
        assert session.metadata_file.exists()
        assert session.data_dir.exists()

    def test_create_session_directory_structure(self, temp_session_dir, test_password):
        """Test session directory structure is created correctly."""
        session = Session.create(
            password=test_password, session_dir=temp_session_dir
        )

        # Check directories
        assert (session.data_dir / "logs").exists()
        assert (session.data_dir / "metrics").exists()
        assert (session.data_dir / "traces").exists()

    def test_create_session_without_password(self, temp_session_dir):
        """Test creating session without password raises error."""
        with pytest.raises(SessionError, match="Password required"):
            Session.create(session_dir=temp_session_dir)

    def test_create_session_with_name(self, temp_session_dir, test_password):
        """Test creating session with custom name."""
        session = Session.create(
            name="My Investigation",
            password=test_password,
            session_dir=temp_session_dir,
        )

        metadata = session.get_metadata()
        assert metadata.name == "My Investigation"

    def test_create_session_unique_ids(self, temp_session_dir, test_password):
        """Test that created sessions have unique IDs."""
        # Create multiple sessions and verify they all have unique IDs
        session1 = Session.create(password=test_password, session_dir=temp_session_dir)
        session2 = Session.create(password=test_password, session_dir=temp_session_dir)
        session3 = Session.create(password=test_password, session_dir=temp_session_dir)

        assert session1.session_id != session2.session_id
        assert session1.session_id != session3.session_id
        assert session2.session_id != session3.session_id

    def test_session_id_format(self, temp_session_dir, test_password):
        """Test session ID has correct format."""
        session = Session.create(password=test_password, session_dir=temp_session_dir)

        # Should be INC-XXXX where XXXX is 4 hex characters
        assert len(session.session_id) == 8
        assert session.session_id.startswith("INC-")
        # Check hex characters
        hex_part = session.session_id[4:]
        assert len(hex_part) == 4
        int(hex_part, 16)  # Should not raise ValueError

    def test_session_id_uniqueness(self, temp_session_dir, test_password):
        """Test generated session IDs are unique."""
        ids = set()
        for _ in range(10):
            session_id = Session._generate_session_id(temp_session_dir)
            assert session_id not in ids
            ids.add(session_id)


class TestSessionResume:
    """Tests for resuming sessions."""

    def test_resume_session(self, temp_session_dir, test_password):
        """Test resuming an existing session."""
        # Create session
        session1 = Session.create(
            name="Original", password=test_password, session_dir=temp_session_dir
        )
        session_id = session1.session_id

        # Resume session
        session2 = Session.resume(
            session_id, password=test_password, session_dir=temp_session_dir
        )

        assert session2.session_id == session_id
        metadata = session2.get_metadata()
        assert metadata.name == "Original"

    def test_resume_nonexistent_session(self, temp_session_dir, test_password):
        """Test resuming nonexistent session raises error."""
        with pytest.raises(SessionNotFoundError):
            Session.resume(
                "INC-XXXX", password=test_password, session_dir=temp_session_dir
            )

    def test_resume_with_wrong_password(self, temp_session_dir, test_password):
        """Test resuming with wrong password raises error."""
        # Create session
        session = Session.create(password=test_password, session_dir=temp_session_dir)

        # Try to resume with wrong password
        with pytest.raises(Exception):  # Will raise decryption error
            Session.resume(
                session.session_id, password="wrong-password", session_dir=temp_session_dir
            )


class TestSessionList:
    """Tests for listing sessions."""

    def test_list_empty(self, temp_session_dir):
        """Test listing sessions when none exist."""
        sessions = Session.list_sessions(session_dir=temp_session_dir)
        assert sessions == []

    def test_list_sessions(self, temp_session_dir, test_password):
        """Test listing multiple sessions."""
        # Create multiple sessions
        session1 = Session.create(password=test_password, session_dir=temp_session_dir)
        session2 = Session.create(password=test_password, session_dir=temp_session_dir)

        sessions = Session.list_sessions(session_dir=temp_session_dir)

        assert len(sessions) == 2
        ids = [s["id"] for s in sessions]
        assert session1.session_id in ids
        assert session2.session_id in ids

    def test_list_sessions_sorted(self, temp_session_dir, test_password):
        """Test sessions are sorted by creation time."""
        # Create sessions
        Session.create(password=test_password, session_dir=temp_session_dir)
        Session.create(password=test_password, session_dir=temp_session_dir)

        sessions = Session.list_sessions(session_dir=temp_session_dir)

        # Should be sorted by created timestamp (newest first)
        timestamps = [s["created"] for s in sessions]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_list_nonexistent_directory(self):
        """Test listing from nonexistent directory returns empty list."""
        sessions = Session.list_sessions(session_dir=Path("/nonexistent"))
        assert sessions == []


class TestSessionDelete:
    """Tests for deleting sessions."""

    def test_delete_session(self, temp_session_dir, test_password):
        """Test deleting a session."""
        session = Session.create(password=test_password, session_dir=temp_session_dir)
        session_path = session.session_path

        assert session_path.exists()

        session.delete()

        assert not session_path.exists()

    def test_delete_nonexistent_session(self, temp_session_dir):
        """Test deleting nonexistent session raises error."""
        session = Session("INC-XXXX", session_dir=temp_session_dir)

        with pytest.raises(SessionNotFoundError):
            session.delete()

    def test_delete_removes_all_data(self, temp_session_dir, test_password):
        """Test deleting session removes all data."""
        session = Session.create(password=test_password, session_dir=temp_session_dir)

        # Create some data files
        log_file = session.data_dir / "logs" / "test.log"
        log_file.write_text("test log")

        session.delete()

        assert not session.session_path.exists()
        assert not log_file.exists()


class TestSessionExport:
    """Tests for exporting sessions."""

    def test_export_session(self, temp_session_dir, test_password, tmp_path):
        """Test exporting a session."""
        session = Session.create(password=test_password, session_dir=temp_session_dir)

        output_path = tmp_path / "export.tar.gz.enc"
        result_path = session.export(output_path)

        assert result_path == output_path
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_export_session_default_path(self, temp_session_dir, test_password):
        """Test exporting with default output path."""
        session = Session.create(password=test_password, session_dir=temp_session_dir)

        result_path = session.export()

        expected_name = f"{session.session_id}.tar.gz.enc"
        assert result_path.name == expected_name
        assert result_path.exists()

        # Cleanup
        result_path.unlink()

    def test_export_nonexistent_session(self, temp_session_dir, test_password):
        """Test exporting nonexistent session raises error."""
        session = Session("INC-XXXX", session_dir=temp_session_dir, password=test_password)

        with pytest.raises(SessionNotFoundError):
            session.export()

    def test_export_without_password(self, temp_session_dir, test_password):
        """Test exporting without password raises error."""
        session = Session.create(password=test_password, session_dir=temp_session_dir)

        # Create new session object without password
        session2 = Session(session.session_id, session_dir=temp_session_dir)

        with pytest.raises(SessionError, match="password required"):
            session2.export()


class TestSessionImport:
    """Tests for importing sessions."""

    def test_import_session(self, temp_session_dir, test_password, tmp_path):
        """Test importing a session."""
        # Create and export session
        session1 = Session.create(
            name="Export Test", password=test_password, session_dir=temp_session_dir
        )
        session1_id = session1.session_id

        archive_path = tmp_path / "export.tar.gz.enc"
        session1.export(archive_path)

        # Delete original
        session1.delete()

        # Import session
        session2 = Session.import_session(
            archive_path, password=test_password, session_dir=temp_session_dir
        )

        assert session2.session_id == session1_id
        assert session2.session_path.exists()

        metadata = session2.get_metadata()
        assert metadata.name == "Export Test"

    def test_import_nonexistent_archive(self, temp_session_dir, test_password):
        """Test importing nonexistent archive raises error."""
        with pytest.raises(SessionError, match="Archive not found"):
            Session.import_session(
                Path("/nonexistent.tar.gz.enc"),
                password=test_password,
                session_dir=temp_session_dir,
            )

    def test_import_duplicate_session(self, temp_session_dir, test_password, tmp_path):
        """Test importing when session already exists raises error."""
        # Create and export session
        session = Session.create(password=test_password, session_dir=temp_session_dir)

        archive_path = tmp_path / "export.tar.gz.enc"
        session.export(archive_path)

        # Try to import while original still exists
        with pytest.raises(SessionExistsError):
            Session.import_session(
                archive_path, password=test_password, session_dir=temp_session_dir
            )


class TestSessionMetadataOperations:
    """Tests for session metadata operations."""

    def test_get_metadata(self, temp_session_dir, test_password):
        """Test getting session metadata."""
        session = Session.create(
            name="Test", password=test_password, session_dir=temp_session_dir
        )

        metadata = session.get_metadata()

        assert metadata.id == session.session_id
        assert metadata.name == "Test"
        assert metadata.status == "active"
        assert metadata.mode == "guided"

    def test_update_status(self, temp_session_dir, test_password):
        """Test updating session status."""
        session = Session.create(password=test_password, session_dir=temp_session_dir)

        session.update_status("completed")

        metadata = session.get_metadata()
        assert metadata.status == "completed"

    def test_update_status_invalid(self, temp_session_dir, test_password):
        """Test updating to invalid status raises error."""
        session = Session.create(password=test_password, session_dir=temp_session_dir)

        with pytest.raises(SessionError, match="Invalid status"):
            session.update_status("invalid")

    def test_metadata_timestamps(self, temp_session_dir, test_password):
        """Test metadata timestamps are updated."""
        session = Session.create(password=test_password, session_dir=temp_session_dir)

        metadata1 = session.get_metadata()
        created_time = datetime.fromisoformat(metadata1.created)

        # Update status to trigger metadata save
        session.update_status("completed")

        metadata2 = session.get_metadata()
        updated_time = datetime.fromisoformat(metadata2.updated)

        # Updated time should be >= created time
        assert updated_time >= created_time


class TestSessionEncryption:
    """Tests for session encryption."""

    def test_metadata_encrypted(self, temp_session_dir, test_password):
        """Test metadata file is encrypted."""
        session = Session.create(password=test_password, session_dir=temp_session_dir)

        # Read raw file content
        with open(session.metadata_file, "rb") as f:
            content = f.read()

        # Should not contain plaintext session ID or name
        assert session.session_id.encode() not in content
        assert b"guided" not in content

    def test_different_passwords_different_encryption(
        self, temp_session_dir, test_password
    ):
        """Test different passwords produce different encrypted data."""
        # Create two sessions with different passwords
        session1 = Session.create(password="password1", session_dir=temp_session_dir)
        session2 = Session.create(password="password2", session_dir=temp_session_dir)

        # Read encrypted metadata
        with open(session1.metadata_file, "rb") as f:
            encrypted1 = f.read()

        with open(session2.metadata_file, "rb") as f:
            encrypted2 = f.read()

        # Should be different
        assert encrypted1 != encrypted2


class TestSessionEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_concurrent_session_creation(self, temp_session_dir, test_password):
        """Test creating multiple sessions doesn't cause ID collisions."""
        sessions = []
        for _ in range(5):
            session = Session.create(password=test_password, session_dir=temp_session_dir)
            sessions.append(session)

        # All IDs should be unique
        ids = [s.session_id for s in sessions]
        assert len(ids) == len(set(ids))

    def test_session_without_password_operations(self, temp_session_dir, test_password):
        """Test operations without password raise appropriate errors."""
        session = Session.create(password=test_password, session_dir=temp_session_dir)

        # Create new session object without password
        session2 = Session(session.session_id, session_dir=temp_session_dir)

        with pytest.raises(SessionError, match="Metadata not loaded"):
            session2.get_metadata()

    def test_corrupted_metadata(self, temp_session_dir, test_password):
        """Test handling of corrupted metadata file."""
        session = Session.create(password=test_password, session_dir=temp_session_dir)

        # Corrupt metadata file
        with open(session.metadata_file, "wb") as f:
            f.write(b"corrupted data")

        # Create new session object
        session2 = Session(
            session.session_id, session_dir=temp_session_dir, password=test_password
        )

        # Should raise decryption error
        with pytest.raises(Exception):
            session2._load_metadata()
