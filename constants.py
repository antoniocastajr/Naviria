# PROJECT: NAVIRIA
# AUTOR: ANTONIO CASTAÑARES RODRÍGUEZ

# DESCRIPTION: Naviria is a personal AI assistant that can help you with various tasks such as answering questions, writing emails, and scheduling meetings.
# DESCRIPTION OF THE FILE: This script contains the API keys, tokens and prompts used in the project.

# ----------------------------------------TOKENS-----------------------------------------

TELEGRAM_TOKEN = "your-telegram-bot-token-here"  
OPENAI_API_KEY= "your-openai-api-key-here"  
TAVILY_API_KEY= "your-tavily-api-key-here"

# ----------------------------------------PROMPTS-----------------------------------------

START_PROMPT = ("Welcome to Naviria, your personal AI assistant created by Antonio Castañares Rodríguez.\n\n"
                "How can I assist you today?\n\n"
)

HELP_PROMPT = ("Naviria is your personal AI assistant.\n\n"
               "You can ask me anything, and I will do my best to assist you. Here are some functionalities:\n\n"
                "- Conversation mode:\n"
)

SYSTEM_PROMPT = ("You are Naviria, a personal AI assistant created by Antonio Castañares Rodríguez.\n"
                 )