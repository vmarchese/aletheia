"""Gateway session management for Aletheia daemon."""

import asyncio
from pathlib import Path
from typing import AsyncIterator

from aletheia.agents.entrypoint import Orchestrator
from aletheia.agents.instructions_loader import Loader
from aletheia.config import Config
from aletheia.daemon.history import ChatHistoryLogger
from aletheia.engram.tools import Engram
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session


class GatewaySessionManager:
    """
    Manages sessions for the gateway daemon.

    Currently supports single active session.
    Designed for future multi-session support.
    """

    def __init__(self, config: Config, engram: Engram | None = None):
        """Initialize session manager."""
        self.config = config
        self.engram = engram
        self.active_session: Session | None = None
        self.orchestrator: Orchestrator | None = None
        self.chat_logger: ChatHistoryLogger | None = None
        self.additional_middleware: list | None = None  # For Web UI function middleware

    async def create_session(
        self,
        name: str | None = None,
        password: str | None = None,
        unsafe: bool = False,
        verbose: bool = False,
    ) -> Session:
        """Create and activate a new session."""
        # Close any existing session first
        if self.active_session is not None:
            await self.close_active_session()

        # Create new session
        session = Session.create(
            name=name,
            password=password,
            unsafe=unsafe,
            verbose=verbose,
        )

        # Initialize orchestrator for this session
        await self._init_orchestrator(session)

        # Initialize chat history logger
        self.chat_logger = ChatHistoryLogger(session.session_path)

        self.active_session = session
        return session

    async def resume_session(
        self,
        session_id: str,
        password: str | None = None,
        unsafe: bool = False,
    ) -> Session:
        """Resume an existing session and make it active."""
        # Close any existing session first
        if self.active_session is not None:
            await self.close_active_session()

        # Resume session
        session = Session.resume(
            session_id=session_id,
            password=password,
            unsafe=unsafe,
        )

        # Initialize orchestrator for this session
        await self._init_orchestrator(session)

        # Initialize chat history logger
        self.chat_logger = ChatHistoryLogger(session.session_path)

        self.active_session = session
        return session

    async def close_active_session(self) -> None:
        """Close the currently active session and cleanup orchestrator."""
        if self.orchestrator:
            try:
                await self.orchestrator.cleanup()
            except Exception:
                pass

            # Clean up sub-agents
            for agent in getattr(self.orchestrator, "sub_agent_instances", []):
                try:
                    await agent.cleanup()
                except Exception:
                    pass

        self.orchestrator = None
        self.active_session = None
        self.chat_logger = None

    def get_active_session(self) -> Session | None:
        """Get the currently active session."""
        return self.active_session

    def get_orchestrator(self) -> Orchestrator | None:
        """Get the orchestrator for the active session."""
        return self.orchestrator

    async def send_message(
        self, message: str, channel: str
    ) -> AsyncIterator[dict[str, any]]:
        """Send message to active session and yield streaming JSON response chunks.

        All channels now receive streaming JSON chunks and decide how to render them:
        - Web UI: Renders structured JSON incrementally with tabs
        - TUI/Telegram: Accumulates JSON and formats to markdown

        Yields:
            dict with keys:
                - type: "json_chunk" | "json_complete" | "json_error" | "usage"
                - content: JSON string (for json_chunk/json_complete) or error message
                - parsed: Optional parsed JSON dict (for json_complete)
        """
        if not self.active_session or not self.orchestrator:
            raise RuntimeError("No active session")

        # Log user message
        if self.chat_logger:
            self.chat_logger.log_user_message(message, channel)

        # Import here to avoid circular dependency
        import json
        import logging

        from agent_framework import (
            ChatMessage,
            Role,
            TextContent,
            UsageContent,
        )
        from aletheia.agents.model import AgentResponse

        logger = logging.getLogger(__name__)

        # Send to orchestrator and stream response
        json_buffer = ""
        parsed_response = None
        parsed_successfully = False

        async for response in self.orchestrator.agent.run_stream(
            messages=[
                ChatMessage(role=Role.USER, contents=[TextContent(text=message)])
            ],
            thread=self.orchestrator.thread,
            response_format=AgentResponse,
        ):
            # Check for regular text content
            if response and response.text:
                json_buffer += response.text

                # Try to parse the accumulated JSON
                try:
                    parsed_response = json.loads(json_buffer)
                    parsed_successfully = True

                    # Yield complete parsed JSON
                    yield {
                        "type": "json_complete",
                        "content": json_buffer,
                        "parsed": parsed_response,
                    }
                except json.JSONDecodeError:
                    # JSON not complete yet, yield chunk for incremental rendering
                    yield {
                        "type": "json_chunk",
                        "content": response.text,
                        "buffer": json_buffer,
                    }

            # Check for usage content
            if response and response.contents:
                for content in response.contents:
                    if isinstance(content, UsageContent):
                        # Update session usage
                        self.active_session.update_usage(
                            input_tokens=content.details.input_token_count,
                            output_tokens=content.details.output_token_count,
                        )

                        yield {
                            "type": "usage",
                            "usage": {
                                "input_tokens": content.details.input_token_count,
                                "output_tokens": content.details.output_token_count,
                                "total_tokens": content.details.total_token_count,
                            },
                        }

        # Final check: If JSON parsing never succeeded, send error
        if not parsed_successfully and json_buffer.strip():
            logger.warning(
                f"Session manager: JSON parsing failed. Buffer length: {len(json_buffer)}"
            )
            logger.warning(f"Buffer preview: {json_buffer[:500]}")
            yield {
                "type": "json_error",
                "content": json_buffer,
                "error": "Failed to parse JSON response",
            }

        # Log complete response
        if self.chat_logger:
            self.chat_logger.log_assistant_response(
                json_buffer,
                parsed_response.get("agent") if parsed_response else None,
                channel,
            )

    def list_sessions(self) -> list[dict[str, any]]:
        """List all available sessions."""
        return Session.list_sessions()

    async def _init_orchestrator(self, session: Session) -> None:
        """Initialize orchestrator for a session (extracted from cli.py)."""
        # Import here to avoid circular dependency at module level
        from aletheia.cli import _build_plugins

        prompt_loader = Loader()

        # Initialize scratchpad
        scratchpad = Scratchpad(
            session_dir=session.session_path, encryption_key=session.get_key()
        )
        session.scratchpad = scratchpad

        # Build plugins with additional middleware (e.g., WebUIFunctionMiddleware)
        tools, agent_instances = _build_plugins(
            config=self.config,
            prompt_loader=prompt_loader,
            session=session,
            scratchpad=scratchpad,
            additional_middleware=self.additional_middleware,
            engram=self.engram,
        )

        # Create orchestrator with additional middleware
        orchestrator = Orchestrator(
            name="orchestrator",
            description="Orchestrator agent managing the investigation workflow",
            instructions=prompt_loader.load("orchestrator", "instructions"),
            session=session,
            sub_agents=tools,
            scratchpad=scratchpad,
            config=self.config,
            additional_middleware=self.additional_middleware,
            engram=self.engram,
        )

        # Initialize thread
        orchestrator.thread = orchestrator.agent.get_new_thread()

        # Store for cleanup
        orchestrator.sub_agent_instances = agent_instances

        self.orchestrator = orchestrator
