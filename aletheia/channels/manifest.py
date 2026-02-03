"""Channel manifest and capability definitions."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChannelCapability(Enum):
    """Channel capabilities that affect gateway behavior."""

    STREAMING = "streaming"  # Supports streaming responses
    RICH_TEXT = "rich_text"  # Supports markdown/formatting
    IMAGES = "images"  # Can display images
    FILE_UPLOAD = "file_upload"  # Can upload files
    FILE_DOWNLOAD = "file_download"  # Can download files
    INTERACTIVE = "interactive"  # Supports interactive elements (buttons, etc.)
    MULTI_USER = "multi_user"  # Supports multiple users per channel instance
    PERSISTENT = "persistent"  # Maintains persistent connection
    SECURE = "secure"  # Provides E2E encryption
    VOICE = "voice"  # Supports voice input/output


@dataclass
class ChannelManifest:
    """
    Declarative metadata for a channel connector.

    Attributes:
        channel_type: str - Unique identifier (e.g., "slack", "discord")
        display_name: str - Human-readable name
        description: str - Channel description
        version: str - Connector version (semver)
        author: str - Author or maintainer
        capabilities: set[ChannelCapability] - Supported capabilities
        config_schema: dict - JSON Schema for channel configuration
        requires_daemon: bool - Whether channel requires gateway daemon
        max_message_length: int | None - Maximum message length (None = unlimited)
        supports_threading: bool - Supports threaded conversations
        documentation_url: str | None - Link to documentation
    """

    channel_type: str
    display_name: str
    description: str
    version: str = "1.0.0"
    author: str = "Aletheia Team"
    capabilities: set[ChannelCapability] = field(default_factory=set)
    config_schema: dict[str, Any] = field(default_factory=dict)
    requires_daemon: bool = True
    max_message_length: int | None = None
    supports_threading: bool = False
    documentation_url: str | None = None

    def has_capability(self, capability: ChannelCapability) -> bool:
        """Check if channel has a specific capability."""
        return capability in self.capabilities

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "channel_type": self.channel_type,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "capabilities": [c.value for c in self.capabilities],
            "config_schema": self.config_schema,
            "requires_daemon": self.requires_daemon,
            "max_message_length": self.max_message_length,
            "supports_threading": self.supports_threading,
            "documentation_url": self.documentation_url,
        }
