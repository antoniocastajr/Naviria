# PROJECT: NAVIRIA
# AUTOR: ANTONIO CASTAÑARES RODRÍGUEZ

# DESCRIPTION: Naviria is a personal AI assistant that can help you with various tasks such as answering questions, writing emails, and scheduling meetings.

# ----------------------------------------IMPORTS----------------------------------------
import logging                                                                                  # For debugging and information purposes                                 
import os                                                                                       # To set environment variables for API keys
import constants                                                                                # constants.py contains the API keys  

from telegram import ForceReply, Update                                                         # To send messages and replies to users
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters     # To handle commands and messages from users
from langchain_openai import ChatOpenAI                                                         # To use OpenAI's chat model for generating responses
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ChatMessage         # To handle different types of messages in the chat

# ----------------------------------------TOKENS-----------------------------------------

TELEGRAM_TOKEN = constants.TELEGRAM_TOKEN  
OPENAI_API_KEY= constants.OPENAI_API_KEY   
TAVILY_API_KEY= constants.TAVILY_API_KEY   

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY

# Set the OpenAI model to use for generating responses
llm = ChatOpenAI(model_name = "gpt-3.5-turbo", temperature = 0)

# ----------------------------------------SETUP------------------------------------------

# Logging configuration (print time, name, level and message using the terminal)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Suppress the httpx library logs to avoid cluttering the output
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

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

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    messages = [HumanMessage(content=update.message.text)] 
    try:
        response = llm.invoke(messages)  
        await update.message.reply_text(response.content)  
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text("Sorry, I couldn't process your request. Please try again later.")


# ----------------------------------------MAIN FUNCTION-----------------------------------

def main() -> None:
    # Initialize the application with the bot token
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Command handlers for the bot
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Message handler for text messages (excluding commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()