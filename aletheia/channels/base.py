"""Base channel connector for Aletheia gateway."""

import asyncio
import uuid
from abc import ABC, abstractmethod
from typing import Any

import structlog
import websockets
from websockets.client import WebSocketClientProtocol

from aletheia.channels.manifest import ChannelManifest
from aletheia.daemon.protocol import ProtocolMessage


class BaseChannelConnector(ABC):
    """
    Abstract base class for channel connectors.

    A channel connector bridges a specific interface (TUI, Web, Telegram)
    with the Aletheia gateway via WebSocket.
    """

    def __init__(
        self,
        gateway_url: str = "ws://127.0.0.1:8765",
        config: dict[str, Any] | None = None,
    ):
        """Initialize channel connector."""
        self.gateway_url = gateway_url
        self.config = config or {}
        self.websocket: WebSocketClientProtocol | None = None
        self.connected = False
        self.channel_id = str(uuid.uuid4())
        self.logger = structlog.get_logger(
            f"aletheia.channel.{self.manifest().channel_type}"
        )
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 1.0
        self._receive_task: asyncio.Task | None = None

    @classmethod
    @abstractmethod
    def manifest(cls) -> ChannelManifest:
        """Return channel manifest with metadata and capabilities."""
        pass

    async def connect(self) -> None:
        """Establish connection to gateway."""
        try:
            self.websocket = await websockets.connect(self.gateway_url)
            self.connected = True

            # Register with gateway
            register_msg = ProtocolMessage.create(
                "channel_register",
                {
                    "channel_type": self.manifest().channel_type,
                    "channel_id": self.channel_id,
                },
            )
            await self.websocket.send(register_msg.to_json())

            # Wait for registration confirmation
            response_raw = await self.websocket.recv()
            response = ProtocolMessage.from_json(response_raw)

            if response.type == "channel_registered":
                self.logger.info(f"Channel {self.channel_id} registered successfully")
                await self.on_connected(response.payload)
            else:
                raise RuntimeError(f"Unexpected response: {response.type}")

            # Start receiving messages
            self._receive_task = asyncio.create_task(self._receive_loop())

        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self.connected = False
            raise

    async def disconnect(self) -> None:
        """Disconnect from gateway."""
        if self.websocket:
            # Send unregister message
            try:
                unregister_msg = ProtocolMessage.create("channel_unregister", {})
                await self.websocket.send(unregister_msg.to_json())
            except Exception:
                pass

            # Cancel receive task
            if self._receive_task:
                self._receive_task.cancel()
                try:
                    await self._receive_task
                except asyncio.CancelledError:
                    pass

            # Close websocket
            await self.websocket.close()
            self.websocket = None

        self.connected = False
        self.logger.info("Disconnected from gateway")

    async def send_message(self, message: str) -> None:
        """Send chat message to gateway."""
        if not self.connected or not self.websocket:
            raise RuntimeError("Not connected to gateway")

        msg = ProtocolMessage.create("chat_message", {"message": message})
        await self.websocket.send(msg.to_json())

    async def create_session(
        self,
        name: str | None = None,
        password: str | None = None,
        unsafe: bool = False,
        verbose: bool = False,
    ) -> None:
        """Request session creation from gateway."""
        if not self.connected or not self.websocket:
            raise RuntimeError("Not connected to gateway")

        msg = ProtocolMessage.create(
            "session_create",
            {
                "name": name,
                "password": password,
                "unsafe": unsafe,
                "verbose": verbose,
            },
        )
        await self.websocket.send(msg.to_json())

    async def resume_session(
        self,
        session_id: str,
        password: str | None = None,
        unsafe: bool = False,
    ) -> None:
        """Request session resume from gateway."""
        if not self.connected or not self.websocket:
            raise RuntimeError("Not connected to gateway")

        msg = ProtocolMessage.create(
            "session_resume",
            {
                "session_id": session_id,
                "password": password,
                "unsafe": unsafe,
            },
        )
        await self.websocket.send(msg.to_json())

    async def list_sessions(self) -> None:
        """Request session list from gateway."""
        if not self.connected or not self.websocket:
            raise RuntimeError("Not connected to gateway")

        msg = ProtocolMessage.create("session_list", {})
        await self.websocket.send(msg.to_json())

    async def request_session_metadata(
        self,
        session_id: str,
        password: str | None = None,
        unsafe: bool = False,
    ) -> None:
        """Request session metadata from gateway."""
        if not self.connected or not self.websocket:
            raise RuntimeError("Not connected to gateway")

        msg = ProtocolMessage.create(
            "session_metadata",
            {
                "session_id": session_id,
                "password": password,
                "unsafe": unsafe,
            },
        )
        await self.websocket.send(msg.to_json())

    async def request_timeline(
        self,
        session_id: str,
        password: str | None = None,
        unsafe: bool = False,
    ) -> None:
        """Request session timeline from gateway."""
        if not self.connected or not self.websocket:
            raise RuntimeError("Not connected to gateway")

        msg = ProtocolMessage.create(
            "timeline_get",
            {
                "session_id": session_id,
                "password": password,
                "unsafe": unsafe,
            },
        )
        await self.websocket.send(msg.to_json())

    async def _receive_loop(self) -> None:
        """Receive and handle messages from gateway."""
        try:
            async for raw_message in self.websocket:
                try:
                    message = ProtocolMessage.from_json(raw_message)
                    await self.handle_gateway_message(message)
                except Exception as e:
                    self.logger.error(f"Error handling message: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Receive loop error: {e}")
            self.connected = False

    @abstractmethod
    async def handle_gateway_message(self, message: ProtocolMessage) -> None:
        """Handle incoming message from gateway."""
        pass

    @abstractmethod
    async def render_response(self, response: dict[str, Any]) -> None:
        """Render response in channel-specific format."""
        pass

    async def on_connected(self, payload: dict[str, Any]) -> None:
        """Called when successfully connected and registered.

        Override to handle initial connection state (e.g., display session info).
        """
        pass
