# PROJECT: NAVIRIA
# AUTOR: ANTONIO CASTAÑARES RODRÍGUEZ

# DESCRIPTION: Naviria isasync def router_node(state: State, config: RunnableConfig, store: BaseStore):
# DESCRIPTION OF THE FILE: This scripts sets up the langgraph agent for Naviria.

# -------------------------------------IMPORTS----------------------------------------
import operator
import os

from langchain.chat_models import init_chat_model 
from langchain_ollama import ChatOllama                                                     
from langchain_core.messages import HumanMessage, SystemMessage, AnyMessage, AIMessage  
from langchain_core.runnables.config import RunnableConfig
from langgraph.store.memory import InMemoryStore
from langgraph.store.base import BaseStore
from langgraph.checkpoint.memory import MemorySaver                                 
from langgraph.graph import StateGraph, START, END                          
from pydantic import BaseModel, Field                                        

from main import LOGGER
from dotenv import load_dotenv                                                                  
from prompts import LLM_PROMPT, CREATE_MEMORY_PROMPT, ROUTER_PROMPT, TAVILY_PROMPT                                                       
from typing import Annotated, List
from typing import Literal
from mcp_clients import tavily_client

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
naviria_path = 'naviria_graph.png'                                                  

# -------------------------------------ROUTE_MODEL-----------------------------------

class Route(BaseModel):
    '''Route to next step'''
    next: Literal['respond', 'browser'] = Field(
        description='Whether to respond directly or use browser search'
    )                                                  

# -------------------------------------STATE------------------------------------------

class State(BaseModel):
    messages: Annotated[List[AnyMessage], operator.add] = Field(
        description='List of messages in the conversation')
    next_action: str = Field(description='Next action to take', default='respond')

# -------------------------------------AUXILIARY_FUNCTIONS----------------------------

def get_memory(config: RunnableConfig, store: BaseStore) -> str:

    ''' Retrieves the user's memory from the store '''

    # Memory path: memory/{user_id}/user_memory
    user_id = config['configurable']['user_id']
    namespace = ('memory', user_id)
    key = 'user_memory'

    # Get the user's memory
    existing_memory = store.get(namespace, key)
    if existing_memory:
        memory = existing_memory.value.get('memory')
    else:
        memory = 'No existing memory found.'

    return memory

def print_messages(state: State):

    ''' Prints all sequence of messages '''

    for message in state.messages:
        print(f'{message}\n')

def last_user_message(state: State) -> HumanMessage:

    ''' Get the last user's message '''

    last_user_message = None 
    # Get messages in reversed order 
    for msg in reversed(state.messages):
        if isinstance(msg, HumanMessage):
            last_user_message = msg
            return last_user_message

# -------------------------------------NODES------------------------------------------

async def router_node(state: State, config: RunnableConfig, store: BaseStore):

    ''' Decides the next step: whether to use Tavily search or respond directly ''' 

    # Get the last user message for routing decision
    last_message = last_user_message(state)
    
    # If not user's message, respond directly 
    if not last_message:
        return {'next_action': 'respond'}
    
    messages = [
        {'role': 'system', 'content': ROUTER_PROMPT},
        {'role': 'user', 'content': last_message.content}
    ]
    
    try:
        # Decides the next node based on the last user's message
        response = await llm.with_structured_output(Route, method="function_calling").ainvoke(messages)            # response = ['respond' or 'browser']
        LOGGER.info(f'Router decided: {response.next}')
        return {'next_action': response.next}
    except Exception as e:
        LOGGER.error(f'Router Node Error: {e}')
        # Default to respond if routing fails
        return {'next_action': 'respond'}

async def browser_node(state: State, config: RunnableConfig, store: BaseStore):
    
    '''Node that uses Tavily search to answer questions'''
    
    # Get the last user message
    last_message = last_user_message(state)

    if not last_message:
        return {'messages': [AIMessage(content='No question to search for.')]}
    
    try:
        # Use the MCP Tavily Client
        search_result = await tavily_client(last_message.content)
        
        # Create response incorporating search results and previous messages to the PROMPT
        memory = get_memory(config, store)
        system_msg = TAVILY_PROMPT.format(memory=memory, last_message=last_message.content, search_result=search_result)

        messages = [
            SystemMessage(content=system_msg),
            last_message
        ]
        # Memory and search results are available for LLM because they were included into the PROMPT
        response = await llm.ainvoke(messages)
        
        return {'messages': [response]}
        
    except Exception as e:
        LOGGER.error(f'Tavily Node Error: {e}')
        return {'messages': [AIMessage(content='I encountered an error searching for information.')]}

async def respond_node(state: State, config: RunnableConfig, store: BaseStore):

    '''Node that responds directly without external tools'''
    
    # Get the memory and included it into the PROMPT
    memory = get_memory(config, store)
    system_msg = LLM_PROMPT.format(memory=memory)
    
    try:
        response = await llm.ainvoke([SystemMessage(content=system_msg)] + state.messages)
        return {'messages': [response]}
    except Exception as e:
        LOGGER.error(f'Respond Node Error: {e}')
        return {'messages': [AIMessage(content='I encountered an error processing your request.')]}

async def save_memory(state: State, config: RunnableConfig, store: BaseStore):

    ''' Saves the conversation in memory'''

    # Get the memory and included it into the PROMPT
    memory = get_memory(config, store)
    system_msg = CREATE_MEMORY_PROMPT.format(memory=memory)

    try:
        # Summarizes the existing memory
        response = await llm.ainvoke([SystemMessage(content=system_msg)] + state.messages)
        
        # Memory path: memory/{user_id}/user_memory
        user_id = config['configurable']['user_id']
        namespace = ('memory', user_id)
        key = 'user_memory'

        # Update the exisiting memory with the summary generated by the LLM
        store.put(namespace, key, {'memory': response.content})
        
        # If the list of messages get too long, we keep only with the last six messages
        if len(state.messages) > 12:
            state.messages = state.messages[-6:]
            
        LOGGER.info(f'Memory saved for user {user_id}')
        
    except Exception as e:
        LOGGER.error(f'Save Memory Error: {e}')

def route_after_router(state: State):
    '''Routes based on router decision'''
    return state.next_action

# -------------------------------------GRAPH------------------------------------------

builder = StateGraph(State)

# Nodes
builder.add_node('router', router_node)
builder.add_node('respond', respond_node)
builder.add_node('browser', browser_node)
builder.add_node('save_memory', save_memory)

# Logic Flow
builder.add_edge(START, 'router')
builder.add_conditional_edges('router', route_after_router, ['respond', 'browser'])
builder.add_edge('respond', 'save_memory')
builder.add_edge('browser', 'save_memory')
builder.add_edge('save_memory', END)

graph = builder.compile(checkpointer=MemorySaver(), store=InMemoryStore())

# -------------------------------------PLOTTING---------------------------------------

""" Generates the graph only if it was not generated previously """

if not os.path.exists(naviria_path):
    naviria_graph = graph.get_graph().draw_mermaid_png(max_retries=5, retry_delay=2.0)    # Use the mermaid API to draw the graph
    with open(naviria_path, 'wb') as f:
        f.write(naviria_graph)
        f.close()  

# -------------------------------------MODEL------------------------------------------

async def set_model(input: str, user_id: int):

    """ Initializes the graph and returns the response to the TELEGRAM API """

    # Config for short-long memory associated to user
    config = {'configurable': {'thread_id': str(user_id), 'user_id': str(user_id)}}
    response = await graph.ainvoke({'messages': [HumanMessage(content=input)]}, config)
    return response['messages'][-1].content