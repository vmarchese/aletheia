"""Simplified Scratchpad implementation.

The scratchpad is a simple journal where agents can write timestamped entries.
All data is encrypted at rest using session encryption keys.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, List

from agent_framework import ai_function, ToolProtocol

from aletheia.encryption import encrypt_data, decrypt_data, EncryptionError, DecryptionError
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.utils.logging import log_debug
from aletheia.plugins.base import BasePlugin


class ScratchpadFileName(Enum):
    """Scratchpad file naming conventions."""
    
    PLAINTEXT = "scratchpad.md"
    ENCRYPTED = "scratchpad.encrypted"


class Scratchpad(BasePlugin):
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
        self.name = "Scratchpad"        
        self.session_dir = Path(session_dir)
        self.encryption_key = encryption_key
        self.unsafe = encryption_key is None
        if self.unsafe:
           self._scratchpad_file = self.session_dir / ScratchpadFileName.PLAINTEXT.value
        else:
           self._scratchpad_file = self.session_dir / ScratchpadFileName.ENCRYPTED.value
        
        # Load existing scratchpad if it exists
        self._load_from_disk()
        loader = PluginInfoLoader()
        self.instructions = loader.load("scratchpad")        

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

#    #@ai_function
    def read_scratchpad(self) -> str:
        """Read the whole scratchpad.

        Returns:
            Complete scratchpad content as string
        """
        return self._journal

#    #@ai_function
    def write_journal_entry(self, 
                            agent: Annotated[str,"The name of the agent writing the entry"],
                            description: Annotated[str,"Description of the entry"],
                            text: Annotated[str,"Text content of the entry"]) -> str:
        """Append an entry to the scratchpad and save to disk.

        Args:
            agent: Name of the agent writing the entry
            description: Description of the entry
            text: Text content of the entry

        Example:
            >>> scratchpad.write_journal_entry(
            ...     "Data Collection",
            ...     "Collected 200 logs from payments-svc pod"
            ... )
        """
        log_debug(f"Scratchpad::write_journal_entry: Writing journal entry by agent '{agent}' with description '{description}'")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"## Date: {timestamp}\n"
        entry += f"- **Agent:** {agent}\n"
        entry += f"- **Description:** {description}\n\n"
        entry += f"{text}\n"
        self._journal += entry
        self._save_to_disk()
        return "Entry added to scratchpad."

    def get_tools(self) -> List[ToolProtocol]:
        return [
            self.write_journal_entry,
            self.read_scratchpad
        ]


