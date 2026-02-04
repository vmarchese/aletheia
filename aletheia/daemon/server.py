"""WebSocket server for Aletheia gateway."""

from typing import Any

import structlog
import websockets
from websockets.server import WebSocketServerProtocol

from aletheia.daemon.protocol import ProtocolMessage


class WebSocketServer:
    """
    Manages WebSocket connections from channel connectors.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        """Initialize WebSocket server."""
        self.host = host
        self.port = port
        self.connections: dict[str, WebSocketServerProtocol] = {}
        self.server: websockets.WebSocketServer | None = None
        self.logger = structlog.get_logger("aletheia.daemon.server")

    async def start(self, handler) -> None:
        """Start WebSocket server with given handler."""
        self.server = await websockets.serve(
            handler,
            self.host,
            self.port,
        )
        self.logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop WebSocket server and close all connections."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Close all connections
        for websocket in list(self.connections.values()):
            await websocket.close()

        self.connections.clear()
        self.logger.info("WebSocket server stopped")

    def register_connection(
        self, channel_id: str, websocket: WebSocketServerProtocol
    ) -> None:
        """Register a new channel connection."""
        self.connections[channel_id] = websocket
        self.logger.info(f"Channel registered: {channel_id}")

    def unregister_connection(self, channel_id: str) -> None:
        """Remove a channel connection."""
        if channel_id in self.connections:
            del self.connections[channel_id]
            self.logger.info(f"Channel unregistered: {channel_id}")

    async def send_to_channel(self, channel_id: str, message: dict[str, Any]) -> None:
        """Send message to specific channel."""
        if channel_id in self.connections:
            websocket = self.connections[channel_id]
            try:
                msg = ProtocolMessage.create(
                    message["type"], message.get("payload", {})
                )
                await websocket.send(msg.to_json())
            except Exception as e:
                self.logger.error(f"Error sending to channel {channel_id}: {e}")
                # Remove dead connection
                self.unregister_connection(channel_id)

    async def broadcast(
        self, message: dict[str, Any], exclude: str | None = None
    ) -> None:
        """Broadcast message to all channels."""
        msg = ProtocolMessage.create(message["type"], message.get("payload", {}))
        json_msg = msg.to_json()

        # Send to all connections except excluded one
        dead_connections = []
        for channel_id, websocket in self.connections.items():
            if channel_id != exclude:
                try:
                    await websocket.send(json_msg)
                except Exception as e:
                    self.logger.error(f"Error broadcasting to {channel_id}: {e}")
                    dead_connections.append(channel_id)

        # Clean up dead connections
        for channel_id in dead_connections:
            self.unregister_connection(channel_id)
