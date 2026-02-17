"""Main gateway daemon for Aletheia."""

import asyncio
import json
import signal
from typing import Any

import structlog
from agent_framework import FunctionInvocationContext, FunctionMiddleware
from websockets.server import WebSocketServerProtocol

from aletheia.agents.middleware import get_current_agent_name
from aletheia.config import Config, load_config
from aletheia.daemon.protocol import ProtocolMessage
from aletheia.daemon.server import WebSocketServer
from aletheia.daemon.session_manager import GatewaySessionManager
from aletheia.daemon.watcher import ConfigWatcher
from aletheia.engram.tools import Engram
from aletheia.session import Session, SessionError, SessionNotFoundError


class GatewayFunctionMiddleware(FunctionMiddleware):
    """Function middleware that sends function call events via WebSocket.

    Installed by the gateway so all channels receive function_call events
    as part of the chat stream protocol.
    """

    def __init__(self) -> None:
        """Initialize with no active websocket."""
        self.websocket: WebSocketServerProtocol | None = None
        self.message_id: str | None = None

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Any,
    ) -> None:
        """Intercept function calls and send them via WebSocket."""
        logger = structlog.get_logger("aletheia.daemon.gateway.middleware")

        skipped_functions = ["write_journal_entry", "read_scratchpad"]
        try:
            from aletheia.commands import COMMANDS

            if "agents" in COMMANDS:
                for agent in COMMANDS["agents"].agents:
                    skipped_functions.append(agent.name)
        except (ImportError, KeyError):
            pass

        if (
            self.websocket
            and self.message_id
            and context.function.name not in skipped_functions
        ):
            arguments = {}
            for arg_key, arg_value in context.arguments.model_dump().items():
                str_value = str(arg_value)
                if len(str_value) > 100:
                    str_value = str_value[:97] + "..."
                arguments[arg_key] = str_value

            try:
                agent_name = get_current_agent_name() or "orchestrator"
                chunk_msg = ProtocolMessage.create(
                    "chat_stream_chunk",
                    {
                        "message_id": self.message_id,
                        "chunk_type": "function_call",
                        "content": {
                            "agent_name": agent_name,
                            "function_name": context.function.name,
                            "arguments": arguments,
                        },
                    },
                )
                await self.websocket.send(chunk_msg.to_json())
            except Exception as e:
                logger.debug(f"[GatewayFunctionMiddleware] Error sending event: {e}")

        await call_next()


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

        # Configure logging for gateway
        from aletheia.utils.logging import setup_logging

        setup_logging()
        self.logger = structlog.get_logger("aletheia.daemon.gateway")

        # Function middleware for sending function call events via WebSocket
        self.function_middleware = GatewayFunctionMiddleware()
        self.session_manager.additional_middleware = [self.function_middleware]

        # Optional server components
        self.web_server = None
        self.web_channel: Any = None
        self.telegram_task = None
        self.config_watcher: ConfigWatcher | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        if enable_memory:
            from aletheia.config import get_config_dir

            self.engram = Engram(identity=str(get_config_dir()))
            self.session_manager.engram = self.engram

    async def start(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        web_host: str = "127.0.0.1",
        web_port: int = 8000,
    ) -> None:
        """Start the gateway daemon and all channel servers.

        Args:
            host: Host to bind WebSocket server to
            port: Port for WebSocket server (TUI clients)
            web_host: Host to bind Web/FastAPI server to
            web_port: Port for Web/FastAPI server
        """
        self.running = True
        self._loop = asyncio.get_running_loop()

        # Track which channels are enabled
        enabled_channels = []

        # Start Engram watcher if enabled
        if self.engram:
            self.engram.start_watcher()
            self.logger.info("Memory system (Engram) enabled")

        # Start ConfigWatcher for skills and commands hot-reload
        skills_dirs = ConfigWatcher.get_skills_directories(self.config)
        self.config_watcher = ConfigWatcher(
            skills_directories=skills_dirs,
            commands_directory=self.config.commands_directory,
            on_skills_changed=self._on_skills_changed,
            on_commands_changed=self._on_commands_changed,
        )
        self.config_watcher.start()
        self.logger.info("ConfigWatcher started for skills and commands")

        # Start WebSocket server (for TUI)
        await self.websocket_server.start(self.handle_connection)
        self.logger.info(f"WebSocket server started on ws://{host}:{port}")
        enabled_channels.append(f"TUI (ws://{host}:{port})")

        # Start Web/FastAPI server (always enabled)
        await self._start_web_server(web_host, web_port, ws_host=host, ws_port=port)
        enabled_channels.append(f"Web UI (http://{web_host}:{web_port})")

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

        # Disconnect web channel
        if self.web_channel:
            await self.web_channel.disconnect()

        # Stop Web server
        if self.web_server:
            self.web_server.should_exit = True
            await asyncio.sleep(0.1)  # Give it time to shutdown

        # Stop Engram watcher
        if self.engram:
            self.engram.stop_watcher()

        # Stop ConfigWatcher
        if self.config_watcher:
            self.config_watcher.stop()

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

        elif msg_type == "session_delete":
            await self._handle_session_delete(websocket, payload)

        elif msg_type == "session_metadata":
            await self._handle_session_metadata(websocket, payload)

        elif msg_type == "command_list":
            await self._handle_command_list(websocket)

        elif msg_type == "command_execute":
            await self._handle_command_execute(websocket, payload)

        elif msg_type == "scratchpad_get":
            await self._handle_scratchpad_get(websocket, payload)

        elif msg_type == "timeline_get":
            await self._handle_timeline_get(websocket, payload)

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

            # Check session metadata to detect if it's unsafe/unencrypted
            sessions = Session.list_sessions()
            for s in sessions:
                if s["id"] == session_id:
                    if s.get("unsafe") is True:
                        unsafe = True
                    break

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

    async def _handle_session_delete(
        self, websocket: WebSocketServerProtocol, payload: dict[str, Any]
    ) -> None:
        """Handle session deletion request."""
        try:
            session_id = payload.get("session_id")
            if not session_id:
                error_msg = ProtocolMessage.create(
                    "error",
                    {"code": "MISSING_SESSION_ID", "message": "session_id required"},
                )
                await websocket.send(error_msg.to_json())
                return

            # Close if it's the active session
            active_session = self.session_manager.get_active_session()
            if active_session and active_session.session_id == session_id:
                await self.session_manager.close_active_session()

            # Delete from disk
            session = Session(session_id=session_id)
            session.delete()

            response = ProtocolMessage.create(
                "session_deleted",
                {"session_id": session_id},
            )
            await websocket.send(response.to_json())

        except SessionNotFoundError:
            error_msg = ProtocolMessage.create(
                "error",
                {"code": "SESSION_NOT_FOUND", "message": "Session not found"},
            )
            await websocket.send(error_msg.to_json())
        except Exception as e:
            error_msg = ProtocolMessage.create(
                "error",
                {"code": "SESSION_DELETE_ERROR", "message": str(e)},
            )
            await websocket.send(error_msg.to_json())

    async def _handle_session_metadata(
        self, websocket: WebSocketServerProtocol, payload: dict[str, Any]
    ) -> None:
        """Handle session metadata request."""
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

            # Check if this is the active session
            active_session = self.session_manager.get_active_session()
            if active_session and active_session.session_id == session_id:
                data = active_session.get_metadata().to_dict()
            else:
                # Load from disk
                sessions = Session.list_sessions()
                target = None
                for s in sessions:
                    if s["id"] == session_id:
                        target = s
                        break

                if not target:
                    error_msg = ProtocolMessage.create(
                        "error",
                        {"code": "SESSION_NOT_FOUND", "message": "Session not found"},
                    )
                    await websocket.send(error_msg.to_json())
                    return

                try:
                    is_unsafe = target.get("unsafe") is True
                    use_unsafe = unsafe or is_unsafe
                    session = Session.resume(
                        session_id=session_id,
                        password=password,
                        unsafe=use_unsafe,
                    )
                    data = session.get_metadata().to_dict()
                except Exception:
                    if password:
                        error_msg = ProtocolMessage.create(
                            "error",
                            {
                                "code": "SESSION_METADATA_ERROR",
                                "message": "Invalid password or session data",
                            },
                        )
                        await websocket.send(error_msg.to_json())
                        return
                    data = target

            # Calculate cost
            config = load_config()
            input_tokens = data.get("total_input_tokens", 0)
            output_tokens = data.get("total_output_tokens", 0)
            data["total_cost"] = (input_tokens * config.cost_per_input_token) + (
                output_tokens * config.cost_per_output_token
            )

            response = ProtocolMessage.create("session_metadata", {"metadata": data})
            await websocket.send(response.to_json())

        except Exception as e:
            error_msg = ProtocolMessage.create(
                "error",
                {"code": "SESSION_METADATA_ERROR", "message": str(e)},
            )
            await websocket.send(error_msg.to_json())

    async def _handle_command_list(self, websocket: WebSocketServerProtocol) -> None:
        """Handle command list request."""
        try:
            from aletheia.commands import COMMANDS, get_custom_commands

            config = load_config()
            commands_list = []

            # Built-in commands
            for name, cmd_obj in COMMANDS.items():
                commands_list.append(
                    {
                        "name": name,
                        "description": cmd_obj.description,
                        "type": "built-in",
                    }
                )

            # Custom commands
            try:
                custom_cmds = get_custom_commands(config)
                for command_name, custom_cmd in custom_cmds.items():
                    commands_list.append(
                        {
                            "name": command_name,
                            "description": f"{custom_cmd.name}: {custom_cmd.description}",
                            "type": "custom",
                        }
                    )
            except Exception:
                pass

            commands_list.sort(key=lambda x: x["name"])

            response = ProtocolMessage.create(
                "command_list", {"commands": commands_list}
            )
            await websocket.send(response.to_json())

        except Exception as e:
            error_msg = ProtocolMessage.create(
                "error",
                {"code": "COMMAND_LIST_ERROR", "message": str(e)},
            )
            await websocket.send(error_msg.to_json())

    async def _handle_command_execute(
        self, websocket: WebSocketServerProtocol, payload: dict[str, Any]
    ) -> None:
        """Handle built-in command execution."""
        import io
        import re
        import uuid

        from rich.console import Console
        from rich.markdown import Markdown

        from aletheia.commands import COMMANDS, expand_custom_command

        try:
            message = payload.get("message", "")
            config = load_config()

            # Try custom command expansion first
            expanded_message, was_expanded = expand_custom_command(message, config)
            if was_expanded:
                # Custom command expanded - treat as chat message
                await self._handle_chat_message(
                    websocket,
                    {"message": expanded_message},
                    payload.get("channel", "web"),
                )
                return

            # Parse built-in command
            command_parts = message.strip()[1:].split()
            command_name = command_parts[0]
            args = command_parts[1:]

            command = COMMANDS.get(command_name)
            if not command:
                error_msg = ProtocolMessage.create(
                    "error",
                    {
                        "code": "UNKNOWN_COMMAND",
                        "message": f"Unknown command: /{command_name}",
                    },
                )
                await websocket.send(error_msg.to_json())
                return

            # Execute command with mock console
            class MockConsole:
                def __init__(self) -> None:
                    self.file = io.StringIO()
                    self.console = Console(
                        file=self.file,
                        force_terminal=False,
                        width=80,
                        legacy_windows=False,
                        no_color=True,
                        markup=False,
                    )

                def print(self, *print_args: Any, **kwargs: Any) -> None:
                    for arg in print_args:
                        if isinstance(arg, Markdown):
                            self.file.write(arg.markup + "\n")
                        else:
                            self.console.print(arg, **kwargs)

                def get_output(self) -> str:
                    output = self.file.getvalue()
                    output = re.sub(r"\[/?[a-z_]+[^\]]*\]", "", output)
                    return output

            mock_console = MockConsole()

            kwargs: dict[str, Any] = {"config": config}
            if command_name == "reload":
                orchestrator = self.session_manager.get_orchestrator()
                if orchestrator:
                    kwargs["orchestrator"] = orchestrator
            if command_name == "cost":
                session = self.session_manager.get_active_session()
                if session:
                    metadata = session.get_metadata()
                    if metadata.total_input_tokens or metadata.total_output_tokens:
                        kwargs["completion_usage"] = {
                            "input_token_count": metadata.total_input_tokens,
                            "output_token_count": metadata.total_output_tokens,
                        }

            command.execute(*args, console=mock_console, **kwargs)

            # Send result as stream
            message_id = str(uuid.uuid4())
            start_msg = ProtocolMessage.create(
                "chat_stream_start", {"message_id": message_id}
            )
            await websocket.send(start_msg.to_json())

            output = mock_console.get_output()
            chunk_msg = ProtocolMessage.create(
                "chat_stream_chunk",
                {
                    "message_id": message_id,
                    "chunk_type": "text",
                    "content": output,
                },
            )
            await websocket.send(chunk_msg.to_json())

            end_msg = ProtocolMessage.create(
                "chat_stream_end", {"message_id": message_id, "usage": {}}
            )
            await websocket.send(end_msg.to_json())

            # After /reload, broadcast updated commands to all channels
            if command_name == "reload":
                await self._broadcast_commands_updated()

        except Exception as e:
            error_msg = ProtocolMessage.create(
                "error",
                {"code": "COMMAND_EXECUTE_ERROR", "message": str(e)},
            )
            await websocket.send(error_msg.to_json())

    async def _handle_scratchpad_get(
        self, websocket: WebSocketServerProtocol, payload: dict[str, Any]
    ) -> None:
        """Handle scratchpad content request."""
        from aletheia.plugins.scratchpad.scratchpad import Scratchpad

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

            # Get session
            active_session = self.session_manager.get_active_session()
            if active_session and active_session.session_id == session_id:
                session = active_session
            else:
                sessions = Session.list_sessions()
                is_unsafe = False
                for s in sessions:
                    if s["id"] == session_id:
                        is_unsafe = s.get("unsafe") is True
                        break
                use_unsafe = unsafe or is_unsafe
                session = Session.resume(
                    session_id=session_id, password=password, unsafe=use_unsafe
                )

            scratchpad = Scratchpad(
                session_dir=session.session_path, encryption_key=session.get_key()
            )
            content = scratchpad.read_scratchpad()

            response = ProtocolMessage.create("scratchpad_data", {"content": content})
            await websocket.send(response.to_json())

        except Exception as e:
            error_msg = ProtocolMessage.create(
                "error",
                {"code": "SCRATCHPAD_ERROR", "message": str(e)},
            )
            await websocket.send(error_msg.to_json())

    async def _handle_timeline_get(
        self, websocket: WebSocketServerProtocol, payload: dict[str, Any]
    ) -> None:
        """Handle timeline generation request."""
        from agent_framework import Content, Message

        from aletheia.agents.instructions_loader import Loader
        from aletheia.agents.model import Timeline
        from aletheia.agents.timeline.timeline_agent import TimelineAgent
        from aletheia.plugins.scratchpad.scratchpad import Scratchpad

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

            # Get session
            active_session = self.session_manager.get_active_session()
            if active_session and active_session.session_id == session_id:
                session = active_session
            else:
                sessions = Session.list_sessions()
                is_unsafe = False
                for s in sessions:
                    if s["id"] == session_id:
                        is_unsafe = s.get("unsafe") is True
                        break
                use_unsafe = unsafe or is_unsafe
                session = Session.resume(
                    session_id=session_id, password=password, unsafe=use_unsafe
                )

            # Read scratchpad
            scratchpad_file = session.scratchpad_file
            if not scratchpad_file.exists():
                response = ProtocolMessage.create("timeline_data", {"timeline": []})
                await websocket.send(response.to_json())
                return

            scratchpad = Scratchpad(
                session_dir=session.session_path, encryption_key=session.get_key()
            )
            journal_content = scratchpad.read_scratchpad()
            if not journal_content or not journal_content.strip():
                response = ProtocolMessage.create("timeline_data", {"timeline": []})
                await websocket.send(response.to_json())
                return

            # Generate timeline
            prompt_loader = Loader()
            timeline_agent = TimelineAgent(
                name="timeline_agent",
                instructions=prompt_loader.load("timeline", "json_instructions"),
                description="Timeline Agent for generating session timeline",
            )

            message = Message(
                role="user",
                contents=[
                    Content.from_text(
                        f"Generate a timeline of the following "
                        f"troubleshooting session scratchpad data:\n\n"
                        f"{journal_content}"
                    )
                ],
            )

            agent_response = await timeline_agent.agent.run(
                message, options={"response_format": Timeline}
            )

            if agent_response and agent_response.text:
                try:
                    timeline_data = json.loads(str(agent_response.text))
                    entries = (
                        timeline_data.get("entries", timeline_data)
                        if isinstance(timeline_data, dict)
                        else timeline_data
                    )

                    normalized_entries = []
                    for event in entries:
                        normalized_entries.append(
                            {
                                "timestamp": event.get("timestamp", ""),
                                "type": event.get(
                                    "entry_type", event.get("type", "INFO")
                                ),
                                "content": event.get(
                                    "content", event.get("description", "")
                                ),
                            }
                        )

                    response = ProtocolMessage.create(
                        "timeline_data", {"timeline": normalized_entries}
                    )
                    await websocket.send(response.to_json())
                except json.JSONDecodeError:
                    response = ProtocolMessage.create(
                        "timeline_data",
                        {"timeline": [], "raw_text": str(agent_response.text)},
                    )
                    await websocket.send(response.to_json())
            else:
                response = ProtocolMessage.create("timeline_data", {"timeline": []})
                await websocket.send(response.to_json())

        except Exception as e:
            error_msg = ProtocolMessage.create(
                "error",
                {"code": "TIMELINE_ERROR", "message": str(e)},
            )
            await websocket.send(error_msg.to_json())

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

        # Update function middleware to send events on this websocket
        self.function_middleware.websocket = websocket
        self.function_middleware.message_id = message_id

        start_msg = ProtocolMessage.create(
            "chat_stream_start",
            {"message_id": message_id},
        )
        await websocket.send(start_msg.to_json())

        # Stream response - send raw JSON chunks to channel for rendering
        try:
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
                            "parsed": chunk.get("parsed"),
                            "usage": chunk.get("usage"),
                        },
                    )
                    await websocket.send(chunk_msg.to_json())

            # Send stream end
            end_msg = ProtocolMessage.create(
                "chat_stream_end",
                {"message_id": message_id},
            )
            await websocket.send(end_msg.to_json())

        except Exception as e:
            self.logger.error(f"Error streaming response: {e}")
            error_msg = ProtocolMessage.create(
                "error",
                {"code": "CHAT_ERROR", "message": str(e)},
            )
            await websocket.send(error_msg.to_json())

    def _on_skills_changed(self) -> None:
        """Callback invoked by ConfigWatcher when skill files change."""
        self.logger.info("Skills changed on disk, reloading agent instructions")
        orchestrator = self.session_manager.get_orchestrator()
        if not orchestrator:
            self.logger.debug("No active orchestrator, skipping skills reload")
            return

        orchestrator.reload_skills()
        for agent in getattr(orchestrator, "sub_agent_instances", []):
            if hasattr(agent, "reload_skills"):
                agent.reload_skills()

    def _on_commands_changed(self) -> None:
        """Callback invoked by ConfigWatcher when command files change.

        Broadcasts a commands_updated event to all channels so they can
        refresh their command lists.
        """
        self.logger.info("Custom commands changed on disk, notifying channels")
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(
                self._broadcast_commands_updated(), self._loop
            )

    async def _broadcast_commands_updated(self) -> None:
        """Broadcast updated command list to all connected channels."""
        try:
            from aletheia.commands import COMMANDS, get_custom_commands

            config = load_config()
            commands_list = []

            for name, cmd_obj in COMMANDS.items():
                commands_list.append(
                    {
                        "name": name,
                        "description": cmd_obj.description,
                        "type": "built-in",
                    }
                )

            try:
                custom_cmds = get_custom_commands(config)
                for command_name, custom_cmd in custom_cmds.items():
                    commands_list.append(
                        {
                            "name": command_name,
                            "description": f"{custom_cmd.name}: {custom_cmd.description}",
                            "type": "custom",
                        }
                    )
            except Exception:
                pass

            commands_list.sort(key=lambda x: x["name"])

            await self.websocket_server.broadcast(
                {"type": "commands_updated", "payload": {"commands": commands_list}}
            )
        except Exception as e:
            self.logger.error(f"Error broadcasting commands update: {e}")

    async def broadcast_to_channels(self, message: dict[str, Any]) -> None:
        """Broadcast message to all connected channels."""
        await self.websocket_server.broadcast(message)

    async def _start_web_server(
        self, host: str, port: int, ws_host: str = "127.0.0.1", ws_port: int = 8765
    ) -> None:
        """Start the Web/FastAPI server as part of the gateway process.

        Creates a WebChannelConnector that connects back to the gateway's
        WebSocket server, then serves its FastAPI app via uvicorn.

        Args:
            host: Host to bind web server to
            port: Port for the web server
            ws_host: Host of the gateway's WebSocket server
            ws_port: Port of the gateway's WebSocket server
        """
        try:
            import uvicorn

            from aletheia.channels.web import WebChannelConnector

            # Create web channel connector and connect to gateway's WebSocket
            self.web_channel = WebChannelConnector(
                gateway_url=f"ws://{ws_host}:{ws_port}"
            )
            await self.web_channel.connect()

            # Get the FastAPI app from the connector
            app = self.web_channel.create_app()

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
