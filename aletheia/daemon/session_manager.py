"""Gateway session management for Aletheia daemon."""

import json
from collections.abc import AsyncIterator

import structlog
from agent_framework import AgentSession, Content, Message

from aletheia.agents.entrypoint import Orchestrator
from aletheia.agents.instructions_loader import Loader
from aletheia.agents.model import AgentResponse
from aletheia.cli import _build_plugins
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

        # Enable verbose file logging if requested
        if session.get_metadata().verbose:
            from aletheia.utils.logging import enable_session_file_logging

            enable_session_file_logging(session.session_path)

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

        # Re-enable verbose file logging if session was created with verbose
        if session.get_metadata().verbose:
            from aletheia.utils.logging import enable_session_file_logging

            enable_session_file_logging(session.session_path)

        self.active_session = session
        return session

    async def close_active_session(self) -> None:
        """Close the currently active session and cleanup orchestrator."""
        # Disable session file logging if it was enabled
        from aletheia.utils.logging import disable_session_file_logging

        disable_session_file_logging()

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
                      | "compaction_start" | "compaction_end"
                - content: JSON string (for json_chunk/json_complete) or error message
                - parsed: Optional parsed JSON dict (for json_complete)
        """
        if not self.active_session or not self.orchestrator:
            raise RuntimeError("No active session")

        # Log user message
        if self.chat_logger:
            self.chat_logger.log_user_message(message, channel)

        logger = structlog.get_logger(__name__)

        # Context compaction check
        async for chunk in self._maybe_compact_context():
            yield chunk

        # Send to orchestrator and stream response
        stream = self.orchestrator.agent.run(
            messages=[Message(role="user", contents=[Content.from_text(message)])],
            stream=True,
            session=self.orchestrator.agent_session,
            options={"response_format": AgentResponse},
        )
        agent_resp = await stream.get_final_response()

        input_tokens = agent_resp.usage_details.get("input_token_count", 0)
        output_tokens = agent_resp.usage_details.get("output_token_count", 0)

        self.active_session.update_usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        max_context = self.config.max_context_window
        # Sum individual section estimates (same as /context command's
        # ContextWindow.estimated_used) to stay consistent. We must NOT
        # use "total_estimated" because it is recorded before message
        # trimming, while the individual keys are updated after trimming.
        ctx_state = self.orchestrator.agent_session.state.get(
            "context_window", {}
        )
        estimated_used = (
            ctx_state.get("system_prompt_tokens", 0)
            + ctx_state.get("tools_tokens", 0)
            + ctx_state.get("memory_tokens", 0)
            + ctx_state.get("messages_tokens", 0)
        )
        usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "max_context_window": max_context,
            "context_utilization": (
                round(estimated_used / max_context * 100, 1)
                if max_context > 0
                else 0
            ),
        }

        logger.debug("Session manager: Completed streaming response - {agent_resp}")
        if agent_resp.value:
            yield {
                "type": "json_complete",
                "content": json.dumps(agent_resp.value),
                "parsed": json.loads(json.dumps(agent_resp.value)),
                "usage": usage,
            }
        else:
            # value is None — try to parse the raw text as AgentResponse
            logger.warning(
                "Session manager: agent_resp.value is None, "
                "attempting to parse agent_resp.text"
            )
            try:
                parsed = AgentResponse.model_validate_json(agent_resp.text)
                yield {
                    "type": "json_complete",
                    "content": parsed.model_dump_json(),
                    "parsed": parsed.model_dump(),
                    "usage": usage,
                }
            except Exception as e:
                logger.error(
                    "Session manager: Failed to parse agent_resp.text "
                    "as AgentResponse: %s",
                    e,
                )
                yield {
                    "type": "json_complete",
                    "content": agent_resp.text,
                    "parsed": "",
                    "usage": usage,
                }

        """
        # Log complete response
        if self.chat_logger:
            self.chat_logger.log_assistant_response(
                json_buffer,
                parsed_response.get("agent") if parsed_response else None,
                channel,
            )
        """

    def list_sessions(self) -> list[dict[str, any]]:
        """List all available sessions."""
        return Session.list_sessions()

    async def _maybe_compact_context(
        self,
    ) -> AsyncIterator[dict[str, any]]:
        """Check context utilization and compact if above threshold.

        Yields compaction_start and compaction_end chunks if compaction occurs.
        """
        if not self.orchestrator or not self.active_session:
            return

        logger = structlog.get_logger(__name__)

        # Get context state from previous turn
        agent_session = self.orchestrator.agent_session
        ctx_state = agent_session.state.get("context_window", {})
        # Sum individual section estimates (same as /context command's
        # ContextWindow.estimated_used). We must NOT use "total_estimated"
        # because it is recorded before message trimming.
        estimated_used = (
            ctx_state.get("system_prompt_tokens", 0)
            + ctx_state.get("tools_tokens", 0)
            + ctx_state.get("memory_tokens", 0)
            + ctx_state.get("messages_tokens", 0)
        )
        max_tokens = self.config.max_context_window

        if max_tokens <= 0 or estimated_used <= 0:
            return

        utilization = estimated_used / max_tokens
        threshold = self.config.context_compaction_threshold

        if utilization < threshold:
            return

        # Get current messages from InMemoryHistoryProvider state
        in_memory_state = agent_session.state.get("in_memory", {})
        messages = in_memory_state.get("messages", [])

        if len(messages) < 2:
            return  # Not enough to compact

        initial_pct = round(utilization * 100, 1)
        logger.info(
            f"Context at {initial_pct}% (threshold: "
            f"{threshold * 100}%) - starting compaction"
        )

        # Yield start notification
        yield {
            "type": "compaction_start",
            "content": {
                "context_pct": initial_pct,
                "message": f"Context at {initial_pct}% - compacting...",
            },
        }

        # Serialize messages for compaction
        from aletheia.context import (
            _serialize_message,
            estimate_tokens,
        )

        conversation_text = "\n\n".join(
            f"[{getattr(msg, 'role', 'unknown')}]: {_serialize_message(msg)}"
            for msg in messages
        )

        # Run compaction
        summary = await self._run_compaction(conversation_text)

        # Replace messages with compacted summary
        summary_message = Message(
            role="assistant",
            contents=[Content.from_text(f"[COMPACTED CONTEXT]\n\n{summary}")],
        )
        in_memory_state["messages"] = [summary_message]

        # Calculate new utilization
        new_msg_tokens = estimate_tokens(summary)
        fixed_tokens = (
            ctx_state.get("system_prompt_tokens", 0)
            + ctx_state.get("tools_tokens", 0)
            + ctx_state.get("memory_tokens", 0)
        )
        new_total = fixed_tokens + new_msg_tokens
        final_pct = round(new_total / max_tokens * 100, 1) if max_tokens > 0 else 0

        # Write to scratchpad
        scratchpad = getattr(self.active_session, "scratchpad", None)
        if scratchpad:
            scratchpad.write_journal_entry(
                agent="CompactionAgent",
                description="Context compaction performed",
                text=(
                    f"Initial context: {initial_pct}%\n"
                    f"Final context: {final_pct}%\n"
                    f"Messages before: {len(messages)}\n"
                    f"Messages after: 1"
                ),
            )

        logger.info(f"Compaction complete: {initial_pct}% -> {final_pct}%")

        # Yield end notification
        yield {
            "type": "compaction_end",
            "content": {
                "initial_pct": initial_pct,
                "final_pct": final_pct,
                "message": (f"Compaction complete: {initial_pct}% -> {final_pct}%"),
            },
        }

    async def _run_compaction(self, conversation_text: str) -> str:
        """Run the compaction agent on conversation text.

        Args:
            conversation_text: Serialized conversation history.

        Returns:
            Compressed summary text.
        """
        from aletheia.agents.compaction.compaction_agent import (
            CompactionAgent,
        )

        loader = Loader()
        instructions = loader.load("compaction", "instructions")

        compaction_agent = CompactionAgent(
            name="compaction_agent",
            instructions=instructions,
            description="Compresses conversation context",
        )

        compaction_session = AgentSession()
        response = await compaction_agent.agent.run(
            messages=[
                Message(
                    role="user",
                    contents=[
                        Content.from_text(
                            "Compress the following conversation "
                            "history:\n\n" + conversation_text
                        )
                    ],
                )
            ],
            session=compaction_session,
        )

        return response.text or ""

    async def _init_orchestrator(self, session: Session) -> None:
        """Initialize orchestrator for a session (extracted from cli.py)."""
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

        # Initialize session for conversation state
        orchestrator.agent_session = AgentSession()

        # Store for cleanup
        orchestrator.sub_agent_instances = agent_instances

        self.orchestrator = orchestrator
