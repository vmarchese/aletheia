"""WebSocket protocol definitions for Aletheia gateway communication."""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass
class ProtocolMessage:
    """Base WebSocket protocol message."""

    type: str
    id: str
    timestamp: str
    payload: dict[str, Any]

    @classmethod
    def create(
        cls, msg_type: str, payload: dict[str, Any] | None = None
    ) -> "ProtocolMessage":
        """Create a new protocol message with generated ID and timestamp."""
        return cls(
            type=msg_type,
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            payload=payload or {},
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "ProtocolMessage":
        """Deserialize from JSON string."""
        obj = json.loads(data)
        return cls(**obj)


@dataclass
class SessionInfo:
    """Session information for protocol messages."""

    id: str
    name: str | None
    created: str
    updated: str
    status: str
    unsafe: bool
    total_input_tokens: int = 0
    total_output_tokens: int = 0


@dataclass
class ChatEntry:
    """Single chat history entry."""

    timestamp: str
    role: str  # "user" | "assistant"
    content: str
    agent: str | None
    channel: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChatEntry":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class ChannelInfo:
    """Connected channel information."""

    channel_id: str
    channel_type: str  # "tui" | "web" | "telegram"
    connected_at: str
    user_id: str | None = None  # For Telegram


@dataclass
class UsageInfo:
    """Token usage information."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass
class StreamChunk:
    """Streaming response chunk."""

    message_id: str
    chunk_type: str
    content: Any
