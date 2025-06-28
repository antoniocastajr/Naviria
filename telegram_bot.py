# PROJECT: NAVIRIA
# AUTOR: ANTONIO CASTAÑARES RODRÍGUEZ

# DESCRIPTION: Naviria is a personal AI assistant that can help you with various tasks such as answering questions, writing emails, and scheduling meetings.

# ----------------------------------------IMPORTS----------------------------------------                              
from telegram import ForceReply, Update                                                         # To send messages and replies to users
from telegram.ext import ContextTypes                                                           # To handle commands and messages from users
from telegram.error import NetworkError

from main import LOGGER                                                                         # Logger for debugging and information purposes    
from agent import set_model                                                                     # Function to set the model for generating responses
from constants import START_PROMPT, HELP_PROMPT                                                 # Constants for initial prompts

# ----------------------------------------COMMAND HANDLERS--------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    # Send a message when the command /start is issued
    await update.message.reply_html(
        f"Hi {user.mention_html()}! \n\n{START_PROMPT}",
        reply_markup=ForceReply(selective=True)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Send a message when the command /start is issued
    await update.message.reply_text(HELP_PROMPT)
        
async def respond(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        response = set_model(update.message.text)  
        await update.message.reply_text(response)  
    except NetworkError as e:
        LOGGER.error("Network error during message processing: %s", str(e))
        await update.message.reply_text("I'm having trouble connecting to external services. Please try again later.")
    except Exception as e:
        LOGGER.exception("Unexpected error: %s", str(e))
        await update.message.reply_text("Something went wrong. Try again.")
