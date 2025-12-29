"""Middleware implementations for logging agent activities."""
import asyncio
import json
from typing import Awaitable, Callable
from rich.syntax import Syntax

from agent_framework import FunctionMiddleware, FunctionInvocationContext
from agent_framework import AgentMiddleware, AgentRunContext
from agent_framework import ChatMiddleware, ChatContext

from aletheia.utils.logging import log_debug
from aletheia.console import get_console_wrapper
# Lazy import to avoid circular dependency
# from aletheia.commands import COMMANDS


class ConsoleFunctionMiddleware(FunctionMiddleware):
    """Function middleware that logs function execution."""

    async def process(
        self,
        context: FunctionInvocationContext,
        next: Callable[[FunctionInvocationContext], Awaitable[None]],
    ) -> None:
        if get_console_wrapper().get_output_functions() is False:
            await next(context)
            return
        console = get_console_wrapper().get_console()

        # Pre-processing: Log before function execution
        skipped_functions = ["write_journal_entry",
                             "read_scratchpad"]
        try:
            from aletheia.commands import COMMANDS
            for agent in COMMANDS["agents"].agents:
                skipped_functions.append(agent.name)
        except (ImportError, KeyError):
            pass

        if context.function.name not in skipped_functions:
            arguments = ""
            for arg_key, arg_value in context.arguments.model_dump().items():
                arguments += f"{arg_key}=\"{arg_value}\" "

            console.print(f" • [cyan][bold]{context.function.name}[/bold][/cyan]({arguments})")

        # Continue to next middleware or function execution
        await next(context)


class LoggingFunctionMiddleware(FunctionMiddleware):
    """Function middleware that logs function execution."""

    async def process(
        self,
        context: FunctionInvocationContext,
        next: Callable[[FunctionInvocationContext], Awaitable[None]],
    ) -> None:
        # Pre-processing: Log before function execution
        log_debug(f"[Function::{context.function.name}] Calling function: {context.arguments}")

        # Continue to next middleware or function execution
        await next(context)

        # Post-processing: Log after function execution
        log_debug(f"[Function::{context.function.name}] Function completed")


class LoggingAgentMiddleware(AgentMiddleware):
    """Agent middleware that logs execution."""

    async def process(
        self,
        context: AgentRunContext,
        next: Callable[[AgentRunContext], Awaitable[None]],
    ) -> None:
        # Pre-processing: Log before agent execution
        log_debug(f"[Agent::{context.agent.name}] Starting execution {context.metadata}")

        # Continue to next middleware or agent execution
        await next(context)

        # Post-processing: Log after agent execution
        log_debug(f"[Agent::{context.agent.name}] Execution completed: {context.result}")


class LoggingChatMiddleware(ChatMiddleware):
    """Chat middleware that logs AI interactions."""

    async def process(
        self,
        context: ChatContext,
        next: Callable[[ChatContext], Awaitable[None]],
    ) -> None:
        # Pre-processing: Log before AI call
        print(f"[Chat] Sending {len(context.messages)} messages to AI")
        for msg in context.messages:
            print(f"[Chat] Message from {msg.role}: {msg.text}")

        # Continue to next middleware or AI service
        await next(context)

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
        next: Callable[[FunctionInvocationContext], Awaitable[None]],
    ) -> None:
        # Pre-processing: Send function call event
        # Skip functions we don't want to show
        skipped_functions = [
            "write_journal_entry",
            "read_scratchpad"
        ]

        # Also skip agent tool calls
        try:
            from aletheia.commands import COMMANDS
            if "agents" in COMMANDS:
                for agent in COMMANDS["agents"].agents:
                    skipped_functions.append(agent.name)
        except (ImportError, KeyError):
            # COMMANDS might not be available, just skip this
            pass

        log_debug(f"[WebUIFunctionMiddleware] Function called: {context.function.name}")

        if context.function.name not in skipped_functions:
            log_debug("function not in skipped list, preparing to send event")
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
                log_debug(f"[WebUIFunctionMiddleware] Sending function_call event for {context.function.name}")
                await self.event_queue.put({
                    "type": "function_call",
                    "content": {
                        "function_name": context.function.name,
                        "arguments": arguments
                    }
                })
                log_debug(f"[WebUIFunctionMiddleware] Event sent successfully")
            except Exception as e:
                log_debug(f"[WebUIFunctionMiddleware] Error sending event: {e}")

        # Continue to next middleware or function execution
        await next(context)
