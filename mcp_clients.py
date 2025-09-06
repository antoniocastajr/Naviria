# PROJECT: NAVIRIA
# AUTOR: ANTONIO CASTAÑARES RODRÍGUEZ

# DESCRIPTION: Naviria is a personal AI assistant that can help you with various tasks such as answering questions, writing emails, and scheduling meetings.
# DESCRIPTION OF THE FILE: This file manages connections to external services via MCP clients.

import json

from dotenv import load_dotenv
from mcp_use import MCPAgent, MCPClient
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama 

from main import LOGGER

# -------------------------------------TOKENS-----------------------------------------

load_dotenv()

# -------------------------------------MODELS-----------------------------------------

models = {
    'llama3.1': ChatOllama(model='llama3.1:8b'),
    'gpt-oss:20b': ChatOllama(model='gpt-oss:20b'), 
    'gpt-5-nano': ChatOpenAI(model='gpt-5-nano'),                                                 # Input/Output price: $0.05/$0.4
    'gpt-4.1-nano': ChatOpenAI(model='gpt-4.1-nano'),                                             # Input/Output price: $0.1/$0.4
    'gpt-4o-mini': ChatOpenAI(model='gpt-4o-mini')                                                # Input/Output price: $0.15/$0.6
}

# -------------------------------------VARIABLES--------------------------------------

llm = models['gpt-5-nano']     # WRITE THE MODEL THAT YOU WANT TO USE!!!

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
        session = client.get_session('tavily-remote')
        
        #tools = await session.list_tools()
        #LOGGER.info(f'Available tools: {[tool.name for tool in tools]}')
        
        # Call tavily_search with proper parameters
        results = await session.call_tool(
            name='tavily_search',
            arguments={
                'query': query,
                'max_results': 2,
                'search_depth': 'basic',
                'topic': 'general',
                'include_raw_content': False,
            }
        )
        
        # Extract structured content from the CallToolResult
        if results.structuredContent:
            search_data = results.structuredContent
            search_results = search_data.get('results', [])
            
            # Create a list of unique content from each document
            results = []
            seen_content = set()  # To track unique content
            
            for result in search_results:
                content = result.get('content', '').strip()
                title = result.get('title', '').strip()
                
                # Create a unique identifier based on content to avoid duplicates
                content_hash = hash(content) if content else None
                
                if content and content_hash not in seen_content:
                    results.append({'title': title, 'content': content})
                    seen_content.add(content_hash)
            
            return results
        else:
            LOGGER.warning('No structured content found in Tavily results')
            return [f"Search completed but no results found for: {query}"]
        
    except Exception as e:
        LOGGER.error(f'MCP Tavily connection failed: {e}')
        return [f"Search temporarily unavailable. Please try asking about general topics or try again later."]

    finally:
        # Ensure sessions are properly closed even if errors occur
        if client:
            try:
                await client.close_all_sessions()
            except Exception as close_error:
                LOGGER.error(f'Error closing MCP sessions: {close_error}')

