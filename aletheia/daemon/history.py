"""Chat history logging for Aletheia sessions."""

import json
from datetime import datetime
from pathlib import Path

from aletheia.daemon.protocol import ChatEntry


class ChatHistoryLogger:
    """
    Logs all chat interactions for a session.

    Writes to session folder for persistence and replay.
    """

    def __init__(self, session_path: Path):
        """Initialize logger for session."""
        self.session_path = session_path
        self.history_file = session_path / "chat_history.jsonl"
        self.entries: list[ChatEntry] = []

        # Create history file if it doesn't exist
        if not self.history_file.exists():
            self.history_file.touch()
        else:
            # Load existing history
            self.entries = self._load_history()

    def log_user_message(
        self,
        message: str,
        channel: str,
        timestamp: datetime | None = None,
    ) -> ChatEntry:
        """Log a user message."""
        if timestamp is None:
            timestamp = datetime.now()

        entry = ChatEntry(
            timestamp=timestamp.isoformat(),
            role="user",
            content=message,
            agent=None,
            channel=channel,
        )

        self._write_entry(entry)
        self.entries.append(entry)
        return entry

    def log_assistant_response(
        self,
        response: str,
        agent: str | None,
        channel: str,
        timestamp: datetime | None = None,
    ) -> ChatEntry:
        """Log an assistant response."""
        if timestamp is None:
            timestamp = datetime.now()

        entry = ChatEntry(
            timestamp=timestamp.isoformat(),
            role="assistant",
            content=response,
            agent=agent,
            channel=channel,
        )

        self._write_entry(entry)
        self.entries.append(entry)
        return entry

    def get_history(self, limit: int | None = None) -> list[ChatEntry]:
        """Get chat history entries."""
        if limit is None:
            return self.entries.copy()
        return self.entries[-limit:]

    def _write_entry(self, entry: ChatEntry) -> None:
        """Write entry to history file."""
        with open(self.history_file, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    def _load_history(self) -> list[ChatEntry]:
        """Load history from file."""
        entries = []
        if not self.history_file.exists():
            return entries

        with open(self.history_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries.append(ChatEntry.from_dict(data))
                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue

        return entries
