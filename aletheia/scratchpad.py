"""Simplified Scratchpad implementation.

The scratchpad is a simple journal where agents can write timestamped entries.
All data is encrypted at rest using session encryption keys.
"""

from datetime import datetime
from pathlib import Path
from semantic_kernel.functions import kernel_function

from aletheia.encryption import encrypt_data, decrypt_data, EncryptionError, DecryptionError


class Scratchpad:
    """Simplified scratchpad for agent communication.

    The scratchpad maintains a simple journal of entries with timestamps
    and descriptions. Data can be encrypted or stored in plaintext based on configuration.

    Example:
        >>> from aletheia.session import Session
        >>> session = Session.create(password="secret")
        >>> scratchpad = Scratchpad(
        ...     session_dir=session.session_path,
        ...     encryption_key=session._get_key()
        ... )
        >>> scratchpad.write_journal_entry("Data Collection", "Collected 200 logs from payments-svc")
        >>> content = scratchpad.read_scratchpad()
        >>> print(content)
    """

    def __init__(self, session_dir: Path, encryption_key: bytes = None):
        """Initialize a new scratchpad.

        Args:
            session_dir: Path to session directory
            encryption_key: Encryption key for saving/loading (None for plaintext mode)
        """
        self.session_dir = Path(session_dir)
        self.encryption_key = encryption_key
        self.unsafe = encryption_key is None
        self._scratchpad_file = self.session_dir / "scratchpad.enc"
        
        # Load existing scratchpad if it exists
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load scratchpad from file (encrypted or plaintext)."""
        if self._scratchpad_file.exists():
            try:
                with open(self._scratchpad_file, 'rb') as f:
                    file_data = f.read()
                
                if file_data:  # Only process if file has content
                    if self.unsafe:
                        # Plaintext mode - just decode
                        self._journal = file_data.decode('utf-8')
                    else:
                        # Encrypted mode - decrypt then decode
                        decrypted_data = decrypt_data(file_data, self.encryption_key)
                        self._journal = decrypted_data.decode('utf-8')
                else:
                    self._journal = ""
            except (DecryptionError, Exception):
                # If decryption fails or file is corrupted, start fresh
                self._journal = ""
        else:
            self._journal = ""

    def _save_to_disk(self) -> None:
        """Save scratchpad to file (encrypted or plaintext)."""
        try:
            journal_bytes = self._journal.encode('utf-8')
            
            if self.unsafe:
                # Plaintext mode - save directly
                with open(self._scratchpad_file, 'wb') as f:
                    f.write(journal_bytes)
            else:
                # Encrypted mode - encrypt then save
                encrypted_data = encrypt_data(journal_bytes, self.encryption_key)
                with open(self._scratchpad_file, 'wb') as f:
                    f.write(encrypted_data)
        except EncryptionError as e:
            raise EncryptionError(f"Failed to save scratchpad: {e}") from e

    @kernel_function
    def read_scratchpad(self) -> str:
        """Read the whole scratchpad.

        Returns:
            Complete scratchpad content as string
        """
        return self._journal

    @kernel_function
    def write_journal_entry(self, description: str, text: str) -> None:
        """Append an entry to the scratchpad and save to disk.

        Args:
            description: Description of the entry
            text: Text content of the entry

        Example:
            >>> scratchpad.write_journal_entry(
            ...     "Data Collection",
            ...     "Collected 200 logs from payments-svc pod"
            ... )
        """
        timestamp = datetime.now().strftime("%y%m%d-%H:%M:%S")
        entry = f"Date: {timestamp}\nDescription: {description}\n{text}\n\n"
        self._journal += entry
        self._save_to_disk()

