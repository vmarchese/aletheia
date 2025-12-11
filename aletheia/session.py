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
import base64
import secrets
import shutil
import tarfile
import tempfile
import logging # Added for logging warning

from enum import Enum
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from aletheia.encryption import encrypt_file, decrypt_file
from aletheia.plugins.scratchpad.scratchpad import ScratchpadFileName
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.utils.logging import log_debug, enable_trace_logging

from aletheia.encryption import (
    create_session_encryption,
    decrypt_json_file,
    derive_session_key,
    encrypt_json_file,
    encrypt_data,
    decrypt_data
)


from aletheia.enums import SessionDataType


class SessionError(Exception):
    """Base exception for session-related errors."""


class SessionNotFoundError(SessionError):
    """Raised when a session cannot be found."""


class SessionExistsError(SessionError):
    """Raised when attempting to create a session that already exists."""


@dataclass
class SessionMetadata:
    """Metadata for a session."""

    id: str
    name: Optional[str]
    created: str  # ISO format datetime
    updated: str  # ISO format datetime
    status: str  # active | completed | failed
    salt: str  # Base64-encoded salt for encryption
    verbose: bool = False  # whether very-verbose mode (-vv) is enabled
    unsafe: bool = False  # whether plaintext mode is enabled (no encryption)
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMetadata":
        """Create from dictionary."""
        # Handle backwards compatibility for sessions without verbose field
        if "verbose" not in data:
            data["verbose"] = False
        # Handle backwards compatibility for sessions without unsafe field
        if "unsafe" not in data:
            data["unsafe"] = False
        # Handle backwards compatibility for sessions without token fields
        if "total_input_tokens" not in data:
            data["total_input_tokens"] = 0
        if "total_output_tokens" not in data:
            data["total_output_tokens"] = 0
            
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
        scratchpad: Optional[Scratchpad] = None,
        session_dir: Optional[Path] = None,
        password: Optional[str] = None,
        unsafe: bool = False,
    ):
        """
        Initialize a Session object.

        Args:
            session_id: Unique session identifier
            session_dir: Base directory for sessions (default: ~/.aletheia/sessions)
            password: Session password for encryption (required for operations unless unsafe=True)
            unsafe: If True, use plaintext storage without encryption
        """
        self.session_id = session_id
        self.base_dir = session_dir or self.DEFAULT_SESSION_DIR
        self.session_path = self.base_dir / session_id
        self.password = password
        self.unsafe = unsafe
        self._key: Optional[bytes] = None
        self._metadata: Optional[SessionMetadata] = None
        self._scratchpad = scratchpad

    @property
    def metadata_file(self) -> Path:
        """Path to metadata file. Always plaintext JSON now."""
        # We always prefer the plaintext metadata file now.
        return self.session_path / "metadata.json"

    @property
    def scratchpad_file(self) -> Path:
        """Path to scratchpad file (encrypted or plaintext based on unsafe mode)."""
        if self.unsafe:
            return self.session_path / ScratchpadFileName.PLAINTEXT.value
        return self.session_path / ScratchpadFileName.ENCRYPTED.value

    @property
    def data_dir(self) -> Path:
        """Path to data directory."""
        return self.session_path / "data"

    @property
    def scratchpad(self) -> Optional[Scratchpad]:
        """Get the scratchpad associated with this session."""
        return self._scratchpad

    @scratchpad.setter
    def scratchpad(self, value: Scratchpad) -> None:
        """Set the scratchpad associated with this session."""
        self._scratchpad = value

    def save_data(self, _type: SessionDataType, name: str, data: str) -> Path:
        """Save collected data to session data directory.

        Args:
            type: Type of data (logs, metrics, traces)
            name: Name of the data file
            data: Data content to save

        Returns:
            Path to saved data file
        """
        data_type_dir = self.data_dir / str(_type.value)
        data_type_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"{timestamp}_{name}"
        file_path = data_type_dir / name

        if self.unsafe:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(data)
        else:
            ciphertext = encrypt_data(data.encode('utf-8'), self.get_key())
            with open(file_path, 'wb') as f:
                f.write(ciphertext)

        if self._scratchpad:
            self._scratchpad.write_journal_entry("Session",
                                                 f"Saved {_type.value} data",
                                                 f"Saved {_type.value} data to {file_path}\n")
        return file_path

    def _ensure_password(self) -> None:
        """Ensure password is set (unless in unsafe mode)."""
        if not self.unsafe and self.password is None:
            raise SessionError("Session password required for this operation")

    def _derive_key(self, salt: bytes) -> bytes:
        """Derive encryption key from password and salt."""
        self._ensure_password()
        return derive_session_key(self.password, salt)

    def _load_metadata(self, key: Optional[bytes]) -> SessionMetadata:
        """Load session metadata from file (encrypted or plaintext).

        Args:
            key: Encryption key to use for decryption (None in unsafe mode)

        Returns:
            Loaded session metadata
        """
        # Check for plaintext metadata first (new standard)
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return SessionMetadata.from_dict(data)

        # Fallback: Check for encrypted metadata (legacy)
        legacy_encrypted_file = self.session_path / "metadata.encrypted"
        if legacy_encrypted_file.exists():
            if key is None:
                # If we don't have a key but need to migrate, we can't fully load yet unless unsafe was explicitly requested but file is encrypted (shouldnt happen in valid state)
                # But typically this method is called when we HAVE the key or are in unsafe mode.
                # If we are here, it means we have an encrypted file.
                raise SessionError("Cannot migrate legacy encrypted metadata without encryption key")
            
            # Decrypt legacy file
            data = decrypt_json_file(legacy_encrypted_file, key)
            
            # Auto-migrate to plaintext
            self._save_metadata(SessionMetadata.from_dict(data))
            logging.info(f"Migrated session {self.session_id} metadata to plaintext.")
            
            return SessionMetadata.from_dict(data)

        raise SessionNotFoundError(f"Session {self.session_id} metadata not found")

    def _save_metadata(self, metadata: SessionMetadata) -> None:
        """Save session metadata to file (encrypted or plaintext)."""
        self._ensure_password()

        # Update timestamp
        metadata.updated = datetime.now().isoformat()

        if self.unsafe:
            # Save plaintext metadata
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata.to_dict(), f, indent=2)
        else:
            # Save plaintext metadata (even for "authenticated" sessions, metadata is now open)
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata.to_dict(), f, indent=2)

    def get_key(self) -> Optional[bytes]:
        """Get or derive encryption key (None in unsafe mode)."""
        if self.unsafe:
            return None

        if self._key is None:
            # Need to load metadata first to get the salt
            if self._metadata is None:
                raise SessionError(
                    "Cannot get encryption key without loading metadata first. "
                    "This is an internal error - metadata should be loaded during session creation/resume."
                )

            salt = base64.b64decode(self._metadata.salt)
            self._key = self._derive_key(salt)

        return self._key

    def _validate_key(self) -> None:
        """
        Validate that the derived key is correct by attempting to decrypt known files.
        Raises SessionError if validation fails.
        """
        if self.unsafe or self._key is None:
            return

        # 1. Check for canary file (new sessions)
        canary_file = self.session_path / ".canary"
        if canary_file.exists():
            try:
                with open(canary_file, 'rb') as f:
                    data = f.read()
                decrypted = decrypt_data(data, self._key)
                if decrypted != b"ALETHEIA_CHECK":
                    raise SessionError("Invalid password (canary check failed)")
                return # Validated
            except Exception:
                raise SessionError("Invalid password")

        # 2. Check for scratchpad (existing sessions)

        # 2. Check for scratchpad (existing sessions)
        scratchpad_file = self.session_path / ScratchpadFileName.ENCRYPTED.value
        if scratchpad_file.exists():
            try:
                with open(scratchpad_file, 'rb') as f:
                    data = f.read()
                if data: # Only check if not empty
                    decrypt_data(data, self._key)
                return # Validated (or empty)
            except Exception:
                raise SessionError("Invalid password")
        
        # 3. If no encrypted files exist, we can't validate, assume OK.
        # This happens for old empty sessions. User will just create new encrypted files with this password.


    def update_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Update session token usage statistics.
        
        Args:
            input_tokens: Total accumulated input tokens
            output_tokens: Total accumulated output tokens
        """
        if self._metadata is None:
             # Try to load if key is available or unsafe
             key = self.get_key() if not self.unsafe else None
             self._metadata = self._load_metadata(key)

        self._metadata.total_input_tokens = input_tokens
        self._metadata.total_output_tokens = output_tokens
        self._metadata.updated = datetime.now().isoformat()
        
        self._save_metadata(self._metadata)

    def get_metadata(self) -> SessionMetadata:
        """Get session metadata."""
        if self._metadata is None:
            key = self.get_key() if not self.unsafe else None
            self._metadata = self._load_metadata(key)
        return self._metadata

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
        password: Optional[str] = None,
        session_dir: Optional[Path] = None,
        verbose: bool = False,
        unsafe: bool = False,
    ) -> "Session":
        """
        Create a new session.

        Args:
            name: Optional human-readable session name
            password: Session password for encryption (not required if unsafe=True)
            session_dir: Base directory for sessions
            verbose: Enable very-verbose mode (-vv) with trace logging
            unsafe: If True, use plaintext storage without encryption

        Returns:
            New Session instance

        Raises:
            SessionExistsError: If session already exists
            SessionError: If password not provided when unsafe=False
        """
        if not unsafe and password is None:
            raise SessionError("Password required to create session (unless --unsafe is used)")

        # Generate unique session ID
        session_id = cls._generate_session_id(session_dir)

        # Create session instance
        session = cls(
                      session_id=session_id,
                      session_dir=session_dir,
                      password=password,
                      unsafe=unsafe)

        # Check if session already exists
        if session.session_path.exists():
            raise SessionExistsError(f"Session {session_id} already exists")

        # Create directory structure
        session._create_directory_structure()

        if unsafe:
            # In unsafe mode, use a dummy salt (no actual encryption)
            salt = b'unsafe_mode_no_encryption'
            session._key = None
        else:
            # Generate encryption key and salt
            key, salt = create_session_encryption(password)
            session._key = key

            # Save salt to separate file (unencrypted, as salt is not secret)
            salt_file = session.session_path / "salt"
            salt_file.write_text(base64.b64encode(salt).decode("utf-8"))

            # Create canary file for password validation
            canary_file = session.session_path / ".canary"
            canary_ciphertext = encrypt_data(b"ALETHEIA_CHECK", key)
            with open(canary_file, 'wb') as f:
                f.write(canary_ciphertext)

        # Create metadata
        now = datetime.now().isoformat()
        metadata = SessionMetadata(
            id=session_id,
            name=name,
            created=now,
            updated=now,
            status="active",
            salt=base64.b64encode(salt).decode("utf-8"),
            verbose=verbose,
            unsafe=unsafe,
        )

        session._metadata = metadata
        session._save_metadata(metadata)

        # Enable trace logging if verbose
        if verbose:
            enable_trace_logging(session.session_path)

        return session

    @classmethod
    def resume(
        cls,
        session_id: str,
        password: Optional[str],
        session_dir: Optional[Path] = None,
        unsafe: bool = False,
    ) -> "Session":
        """
        Resume an existing session.

        Args:
            session_id: Session identifier to resume
            password: Session password for decryption (not required if unsafe=True)
            session_dir: Base directory for sessions
            unsafe: If True, session uses plaintext storage

        Returns:
            Session instance

        Raises:
            SessionNotFoundError: If session doesn't exist
            SessionError: If password is incorrect
        """

        session = cls(session_id=session_id,
                      session_dir=session_dir,
                      password=password,
                      unsafe=unsafe)

        if not session.session_path.exists():
            raise SessionNotFoundError(f"Session {session_id} not found")

        if unsafe:
            # In unsafe mode, no encryption - load metadata directly
            session._key = None
            session._metadata = session._load_metadata(None)
        else:
            # Encrypted mode - need salt and password
            salt_file = session.session_path / "salt"
            if not salt_file.exists():
                raise SessionNotFoundError(f"Session {session_id} salt file not found")

            # Read salt
            salt = base64.b64decode(salt_file.read_text())

            # Derive key
            session._key = session._derive_key(salt)

            # Load metadata (metadata is plaintext now, so this doesn't validate password)
            session._metadata = session._load_metadata(session._key)
            
            # Explicitly validate password
            session._validate_key()

        # Enable trace logging if sticky verbose mode is on
        if session._metadata.verbose:
            enable_trace_logging(session.session_path)

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
            if session_path.is_dir():
                metadata_path = session_path / "metadata.json"
                encrypted_metadata_path = session_path / "metadata.encrypted"
                
                session_name = None
                is_unsafe = "False" # Default to string "False" for consistency with existing return
                
                if metadata_path.exists():
                   try:
                       with open(metadata_path, 'r', encoding='utf-8') as f:
                           meta = json.load(f)
                           session_name = meta.get("name")
                           # Handle unsafe: "True"/"False" string or boolean
                           unsafe_val = meta.get("unsafe", False)
                           if isinstance(unsafe_val, str):
                               is_unsafe = unsafe_val == "True"
                           else:
                               is_unsafe = bool(unsafe_val)
                   except Exception:
                       pass
                elif encrypted_metadata_path.exists():
                    # Legacy session, name unknown without decryption
                    pass
                else:
                    # No metadata found, skip
                    continue

                sessions.append(
                    {
                        "id": session_path.name,
                        "name": session_name,
                        "path": str(session_path),
                        "created": datetime.fromtimestamp(
                            session_path.stat().st_ctime
                        ).strftime("%Y-%m-%d %H:%M:%S"),
                        "unsafe": is_unsafe,
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

            if self.unsafe:
                # In unsafe mode, just copy the tar.gz to output
                shutil.copy2(tmp_path, output_path)
            else:
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
        password: Optional[str],
        session_dir: Optional[Path] = None,
        unsafe: bool = False,
    ) -> "Session":
        """
        Import session from archive (encrypted or plaintext).

        Args:
            archive_path: Path to archive
            password: Session password for decryption (not required if unsafe=True)
            session_dir: Base directory for sessions
            unsafe: If True, archive uses plaintext storage

        Returns:
            Session instance

        Raises:
            SessionExistsError: If session already exists
            SessionError: If import fails
        """

        log_debug(f"Importing session from archive: {archive_path} unsafe: {unsafe}")
        if not archive_path.exists():
            raise SessionError(f"Archive not found: {archive_path}")

        base_dir = session_dir or cls.DEFAULT_SESSION_DIR
        base_dir.mkdir(parents=True, exist_ok=True)

        # Create temporary file for decrypted archive
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Decrypt archive

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

                salt = base64.b64decode(salt_file.read_text())

                # Derive correct key from password and salt
                key = derive_session_key(password, salt)

                # Move extracted session to final location
                (temp_extract_path / session_id).rename(session_path)

            # Create session instance
            session = cls(session_id=session_id, session_dir=session_dir, password=password)
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
