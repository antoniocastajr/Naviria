import json

from dotenv import load_dotenv
from mcp_use import MCPAgent, MCPClient
from langchain.chat_models import init_chat_model 
from langchain_ollama import ChatOllama 

from main import LOGGER

# -------------------------------------TOKENS-----------------------------------------

load_dotenv()

# -------------------------------------MODELS-----------------------------------------

models = {
    'llama3.1': ChatOllama(model='llama3.1:8b'),
    'gpt-oss:20b': ChatOllama(model='gpt-oss:20b'), 
    'openai:gpt-3.5-turbo': init_chat_model('openai:gpt-3.5-turbo'),
    'openai:gpt-4': init_chat_model('openai:gpt-4')  
}

# -------------------------------------VARIABLES--------------------------------------

llm = models['openai:gpt-3.5-turbo']     # WRITE THE MODEL THAT YOU WANT TO USE!!!                                                                                            

# -------------------------------------MCP_CLIENTS------------------------------------

async def tavily_client(query: str):
    """ Use Tavily via MCP """
    
    client = None
    try:
        # Get the config from JSON
        with open("tavily.json", "r") as f:
            config = json.load(f)

        # Builds the MCP client
        client = MCPClient.from_dict(config)

        # Create sessions between clients and servers with timeout
        await client.create_all_sessions()

        # MCP Agent who controls the flow of the conversation
        # Receives the list of tools and decides which one to use
        agent = MCPAgent(llm=llm, client=client, max_steps=5) 

        # Add timeout to the agent run
        result = await agent.run(query)
        
        return result
        
    except Exception as e:
        LOGGER.error(f'MCP Tavily connection failed: {e}')
        return f"Search temporarily unavailable. Please try asking about general topics or try again later."
    
    finally:
        # Ensure sessions are properly closed even if errors occur
        if client:
            try:
                await client.close_all_sessions()
            except Exception as close_error:
                LOGGER.error(f'Error closing MCP sessions: {close_error}')

