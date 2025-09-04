import json

from dotenv import load_dotenv
from mcp_use import MCPAgent, MCPClient
from langchain.chat_models import init_chat_model 

load_dotenv()

llm = init_chat_model('openai:gpt-4')

async def tavily_client(query: str):
    """ Use Tavily via MCP """
    
    with open("tavily.json", "r") as f:
        config = json.load(f)

    client = MCPClient.from_dict(config)

    await client.create_all_sessions()

    agent = MCPAgent(llm=llm, client=client, max_steps=30)

    try:
        result = await agent.run(query)
        await client.close_all_sessions()
        return result
    except Exception as e:
        print(f"Error running Tavily agent: {e}")
        return "Error processing your request."
