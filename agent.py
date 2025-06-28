# PROJECT: NAVIRIA
# AUTOR: ANTONIO CASTAÑARES RODRÍGUEZ

# DESCRIPTION: Naviria is a personal AI assistant that can help you with various tasks such as answering questions, writing emails, and scheduling meetings.
# DESCRIPTION OF THE FILE: This scripts sets up the langgraph agent for Naviria.

# ----------------------------------------IMPORTS----------------------------------------
import os                                                                                       # To set environment variables for API keys
import constants                                                                                # constants.py contains the API keys

from langchain_openai import ChatOpenAI                                                         # To use OpenAI's chat model for generating responses
from langchain_tavily import TavilySearch                                                       # To use Tavily's chat model for generating responses
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage                      # To handle different types of messages in the chat
from langgraph.graph import MessagesState, StateGraph, START, END                               # To create a state graph and nodes for the agent
from langgraph.prebuilt import tools_condition, ToolNode                                        # To create a tool node for the agent

from main import LOGGER
from constants import OPENAI_API_KEY, TAVILY_API_KEY, SYSTEM_PROMPT                             # Import the API keys and system prompt from constants
#from IPython.display import Image, display
# ----------------------------------------TOKENS-----------------------------------------

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY

# ----------------------------------------MODELS-----------------------------------------

# OPENAI
gpt35 = ChatOpenAI(model_name = "gpt-3.5-turbo", temperature = 0)
gpt4 = ChatOpenAI(model_name = "gpt-4", temperature = 0)

llm = gpt35                                                                                     # Default model for the agent   

# ----------------------------------------NODES------------------------------------------

def llm_node(state: MessagesState):
    """This function runs to the LLM with the messages and returns the response."""
    print(state["messages"], "\n")
    return {"messages": [llm.invoke(state["messages"])]}                                        # Build the dictionary with the messages to return

def tavily_tool(query: str) -> str:
    """Search the web using Tavily based on the user query."""
    tavily_search = TavilySearch(max_results=1)
    result = tavily_search.invoke(query)

    if isinstance(result, dict) and result.get("results"):
        doc = result["results"][0]
        return f"[Tavily Search Complete]\n{doc['title']} — {doc['url']}\n{doc['content']}"
    else:
        return "[Tavily Search Complete]\nNo relevant results found."
    
    
tools = [tavily_tool]                                                                           # List of tools available for the agent
llm = llm.bind_tools(tools)                                                                     # Associate the tools with the LLM  
# ----------------------------------------GRAPH------------------------------------------

builder = StateGraph(MessagesState)

# Nodes
builder.add_node("llm", llm_node)
builder.add_node("tools", ToolNode(tools))                                         

# Logic
builder.add_edge(START, "llm")  
builder.add_conditional_edges(
    "llm",
    # If the latest message (result) from assistant is a tool call -> tools_condition routes to tools
    # If the latest message (result) from assistant is a not a tool call -> tools_condition routes to END
    tools_condition,
)

builder.add_edge("tools", "llm")

graph = builder.compile()

# ----------------------------------------MODEL-------------------------------------------

def set_model(input: str):
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"{input}")
    ]
    response = graph.invoke({"messages": messages})                                             # Invoke the graph with the messages state      
    return response["messages"][-1].content                                                     # The last message in the response is the LLM´s response
