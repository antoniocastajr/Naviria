# PROJECT: NAVIRIA
# AUTOR: ANTONIO CASTAÑARES RODRÍGUEZ

# DESCRIPTION: Naviria is a personal AI assistant that can help you with various tasks such as answering questions, writing emails, and scheduling meetings.
# DESCRIPTION OF THE FILE: This script sets up a Telegram bot using the python-telegram-bot library.

# ----------------------------------------IMPORTS----------------------------------------
import logging                                                                                  # For debugging and information purposes
import constants                                                                                # constants.py contains the API keys
import telegram_bot                                                                             # Import the telegram module for bot functionalities

from telegram import  Update                                                                    # To send messages and replies to users
from telegram.ext import Application, CommandHandler, MessageHandler, filters                   # To handle commands and messages from users

# ----------------------------------------TOKENS-----------------------------------------

TELEGRAM_TOKEN = constants.TELEGRAM_TOKEN  

# ----------------------------------------SETUP------------------------------------------

# Logging configuration (print time, name, level and message using the terminal)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Suppress the httpx library logs to avoid cluttering the output
logging.getLogger("httpx").setLevel(logging.WARNING)

LOGGER = logging.getLogger(__name__)

# ----------------------------------------MAIN-------------------------------------------

def main() -> None:
    # Initialize the application with the bot token
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Command handlers for the bot
    application.add_handler(CommandHandler("start", telegram_bot.start))
    application.add_handler(CommandHandler("help", telegram_bot.help_command))

    # Message handler for text messages (excluding commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_bot.respond))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

