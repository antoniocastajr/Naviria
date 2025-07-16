# PROJECT: NAVIRIA
# AUTOR: ANTONIO CASTAÑARES RODRÍGUEZ

# DESCRIPTION: Naviria is a personal AI assistant that can help you with various tasks such as answering questions, writing emails, and scheduling meetings.
# DESCRIPTION OF THE FILE: This scripts sets up the langgraph agent for Naviria.

# -------------------------------------IMPORTS----------------------------------------
import operator
import os

from langchain.chat_models import init_chat_model                                                      
from langchain_core.messages import HumanMessage, SystemMessage, AnyMessage, AIMessage  
from langchain_core.runnables.config import RunnableConfig
from langgraph.store.memory import InMemoryStore
from langgraph.store.base import BaseStore
from langgraph.checkpoint.memory import MemorySaver 
from langchain_tavily import TavilySearch
from langchain_community.document_loaders import WikipediaLoader
from langchain_core.tools import tool  
from langgraph.prebuilt import ToolNode                                 
from langgraph.graph import StateGraph, START, END                          
from pydantic import BaseModel, Field                                        

from main import LOGGER
from dotenv import load_dotenv                                                                  
from prompts import LLM_PROMPT, CREATE_MEMORY_PROMPT                                                         
from typing import Annotated, List

# -------------------------------------TOKENS-----------------------------------------

load_dotenv()

# -------------------------------------MODELS-----------------------------------------

models = {#'openai:gpt-4.1': init_chat_model("openai:gpt-4.1"), 
          'openai:gpt-3.5-turbo': init_chat_model("openai:gpt-3.5-turbo")}

# -------------------------------------VARIABLES--------------------------------------

llm = models['openai:gpt-3.5-turbo']                                                  
naviria_path = "naviria_graph.png"  
across_thread_memory = InMemoryStore() 
within_thread_memory = MemorySaver()                                                        

# -------------------------------------STATE------------------------------------------

class State(BaseModel):
    messages : Annotated[List[AnyMessage], operator.add] = Field(
        description="List of messages in the conversation")

# -------------------------------------NODES------------------------------------------

def llm_node(state: State, config: RunnableConfig, store: BaseStore):

    """ Runs the LLM without deep_research """ 

    user_id = config["configurable"]["user_id"]
    namespace = ("memory", user_id)
    key = "user_memory"

    existing_memory = store.get(namespace, key)
    if existing_memory:
        # Value is a dictionary with a memory key
        memory = existing_memory.value.get('memory')
    else:
        memory = "No existing memory found."
        
    system_msg = LLM_PROMPT.format(memory=memory)

    response = llm.invoke([SystemMessage(content=system_msg)] + state.messages)

    return {"messages": [response]}

@tool
def tavily_tool(query: str):
    
    """ Retrieve docs from internet using Tavily """

    tavily_search = TavilySearch(max_results=1, 
                                 exclude_domains=['wikipedia.org'])
    result = tavily_search.invoke(query)

    return result["results"][0]

@tool    
def wikipedia_tool(query: str):
    
    """ Retrieve docs from Wikipedia """

    result = WikipediaLoader(query=query, load_max_docs=1).load()

    return result[0]

def save_memory(state: State, config: RunnableConfig, store: BaseStore):

    """ Saves the conversation in memory"""

    user_id = config["configurable"]["user_id"]
    namespace = ("memory", user_id)
    key = "user_memory"

    existing_memory = store.get(namespace, key)
    if existing_memory:
        # Value is a dictionary with a memory key
        memory = existing_memory.value.get('memory')
    else:
        memory = "No existing memory found."

    system_msg = CREATE_MEMORY_PROMPT.format(memory=memory)
    response = llm.invoke([SystemMessage(content=system_msg)] + state.messages)

    store.put(namespace,key, {"memory": response.content})

def tools_condition(state: State, config: RunnableConfig):

    """ Determines which is the next node to run"""

    last_message = state.messages[-1]
    if isinstance(last_message, AIMessage) and last_message.additional_kwargs.get("tool_calls"):
        return "search_tools"
    return "save_memory"

# -------------------------------------LLM_CONFIGURATION------------------------------

tools = [tavily_tool, wikipedia_tool]
llm = llm.bind_tools(tools)  

# -------------------------------------GRAPH------------------------------------------

builder = StateGraph(State)

# Nodes
builder.add_node("llm", llm_node)    
builder.add_node("search_tools", ToolNode(tools))  
builder.add_node("save_memory", save_memory) 

# Logic
builder.add_edge(START, "llm")
builder.add_conditional_edges('llm', tools_condition, ["search_tools", "save_memory"]) 
builder.add_edge("search_tools", "llm")
builder.add_edge("save_memory", END)

graph = builder.compile(checkpointer=within_thread_memory, store=across_thread_memory)

# -------------------------------------PLOTTING---------------------------------------

if not os.path.exists(naviria_path):
    naviria_graph = graph.get_graph().draw_mermaid_png()
    with open(naviria_path, "wb") as f:
        f.write(naviria_graph)
        f.close()  

# -------------------------------------MODEL------------------------------------------

def set_model(input: str, user_id: int):
    config = {"configurable": {"thread_id": str(user_id), "user_id": str(user_id)}}
    response = graph.invoke({"messages": [HumanMessage(content=input)]}, config)
    return response["messages"][-1].content