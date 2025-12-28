"""Middleware implementations for logging agent activities."""
import json
from typing import Awaitable, Callable
from rich.syntax import Syntax

from agent_framework import FunctionMiddleware, FunctionInvocationContext
from agent_framework import AgentMiddleware, AgentRunContext
from agent_framework import ChatMiddleware, ChatContext

from aletheia.utils.logging import log_debug
from aletheia.console import get_console_wrapper
from aletheia.commands import COMMANDS


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
        for agent in COMMANDS["agents"].agents:
            skipped_functions.append(agent.name)

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
