# PROJECT: NAVIRIA
# AUTOR: ANTONIO CASTAÑARES RODRÍGUEZ

# DESCRIPTION: Naviria is a personal AI assistant that can help you with various tasks such as answering questions, writing emails, and scheduling meetings.
# DESCRIPTION OF THE FILE: This script sets up a Telegram bot using the python-telegram-bot library.

# --------------------------------------IMPORTS------------------------------------------
import asyncio
import os
import logging                                                                                  # For debugging and information purposes
import telegram_bot                                                                             # Import the telegram module for bot functionalities

from telegram import  Update                                                                    # To send messages and replies to users
from telegram.ext import Application, CommandHandler, MessageHandler, filters                   # To handle commands and messages from users
from dotenv import load_dotenv                                                                  # To set environment variables for API keys
# ----------------------------------------TOKENS-----------------------------------------

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# --------------------------------------DEBUGGING----------------------------------------

# Logging configuration (print time, name, level and message using the terminal)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Suppress the httpx library logs to avoid cluttering the output
logging.getLogger("httpx").setLevel(logging.WARNING)

LOGGER = logging.getLogger(__name__)

# ----------------------------------------MAIN-------------------------------------------

async def main() -> None:
    # Validate that the token is loaded
    if not TELEGRAM_TOKEN:
        LOGGER.error("TELEGRAM_TOKEN not found in environment variables")
        return
    
    # Initialize the application with the bot token
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Initialize the bot properly
    await application.initialize()
    
    # Command handlers for the bot
    application.add_handler(CommandHandler("start", telegram_bot.start))
    application.add_handler(CommandHandler("help", telegram_bot.help_command))

    # Message handler for text messages (excluding commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_bot.respond))

    # Start the bot
    await application.start()
    
    # Start polling for updates
    await application.updater.start_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )
    
    LOGGER.info("Bot is running. Press Ctrl+C to stop.")
    
    try:
        # Keep the bot running
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        LOGGER.info("Stopping bot...")
    finally:
        # Stop the updater and application
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    asyncio.run(main())

