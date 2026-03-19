"""WebSocket protocol definitions for Aletheia gateway communication.

Message types (all carried in ProtocolMessage.type):

Session management:
  session_create, session_resume, session_close, session_list,
  session_created, session_resumed, session_closed, session_deleted,
  session_metadata, session_required

Chat streaming:
  chat_message, chat_stream_start, chat_stream_chunk, chat_stream_end

Commands:
  command_list, command_execute, commands_updated

Scratchpad / Timeline:
  scratchpad_get, scratchpad_data, timeline_get, timeline_data

Async jobs:
  job_submit      – client → gateway: {message, session_id}
  job_submitted   – gateway → client: {job_id}
  job_completed   – gateway → all:    {job_id, session_id}
  job_failed      – gateway → all:    {job_id, session_id, error}
  job_status      – client → gateway: {job_id}
  job_result      – gateway → client: {job: Job.to_dict()}
  job_list        – client → gateway: {session_id}
  job_list_response – gateway → client: {jobs: [Job.to_dict(), ...]}

General:
  error, ping, pong, shutdown, shutdown_ack
"""

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
