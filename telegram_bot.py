# PROJECT: NAVIRIA
# AUTOR: ANTONIO CASTAÑARES RODRÍGUEZ

# DESCRIPTION: Naviria is a personal AI assistant that can help you with various tasks such as answering questions, writing emails, and scheduling meetings.

# ----------------------------------------IMPORTS----------------------------------------                              
from telegram import ForceReply, Update                                                         # To send messages and replies to users
from telegram.ext import ContextTypes                                                           # To handle commands and messages from users

from main import LOGGER                                                                         # Logger for debugging and information purposes    
from agent import set_model                                                                     # Function to set the model for generating responses

# ----------------------------------------COMMAND HANDLERS--------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    reply = (
        "Welcome to Naviria, your personal AI assistant created by Antonio Castañares Rodríguez.\n\n"
        "I can help you with various tasks such as answering questions, writing emails, and scheduling meetings.\n\n"
    )
    # Send a message when the command /start is issued
    await update.message.reply_html(
        f"Hi {user.mention_html()}! \n\n{reply}",
        reply_markup=ForceReply(selective=True)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    reply = "Naviria is your personal AI assistant.\n\n" \
            "You can ask me anything, and I will do my best to assist you. Here are some funcionabilities:\n\n" \
            "- Conversation mode:\n" \
            "- Answering questions using deep research\n" \
            "- Write a email using Gmail\n" \
            "- Stablish a meeting on Google Calendar\n" 
    await update.message.reply_text(reply)

async def respond(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        response = set_model(update.message.text)  
        await update.message.reply_text(response)  
    except Exception as e:
        LOGGER.error(f"Error processing message: {e}")
        await update.message.reply_text("Sorry, I couldn't process your request. Please try again later.")
