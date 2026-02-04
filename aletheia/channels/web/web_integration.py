"""Web channel connector for the Aletheia gateway.

This module implements the web channel as a BaseChannelConnector that
communicates with the gateway via WebSocket, and exposes a FastAPI app
for the browser frontend.

Flow: Frontend (REST/SSE) → WebChannelConnector → WebSocket → Gateway
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from aletheia.channels.base import BaseChannelConnector
from aletheia.channels.manifest import ChannelCapability, ChannelManifest
from aletheia.daemon.protocol import ProtocolMessage

logger = structlog.get_logger("aletheia.channel.web")


class WebChannelConnector(BaseChannelConnector):
    """Web channel that bridges browser clients to the gateway via WebSocket.

    - Extends BaseChannelConnector for gateway WebSocket communication
    - Exposes a FastAPI app for the browser frontend (REST + SSE)
    - All business logic is delegated to the gateway
    """

    def __init__(
        self,
        gateway_url: str = "ws://127.0.0.1:8765",
        config: dict[str, Any] | None = None,
    ):
        """Initialize web channel connector."""
        super().__init__(gateway_url, config)
        self._pending_responses: dict[str, asyncio.Future[ProtocolMessage]] = {}
        self._stream_queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._active_session_id: str | None = None

    @classmethod
    def manifest(cls) -> ChannelManifest:
        """Return web channel manifest."""
        return ChannelManifest(
            channel_type="web",
            display_name="Web UI",
            description="Browser-based web interface for Aletheia",
            capabilities={
                ChannelCapability.STREAMING,
                ChannelCapability.RICH_TEXT,
                ChannelCapability.INTERACTIVE,
            },
            requires_daemon=True,
            supports_threading=False,
        )

    async def handle_gateway_message(self, message: ProtocolMessage) -> None:
        """Route incoming gateway messages to pending futures or stream queues."""
        msg_type = message.type

        # Streaming messages go to the session's SSE queue
        if msg_type in ("chat_stream_start", "chat_stream_chunk", "chat_stream_end"):
            await self._handle_stream_message(message)
            return

        # Error responses - try to resolve a pending future
        if msg_type == "error":
            self._resolve_error(message)
            return

        # Session required (no active session for chat)
        if msg_type == "session_required":
            await self._handle_stream_error("No active session")
            return

        # Request-response messages - resolve pending futures
        if msg_type in self._pending_responses:
            future = self._pending_responses.pop(msg_type)
            if not future.done():
                future.set_result(message)
            return

        logger.debug(f"Unhandled gateway message type: {msg_type}")

    async def render_response(self, response: dict[str, Any]) -> None:
        """No-op - rendering is handled by the browser frontend."""
        pass

    async def on_connected(self, payload: dict[str, Any]) -> None:
        """Handle initial connection to gateway."""
        session_info = payload.get("session")
        if session_info:
            self._active_session_id = session_info.get("id")
        logger.info("Web channel connected to gateway")

    # ------------------------------------------------------------------
    # Gateway communication helpers
    # ------------------------------------------------------------------

    async def _send_and_wait(
        self,
        msg_type: str,
        payload: dict[str, Any],
        response_type: str,
        timeout: float = 30.0,
    ) -> ProtocolMessage:
        """Send a message to the gateway and wait for a specific response type."""
        if not self.connected or not self.websocket:
            raise RuntimeError("Not connected to gateway")

        future: asyncio.Future[ProtocolMessage] = (
            asyncio.get_event_loop().create_future()
        )
        self._pending_responses[response_type] = future

        msg = ProtocolMessage.create(msg_type, payload)
        await self.websocket.send(msg.to_json())

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_responses.pop(response_type, None)
            raise

    def _resolve_error(self, message: ProtocolMessage) -> None:
        """Try to resolve a pending future with an error."""
        code = message.payload.get("code", "")
        error_msg = message.payload.get("message", "Unknown error")

        # Map error code prefixes to the response types they correspond to
        error_to_response = {
            "SESSION_CREATE": "session_created",
            "SESSION_RESUME": "session_resumed",
            "SESSION_DELETE": "session_deleted",
            "SESSION_NOT_FOUND": "session_deleted",
            "SESSION_METADATA": "session_metadata",
            "COMMAND_LIST": "command_list",
            "COMMAND_EXECUTE": "chat_stream_end",
            "SCRATCHPAD": "scratchpad_data",
            "TIMELINE": "timeline_data",
            "MISSING_SESSION_ID": None,
            "MISSING_MESSAGE": None,
        }

        for prefix, response_type in error_to_response.items():
            if prefix in code:
                if response_type and response_type in self._pending_responses:
                    future = self._pending_responses.pop(response_type)
                    if not future.done():
                        future.set_exception(
                            HTTPException(status_code=400, detail=error_msg)
                        )
                return

        # If no pending future matched, push error to stream queue
        asyncio.create_task(self._handle_stream_error(error_msg))

    async def _handle_stream_message(self, message: ProtocolMessage) -> None:
        """Push streaming message to the appropriate session queue."""
        payload = message.payload
        msg_type = message.type

        session_id = self._active_session_id or "default"
        if session_id not in self._stream_queues:
            self._stream_queues[session_id] = asyncio.Queue()

        queue = self._stream_queues[session_id]

        if msg_type == "chat_stream_start":
            pass  # Stream start is implicit for the frontend
        elif msg_type == "chat_stream_chunk":
            chunk_type = payload.get("chunk_type")
            if chunk_type == "function_call":
                await queue.put(
                    {
                        "type": "function_call",
                        "content": payload.get("content", {}),
                    }
                )
            elif chunk_type == "text":
                await queue.put(
                    {
                        "type": "text",
                        "content": payload.get("content", ""),
                    }
                )
            else:
                # json_chunk, json_complete, json_error
                item: dict[str, Any] = {
                    "type": chunk_type,
                    "content": payload.get("content", ""),
                    "parsed": payload.get("parsed"),
                }
                usage = payload.get("usage")
                if usage:
                    item["usage"] = usage
                await queue.put(item)
        elif msg_type == "chat_stream_end":
            logger.debug("Web channel: Stream ended - %s", payload)
            await queue.put({"type": "done"})

    async def _handle_stream_error(self, error_msg: str) -> None:
        """Push an error event to the active stream queue."""
        session_id = self._active_session_id or "default"
        if session_id in self._stream_queues:
            queue = self._stream_queues[session_id]
            await queue.put({"type": "error", "content": error_msg})

    async def _ensure_session_active(
        self,
        session_id: str,
        password: str | None = None,
        unsafe: bool = False,
    ) -> None:
        """Ensure the given session is active in the gateway."""
        if self._active_session_id == session_id:
            return

        await self._send_and_wait(
            "session_resume",
            {
                "session_id": session_id,
                "password": password,
                "unsafe": unsafe,
            },
            "session_resumed",
        )
        self._active_session_id = session_id

    # ------------------------------------------------------------------
    # FastAPI app
    # ------------------------------------------------------------------

    def create_app(self) -> FastAPI:
        """Create and return the FastAPI app with thin forwarding endpoints."""
        app = FastAPI(
            title="Aletheia Web UI",
            description="Web interface for Aletheia - gateway integrated",
        )

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Mount static files
        static_dir = Path(__file__).parent.parent.parent / "ui" / "static"
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        connector = self

        # Request models
        class SessionCreateRequest(BaseModel):
            name: str | None = None
            password: str | None = None
            unsafe: bool = False
            verbose: bool = True

        class ChatRequest(BaseModel):
            message: str
            password: str | None = None

        # --- Routes ---

        @app.get("/")
        async def read_root() -> FileResponse:
            return FileResponse(static_dir / "index.html")

        @app.get("/sessions", response_model=list[dict[str, Any]])
        async def list_sessions() -> list[dict[str, Any]]:
            """List all available sessions."""
            response = await connector._send_and_wait(
                "session_list", {}, "session_list"
            )
            return response.payload.get("sessions", [])

        @app.post("/sessions", response_model=dict[str, Any])
        async def create_session(request: SessionCreateRequest) -> dict[str, Any]:
            """Create a new session via gateway."""
            response = await connector._send_and_wait(
                "session_create",
                {
                    "name": request.name,
                    "password": request.password,
                    "unsafe": request.unsafe,
                    "verbose": request.verbose,
                },
                "session_created",
            )
            session_data = response.payload.get("session", {})
            connector._active_session_id = session_data.get("id")
            return session_data

        @app.get("/sessions/{session_id}", response_model=dict[str, Any])
        async def get_session_metadata(
            session_id: str,
            password: str | None = None,
            unsafe: bool = False,
        ) -> dict[str, Any]:
            """Get session metadata."""
            response = await connector._send_and_wait(
                "session_metadata",
                {
                    "session_id": session_id,
                    "password": password,
                    "unsafe": unsafe,
                },
                "session_metadata",
            )
            return response.payload.get("metadata", {})

        @app.delete("/sessions/{session_id}")
        async def delete_session(session_id: str) -> dict[str, str]:
            """Delete a session."""
            await connector._send_and_wait(
                "session_delete",
                {"session_id": session_id},
                "session_deleted",
            )

            # Clear local state
            if connector._active_session_id == session_id:
                connector._active_session_id = None
            connector._stream_queues.pop(session_id, None)

            return {
                "status": "success",
                "message": f"Session {session_id} deleted",
            }

        @app.get("/commands", response_model=list[dict[str, str]])
        async def list_commands() -> list[dict[str, str]]:
            """List all available commands."""
            response = await connector._send_and_wait(
                "command_list", {}, "command_list"
            )
            return response.payload.get("commands", [])

        @app.post("/sessions/{session_id}/chat")
        async def chat_session(
            session_id: str,
            request: ChatRequest,
            unsafe: bool = False,
        ) -> dict[str, str]:
            """Send a message to a session via gateway."""
            # Ensure queue exists for this session
            if session_id not in connector._stream_queues:
                connector._stream_queues[session_id] = asyncio.Queue()

            # Ensure session is active
            await connector._ensure_session_active(session_id, request.password, unsafe)

            # Check for slash commands
            if request.message.strip().startswith("/"):
                msg = ProtocolMessage.create(
                    "command_execute",
                    {"message": request.message, "channel": "web"},
                )
                await connector.websocket.send(msg.to_json())
                return {"status": "processing_command"}

            # Send chat message to gateway
            msg = ProtocolMessage.create(
                "chat_message",
                {"message": request.message},
            )
            await connector.websocket.send(msg.to_json())
            return {"status": "processing"}

        @app.get("/sessions/{session_id}/stream")
        async def stream_session(session_id: str) -> EventSourceResponse:
            """SSE endpoint for session updates."""
            if session_id not in connector._stream_queues:
                connector._stream_queues[session_id] = asyncio.Queue()

            queue = connector._stream_queues[session_id]

            async def event_generator() -> Any:
                while True:
                    try:
                        data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield {"event": "ping", "data": ""}
                        continue

                    if data["type"] == "done":
                        yield {"data": json.dumps(data)}
                        continue

                    if data["type"] == "error":
                        yield {"event": "error", "data": data["content"]}
                        break

                    logger.debug(f"Web channel: Streaming data - {data}")
                    yield {"data": json.dumps(data)}

            return EventSourceResponse(event_generator())

        @app.get("/sessions/{session_id}/scratchpad")
        async def get_session_scratchpad(
            session_id: str,
            password: str | None = None,
            unsafe: bool = False,
        ) -> dict[str, Any]:
            """Get session scratchpad content."""
            response = await connector._send_and_wait(
                "scratchpad_get",
                {
                    "session_id": session_id,
                    "password": password,
                    "unsafe": unsafe,
                },
                "scratchpad_data",
            )
            return {"content": response.payload.get("content", "")}

        @app.get("/sessions/{session_id}/timeline")
        async def get_session_timeline(
            session_id: str,
            password: str | None = None,
            unsafe: bool = False,
        ) -> dict[str, Any]:
            """Get session timeline."""
            response = await connector._send_and_wait(
                "timeline_get",
                {
                    "session_id": session_id,
                    "password": password,
                    "unsafe": unsafe,
                },
                "timeline_data",
                timeout=120.0,  # Timeline generation can be slow
            )
            return response.payload

        return app
