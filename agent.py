# PROJECT: NAVIRIA
# AUTOR: ANTONIO CASTAÑARES RODRÍGUEZ

# DESCRIPTION: Naviria is a personal AI assistant that can help you with various tasks such as answering questions, writing emails, and scheduling meetings.
# DESCRIPTION OF THE FILE: This scripts sets up the langgraph agent for Naviria.

# -------------------------------------IMPORTS----------------------------------------
import operator
import os

from langchain.chat_models import init_chat_model                                                      
from langchain_core.messages import HumanMessage, SystemMessage, AnyMessage                      
from langchain_tavily import TavilySearch
from langchain_community.document_loaders import WikipediaLoader
from langchain_core.tools import tool  
from langgraph.prebuilt import ToolNode, tools_condition                                   
from langgraph.graph import StateGraph, START, END                          
from pydantic import BaseModel, Field                                        

from main import LOGGER
from dotenv import load_dotenv                                                                  
from prompts import LLM_PROMPT                                                         
from typing import Annotated, List

# -------------------------------------TOKENS-----------------------------------------

load_dotenv()

# -------------------------------------MODELS-----------------------------------------

models = {#'openai:gpt-4.1': init_chat_model("openai:gpt-4.1"), 
          'openai:gpt-3.5-turbo': init_chat_model("openai:gpt-3.5-turbo")}

# -------------------------------------VARIABLES--------------------------------------

llm = models['openai:gpt-3.5-turbo']                                                  
naviria_path = "naviria_graph.png"                                                             

# -------------------------------------STATE------------------------------------------
class State(BaseModel):
    messages : Annotated[List[AnyMessage], operator.add] = Field(
        description="List of messages in the conversation")
    context : Annotated[List[str], operator.add] = Field(
        description="Context provided by Tavily and Wikipedia")

# -------------------------------------NODES------------------------------------------
def llm_node(state: State):

    """ Runs the LLM without deep_research """ 

    LOGGER.info("Running LLM with messages:%s\n", state.messages)

    response = llm.invoke([SystemMessage(content=LLM_PROMPT)] + state.messages)

    return {"messages": [response]}

@tool
def tavily_tool(query: str):
    
    """ Retrieve docs from internet using Tavily """

    LOGGER.info("Running Tavily tool with query:%s\n", query)
    
    tavily_search = TavilySearch(max_results=1, exclude_domains=['wikipedia.org'])
    result = tavily_search.invoke(query)
 
    if not result or not result["results"]:
        LOGGER.warning("No results found by Tavily for query: %s", query)
        return {"context": ["No relevant documents found by Tavily."]}
        
    doc = result["results"][0]
    formatted_doc = f'<Document href="{doc["url"]}"/>\n{doc["content"]}\n</Document>'
    return {"context": [formatted_doc]}  

@tool    
def wikipedia_tool(query: str):
    
    """ Retrieve docs from Wikipedia """

    LOGGER.info("Running Wikipedia tool with query:%s\n", query)

    result = WikipediaLoader(query=query, load_max_docs=1).load()

    if not result:
        return {"context": ["No relevant documents found in Wikipedia."]}

    doc = result[0]
    formatted_doc = f'<Document source="{doc.metadata["source"]}"/>\n{doc.page_content}\n</Document>'
    return {"context": [formatted_doc]}


# -------------------------------------LLM_CONFIGURATION------------------------------

tools = [tavily_tool, wikipedia_tool]
llm = llm.bind_tools(tools)  

# -------------------------------------GRAPH------------------------------------------

builder = StateGraph(State)

# Nodes
builder.add_node("llm", llm_node)    
builder.add_node("tools", ToolNode(tools))      
# Logic
builder.add_edge(START, "llm")
builder.add_conditional_edges('llm', tools_condition) 
builder.add_edge("tools", "llm")

builder.add_edge("llm", END)

graph = builder.compile()

# -------------------------------------PLOTTING---------------------------------------

if not os.path.exists(naviria_path):
    naviria_graph = graph.get_graph().draw_mermaid_png()
    with open(naviria_path, "wb") as f:
        f.write(naviria_graph)
        f.close()  

# -------------------------------------MODEL------------------------------------------

def set_model(input: str):
    response = graph.invoke({"messages": [HumanMessage(content=input)]})
    return response["messages"][-1].content
