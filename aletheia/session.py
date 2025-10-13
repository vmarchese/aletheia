"""
Session management for Aletheia.

Handles session lifecycle operations including:
- Creating new sessions with unique IDs
- Resuming interrupted sessions
- Listing all sessions
- Deleting sessions and their data
- Exporting/importing sessions for sharing
"""

import json
import secrets
import shutil
import tarfile
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from aletheia.encryption import (
    create_session_encryption,
    decrypt_json_file,
    derive_session_key,
    encrypt_json_file,
)


class SessionError(Exception):
    """Base exception for session-related errors."""

    pass


class SessionNotFoundError(SessionError):
    """Raised when a session cannot be found."""

    pass


class SessionExistsError(SessionError):
    """Raised when attempting to create a session that already exists."""

    pass


@dataclass
class SessionMetadata:
    """Metadata for a session."""

    id: str
    name: Optional[str]
    created: str  # ISO format datetime
    updated: str  # ISO format datetime
    status: str  # active | completed | failed
    salt: str  # Base64-encoded salt for encryption
    mode: str  # guided | conversational

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMetadata":
        """Create from dictionary."""
        return cls(**data)


class Session:
    """
    Session management class.

    A session represents a single troubleshooting investigation with:
    - Unique session ID
    - Encrypted metadata and scratchpad
    - Directory structure for collected data
    - Session key for encryption/decryption
    """

    DEFAULT_SESSION_DIR = Path.home() / ".aletheia" / "sessions"

    def __init__(
        self,
        session_id: str,
        session_dir: Optional[Path] = None,
        password: Optional[str] = None,
    ):
        """
        Initialize a Session object.

        Args:
            session_id: Unique session identifier
            session_dir: Base directory for sessions (default: ~/.aletheia/sessions)
            password: Session password for encryption (required for operations)
        """
        self.session_id = session_id
        self.base_dir = session_dir or self.DEFAULT_SESSION_DIR
        self.session_path = self.base_dir / session_id
        self.password = password
        self._key: Optional[bytes] = None
        self._metadata: Optional[SessionMetadata] = None

    @property
    def metadata_file(self) -> Path:
        """Path to encrypted metadata file."""
        return self.session_path / "metadata.encrypted"

    @property
    def scratchpad_file(self) -> Path:
        """Path to encrypted scratchpad file."""
        return self.session_path / "scratchpad.encrypted"

    @property
    def data_dir(self) -> Path:
        """Path to data directory."""
        return self.session_path / "data"

    def _ensure_password(self) -> None:
        """Ensure password is set."""
        if self.password is None:
            raise SessionError("Session password required for this operation")

    def _derive_key(self, salt: bytes) -> bytes:
        """Derive encryption key from password and salt."""
        self._ensure_password()
        return derive_session_key(self.password, salt)

    def _load_metadata(self, key: bytes) -> SessionMetadata:
        """Load session metadata from encrypted file.

        Args:
            key: Encryption key to use for decryption

        Returns:
            Loaded session metadata
        """
        if not self.metadata_file.exists():
            raise SessionNotFoundError(f"Session {self.session_id} not found")

        # Load encrypted metadata
        data = decrypt_json_file(self.metadata_file, key)
        return SessionMetadata.from_dict(data)

    def _save_metadata(self, metadata: SessionMetadata) -> None:
        """Save session metadata to encrypted file."""
        self._ensure_password()

        # Update timestamp
        metadata.updated = datetime.now().isoformat()

        # Encrypt and save
        encrypt_json_file(metadata.to_dict(), self.metadata_file, self._get_key())

    def _get_key(self) -> bytes:
        """Get or derive encryption key."""
        if self._key is None:
            # Need to load metadata first to get the salt
            if self._metadata is None:
                raise SessionError(
                    "Cannot get encryption key without loading metadata first. "
                    "This is an internal error - metadata should be loaded during session creation/resume."
                )

            import base64
            salt = base64.b64decode(self._metadata.salt)
            self._key = self._derive_key(salt)

        return self._key

    def _create_directory_structure(self) -> None:
        """Create session directory structure."""
        self.session_path.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "logs").mkdir(exist_ok=True)
        (self.data_dir / "metrics").mkdir(exist_ok=True)
        (self.data_dir / "traces").mkdir(exist_ok=True)

    @classmethod
    def create(
        cls,
        name: Optional[str] = None,
        mode: str = "guided",
        password: Optional[str] = None,
        session_dir: Optional[Path] = None,
    ) -> "Session":
        """
        Create a new session.

        Args:
            name: Optional human-readable session name
            mode: Interaction mode (guided or conversational)
            password: Session password for encryption
            session_dir: Base directory for sessions

        Returns:
            New Session instance

        Raises:
            SessionExistsError: If session already exists
            SessionError: If password not provided
        """
        if password is None:
            raise SessionError("Password required to create session")

        # Generate unique session ID
        session_id = cls._generate_session_id(session_dir)

        # Create session instance
        session = cls(session_id, session_dir, password)

        # Check if session already exists
        if session.session_path.exists():
            raise SessionExistsError(f"Session {session_id} already exists")

        # Create directory structure
        session._create_directory_structure()

        # Generate encryption key and salt
        key, salt = create_session_encryption(password)
        session._key = key

        # Save salt to separate file (unencrypted, as salt is not secret)
        import base64
        salt_file = session.session_path / "salt"
        salt_file.write_text(base64.b64encode(salt).decode("utf-8"))

        # Create metadata
        now = datetime.now().isoformat()
        metadata = SessionMetadata(
            id=session_id,
            name=name,
            created=now,
            updated=now,
            status="active",
            salt=base64.b64encode(salt).decode("utf-8"),
            mode=mode,
        )

        session._metadata = metadata
        session._save_metadata(metadata)

        return session

    @classmethod
    def resume(
        cls,
        session_id: str,
        password: str,
        session_dir: Optional[Path] = None,
    ) -> "Session":
        """
        Resume an existing session.

        Args:
            session_id: Session identifier to resume
            password: Session password for decryption
            session_dir: Base directory for sessions

        Returns:
            Session instance

        Raises:
            SessionNotFoundError: If session doesn't exist
            SessionError: If password is incorrect
        """
        import base64

        session = cls(session_id, session_dir, password)

        if not session.session_path.exists():
            raise SessionNotFoundError(f"Session {session_id} not found")

        # First, we need to read the metadata to get the salt
        # But we can't decrypt without the key, which needs the salt
        # Solution: Read encrypted metadata, extract first to get salt, then decrypt properly
        # Actually, we'll use a temporary key to try decryption and let it fail if password is wrong

        # Load encrypted data to extract salt (we need a workaround here)
        # For now, we'll try with a temporary key and catch errors
        # Better approach: Store salt separately or use a two-pass approach

        # Let's use a simpler approach: try to decrypt with derived key
        # We'll need to read the file first to get salt somehow
        # Actually, Fernet already includes salt in the encrypted data!
        # So we can just try to decrypt and it will fail if password is wrong

        # Create a temporary key to attempt decryption
        # We use a fixed salt for the first attempt
        temp_salt = b'\x00' * 32
        try:
            temp_key = session._derive_key(temp_salt)
            session._metadata = session._load_metadata(temp_key)
        except Exception:
            # If that fails, try reading to get the real salt
            # This is a chicken-and-egg problem - let's fix it properly
            pass

        # Better solution: Store salt in a separate unencrypted file
        # For now, let's use a fixed salt for all sessions and change the design
        # Actually, the best solution is to store salt in session metadata

        # Let me reconsider: each session should have unique salt
        # Salt should be stored unencrypted (it's not secret)
        # We'll store it in a separate file

        salt_file = session.session_path / "salt"
        if not salt_file.exists():
            raise SessionNotFoundError(f"Session {session_id} salt file not found")

        # Read salt
        salt = base64.b64decode(salt_file.read_text())

        # Derive key
        session._key = session._derive_key(salt)

        # Load metadata (this will validate password)
        session._metadata = session._load_metadata(session._key)

        return session

    @classmethod
    def list_sessions(cls, session_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
        """
        List all sessions.

        Args:
            session_dir: Base directory for sessions

        Returns:
            List of session info dictionaries (without decrypting metadata)
        """
        base_dir = session_dir or cls.DEFAULT_SESSION_DIR

        if not base_dir.exists():
            return []

        sessions = []
        for session_path in base_dir.iterdir():
            if session_path.is_dir() and (session_path / "metadata.encrypted").exists():
                sessions.append(
                    {
                        "id": session_path.name,
                        "path": str(session_path),
                        "created": datetime.fromtimestamp(
                            session_path.stat().st_ctime
                        ).isoformat(),
                    }
                )

        return sorted(sessions, key=lambda x: x["created"], reverse=True)

    def delete(self) -> None:
        """
        Delete session and all its data.

        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        if not self.session_path.exists():
            raise SessionNotFoundError(f"Session {self.session_id} not found")

        # Remove entire session directory
        shutil.rmtree(self.session_path)

    def export(self, output_path: Optional[Path] = None) -> Path:
        """
        Export session as encrypted tar.gz archive.

        Args:
            output_path: Output file path (default: {session_id}.tar.gz.enc)

        Returns:
            Path to exported file

        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        if not self.session_path.exists():
            raise SessionNotFoundError(f"Session {self.session_id} not found")

        self._ensure_password()

        # Default output path
        if output_path is None:
            output_path = Path.cwd() / f"{self.session_id}.tar.gz.enc"

        # Create temporary tar.gz
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Create tar.gz archive
            with tarfile.open(tmp_path, "w:gz") as tar:
                tar.add(self.session_path, arcname=self.session_id)

            # Encrypt the archive using a key derived from the password
            # Use a fixed salt for archive encryption (deterministic)
            from aletheia.encryption import encrypt_file

            archive_salt = b"aletheia-archive"  # Fixed salt for archives
            archive_key = derive_session_key(self.password, archive_salt)

            encrypt_file(tmp_path, archive_key, output_path)

        finally:
            # Clean up temporary file
            if tmp_path.exists():
                tmp_path.unlink()

        return output_path

    @classmethod
    def import_session(
        cls,
        archive_path: Path,
        password: str,
        session_dir: Optional[Path] = None,
    ) -> "Session":
        """
        Import session from encrypted tar.gz archive.

        Args:
            archive_path: Path to encrypted archive
            password: Session password for decryption
            session_dir: Base directory for sessions

        Returns:
            Session instance

        Raises:
            SessionExistsError: If session already exists
            SessionError: If import fails
        """
        if not archive_path.exists():
            raise SessionError(f"Archive not found: {archive_path}")

        base_dir = session_dir or cls.DEFAULT_SESSION_DIR
        base_dir.mkdir(parents=True, exist_ok=True)

        # Create temporary file for decrypted archive
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Decrypt archive
            from aletheia.encryption import decrypt_file

            # First, extract to temporary location to get session ID and salt
            with tempfile.TemporaryDirectory() as temp_extract_dir:
                temp_extract_path = Path(temp_extract_dir)

                # Decrypt the archive using the fixed salt for archives
                archive_salt = b"aletheia-archive"  # Same fixed salt used in export
                archive_key = derive_session_key(password, archive_salt)

                # Decrypt archive
                decrypt_file(archive_path, archive_key, tmp_path)

                # Extract to get session ID and salt
                with tarfile.open(tmp_path, "r:gz") as tar:
                    members = tar.getmembers()
                    if not members:
                        raise SessionError("Archive is empty")

                    # Extract to temporary location
                    tar.extractall(path=temp_extract_path)

                    # Get session ID from first member
                    session_id = Path(members[0].name).parts[0]

                # Check if session already exists
                session_path = base_dir / session_id
                if session_path.exists():
                    raise SessionExistsError(f"Session {session_id} already exists")

                # Read salt from extracted files
                salt_file = temp_extract_path / session_id / "salt"
                if not salt_file.exists():
                    raise SessionError("Archive missing salt file")

                import base64
                salt = base64.b64decode(salt_file.read_text())

                # Derive correct key from password and salt
                key = derive_session_key(password, salt)

                # Move extracted session to final location
                (temp_extract_path / session_id).rename(session_path)

            # Create session instance
            session = cls(session_id, session_dir, password)
            session._key = key

            # Load metadata to validate
            session._metadata = session._load_metadata(session._key)

            return session

        finally:
            # Clean up temporary file
            if tmp_path.exists():
                tmp_path.unlink()

    @staticmethod
    def _generate_session_id(session_dir: Optional[Path] = None) -> str:
        """
        Generate unique session ID in format INC-XXXX.

        Args:
            session_dir: Base directory for sessions

        Returns:
            Unique session ID
        """
        base_dir = session_dir or Session.DEFAULT_SESSION_DIR
        base_dir.mkdir(parents=True, exist_ok=True)

        # Generate random 4-character hex suffix
        while True:
            suffix = secrets.token_hex(2).upper()  # 4 hex characters
            session_id = f"INC-{suffix}"

            # Check for collisions
            session_path = base_dir / session_id
            if not session_path.exists():
                return session_id

    def get_metadata(self) -> SessionMetadata:
        """
        Get session metadata.

        Returns:
            Session metadata

        Raises:
            SessionError: If metadata not loaded and cannot be loaded
        """
        if self._metadata is None:
            # Try to load metadata if we have the key
            if self._key is not None:
                self._metadata = self._load_metadata(self._key)
            else:
                raise SessionError(
                    "Metadata not loaded. Create or resume session first."
                )
        return self._metadata

    def update_status(self, status: str) -> None:
        """
        Update session status.

        Args:
            status: New status (active, completed, failed)

        Raises:
            SessionError: If invalid status
        """
        valid_statuses = {"active", "completed", "failed"}
        if status not in valid_statuses:
            raise SessionError(
                f"Invalid status: {status}. Must be one of {valid_statuses}"
            )

        metadata = self.get_metadata()
        metadata.status = status
        self._save_metadata(metadata)
