"""Telegram bot integration for the gateway daemon.

This module runs the Telegram bot using the gateway's session manager
instead of maintaining its own session state.
"""

import asyncio
import uuid

import structlog
import websockets
from telegram import BotCommand, MenuButtonCommands, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from aletheia.channels.formatter import format_response_to_markdown
from aletheia.commands import COMMANDS, get_custom_commands
from aletheia.config import Config
from aletheia.daemon.protocol import ProtocolMessage
from aletheia.daemon.session_manager import GatewaySessionManager
from aletheia.engram.tools import Engram

logger = structlog.get_logger(__name__)


def is_authorized(user_id: int, config: Config) -> bool:
    """Check if user is in the allowlist.

    Args:
        user_id: Telegram user ID
        config: Aletheia configuration

    Returns:
        True if authorized (user in allowlist or allowlist is empty)
    """
    if not config.telegram_allowed_users:
        return True
    return user_id in config.telegram_allowed_users


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command - welcome message."""
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    config: Config = context.bot_data["config"]

    if not is_authorized(user_id, config):
        await update.message.reply_text("⛔ Unauthorized. Contact admin to get access.")
        return

    await update.message.reply_text(
        "👋 Welcome to Aletheia!\n\n"
        "Start with /new_session (optional: --unsafe, --verbose)\n"
        "Resume with /session resume &lt;id&gt;\n"
        "Type /help for commands.",
        parse_mode="HTML",
    )


async def new_session_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /new_session command - create new session via gateway.

    Usage:
        /new_session                    - Create unsafe session (default for convenience)
        /new_session --unsafe          - Explicitly create unsafe session
        /new_session --verbose         - Create unsafe session with verbose mode
        /new_session --unsafe --verbose - Both flags combined
    """
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    config: Config = context.bot_data["config"]
    session_manager: GatewaySessionManager = context.bot_data["session_manager"]

    if not is_authorized(user_id, config):
        await update.message.reply_text("⛔ Unauthorized.")
        return

    # Parse command arguments
    args = context.args or []
    unsafe = "--unsafe" in args or len(args) == 0  # Default to unsafe for Telegram
    verbose = "--verbose" in args

    try:
        # Create session via gateway's session manager
        session = await session_manager.create_session(
            name=f"telegram-{user_id}",
            password=None,
            unsafe=unsafe,
            verbose=verbose,
        )

        metadata = session.get_metadata()
        mode_info = []
        if verbose:
            mode_info.append("verbose")
        if unsafe:
            mode_info.append("unencrypted")
        mode_str = f" ({', '.join(mode_info)})" if mode_info else ""

        await update.message.reply_text(
            f"✅ Session created{mode_str}: <code>{metadata.id}</code>\n"
            f"📝 Name: {metadata.name}\n\n"
            f"Send me a message to start!",
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        await update.message.reply_text(f"❌ Error creating session: {e}")


async def session_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /session command - list/resume/show sessions."""
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    config: Config = context.bot_data["config"]
    session_manager: GatewaySessionManager = context.bot_data["session_manager"]

    if not is_authorized(user_id, config):
        await update.message.reply_text("⛔ Unauthorized.")
        return

    args = context.args or []

    if not args or args[0] == "list":
        # List sessions
        sessions = session_manager.list_sessions()
        if not sessions:
            await update.message.reply_text("No sessions found.")
            return

        lines = ["📋 Available sessions:\n"]
        for sess in sessions[:10]:  # Limit to 10
            lines.append(f"• <code>{sess['id']}</code> - {sess.get('name', 'Unnamed')}")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    elif args[0] == "resume" and len(args) > 1:
        # Resume session
        session_id = args[1]
        try:
            session = await session_manager.resume_session(
                session_id=session_id,
                password=None,
                unsafe=False,
            )
            metadata = session.get_metadata()
            await update.message.reply_text(
                f"✅ Resumed session: <code>{metadata.id}</code>\n"
                f"📝 Name: {metadata.name}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to resume session: {e}")
            await update.message.reply_text(f"❌ Error resuming session: {e}")

    elif args[0] == "show":
        await _handle_session_show(update, session_manager, config)

    elif args[0] == "timeline":
        await _handle_session_timeline(update, session_manager)

    else:
        await update.message.reply_text(
            "Usage:\n"
            "/session list - List available sessions\n"
            "/session resume &lt;id&gt; - Resume a session\n"
            "/session show - Show current session info\n"
            "/session timeline - Show session timeline",
            parse_mode="HTML",
        )


async def _handle_session_show(
    update: Update,
    session_manager: GatewaySessionManager,
    config: Config,
) -> None:
    """Handle /session show - display current session metadata."""
    if not update.message:
        return

    active_session = session_manager.get_active_session()
    if not active_session:
        await update.message.reply_text(
            "No active session. Use /new_session or /session resume &lt;id&gt;.",
            parse_mode="HTML",
        )
        return

    try:
        metadata = active_session.get_metadata()

        input_tokens = metadata.total_input_tokens
        output_tokens = metadata.total_output_tokens
        total_cost = (input_tokens * config.cost_per_input_token) + (
            output_tokens * config.cost_per_output_token
        )

        lines = [
            "<b>Session Info</b>\n",
            f"🆔 ID: <code>{metadata.id}</code>",
            f"📝 Name: {metadata.name or 'unnamed'}",
            f"📊 Status: {metadata.status}",
            f"📅 Created: {metadata.created}",
            f"🔄 Updated: {metadata.updated}",
        ]

        if input_tokens or output_tokens:
            lines.append(f"🔢 Tokens: {input_tokens} in / {output_tokens} out")
        if total_cost:
            lines.append(f"💰 Cost: ${total_cost:.4f}")

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Failed to show session: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


async def _handle_session_timeline(
    update: Update,
    session_manager: GatewaySessionManager,
) -> None:
    """Handle /session timeline - generate and display session timeline."""
    import json

    from agent_framework import ChatMessage, Role, TextContent

    from aletheia.agents.instructions_loader import Loader
    from aletheia.agents.model import Timeline
    from aletheia.agents.timeline.timeline_agent import TimelineAgent
    from aletheia.plugins.scratchpad.scratchpad import Scratchpad

    if not update.message:
        return

    active_session = session_manager.get_active_session()
    if not active_session:
        await update.message.reply_text(
            "No active session. Use /new_session or /session resume &lt;id&gt;.",
            parse_mode="HTML",
        )
        return

    try:
        await update.message.reply_text("⏳ Generating timeline...")

        # Read scratchpad
        scratchpad_file = active_session.scratchpad_file
        if not scratchpad_file.exists():
            await update.message.reply_text(
                "No scratchpad data found for this session."
            )
            return

        scratchpad = Scratchpad(
            session_dir=active_session.session_path,
            encryption_key=active_session.get_key(),  # type: ignore[arg-type]
        )
        journal_content = scratchpad.read_scratchpad()
        if not journal_content or not journal_content.strip():
            await update.message.reply_text(
                "Scratchpad is empty — no timeline to generate."
            )
            return

        # Generate timeline via TimelineAgent
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
                    text=f"Generate a timeline of the following "
                    f"troubleshooting session scratchpad data:\n\n"
                    f"{journal_content}"
                )
            ],
        )

        agent_response = await timeline_agent.agent.run(
            message, response_format=Timeline
        )

        if not agent_response or not agent_response.text:
            await update.message.reply_text("No timeline generated.")
            return

        # Parse and format timeline
        timeline_data = json.loads(str(agent_response.text))
        entries = (
            timeline_data.get("entries", timeline_data)
            if isinstance(timeline_data, dict)
            else timeline_data
        )

        if not entries:
            await update.message.reply_text("No timeline entries found.")
            return

        type_icons = {
            "ACTION": "▶️",
            "OBSERVATION": "👁️",
            "DECISION": "🎯",
            "INFO": "ℹ️",
        }

        lines = ["<b>Session Timeline</b>\n"]
        for entry in entries[:20]:  # Limit for Telegram
            entry_type = entry.get("entry_type", entry.get("type", "INFO")).upper()
            timestamp = entry.get("timestamp", "")
            content = entry.get("content", entry.get("description", ""))
            icon = type_icons.get(entry_type, "•")

            lines.append(f"{icon} <b>{entry_type}</b> {timestamp}")
            lines.append(f"   {content}\n")

        text = "\n".join(lines)

        # Split into Telegram-sized chunks if needed
        from aletheia.telegram.formatter import split_message

        chunks = split_message(text, max_len=4096)
        for chunk_text in chunks:
            await update.message.reply_text(chunk_text, parse_mode="HTML")

    except json.JSONDecodeError:
        await update.message.reply_text("❌ Failed to parse timeline data.")
    except Exception as e:
        logger.error(f"Failed to generate timeline: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error generating timeline: {e}")


async def _execute_gateway_command(command: str, config: Config) -> str:
    """Execute a command via the gateway websocket and return the output.

    Opens a temporary websocket connection to the gateway, sends a
    ``command_execute`` protocol message, collects the streamed text
    response, and returns it.
    """
    gateway_url = f"ws://{config.daemon_host}:{config.daemon_port}"
    channel_id = str(uuid.uuid4())

    async with websockets.connect(gateway_url) as ws:
        # Register as a channel
        register_msg = ProtocolMessage.create(
            "channel_register",
            {"channel_type": "telegram", "channel_id": channel_id},
        )
        await ws.send(register_msg.to_json())
        response = ProtocolMessage.from_json(await ws.recv())
        if response.type != "channel_registered":
            return f"Error: Registration failed: {response.type}"

        # Send command
        cmd_msg = ProtocolMessage.create(
            "command_execute",
            {"message": command, "channel": "telegram"},
        )
        await ws.send(cmd_msg.to_json())

        # Collect streamed response
        output = ""
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
            msg = ProtocolMessage.from_json(raw)
            if msg.type == "chat_stream_chunk":
                content = msg.payload.get("content", "")
                if content:
                    output += content
            elif msg.type == "chat_stream_end":
                break
            elif msg.type == "error":
                return f"Error: {msg.payload.get('message', 'Unknown error')}"

    return output


async def builtin_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle built-in commands (help, version, info, agents, cost).

    Delegates to the gateway via websocket ``command_execute`` so that
    commands like ``/cost`` have access to the orchestrator's usage data.
    """
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    config: Config = context.bot_data["config"]

    if not is_authorized(user_id, config):
        await update.message.reply_text("⛔ Unauthorized.")
        return

    # Extract command name (handle @botname suffix)
    cmd_text = update.message.text or ""
    cmd_name = cmd_text.split()[0].lstrip("/").split("@")[0]

    if cmd_name not in COMMANDS:
        await update.message.reply_text(f"Unknown command: /{cmd_name}")
        return

    try:
        output = await _execute_gateway_command(f"/{cmd_name}", config)
        output = output.strip()

        if output:
            html_output = _convert_markdown_to_html(output)

            from aletheia.telegram.formatter import split_message

            chunks = split_message(html_output, max_len=4096)
            for chunk_text in chunks:
                await update.message.reply_text(chunk_text, parse_mode="HTML")
        else:
            await update.message.reply_text("No output.")

    except Exception as e:
        logger.error(f"Failed to execute command /{cmd_name}: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages - send to active session via gateway."""
    if not update.message or not update.effective_user or not update.message.text:
        return

    user_id = update.effective_user.id
    config: Config = context.bot_data["config"]
    session_manager: GatewaySessionManager = context.bot_data["session_manager"]

    if not is_authorized(user_id, config):
        await update.message.reply_text("⛔ Unauthorized.")
        return

    # Check if there's an active session
    active_session = session_manager.get_active_session()
    if not active_session:
        await update.message.reply_text(
            "No active session. Use /new_session to create one or /session resume &lt;id&gt; to resume.",
            parse_mode="HTML",
        )
        return

    message_text = update.message.text
    session_id = active_session.get_metadata().id

    async def _keep_typing() -> None:
        """Send 'typing' action every 5 seconds until cancelled."""
        while True:
            await update.message.chat.send_action("typing")  # type: ignore[union-attr]
            await asyncio.sleep(5)

    typing_task = asyncio.create_task(_keep_typing())

    try:
        # Stream response from gateway's session manager
        # Session manager yields JSON chunks
        chunk_count = 0
        response_markdown = ""
        charts_data: list[dict] = []

        async for chunk in session_manager.send_message(message_text, "telegram"):
            chunk_count += 1
            chunk_type = chunk.get("type")
            logger.debug(f"Telegram: Received chunk {chunk_count}: type={chunk_type}")

            # Wait for complete JSON, then format to markdown
            if chunk_type == "json_complete":
                parsed = chunk.get("parsed")
                if parsed:
                    # Format JSON to markdown
                    response_markdown = format_response_to_markdown(parsed)
                    logger.info(
                        f"Telegram: Formatted to markdown, length: {len(response_markdown)}"
                    )

                    # Extract charts for rendering
                    findings = parsed.get("findings", {})
                    if isinstance(findings, dict):
                        charts_data = findings.get("charts", [])

            elif chunk_type == "json_error":
                # JSON parsing failed - use raw content
                response_markdown = chunk.get("content", "Error parsing response")
                logger.warning("Telegram: JSON parse error, using raw content")

        if response_markdown and response_markdown.strip():
            # Convert markdown to HTML for Telegram
            html_response = _convert_markdown_to_html(response_markdown)
            logger.info(f"Telegram: Converted to HTML, length: {len(html_response)}")

            # Split into Telegram-sized chunks if needed
            from aletheia.telegram.formatter import split_message

            chunks = split_message(html_response, max_len=4096)
            logger.info(f"Telegram: Split into {len(chunks)} chunks, sending to user")
            for i, chunk_text in enumerate(chunks):
                logger.debug(f"Telegram: Sending chunk {i+1}/{len(chunks)}")
                await update.message.reply_text(chunk_text, parse_mode="HTML")
        else:
            logger.warning("Telegram: No output to send")
            await update.message.reply_text("✅ Done (no output)")

        # Send chart images if present
        if charts_data:
            from aletheia.channels.chart_renderer import render_chart_to_png

            for chart_dict in charts_data:
                try:
                    chart_name = chart_dict.get("name", "Chart")
                    result = render_chart_to_png(chart_dict)
                    if result.image:
                        await update.message.reply_photo(
                            photo=result.image, caption=chart_name
                        )
                    elif result.error:
                        await update.message.reply_text(
                            f"⚠️ {result.error}"
                        )
                except Exception as e:
                    logger.warning(f"Failed to send chart: {e}")

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {e}")
    finally:
        typing_task.cancel()


def _convert_markdown_to_html(text: str) -> str:
    """Convert markdown formatting to HTML for Telegram.

    Converts:
    - **bold** → <b>bold</b>
    - ## Header → <b>Header</b>
    - Escapes HTML special characters
    """
    import html as html_module
    import re

    # First escape HTML special characters
    text = html_module.escape(text)

    # Convert ## headers to bold
    text = re.sub(r"##\s+([^\n]+)", r"<b>\1</b>", text)

    # Convert **bold** to <b>bold</b>
    text = re.sub(r"\*\*([^\*]+)\*\*", r"<b>\1</b>", text)

    return text


def get_bot_commands(config: Config) -> list[BotCommand]:
    """Build list of bot commands for Telegram menu."""
    commands = [
        BotCommand("start", "Welcome to Aletheia"),
        BotCommand("new_session", "Create session (--unsafe, --verbose)"),
        BotCommand("session", "Manage sessions (list/resume/show/timeline)"),
    ]

    # Built-in commands
    for cmd_name, builtin_cmd in COMMANDS.items():
        commands.append(BotCommand(cmd_name, builtin_cmd.description))

    # Custom commands
    custom_cmds = get_custom_commands(config)
    for cmd_name, custom_cmd in custom_cmds.items():
        desc = (
            custom_cmd.description[:256]
            if len(custom_cmd.description) > 256
            else custom_cmd.description
        )
        commands.append(BotCommand(cmd_name, desc))

    return commands


async def run_telegram_bot_integrated(
    token: str,
    config: Config,
    session_manager: GatewaySessionManager,
    engram: Engram | None,
) -> None:
    """Run Telegram bot integrated with gateway's session manager.

    Args:
        token: Telegram bot API token
        config: Aletheia configuration
        session_manager: Gateway's session manager instance
        engram: Gateway's engram instance (if enabled)
    """
    # Create application
    app = Application.builder().token(token).build()

    # Store gateway components in bot_data
    app.bot_data["config"] = config
    app.bot_data["session_manager"] = session_manager
    app.bot_data["engram"] = engram
    app.bot_data["verbose"] = False

    # Register handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("new_session", new_session_handler))
    app.add_handler(CommandHandler("session", session_handler))

    # Register built-in commands (cost, help, version, info, agents, etc.)
    for cmd_name in COMMANDS:
        app.add_handler(CommandHandler(cmd_name, builtin_command_handler))

    # Regular text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Start the bot
    logger.info("Starting Telegram bot...")
    await app.initialize()
    await app.start()

    # Set up bot command menu
    bot_commands = get_bot_commands(config)
    await app.bot.set_my_commands(bot_commands)
    await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    logger.info(f"Registered {len(bot_commands)} commands in bot menu")

    # Start polling
    logger.info("Telegram bot is running")
    await app.updater.start_polling(
        allowed_updates=[Update.MESSAGE],
        drop_pending_updates=True,
    )

    # Keep running until cancelled
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("Stopping Telegram bot...")
    finally:
        # Stop polling first
        if app.updater and app.updater.running:
            await app.updater.stop()
        await app.stop()
        await app.shutdown()
        logger.info("Telegram bot stopped")
