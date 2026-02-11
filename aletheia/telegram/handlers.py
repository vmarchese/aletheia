"""Telegram command handlers for Aletheia bot."""

import asyncio
import html as html_module
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from agent_framework import ChatMessage, TextContent, UsageContent, UsageDetails
from telegram import Chat, Update
from telegram.ext import ContextTypes

from aletheia.agents.model import AgentResponse
from aletheia.commands import COMMANDS, expand_custom_command
from aletheia.config import Config
from aletheia.session import Session, SessionNotFoundError

from .formatter import format_agent_response, split_message
from .session_manager import TelegramSessionManager

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def continuous_typing(chat: Chat, interval: float = 4.0) -> AsyncIterator[None]:
    """Context manager that continuously sends typing indicator.

    Telegram's typing indicator only lasts ~5 seconds, so for longer
    operations we need to periodically refresh it.

    Args:
        chat: Telegram chat to send typing action to
        interval: Seconds between typing actions (default 4s, indicator lasts ~5s)

    Yields:
        None - use as async context manager
    """
    stop_event = asyncio.Event()

    async def send_typing() -> None:
        while not stop_event.is_set():
            try:
                await chat.send_action("typing")
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception:
                # Don't let typing errors break the main flow
                break

    task = asyncio.create_task(send_typing())
    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def new_session_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /new_session command - create a new investigation session.

    Args:
        update: Telegram update object
        context: Telegram context with bot_data
    """
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    session_manager: TelegramSessionManager = context.bot_data["session_manager"]
    config: Config = context.bot_data["config"]

    # Check authorization
    if config.telegram_allowed_users and user_id not in config.telegram_allowed_users:
        await update.message.reply_text("⛔ Unauthorized. Contact admin to get access.")
        return

    try:
        # Create new session in unsafe mode (no password, plaintext storage)
        # Always verbose for Telegram sessions to enable trace logging
        session = Session.create(
            name=f"Telegram-{user_id}",
            password=None,
            unsafe=True,
            verbose=True,
        )

        # Set as active session
        session_manager.set_active_session(user_id, session.session_id)

        # Initialize orchestrator
        from aletheia.cli import init_orchestrator

        engram = context.bot_data.get("engram")
        orchestrator = await init_orchestrator(session, config, engram=engram)
        session_manager.set_orchestrator(session.session_id, orchestrator)

        await update.message.reply_text(
            f"✅ New session created: <code>{session.session_id}</code>\n\n"
            f"You can now send messages to investigate issues.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.exception(f"Error creating session for user {user_id}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def session_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /session subcommands: list, resume, timeline, show.

    Args:
        update: Telegram update object
        context: Telegram context with bot_data
    """
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    config: Config = context.bot_data["config"]

    # Check authorization
    if config.telegram_allowed_users and user_id not in config.telegram_allowed_users:
        await update.message.reply_text("⛔ Unauthorized. Contact admin to get access.")
        return

    args = context.args

    if not args:
        await update.message.reply_text(
            "Usage:\n"
            "/session list\n"
            "/session resume &lt;session-id&gt;\n"
            "/session timeline &lt;session-id&gt;\n"
            "/session show &lt;session-id&gt;",
            parse_mode="HTML",
        )
        return

    action = args[0].lower()

    if action == "list":
        await handle_session_list(update, context)
    elif action == "resume" and len(args) >= 2:
        await handle_session_resume(update, context, args[1])
    elif action == "timeline" and len(args) >= 2:
        await handle_session_timeline(update, context, args[1])
    elif action == "show" and len(args) >= 2:
        await handle_session_show(update, context, args[1])
    else:
        await update.message.reply_text("Unknown action or missing session ID")


async def handle_session_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /session list - list all sessions.

    Args:
        update: Telegram update object
        context: Telegram context with bot_data
    """
    if not update.message:
        return

    try:
        sessions = Session.list_sessions()

        if not sessions:
            await update.message.reply_text("No sessions found.")
            return

        lines = ["<b>Available Sessions:</b>\n"]
        for session in sessions[-10:]:  # Show last 10 sessions
            session_id = session.get("id", "Unknown")
            name = session.get("name", "No name")
            created = session.get("created", "Unknown")
            status = session.get("status", "Unknown")

            lines.append(
                f"• <code>{session_id}</code> - {name}\n"
                f"  Created: {created}\n"
                f"  Status: {status}"
            )

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    except Exception as e:
        logger.exception("Error listing sessions")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def handle_session_resume(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session_id: str
) -> None:
    """Handle /session resume - resume an existing session.

    Args:
        update: Telegram update object
        context: Telegram context with bot_data
        session_id: Session ID to resume
    """
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    session_manager: TelegramSessionManager = context.bot_data["session_manager"]
    config: Config = context.bot_data["config"]

    try:
        # Resume session in unsafe mode (no password)
        session = Session.resume(session_id=session_id, password=None, unsafe=True)

        # Set as active session
        session_manager.set_active_session(user_id, session.session_id)

        # Initialize orchestrator
        from aletheia.cli import init_orchestrator

        engram = context.bot_data.get("engram")
        orchestrator = await init_orchestrator(session, config, engram=engram)
        session_manager.set_orchestrator(session.session_id, orchestrator)

        metadata = session.get_metadata()
        await update.message.reply_text(
            f"✅ Resumed session: <code>{session.session_id}</code>\n"
            f"Name: {metadata.name or 'N/A'}\n"
            f"Created: {metadata.created}\n"
            f"Status: {metadata.status}",
            parse_mode="HTML",
        )

    except SessionNotFoundError:
        await update.message.reply_text(f"❌ Session not found: {session_id}")
    except Exception as e:
        logger.exception(f"Error resuming session {session_id}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def handle_session_timeline(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session_id: str
) -> None:
    """Handle /session timeline - show session timeline using TimelineAgent.

    Args:
        update: Telegram update object
        context: Telegram context with bot_data
        session_id: Session ID to show timeline for
    """
    if not update.message:
        return

    try:
        # Resume session to read scratchpad
        session = Session.resume(session_id=session_id, password=None, unsafe=True)

        # Read scratchpad
        from aletheia.plugins.scratchpad.scratchpad import Scratchpad

        scratchpad = Scratchpad(
            session_dir=session.session_path, encryption_key=session.get_key()
        )
        journal = scratchpad.read_scratchpad()

        if not journal or journal.strip() == "":
            await update.message.reply_text(
                f"Session <code>{session_id}</code> has no timeline entries yet.",
                parse_mode="HTML",
            )
            return

        # Use TimelineAgent to generate structured timeline
        from agent_framework import ChatMessage, Role, TextContent

        from aletheia.agents.instructions_loader import Loader
        from aletheia.agents.model import Timeline
        from aletheia.agents.timeline.timeline_agent import TimelineAgent

        prompt_loader = Loader()
        timeline_agent = TimelineAgent(
            name="timeline_agent",
            instructions=prompt_loader.load("timeline", "json_instructions"),
            description="Timeline Agent for generating session timeline",
        )

        message = ChatMessage(
            role=Role.USER,
            contents=[
                TextContent(
                    text=f"Generate a timeline of the following troubleshooting session scratchpad data:\n\n{journal}\n\n"
                )
            ],
        )

        # Send "typing" while processing
        await update.message.chat.send_action("typing")

        # Generate timeline
        response = await timeline_agent.agent.run(message, response_format=Timeline)

        if response:
            timeline_data = json.loads(str(response.text))

            # Format timeline for Telegram
            lines = [f"<b>📅 Timeline: {session_id}</b>\n"]

            # Handle both Timeline model format and legacy format
            entries = (
                timeline_data.get("entries", timeline_data)
                if isinstance(timeline_data, dict)
                else timeline_data
            )

            for event in entries[:20]:  # Limit to 20 entries for Telegram
                timestamp = event.get("timestamp", "")
                event_type = event.get("entry_type", event.get("type", "INFO"))
                content = event.get("content", event.get("description", ""))

                # Format with emoji based on type
                emoji = {
                    "ACTION": "▶️",
                    "OBSERVATION": "👁️",
                    "DECISION": "🎯",
                    "INFO": "ℹ️",
                }.get(event_type.upper(), "•")

                lines.append(
                    f"{emoji} <b>{timestamp}</b> [{event_type}]\n{html_module.escape(content)}\n"
                )

            if len(entries) > 20:
                lines.append(f"\n<i>... and {len(entries) - 20} more entries</i>")

            # Send timeline in chunks
            for chunk in split_message("\n".join(lines)):
                await update.message.reply_text(chunk, parse_mode="HTML")
        else:
            await update.message.reply_text("❌ Failed to generate timeline")

    except SessionNotFoundError:
        await update.message.reply_text(f"❌ Session not found: {session_id}")
    except Exception as e:
        logger.exception(f"Error showing timeline for session {session_id}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def handle_session_show(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session_id: str
) -> None:
    """Handle /session show - show session metadata and scratchpad.

    Args:
        update: Telegram update object
        context: Telegram context with bot_data
        session_id: Session ID to show scratchpad for
    """
    if not update.message:
        return

    try:
        # Resume session to read metadata and scratchpad
        session = Session.resume(session_id=session_id, password=None, unsafe=True)
        metadata = session.get_metadata()

        # Build metadata section
        lines = [
            f"<b>📋 Session: {metadata.name or session_id}</b>\n",
            f"<b>Status:</b> {metadata.status}",
            f"<b>Created:</b> {metadata.created}",
            f"<b>Updated:</b> {metadata.updated}",
        ]

        # Add token usage if available
        if metadata.total_input_tokens or metadata.total_output_tokens:
            lines.append(
                f"<b>Tokens:</b> {metadata.total_input_tokens} in / {metadata.total_output_tokens} out"
            )

        lines.append("\n<b>📝 Scratchpad Contents:</b>\n")

        # Read scratchpad
        from aletheia.plugins.scratchpad.scratchpad import Scratchpad

        scratchpad = Scratchpad(
            session_dir=session.session_path, encryption_key=session.get_key()
        )
        content = scratchpad.read_scratchpad()

        if not content or content.strip() == "":
            lines.append("<i>(Scratchpad is empty)</i>")
        else:
            # Truncate content to avoid Telegram limits
            truncated = content[:2500]
            if len(content) > 2500:
                truncated += "\n... (truncated)"
            lines.append(f"<pre>{html_module.escape(truncated)}</pre>")

        # Send in chunks if needed
        for chunk in split_message("\n".join(lines)):
            await update.message.reply_text(chunk, parse_mode="HTML")

    except SessionNotFoundError:
        await update.message.reply_text(f"❌ Session not found: {session_id}")
    except Exception as e:
        logger.exception(f"Error showing session {session_id}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


class SessionUsage:
    """Simple wrapper to provide completion_usage interface from session metadata."""

    def __init__(self, input_tokens: int, output_tokens: int):
        self.input_token_count = input_tokens
        self.output_token_count = output_tokens


async def builtin_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle built-in commands like /help, /info, /agents, /cost, /version.

    Args:
        update: Telegram update object
        context: Telegram context with bot_data
    """
    if not update.message or not update.message.text or not update.effective_user:
        return

    user_id = update.effective_user.id
    config: Config = context.bot_data["config"]
    session_manager: TelegramSessionManager = context.bot_data["session_manager"]

    # Check authorization
    if config.telegram_allowed_users and user_id not in config.telegram_allowed_users:
        await update.message.reply_text("⛔ Unauthorized. Contact admin to get access.")
        return

    # Extract command name (remove leading /)
    command = update.message.text[1:].split()[0].lower()

    if command in COMMANDS:
        try:
            # Commands expect a console object for output
            # For Telegram, we'll capture their output and send it
            from io import StringIO

            from rich.console import Console

            # Create an in-memory console to capture output
            buffer = StringIO()
            temp_console = Console(file=buffer, force_terminal=False, width=80)

            # For /cost command, try to get usage from active session
            completion_usage = None
            if command == "cost":
                session_id = session_manager.get_active_session(user_id)
                if session_id:
                    try:
                        session = Session.resume(
                            session_id=session_id, password=None, unsafe=True
                        )
                        metadata = session.get_metadata()
                        if metadata.total_input_tokens or metadata.total_output_tokens:
                            completion_usage = SessionUsage(
                                metadata.total_input_tokens,
                                metadata.total_output_tokens,
                            )
                    except Exception:
                        pass  # Fall back to no usage data

            # Execute command
            COMMANDS[command].execute(
                temp_console,
                completion_usage=completion_usage,
                config=context.bot_data["config"],
            )

            # Get the output
            output = buffer.getvalue()

            if output:
                # Convert to plain text (strip Rich markup)
                # Simple approach: just send as-is, Telegram will ignore markup
                await update.message.reply_text(output or "Command executed.")
            else:
                await update.message.reply_text("Command executed.")

        except Exception as e:
            logger.exception(f"Error executing command /{command}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    else:
        await update.message.reply_text(
            f"Unknown command: /{command}\n"
            "Available commands: /help, /info, /agents, /cost, /version"
        )


async def _send_charts(update: Update, charts: list) -> None:
    """Render and send chart images to the Telegram chat.

    Args:
        update: Telegram update (must have a valid message).
        charts: List of :class:`Chart` model instances from agent findings.
    """
    from aletheia.channels.chart_renderer import render_chart_to_png

    for chart in charts:
        try:
            chart_dict = chart.model_dump()
            result = render_chart_to_png(chart_dict)
            if result.image and update.message:
                await update.message.reply_photo(
                    photo=result.image, caption=chart.name
                )
            elif result.error and update.message:
                await update.message.reply_text(f"⚠️ {result.error}")
        except Exception as e:
            logger.warning(f"Failed to send chart: {e}")


async def custom_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle custom commands - expand and send to orchestrator.

    Custom commands are user-defined in markdown files. When invoked,
    their instructions are expanded and sent to the active session.

    Args:
        update: Telegram update object
        context: Telegram context with bot_data
    """
    if not update.message or not update.message.text or not update.effective_user:
        return

    user_id = update.effective_user.id
    session_manager: TelegramSessionManager = context.bot_data["session_manager"]
    config: Config = context.bot_data["config"]

    # Check authorization
    if config.telegram_allowed_users and user_id not in config.telegram_allowed_users:
        await update.message.reply_text("⛔ Unauthorized. Contact admin to get access.")
        return

    # Check for active session
    session_id = session_manager.get_active_session(user_id)
    if not session_id:
        await update.message.reply_text(
            "⚠️ No active session. Start one with /new_session or /session resume &lt;id&gt;",
            parse_mode="HTML",
        )
        return

    # Get orchestrator
    orchestrator = session_manager.get_orchestrator(session_id)
    if not orchestrator:
        await update.message.reply_text(
            "❌ Session orchestrator not found. Please create a new session."
        )
        session_manager.clear_session(user_id)
        return

    # Expand the custom command
    user_message = update.message.text
    expanded, was_expanded = expand_custom_command(user_message, config)

    if not was_expanded:
        await update.message.reply_text(f"❌ Custom command not found: {user_message}")
        return

    try:
        # Track token usage
        completion_usage = UsageDetails(input_token_count=0, output_token_count=0)

        # Use continuous typing indicator while processing
        async with continuous_typing(update.message.chat):
            # Stream response from orchestrator - accumulate all chunks first
            json_buffer = ""

            async for chunk in orchestrator.agent.run_stream(
                messages=[
                    ChatMessage(role="user", contents=[TextContent(text=expanded)])
                ],
                thread=orchestrator.thread,
                response_format=AgentResponse,
            ):
                # Track usage from response contents
                if chunk and chunk.contents:
                    for content in chunk.contents:
                        if isinstance(content, UsageContent):
                            completion_usage += content.details

                # Just accumulate - don't try to parse yet
                if chunk and chunk.text:
                    json_buffer += chunk.text

            # Parse once after stream completes
            if json_buffer.strip():
                try:
                    parsed = json.loads(json_buffer)
                    agent_response = AgentResponse(**parsed)

                    # Check if this is a direct orchestrator response (case-insensitive)
                    agent_name = parsed.get("agent", "").lower()
                    is_orchestrator = agent_name in ("orchestrator", "aletheia")

                    # Format for Telegram with session header
                    formatted = format_agent_response(
                        agent_response,
                        session_id=session_id,
                        is_orchestrator=is_orchestrator,
                    )

                    # Split and send messages
                    for chunk_text in split_message(formatted):
                        await update.message.reply_text(chunk_text, parse_mode="HTML")

                    # Send chart images if present
                    if agent_response.findings and agent_response.findings.charts:
                        await _send_charts(update, agent_response.findings.charts)

                except (json.JSONDecodeError, ValueError) as e:
                    # Fallback to raw text
                    logger.warning(f"Failed to parse response: {e}")
                    fallback_text = html_module.escape(json_buffer.strip()[:3500])
                    await update.message.reply_text(
                        f"<code>🔗 {session_id}</code>\n{'─' * 20}\n{fallback_text}",
                        parse_mode="HTML",
                    )

        # Update session usage if we tracked any tokens
        input_tokens = completion_usage.input_token_count or 0
        output_tokens = completion_usage.output_token_count or 0
        if input_tokens > 0 or output_tokens > 0:
            orchestrator.session.update_usage(input_tokens, output_tokens)

        # Update last activity
        session_manager.update_activity(user_id)

    except Exception as e:
        logger.exception(f"Error processing custom command for user {user_id}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages - send to active session orchestrator.

    Args:
        update: Telegram update object
        context: Telegram context with bot_data
    """
    if not update.message or not update.message.text or not update.effective_user:
        return

    user_id = update.effective_user.id
    session_manager: TelegramSessionManager = context.bot_data["session_manager"]
    config: Config = context.bot_data["config"]

    logger.debug(
        f"Telegram: Received message from user {user_id}: {update.message.text[:100]}..."
    )

    # Check authorization
    if config.telegram_allowed_users and user_id not in config.telegram_allowed_users:
        logger.debug(f"Telegram: User {user_id} not authorized")
        await update.message.reply_text("⛔ Unauthorized. Contact admin to get access.")
        return

    # Check for active session
    session_id = session_manager.get_active_session(user_id)
    if not session_id:
        logger.debug(f"Telegram: No active session for user {user_id}")
        await update.message.reply_text(
            "⚠️ No active session. Start one with /new_session or /session resume &lt;id&gt;",
            parse_mode="HTML",
        )
        return

    logger.debug(f"Telegram: Using session {session_id} for user {user_id}")

    # Get orchestrator
    orchestrator = session_manager.get_orchestrator(session_id)
    if not orchestrator:
        logger.debug(f"Telegram: Orchestrator not found for session {session_id}")
        await update.message.reply_text(
            "❌ Session orchestrator not found. Please create a new session."
        )
        session_manager.clear_session(user_id)
        return

    user_message = update.message.text

    # Check for custom command expansion
    expanded, was_expanded = expand_custom_command(user_message, config)
    if was_expanded:
        logger.debug(
            f"Telegram: Expanded custom command: {user_message} -> {expanded[:100]}..."
        )
        user_message = expanded

    try:
        # Track token usage
        completion_usage = UsageDetails(input_token_count=0, output_token_count=0)

        logger.debug(
            "operation started: telegram_message_handler",
            session_id=session_id,
            user_id=user_id,
        )

        # Use continuous typing indicator while processing
        async with continuous_typing(update.message.chat):
            # Stream response from orchestrator - accumulate all chunks first
            json_buffer = ""

            async for chunk in orchestrator.agent.run_stream(
                messages=[
                    ChatMessage(role="user", contents=[TextContent(text=user_message)])
                ],
                thread=orchestrator.thread,
                response_format=AgentResponse,
            ):
                # Track usage from response contents
                if chunk and chunk.contents:
                    for content in chunk.contents:
                        if isinstance(content, UsageContent):
                            completion_usage += content.details

                # Just accumulate - don't try to parse yet
                if chunk and chunk.text:
                    json_buffer += chunk.text

            # Parse once after stream completes
            logger.debug(f"Telegram: Stream complete, buffer size: {len(json_buffer)}")

            if json_buffer.strip():
                try:
                    parsed = json.loads(json_buffer)
                    agent_response = AgentResponse(**parsed)

                    # Check if this is a direct orchestrator response (case-insensitive)
                    agent_name = parsed.get("agent", "").lower()
                    is_orchestrator = agent_name in ("orchestrator", "aletheia")

                    logger.debug(
                        f"Telegram: Parsed JSON response from agent: {agent_name}, "
                        f"is_orchestrator: {is_orchestrator}"
                    )

                    # Format for Telegram with session header
                    formatted = format_agent_response(
                        agent_response,
                        session_id=session_id,
                        is_orchestrator=is_orchestrator,
                    )

                    logger.debug(
                        f"Telegram: Formatted response length: {len(formatted)} chars"
                    )

                    # Split and send messages
                    chunks = split_message(formatted)
                    logger.debug(f"Telegram: Sending {len(chunks)} message chunk(s)")
                    for chunk_text in chunks:
                        await update.message.reply_text(chunk_text, parse_mode="HTML")

                    # Send chart images if present
                    if agent_response.findings and agent_response.findings.charts:
                        await _send_charts(update, agent_response.findings.charts)

                    logger.debug("Telegram: Response sent successfully")

                except (json.JSONDecodeError, ValueError) as e:
                    # Fallback to raw text
                    logger.warning(f"Telegram: Failed to parse response: {e}")
                    logger.debug(f"Telegram: Buffer content: {json_buffer[:500]}...")
                    fallback_text = html_module.escape(json_buffer.strip()[:3500])
                    await update.message.reply_text(
                        f"<code>🔗 {session_id}</code>\n{'─' * 20}\n{fallback_text}",
                        parse_mode="HTML",
                    )

        # Update session usage if we tracked any tokens
        input_tokens = completion_usage.input_token_count or 0
        output_tokens = completion_usage.output_token_count or 0
        if input_tokens > 0 or output_tokens > 0:
            orchestrator.session.update_usage(input_tokens, output_tokens)
            logger.debug(
                f"Telegram: Updated session usage: {input_tokens} input, {output_tokens} output tokens"
            )

        # Update last activity
        session_manager.update_activity(user_id)
        logger.debug("operation completed: telegram_message_handler")

    except Exception as e:
        logger.exception(f"Error processing message for user {user_id}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
