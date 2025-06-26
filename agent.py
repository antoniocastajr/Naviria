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

from main import LOGGER

#from IPython.display import Image, display
# ----------------------------------------TOKENS-----------------------------------------
OPENAI_API_KEY = constants.OPENAI_API_KEY   
TAVILY_API_KEY = constants.TAVILY_API_KEY   

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
    return {"messages": [llm.invoke(state["messages"])]}                                        # Build the dictionary with the messages to return

def tavily_node(state: MessagesState):
    """This function runs Tavily, a search engine to retrieve relevant documents (RAGs)."""
    tavily_search = TavilySearch(max_results=3)
    search_docs = tavily_search.invoke(state["messages"][-1].content)                           # Search Tavily for relevant documents based on the last message content    
    return {"messages": state["messages"] + [search_docs]}                                      # Add the search results to the messages state, giving the LLM access to the retrieved documents                  


# ----------------------------------------GRAPH------------------------------------------

builder = StateGraph(MessagesState)

# Nodes
builder.add_node("llm", llm_node)
builder.add_node("tavily", tavily_node)

# Logic
builder.add_edge(START, "llm")
builder.add_edge("llm", END)

graph = builder.compile()

# ----------------------------------------MODEL-------------------------------------------

def set_model(input: str):
    messages = [
        SystemMessage(content=f"You are Naviria, a personal AI assistant that can help with various tasks such as answering questions, writing emails, and scheduling meetings."),
        HumanMessage(content=f"{input}")
    ]
    response = graph.invoke({"messages": messages})                                             # Invoke the graph with the messages state      
    return response["messages"][-1].content                                                     # The last message in the response is the LLM´s response
