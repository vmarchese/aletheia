"""Middleware implementations for logging agent activities."""

import asyncio
import contextvars
from collections.abc import Awaitable, Callable

import structlog
from agent_framework import (
    AgentContext,
    AgentMiddleware,
    ChatContext,
    ChatMiddleware,
    FunctionInvocationContext,
    FunctionMiddleware,
)

from aletheia.console import get_console_wrapper

# Lazy import to avoid circular dependency
# from aletheia.commands import COMMANDS

logger = structlog.get_logger(__name__)

# Context variable to track the currently executing agent name.
# This is set by LoggingAgentMiddleware and read by function middlewares
# to prefix function calls with the agent name.
_current_agent_name: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_current_agent_name", default=None
)


def get_current_agent_name() -> str | None:
    """Get the name of the currently executing agent."""
    return _current_agent_name.get()


class ConsoleFunctionMiddleware(FunctionMiddleware):
    """Function middleware that logs function execution."""

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        if get_console_wrapper().get_output_functions() is False:
            await call_next()
            return
        console = get_console_wrapper().get_console()

        # Pre-processing: Log before function execution
        skipped_functions = ["write_journal_entry", "read_scratchpad"]
        try:
            from aletheia.commands import COMMANDS

            for agent in COMMANDS["agents"].agents:
                skipped_functions.append(agent.name)
        except (ImportError, KeyError):
            pass

        if context.function.name not in skipped_functions:
            arguments = ""
            for arg_key, arg_value in context.arguments.model_dump().items():
                arguments += f'{arg_key}="{arg_value}" '

            agent_name = get_current_agent_name() or "orchestrator"
            console.print(
                f" • [cyan][bold]{agent_name}::{context.function.name}[/bold][/cyan]({arguments})"
            )

        # Continue to next middleware or function execution
        await call_next()


class LoggingFunctionMiddleware(FunctionMiddleware):
    """Function middleware that logs function execution."""

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        # Pre-processing: Log before function execution
        logger.debug(
            f"[Function::{context.function.name}] Calling function: {context.arguments}"
        )

        # Continue to next middleware or function execution
        await call_next()

        # Post-processing: Log after function execution
        logger.debug(f"[Function::{context.function.name}] Function completed")


class LoggingAgentMiddleware(AgentMiddleware):
    """Agent middleware that logs execution and tracks the current agent name."""

    async def process(
        self,
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        # Pre-processing: Log before agent execution
        logger.debug(
            f"[Agent::{context.agent.name}] Starting execution {context.metadata}"
        )

        # Track the current agent name so function middlewares can read it
        token = _current_agent_name.set(context.agent.name)
        try:
            # Continue to next middleware or agent execution
            await call_next()
        finally:
            # Restore previous agent name (handles nested agent calls)
            _current_agent_name.reset(token)

        # Post-processing: Log after agent execution
        logger.debug(
            f"[Agent::{context.agent.name}] Execution completed: {context.result}"
        )


class LoggingChatMiddleware(ChatMiddleware):
    """Chat middleware that logs AI interactions."""

    async def process(
        self,
        context: ChatContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        # Pre-processing: Log before AI call
        print(f"[Chat] Sending {len(context.messages)} messages to AI")
        for msg in context.messages:
            print(f"[Chat] Message from {msg.role}: {msg.text}")

        # Continue to next middleware or AI service
        await call_next()

        # Post-processing: Log after AI response
        print("[Chat] AI response received")


class WebUIFunctionMiddleware(FunctionMiddleware):
    """Function middleware that sends function calls to web UI via event queue."""

    def __init__(self, event_queue: "asyncio.Queue"):
        """Initialize with event queue for web UI streaming.

        Args:
            event_queue: Async queue to send function call events to SSE stream
        """
        self.event_queue = event_queue

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        # Pre-processing: Send function call event
        # Skip functions we don't want to show
        skipped_functions = ["write_journal_entry", "read_scratchpad"]

        # Also skip agent tool calls
        try:
            from aletheia.commands import COMMANDS

            if "agents" in COMMANDS:
                for agent in COMMANDS["agents"].agents:
                    skipped_functions.append(agent.name)
        except (ImportError, KeyError):
            # COMMANDS might not be available, just skip this
            pass

        logger.debug(
            f"[WebUIFunctionMiddleware] Function called: {context.function.name}"
        )

        if context.function.name not in skipped_functions:
            logger.debug("function not in skipped list, preparing to send event")
            # Format arguments
            arguments = {}
            for arg_key, arg_value in context.arguments.model_dump().items():
                # Truncate long values
                str_value = str(arg_value)
                if len(str_value) > 100:
                    str_value = str_value[:97] + "..."
                arguments[arg_key] = str_value

            # Send event to queue
            try:
                agent_name = get_current_agent_name() or "orchestrator"
                logger.debug(
                    f"[WebUIFunctionMiddleware] Sending function_call event for {context.function.name}"
                )
                await self.event_queue.put(
                    {
                        "type": "function_call",
                        "content": {
                            "agent_name": agent_name,
                            "function_name": context.function.name,
                            "arguments": arguments,
                        },
                    }
                )
                logger.debug("[WebUIFunctionMiddleware] Event sent successfully")
            except Exception as e:
                logger.debug(f"[WebUIFunctionMiddleware] Error sending event: {e}")

        # Continue to next middleware or function execution
        await call_next()
