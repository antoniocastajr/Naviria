# PROJECT: NAVIRIA
# AUTOR: ANTONIO CASTAÑARES RODRÍGUEZ

# DESCRIPTION: Naviria is a personal AI assistant that can help you with various tasks such as answering questions, writing emails, and scheduling meetings.
# DESCRIPTION OF THE FILE: This file contains the main agent logic for Naviria, including state management, routing, and interaction with external tools.

# -------------------------------------IMPORTS----------------------------------------
import operator                                                                             # For combining lists of messages        
import os                                                                                   # To handle file paths
import faiss                                                                                # For vector store management

from langchain_openai import ChatOpenAI                                                     # For using OpenAI models
from langchain_ollama import ChatOllama                                                     # For using models by Ollama
from langchain_huggingface.embeddings import HuggingFaceEmbeddings                          # For embedding: embeddinggemma (Google)    
from langchain_community.vectorstores import FAISS                                          # For vector store management
from langchain_community.docstore.in_memory import InMemoryDocstore                         # In-memory document storage for FAISS
from langchain_core.documents import Document                                               # Document structure for storing text data 
from langgraph.store.base import BaseStore                                                  # Base store interface for memory management                                           
from langchain_core.messages import HumanMessage, SystemMessage, AnyMessage, AIMessage      # Types of messages in Langgraph  
from langchain_core.runnables.config import RunnableConfig                                  # Configuration for states
from langgraph.graph import StateGraph, START, END                                          # Nodes in langgraph
from langgraph.store.memory import InMemoryStore                                            # Long-term memory storage
from langgraph.checkpoint.memory import MemorySaver                                         # Short-term memory checkpointing                                                  
from pydantic import BaseModel, Field                                                       # For data validation and settings management of each state                                                                

from main import LOGGER                                                                     # Logger for debugging and information purposes
from dotenv import load_dotenv                                                              # To set environment variables for API keys                                          
from prompts import LLM_PROMPT, CREATE_MEMORY_PROMPT, ROUTER_PROMPT                         # Prompts used in the project                                                       
from typing import Annotated, List                                                          # Types for states
from typing import Literal                                                                  # Options for routing
from mcp_clients import tavily_client                                                       # MCP Clients

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
embedder = HuggingFaceEmbeddings(model_name="google/embeddinggemma-300m",                   # EmbeddingGemma (Google), released 4 September 2025, with 308M parameters.
                                query_encode_kwargs={"prompt_name": "query"},               # Visit https://huggingface.co/google/embeddinggemma-300m to ask for access
                                encode_kwargs={"prompt_name": "document"})                          

vector_store = FAISS(
    embedding_function=embedder,
    index=faiss.IndexFlatIP(len(embedder.embed_query("hello world"))),                      # Using Inner Product (IP) for cosine similarity
    docstore=InMemoryDocstore(),                                                            # Vector store keeps all the documents in memory
    index_to_docstore_id={}
)

naviria_path = 'naviria_graph.png'                                                          # Path to save the graph image  

# -------------------------------------ROUTE_MODEL-----------------------------------

class Route(BaseModel):
    '''Route to next step'''
    next: Literal['retrieve_from_vectorstore', 'browser'] = Field(
        description='Whether to retriever or use browser search'
    )                                                  

# -------------------------------------STATE------------------------------------------

class State(BaseModel):
    messages: Annotated[List[AnyMessage], operator.add] = Field(description='List of messages in the conversation')
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
    
    '''Function uses as conditional_node after router_node '''

    return state.next_action

async def browser_node(state: State, config: RunnableConfig, store: BaseStore):
    
    ''' Node that uses Tavily by MCP to answer questions '''
    
    # Get the last user message
    last_message = last_user_message(state)

    if not last_message:
        LOGGER.error('BrowserNode Error: No user message found')
        return {'search_result': []}

    try:
        # Use the MCP Tavily Client
        search_result = await tavily_client(last_message.content)                           # search_result = [{'title': ..., 'content': ...}, ...]
        return {'search_result': search_result}
        
    except Exception as e:
        LOGGER.error(f'BrowserNode Error: {e}')
        return {'search_result': []}
    
def store_in_vectorstore_node(state: State):
    
    ''' Store search results from Tavily into the vector store '''

    # Get search results from Tavily MCP Client
    search_result = state.search_result    
    
    try:
        # Get the current number of documents in the vector store to create unique IDs
        count = vector_store.index.ntotal
        LOGGER.info(f'Number of documents before adding new ones: {count}')

        # Convert search results to Document objects with unique IDs
        documents = []
        for i, doc in enumerate(search_result):
            document = Document(page_content=doc.get('content', ''), 
                    metadata={
                        'title': doc.get('title', ''), 
                        'id': i + count
                    })
            documents.append(document)
        # Add documents to the vector store
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

    if vector_store.index.ntotal == 0:
        LOGGER.info("Vector store is empty. No documents to retrieve.")
        return {'best_documents': [Document(page_content='No similar documents found.', metadata={"similarity": 0})]}
    try:
        # Get the two documents most similar to the user's last message
        results = vector_store.similarity_search_with_score(last_message.content, k=2)

        # Extract documents and scores from tuples (document, score)
        scores = []
        documents = []
        for doc, score in results:
            # If the score is above 0.35, I consider the document as relevant
            if float(score) > 0.35:
                scores.append(float(score))
                document = Document(page_content=doc.page_content, metadata={"similarity": float(score)})
                documents.append(document)

        if len(documents) != 0:
            LOGGER.info(f"Retrieved {len(documents)} documents with similarity scores: {scores}")
            return {'best_documents': documents}
        
        LOGGER.info("No documents passed the similarity threshold.")
        return {'best_documents': [Document(page_content='No similar documents found.', metadata={"similarity": 0})]}

    except Exception as e:
        LOGGER.error(f"Error retrieving best documents: {e}")
        return {'best_documents': [Document(page_content='No similar documents found.', metadata={"similarity": 0})]}

def get_memory_node(state: State, config: RunnableConfig, store: BaseStore):

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
    LOGGER.info(f'Best documents for response: {best_documents}')
    system_msg = LLM_PROMPT.format(memory=memory, best_documents=best_documents)

    try:
        response = await llm.ainvoke([SystemMessage(content=system_msg)] + state.messages)
        return {'messages': [response]}
    except Exception as e:
        LOGGER.error(f'Respond Node Error: {e}')
        return {'messages': [AIMessage(content='I encountered an error processing your request.')]}

async def save_memory_node(state: State, config: RunnableConfig, store: BaseStore):

    ''' Saves the conversation in memory '''

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

''' Generates the graph only if it was not generated previously '''

if not os.path.exists(naviria_path):
    naviria_graph = graph.get_graph().draw_mermaid_png(max_retries=5, retry_delay=2.0)          # Use the mermaid API to draw the graph
    with open(naviria_path, 'wb') as f:
        f.write(naviria_graph)
        f.close()  

# -------------------------------------MODEL------------------------------------------

async def set_model(input: str, user_id: int):

    ''' Initializes the graph and returns the response to the TELEGRAM API '''

    config = {'configurable': {'thread_id': str(user_id), 'user_id': str(user_id)}}             # Config for short-long memory associated to user
    response = await graph.ainvoke({'messages': [HumanMessage(content=input)]}, config)         # Run the graph in async mode
    return response['messages'][-1].content                                                     # Provide the respond to TELEGRAM API