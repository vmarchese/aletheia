"""Telegram bot integration for the gateway daemon.

This module runs the Telegram bot using the gateway's session manager
instead of maintaining its own session state.
"""

import asyncio
import logging

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
from aletheia.daemon.session_manager import GatewaySessionManager
from aletheia.engram.tools import Engram

logger = logging.getLogger(__name__)


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

    else:
        await update.message.reply_text(
            "Usage:\n"
            "/session list - List available sessions\n"
            "/session resume &lt;id&gt; - Resume a session",
            parse_mode="HTML",
        )


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

    # Send "typing" indicator
    await update.message.chat.send_action("typing")

    try:
        # Stream response from gateway's session manager
        # Session manager yields JSON chunks
        chunk_count = 0
        response_markdown = ""

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

            elif chunk_type == "json_error":
                # JSON parsing failed - use raw content
                response_markdown = chunk.get("content", "Error parsing response")
                logger.warning(f"Telegram: JSON parse error, using raw content")

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
            logger.warning(f"Telegram: No output to send")
            await update.message.reply_text("✅ Done (no output)")

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {e}")


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
        BotCommand("session", "Manage sessions (list/resume)"),
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
