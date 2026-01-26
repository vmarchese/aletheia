"""Telegram session manager for tracking active user sessions."""

from datetime import datetime
from typing import Any


class TelegramSessionManager:
    """Manages active sessions for Telegram users.

    Each Telegram user can have one active session at a time.
    Tracks session IDs, orchestrator instances, and last activity timestamps.
    """

    def __init__(self) -> None:
        """Initialize the session manager."""
        self.active_sessions: dict[int, str] = {}  # user_id → session_id
        self.orchestrators: dict[str, Any] = {}  # session_id → Orchestrator instance
        self.last_activity: dict[int, datetime] = {}  # user_id → timestamp

    def get_active_session(self, user_id: int) -> str | None:
        """Get the active session ID for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            Session ID if user has an active session, None otherwise
        """
        return self.active_sessions.get(user_id)

    def set_active_session(self, user_id: int, session_id: str) -> None:
        """Set the active session for a user.

        Args:
            user_id: Telegram user ID
            session_id: Session ID to set as active
        """
        self.active_sessions[user_id] = session_id
        self.last_activity[user_id] = datetime.now()

    def clear_session(self, user_id: int) -> None:
        """Clear the active session for a user.

        Args:
            user_id: Telegram user ID
        """
        self.active_sessions.pop(user_id, None)
        self.last_activity.pop(user_id, None)

    def get_orchestrator(self, session_id: str) -> Any:
        """Get the orchestrator instance for a session.

        Args:
            session_id: Session ID

        Returns:
            Orchestrator instance if found, None otherwise
        """
        return self.orchestrators.get(session_id)

    def set_orchestrator(self, session_id: str, orchestrator: Any) -> None:
        """Store an orchestrator instance for a session.

        Args:
            session_id: Session ID
            orchestrator: Orchestrator instance to store
        """
        self.orchestrators[session_id] = orchestrator

    def update_activity(self, user_id: int) -> None:
        """Update the last activity timestamp for a user.

        Args:
            user_id: Telegram user ID
        """
        self.last_activity[user_id] = datetime.now()
