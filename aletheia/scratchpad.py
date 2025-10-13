"""Scratchpad implementation for agent communication.

The scratchpad is the shared context mechanism for all agents in Aletheia.
It provides structured sections for each phase of the investigation:
- PROBLEM_DESCRIPTION: User-provided problem statement and context
- DATA_COLLECTED: Raw data and summaries from fetchers
- PATTERN_ANALYSIS: Anomalies, correlations, error clusters
- CODE_INSPECTION: Source code mapping and analysis
- FINAL_DIAGNOSIS: Root cause hypothesis and recommendations

All scratchpad data is encrypted at rest using session encryption keys.
"""

import json
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

from aletheia.encryption import encrypt_json_file, decrypt_json_file


class ScratchpadSection:
    """Enumeration of valid scratchpad sections."""
    PROBLEM_DESCRIPTION = "PROBLEM_DESCRIPTION"
    DATA_COLLECTED = "DATA_COLLECTED"
    PATTERN_ANALYSIS = "PATTERN_ANALYSIS"
    CODE_INSPECTION = "CODE_INSPECTION"
    FINAL_DIAGNOSIS = "FINAL_DIAGNOSIS"


class Scratchpad:
    """Scratchpad for agent communication and state sharing.

    The scratchpad maintains structured sections that agents read from and write to
    during an investigation. All data is stored in-memory and can be persisted to
    an encrypted file.

    Example:
        >>> from aletheia.session import Session
        >>> from aletheia.scratchpad import Scratchpad
        >>>
        >>> session = Session.create(password="secret")
        >>> scratchpad = Scratchpad(session.session_dir, session.key)
        >>>
        >>> # Write problem description
        >>> scratchpad.write_section(
        ...     ScratchpadSection.PROBLEM_DESCRIPTION,
        ...     {
        ...         "description": "API errors in payments service",
        ...         "time_window": "2h",
        ...         "affected_services": ["payments-svc"]
        ...     }
        ... )
        >>>
        >>> # Save to encrypted file
        >>> scratchpad.save()
        >>>
        >>> # Load from encrypted file
        >>> loaded = Scratchpad.load(session.session_dir, session.key)
        >>> problem = loaded.read_section(ScratchpadSection.PROBLEM_DESCRIPTION)
    """

    def __init__(self, session_dir: Path, encryption_key: bytes):
        """Initialize a new scratchpad.

        Args:
            session_dir: Path to session directory
            encryption_key: Encryption key for saving/loading
        """
        self.session_dir = Path(session_dir)
        self.encryption_key = encryption_key
        self._data: Dict[str, Any] = {}
        self._updated_at: Optional[datetime] = None

    def write_section(self, section: str, data: Any) -> None:
        """Write or update a scratchpad section.

        Args:
            section: Section name (use ScratchpadSection constants)
            data: Section data (will be stored as-is)

        Example:
            >>> scratchpad.write_section(
            ...     ScratchpadSection.DATA_COLLECTED,
            ...     {
            ...         "logs": [{"source": "kubernetes", "count": 200}],
            ...         "metrics": [{"source": "prometheus", "summary": "..."}]
            ...     }
            ... )
        """
        self._data[section] = data
        self._updated_at = datetime.now()

    def read_section(self, section: str) -> Optional[Any]:
        """Read a scratchpad section.

        Args:
            section: Section name to read

        Returns:
            Section data, or None if section doesn't exist

        Example:
            >>> data = scratchpad.read_section(ScratchpadSection.DATA_COLLECTED)
            >>> if data:
            ...     print(f"Found {len(data['logs'])} log sources")
        """
        return self._data.get(section)

    def has_section(self, section: str) -> bool:
        """Check if a section exists.

        Args:
            section: Section name to check

        Returns:
            True if section exists and has data

        Example:
            >>> if scratchpad.has_section(ScratchpadSection.PATTERN_ANALYSIS):
            ...     print("Pattern analysis complete")
        """
        return section in self._data

    def append_to_section(self, section: str, data: Any) -> None:
        """Append data to an existing section.

        If the section contains a list, appends to the list.
        If the section contains a dict, updates the dict.
        If the section doesn't exist, creates it with the data.

        Args:
            section: Section name
            data: Data to append

        Example:
            >>> # Append to list
            >>> scratchpad.append_to_section(
            ...     ScratchpadSection.DATA_COLLECTED + ".logs",
            ...     {"source": "elasticsearch", "count": 150}
            ... )
        """
        if section not in self._data:
            self._data[section] = data
        else:
            existing = self._data[section]
            if isinstance(existing, list) and isinstance(data, (list, dict)):
                if isinstance(data, list):
                    existing.extend(data)
                else:
                    existing.append(data)
            elif isinstance(existing, dict) and isinstance(data, dict):
                existing.update(data)
            else:
                # Replace if types don't match
                self._data[section] = data

        self._updated_at = datetime.now()

    def get_all(self) -> Dict[str, Any]:
        """Get entire scratchpad data.

        Returns:
            Complete scratchpad as dictionary

        Example:
            >>> all_data = scratchpad.get_all()
            >>> for section, content in all_data.items():
            ...     print(f"{section}: {len(str(content))} bytes")
        """
        return self._data.copy()

    def clear(self) -> None:
        """Clear all scratchpad data.

        Warning: This operation cannot be undone unless the scratchpad
        has been saved to disk.
        """
        self._data = {}
        self._updated_at = datetime.now()

    def save(self) -> Path:
        """Persist scratchpad to encrypted file.

        Returns:
            Path to saved scratchpad file

        Raises:
            EncryptionError: If encryption fails
            IOError: If file cannot be written

        Example:
            >>> path = scratchpad.save()
            >>> print(f"Scratchpad saved to {path}")
        """
        scratchpad_file = self.session_dir / "scratchpad.encrypted"

        # Prepare data with metadata
        save_data = {
            "updated_at": self._updated_at.isoformat() if self._updated_at else datetime.now().isoformat(),
            "sections": self._data
        }

        # Encrypt and save
        encrypt_json_file(save_data, scratchpad_file, self.encryption_key)

        return scratchpad_file

    @classmethod
    def load(cls, session_dir: Path, encryption_key: bytes) -> "Scratchpad":
        """Load scratchpad from encrypted file.

        Args:
            session_dir: Path to session directory
            encryption_key: Encryption key for decryption

        Returns:
            Loaded Scratchpad instance

        Raises:
            DecryptionError: If decryption fails or password is wrong
            FileNotFoundError: If scratchpad file doesn't exist

        Example:
            >>> scratchpad = Scratchpad.load(session_dir, key)
            >>> print(f"Last updated: {scratchpad._updated_at}")
        """
        scratchpad_file = Path(session_dir) / "scratchpad.encrypted"

        # Decrypt and load
        loaded_data = decrypt_json_file(scratchpad_file, encryption_key)

        # Create instance and restore data
        instance = cls(session_dir, encryption_key)
        instance._data = loaded_data.get("sections", {})

        updated_str = loaded_data.get("updated_at")
        if updated_str:
            instance._updated_at = datetime.fromisoformat(updated_str)

        return instance

    def to_yaml(self) -> str:
        """Export scratchpad to YAML format.

        Useful for human-readable inspection or debugging.

        Returns:
            YAML string representation

        Example:
            >>> yaml_str = scratchpad.to_yaml()
            >>> print(yaml_str)
        """
        return yaml.dump(self._data, default_flow_style=False, sort_keys=False)

    def to_dict(self) -> Dict[str, Any]:
        """Export scratchpad to dictionary.

        Returns:
            Dictionary representation including metadata
        """
        return {
            "updated_at": self._updated_at.isoformat() if self._updated_at else None,
            "sections": self._data
        }

    @property
    def updated_at(self) -> Optional[datetime]:
        """Get last update timestamp."""
        return self._updated_at

    @property
    def section_count(self) -> int:
        """Get number of sections with data."""
        return len(self._data)
