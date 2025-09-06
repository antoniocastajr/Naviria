# PROJECT: NAVIRIA
# AUTOR: ANTONIO CASTAÑARES RODRÍGUEZ

# DESCRIPTION: Naviria is a personal AI assistant that can help you with various tasks such as answering questions, writing emails, and scheduling meetings.
# DESCRIPTION OF THE FILE: This file contains the main agent logic for Naviria, including state management, routing, and interaction with external tools.

# -------------------------------------IMPORTS----------------------------------------
import operator
import os
import faiss

from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama  
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_huggingface.embeddings import HuggingFaceEmbeddings                                                 
from langchain_core.messages import HumanMessage, SystemMessage, AnyMessage, AIMessage  
from langchain_core.runnables.config import RunnableConfig
from langchain_core.documents import Document
from langgraph.store.memory import InMemoryStore
from langgraph.store.base import BaseStore
from langgraph.checkpoint.memory import MemorySaver                                 
from langgraph.graph import StateGraph, START, END                    
from pydantic import BaseModel, Field                                        

from main import LOGGER
from dotenv import load_dotenv                                                                  
from prompts import LLM_PROMPT, CREATE_MEMORY_PROMPT, ROUTER_PROMPT                                                    
from typing import Annotated, List
from typing import Literal
from mcp_clients import tavily_client

# -------------------------------------TOKENS-----------------------------------------

load_dotenv()

# -------------------------------------MODELS_AND_EMBEDDINGS--------------------------

models = {
    'llama3.1': ChatOllama(model='llama3.1:8b'),
    'gpt-oss:20b': ChatOllama(model='gpt-oss:20b'), 
    'gpt-5-nano': ChatOpenAI(model='gpt-5-nano'),                                           # Input/Output price: $0.05/$0.4
    'gpt-4.1-nano': ChatOpenAI(model='gpt-4.1-nano'),                                       # Input/Output price: $0.1/$0.4
    'gpt-4o-mini': ChatOpenAI(model='gpt-4o-mini')                                          # Input/Output price: $0.15/$0.6
}     

# -------------------------------------VARIABLES--------------------------------------

llm = models['gpt-5-nano']                                                                  # WRITE THE MODEL THAT YOU WANT TO USE!!!
embedder = HuggingFaceEmbeddings(model_name="google/embeddinggemma-300m",                   # Visit https://huggingface.co/google/embeddinggemma-300m to ask for access
                                query_encode_kwargs={"prompt_name": "query"},
                                encode_kwargs={"prompt_name": "document"})  

# Calls your embedding model once on "hello world" just to learn the vector dimension
index = faiss.IndexFlatL2(len(embedder.embed_query("hello world")))

vector_store = FAISS(
    embedding_function=embedder,
    index=index,
    docstore=InMemoryDocstore(),                                                            # Vector store keeps all the documents in memory
    index_to_docstore_id={},
    distance_strategy="MAX_INNER_PRODUCT"                                                   # Setting distance_strategy to "MAX_INNER_PRODUCT" uses
                                                                                            # FAISS' FlatIndexIP behind the scenes, which is optimized for inner product search.
)

naviria_path = 'naviria_graph.png'

# -------------------------------------ROUTE_MODEL-----------------------------------

class Route(BaseModel):
    '''Route to next step'''
    next: Literal['retrieve_from_vectorstore', 'browser'] = Field(
        description='Whether to retriever or use browser search'
    )                                                  

# -------------------------------------STATE------------------------------------------

class State(BaseModel):
    messages: Annotated[List[AnyMessage], operator.add] = Field(
        description='List of messages in the conversation')
    search_result: List[dict] = Field(description='Results of Tavily MCP Client', default=[])
    best_documents: List[Document] = Field(description='Most similar documents from vector store', default=None)
    memory: str = Field(description='User memory', default='No existing memory found.')
    next_action: str = Field(description='Next action to take', default='retrieve_from_vectorstore')

# -------------------------------------AUXILIARY_FUNCTIONS----------------------------

def last_user_message(state: State) -> HumanMessage:

    ''' Get the last user's message '''

    last_user_message = None 
    # Get messages in reversed order 
    for msg in reversed(state.messages):
        if isinstance(msg, HumanMessage):
            last_user_message = msg
            return last_user_message

    return last_user_message                                                                # Return None if no HumanMessage found

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
        response = await llm.with_structured_output(Route).ainvoke(messages)                # response = ['retrieve_from_vectorstore' or 'browser']
        LOGGER.info(f'Router decided: {response.next}')
        return {'next_action': response.next}
    except Exception as e:
        LOGGER.error(f'Router Node Error: {e}')
        # Default to respond if routing fails
        return {'next_action': 'respond'}

def route_after_router(state: State):
    
    '''Routes based on router decision'''

    return state.next_action

async def browser_node(state: State, config: RunnableConfig, store: BaseStore):
    
    ''' Node that uses Tavily search to answer questions '''
    
    # Get the last user message
    last_message = last_user_message(state)

    if not last_message:
        LOGGER.error('BrowserNode Error: No user message found')
        return {'search_result': []}

    try:
        # Use the MCP Tavily Client
        search_result = await tavily_client(last_message.content)
        
        return {'search_result': search_result}
        
    except Exception as e:
        LOGGER.error(f'BrowserNode Error: {e}')
        return {'search_result': []}
    
def store_in_vectorstore_node(state: State):
    
    """ Store search results from Tavily into the vector store"""

    search_result = state.search_result    
    
    try:
        count = vector_store.index.ntotal
        LOGGER.info(f'Number of documents before adding new ones: {count}')
        documents = [Document(
            page_content=doc.get('content', ''), 
            metadata={
                'title': doc.get('title', ''), 
                'id': i + count
            }
        ) for i, doc in enumerate(search_result)]
        if documents:
            vector_store.add_documents(documents)
            LOGGER.info(f"Stored {len(documents)} documents in vector store.")
        else:
            LOGGER.warning("No documents to store - search_result may be empty or malformed")
    except Exception as e:
        LOGGER.error(f"Error storing search results in vector store: {e}")

def retrieve_best_documents_node(state: State, config: RunnableConfig, store: BaseStore):
    
    """" Retrieve similar documents from vector store based on query """
    
    # Get the last user message
    last_message = last_user_message(state)

    if not last_message:
        LOGGER.error("No user message found for retrieving best documents.")
        return {'best_documents': [Document(page_content='No similar documents found.', metadata={"similarity": 0})]}

    query = last_message.content
    try:
        results = vector_store.similarity_search_with_score(query, k=2)

        # Extract documents and scores from tuples (document, score)
        scores = []
        documents = []
        for doc, score in results:
            scores.append(float(score))
            documents.append(doc)

        LOGGER.info(f"Retrieved {len(documents)} documents with similarity scores: {scores}")
        return {'best_documents': documents}
    except Exception as e:
        LOGGER.error(f"Error retrieving best documents: {e}")
        return {'best_documents': [Document(page_content='No similar documents found.', metadata={"similarity": 0})]}

def get_memory_node(state: State, config: RunnableConfig, store: BaseStore) -> str:

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

    return {'memory': memory}

async def respond_node(state: State, config: RunnableConfig, store: BaseStore):

    '''Node that responds directly without external tools'''
    
    # Get the memory and included it into the PROMPT
    memory = state.memory
    best_documents = state.best_documents
    system_msg = LLM_PROMPT.format(memory=memory, best_documents=best_documents)

    try:
        response = await llm.ainvoke([SystemMessage(content=system_msg)] + state.messages)
        return {'messages': [response]}
    except Exception as e:
        LOGGER.error(f'Respond Node Error: {e}')
        return {'messages': [AIMessage(content='I encountered an error processing your request.')]}

async def save_memory_node(state: State, config: RunnableConfig, store: BaseStore):

    ''' Saves the conversation in memory'''

    # Get the memory and included it into the PROMPT
    
    system_msg = CREATE_MEMORY_PROMPT.format(memory=state.memory, last_interaction=state.messages[-1].content)

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

# -------------------------------------GRAPH------------------------------------------

builder = StateGraph(State)

# Nodes
builder.add_node('router', router_node)
builder.add_node('browser', browser_node)
builder.add_node('store_in_vectorstore', store_in_vectorstore_node)
builder.add_node('retrieve_from_vectorstore', retrieve_best_documents_node)
builder.add_node('get_memory', get_memory_node)
builder.add_node('respond', respond_node)
builder.add_node('save_memory', save_memory_node)

# Logic Flow
builder.add_edge(START, 'router')
builder.add_conditional_edges('router', route_after_router, ['retrieve_from_vectorstore', 'browser'])
builder.add_edge('browser', 'store_in_vectorstore')
builder.add_edge('store_in_vectorstore', 'retrieve_from_vectorstore')
builder.add_edge('retrieve_from_vectorstore', 'get_memory')
builder.add_edge('get_memory', 'respond')
builder.add_edge('respond', 'save_memory')
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