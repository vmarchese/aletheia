"""Main Telegram bot logic and entry point."""

import asyncio
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from aletheia.config import Config

from .handlers import (
    builtin_command_handler,
    message_handler,
    new_session_handler,
    session_handler,
)
from .session_manager import TelegramSessionManager

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command - welcome message.

    Args:
        update: Telegram update object
        context: Telegram context with bot_data
    """
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    config: Config = context.bot_data["config"]

    if not is_authorized(user_id, config):
        await update.message.reply_text("⛔ Unauthorized. Contact admin to get access.")
        return

    await update.message.reply_text(
        "👋 Welcome to Aletheia!\n\n"
        "Start with /new_session or resume with /session resume &lt;id&gt;\n"
        "Type /help for commands.",
        parse_mode="HTML",
    )


def is_authorized(user_id: int, config: Config) -> bool:
    """Check if user is in the allowlist.

    Args:
        user_id: Telegram user ID
        config: Aletheia configuration

    Returns:
        True if authorized (user in allowlist or allowlist is empty)
    """
    if not config.telegram_allowed_users:
        # Empty allowlist = allow all users
        # This should be warned about in the CLI startup
        return True
    return user_id in config.telegram_allowed_users


async def run_telegram_bot(token: str, config: Config, verbose: bool) -> None:
    """Main entry point for the Telegram bot server.

    Initializes the bot application, registers all handlers, and starts polling.

    Args:
        token: Telegram bot API token
        config: Aletheia configuration
        verbose: Enable verbose logging
    """
    # Configure logging
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    # Initialize session manager
    session_manager = TelegramSessionManager()

    # Create application
    app = Application.builder().token(token).build()

    # Store config and session manager in bot_data for handlers
    app.bot_data["config"] = config
    app.bot_data["session_manager"] = session_manager
    app.bot_data["verbose"] = verbose

    # Register handlers
    # All handlers check authorization internally
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("new_session", new_session_handler))
    app.add_handler(CommandHandler("session", session_handler))

    # Built-in commands
    for cmd_name in ["help", "info", "agents", "cost", "version"]:
        app.add_handler(CommandHandler(cmd_name, builtin_command_handler))

    # Regular text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Start the bot
    logger.info("Starting Telegram bot...")
    await app.initialize()
    await app.start()

    # Start polling
    logger.info("Bot is running. Press Ctrl+C to stop.")
    await app.updater.start_polling(
        allowed_updates=[Update.MESSAGE],
        drop_pending_updates=True,
    )

    # Keep running until interrupted
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down bot...")
    finally:
        # Cleanup
        await app.stop()
        await app.shutdown()
        logger.info("Bot stopped.")
