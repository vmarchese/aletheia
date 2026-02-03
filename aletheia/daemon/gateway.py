"""Main gateway daemon for Aletheia."""

import asyncio
import logging
import signal
from typing import Any

from websockets.server import WebSocketServerProtocol

from aletheia.config import Config
from aletheia.daemon.protocol import ProtocolMessage, SessionInfo
from aletheia.daemon.server import WebSocketServer
from aletheia.daemon.session_manager import GatewaySessionManager
from aletheia.engram.tools import Engram
from aletheia.session import SessionError


class AletheiaGateway:
    """
    Main gateway daemon managing sessions and channel connections.

    The gateway optionally starts:
    - WebSocket server (always) for TUI channel clients
    - Web/FastAPI server (always) for Web UI
    - Telegram bot (conditional) if token is configured
    """

    def __init__(self, config: Config, enable_memory: bool = True):
        """Initialize gateway with configuration."""
        self.config = config
        self.session_manager = GatewaySessionManager(config, engram=None)
        self.websocket_server = WebSocketServer()
        self.engram: Engram | None = None
        self.running = False

        # Configure logging for gateway and related modules
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger("aletheia.daemon.gateway")

        # Set log levels for our modules
        logging.getLogger("aletheia.daemon.session_manager").setLevel(logging.INFO)
        logging.getLogger("aletheia.daemon.telegram_integration").setLevel(logging.INFO)

        # Optional server components
        self.web_server = None
        self.telegram_task = None

        if enable_memory:
            from aletheia.config import get_config_dir

            self.engram = Engram(identity=str(get_config_dir()))
            self.session_manager.engram = self.engram

    async def start(
        self, host: str = "127.0.0.1", port: int = 8765, web_port: int = 8000
    ) -> None:
        """Start the gateway daemon and all channel servers.

        Args:
            host: Host to bind WebSocket server to
            port: Port for WebSocket server (TUI clients)
            web_port: Port for Web/FastAPI server
        """
        self.running = True

        # Track which channels are enabled
        enabled_channels = []

        # Start Engram watcher if enabled
        if self.engram:
            self.engram.start_watcher()
            self.logger.info("Memory system (Engram) enabled")

        # Start WebSocket server (for TUI)
        await self.websocket_server.start(self.handle_connection)
        self.logger.info(f"WebSocket server started on ws://{host}:{port}")
        enabled_channels.append(f"TUI (ws://{host}:{port})")

        # Start Web/FastAPI server (always enabled)
        await self._start_web_server(host, web_port)
        enabled_channels.append(f"Web UI (http://{host}:{web_port})")

        # Start Telegram bot (conditional)
        telegram_enabled = await self._start_telegram_bot()
        if telegram_enabled:
            enabled_channels.append("Telegram Bot")

        # Print summary
        self.logger.info("=" * 60)
        self.logger.info("Aletheia Gateway Started")
        self.logger.info("=" * 60)
        self.logger.info(f"Enabled Channels ({len(enabled_channels)}):")
        for channel in enabled_channels:
            self.logger.info(f"  ✓ {channel}")
        self.logger.info("=" * 60)

        # Set up signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # Keep running until stopped
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Gracefully stop the gateway daemon."""
        self.logger.info("Stopping gateway...")
        self.running = False

        # Stop Telegram bot
        if self.telegram_task and not self.telegram_task.done():
            self.telegram_task.cancel()
            try:
                await self.telegram_task
            except asyncio.CancelledError:
                pass

        # Stop Web server
        if self.web_server:
            self.web_server.should_exit = True
            await asyncio.sleep(0.1)  # Give it time to shutdown

        # Stop Engram watcher
        if self.engram:
            self.engram.stop_watcher()

        # Close active session
        await self.session_manager.close_active_session()

        # Stop WebSocket server
        await self.websocket_server.stop()

        self.logger.info("Gateway stopped")

    async def handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        """Handle new WebSocket connection from a channel."""
        channel_id: str | None = None

        try:
            async for raw_message in websocket:
                try:
                    message = ProtocolMessage.from_json(raw_message)
                    await self.handle_message(websocket, message, channel_id)

                    # Track channel_id after registration
                    if message.type == "channel_register" and channel_id is None:
                        channel_id = message.payload.get("channel_id")

                except Exception as e:
                    self.logger.error(f"Error handling message: {e}")
                    # Send error response
                    error_msg = ProtocolMessage.create(
                        "error",
                        {"code": "MESSAGE_ERROR", "message": str(e)},
                    )
                    await websocket.send(error_msg.to_json())

        except Exception as e:
            self.logger.error(f"Connection error: {e}")
        finally:
            # Unregister channel on disconnect
            if channel_id:
                self.websocket_server.unregister_connection(channel_id)

    async def handle_message(
        self,
        websocket: WebSocketServerProtocol,
        message: ProtocolMessage,
        channel_id: str | None,
    ) -> None:
        """Route incoming messages to appropriate handlers."""
        msg_type = message.type
        payload = message.payload

        if msg_type == "channel_register":
            await self._handle_channel_register(websocket, payload)

        elif msg_type == "channel_unregister":
            if channel_id:
                self.websocket_server.unregister_connection(channel_id)

        elif msg_type == "session_create":
            await self._handle_session_create(websocket, payload)

        elif msg_type == "session_resume":
            await self._handle_session_resume(websocket, payload)

        elif msg_type == "session_close":
            await self._handle_session_close(websocket)

        elif msg_type == "session_list":
            await self._handle_session_list(websocket)

        elif msg_type == "chat_message":
            await self._handle_chat_message(websocket, payload, channel_id or "unknown")

        elif msg_type == "ping":
            # Respond to ping
            pong_msg = ProtocolMessage.create("pong", {})
            await websocket.send(pong_msg.to_json())

        elif msg_type == "shutdown":
            # Handle shutdown request
            shutdown_msg = ProtocolMessage.create(
                "shutdown_ack",
                {"message": "Gateway is shutting down"},
            )
            await websocket.send(shutdown_msg.to_json())
            # Schedule shutdown
            asyncio.create_task(self.stop())

        else:
            # Unknown message type
            error_msg = ProtocolMessage.create(
                "error",
                {
                    "code": "UNKNOWN_MESSAGE_TYPE",
                    "message": f"Unknown type: {msg_type}",
                },
            )
            await websocket.send(error_msg.to_json())

    async def _handle_channel_register(
        self, websocket: WebSocketServerProtocol, payload: dict[str, Any]
    ) -> None:
        """Handle channel registration."""
        channel_type = payload.get("channel_type")
        channel_id = payload.get("channel_id")

        if not channel_type or not channel_id:
            error_msg = ProtocolMessage.create(
                "error",
                {
                    "code": "INVALID_REGISTRATION",
                    "message": "Missing channel_type or channel_id",
                },
            )
            await websocket.send(error_msg.to_json())
            return

        # Register connection
        self.websocket_server.register_connection(channel_id, websocket)

        # Send registration confirmation
        active_session = self.session_manager.get_active_session()
        session_info = None
        if active_session:
            metadata = active_session.get_metadata()
            session_info = {
                "id": metadata.id,
                "name": metadata.name,
                "status": metadata.status,
                "unsafe": metadata.unsafe,
            }

        response = ProtocolMessage.create(
            "channel_registered",
            {"channel_id": channel_id, "session": session_info},
        )
        await websocket.send(response.to_json())

    async def _handle_session_create(
        self, websocket: WebSocketServerProtocol, payload: dict[str, Any]
    ) -> None:
        """Handle session creation request."""
        try:
            name = payload.get("name")
            password = payload.get("password")
            unsafe = payload.get("unsafe", False)
            verbose = payload.get("verbose", False)

            session = await self.session_manager.create_session(
                name=name,
                password=password,
                unsafe=unsafe,
                verbose=verbose,
            )

            metadata = session.get_metadata()
            response = ProtocolMessage.create(
                "session_created",
                {
                    "session": {
                        "id": metadata.id,
                        "name": metadata.name,
                        "created": metadata.created,
                        "updated": metadata.updated,
                        "status": metadata.status,
                        "unsafe": metadata.unsafe,
                    }
                },
            )
            await websocket.send(response.to_json())

        except SessionError as e:
            error_msg = ProtocolMessage.create(
                "error",
                {"code": "SESSION_CREATE_ERROR", "message": str(e)},
            )
            await websocket.send(error_msg.to_json())

    async def _handle_session_resume(
        self, websocket: WebSocketServerProtocol, payload: dict[str, Any]
    ) -> None:
        """Handle session resume request."""
        try:
            session_id = payload.get("session_id")
            password = payload.get("password")
            unsafe = payload.get("unsafe", False)

            if not session_id:
                error_msg = ProtocolMessage.create(
                    "error",
                    {"code": "MISSING_SESSION_ID", "message": "session_id required"},
                )
                await websocket.send(error_msg.to_json())
                return

            session = await self.session_manager.resume_session(
                session_id=session_id,
                password=password,
                unsafe=unsafe,
            )

            metadata = session.get_metadata()

            # Get chat history
            if self.session_manager.chat_logger:
                history = self.session_manager.chat_logger.get_history()
                history_data = [entry.to_dict() for entry in history]
            else:
                history_data = []

            response = ProtocolMessage.create(
                "session_resumed",
                {
                    "session": {
                        "id": metadata.id,
                        "name": metadata.name,
                        "created": metadata.created,
                        "updated": metadata.updated,
                        "status": metadata.status,
                        "unsafe": metadata.unsafe,
                    },
                    "history": history_data,
                },
            )
            await websocket.send(response.to_json())

        except SessionError as e:
            error_msg = ProtocolMessage.create(
                "error",
                {"code": "SESSION_RESUME_ERROR", "message": str(e)},
            )
            await websocket.send(error_msg.to_json())

    async def _handle_session_close(self, websocket: WebSocketServerProtocol) -> None:
        """Handle session close request."""
        await self.session_manager.close_active_session()

        response = ProtocolMessage.create("session_closed", {})
        await websocket.send(response.to_json())

    async def _handle_session_list(self, websocket: WebSocketServerProtocol) -> None:
        """Handle session list request."""
        sessions = self.session_manager.list_sessions()

        response = ProtocolMessage.create("session_list", {"sessions": sessions})
        await websocket.send(response.to_json())

    async def _handle_chat_message(
        self, websocket: WebSocketServerProtocol, payload: dict[str, Any], channel: str
    ) -> None:
        """Handle chat message from channel."""
        message = payload.get("message")

        if not message:
            error_msg = ProtocolMessage.create(
                "error",
                {"code": "MISSING_MESSAGE", "message": "message field required"},
            )
            await websocket.send(error_msg.to_json())
            return

        # Check if session is active
        if not self.session_manager.get_active_session():
            # No active session, prompt user to create/resume one
            sessions = self.session_manager.list_sessions()
            response = ProtocolMessage.create(
                "session_required",
                {"available_sessions": sessions},
            )
            await websocket.send(response.to_json())
            return

        # Send stream start
        import uuid

        message_id = str(uuid.uuid4())
        start_msg = ProtocolMessage.create(
            "chat_stream_start",
            {"message_id": message_id},
        )
        await websocket.send(start_msg.to_json())

        # Stream response - send raw JSON chunks to channel for rendering
        try:
            last_usage = {}

            async for chunk in self.session_manager.send_message(message, channel):
                chunk_type = chunk.get("type")

                # Send JSON chunks as-is - channels handle rendering
                if chunk_type in ("json_chunk", "json_complete", "json_error"):
                    chunk_msg = ProtocolMessage.create(
                        "chat_stream_chunk",
                        {
                            "message_id": message_id,
                            "chunk_type": chunk_type,
                            "content": chunk.get("content", ""),
                            "parsed": chunk.get("parsed"),  # For json_complete
                        },
                    )
                    await websocket.send(chunk_msg.to_json())

                # Track usage for stream end
                elif chunk_type == "usage":
                    last_usage = chunk.get("usage", {})

            # Send stream end
            end_msg = ProtocolMessage.create(
                "chat_stream_end",
                {
                    "message_id": message_id,
                    "usage": last_usage,
                },
            )
            await websocket.send(end_msg.to_json())

        except Exception as e:
            self.logger.error(f"Error streaming response: {e}")
            error_msg = ProtocolMessage.create(
                "error",
                {"code": "CHAT_ERROR", "message": str(e)},
            )
            await websocket.send(error_msg.to_json())

    async def broadcast_to_channels(self, message: dict[str, Any]) -> None:
        """Broadcast message to all connected channels."""
        await self.websocket_server.broadcast(message)

    async def _start_web_server(self, host: str, port: int) -> None:
        """Start the Web/FastAPI server as part of the gateway process.

        Args:
            host: Host to bind to
            port: Port to listen on
        """
        try:
            import uvicorn
            from aletheia.channels.web import create_web_app

            # Create FastAPI app integrated with gateway's session manager
            app = create_web_app(self.session_manager, self.engram)

            # Create uvicorn config
            config = uvicorn.Config(
                app,
                host=host,
                port=port,
                log_level="info",
                access_log=False,
            )
            self.web_server = uvicorn.Server(config)

            # Start server in background task
            asyncio.create_task(self.web_server.serve())
            self.logger.info(f"Web UI server started on http://{host}:{port}")

        except Exception as e:
            self.logger.error(f"Failed to start Web UI server: {e}")

    async def _start_telegram_bot(self) -> bool:
        """Start the Telegram bot if configured.

        Only starts if ALETHEIA_TELEGRAM_BOT_TOKEN and ALETHEIA_TELEGRAM_ALLOWED_USERS
        environment variables are set.

        Returns:
            True if Telegram bot was started, False otherwise
        """
        if not self.config.telegram_bot_token:
            self.logger.info("Telegram bot disabled (no token configured)")
            return False

        if not self.config.telegram_allowed_users:
            self.logger.warning(
                "Telegram bot token configured but no allowed users specified. "
                "Bot will accept messages from ANY user. "
                "Set ALETHEIA_TELEGRAM_ALLOWED_USERS to restrict access."
            )

        try:
            from aletheia.channels.telegram import run_telegram_bot_integrated

            # Start bot in background task
            self.telegram_task = asyncio.create_task(
                run_telegram_bot_integrated(
                    token=self.config.telegram_bot_token,
                    config=self.config,
                    session_manager=self.session_manager,
                    engram=self.engram,
                )
            )
            self.logger.info("Telegram bot started")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start Telegram bot: {e}")
            return False
