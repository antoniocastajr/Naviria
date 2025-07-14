# PROJECT: NAVIRIA
# AUTOR: ANTONIO CASTAÑARES RODRÍGUEZ

# DESCRIPTION: Naviria is a personal AI assistant that can help you with various tasks such as answering questions, writing emails, and scheduling meetings.
# DESCRIPTION OF THE FILE: This scripts sets up the langgraph agent for Naviria.

# -------------------------------------IMPORTS----------------------------------------


# -------------------------------------STATE------------------------------------------
class ResearchState(BaseModel):
    query : str = Field(None, description="Query for the research task")
    context : Annotated[List[str], operator.add] = Field(description="Context provided by Tavily and Wikipedia")
    content : str = Field(None, description="Content of the response from the LLM")
    introduction: str = Field(None, description="Introduction to the response")
    conclusion: str = Field(None, description="Conclusion of the response")
    final_answer: str = Field(None, description="Final answer to the question")

class SearchQuery(BaseModel):
    search_query: str = Field(None, description="Search query for retrieval.")

# -------------------------------------NODES------------------------------------------

def deep_research_node(state: ResearchState):

    """ Runs to the LLM with the current query and documents obtained from the tools"""

    message = state.messages[-1] 
    docs = state.context

    system_msg = SYSTEM_PROMPT.format(context=docs)

    return {"messages": [llm.invoke([SystemMessage(content=system_msg)] + message)]}

def search_web(state: ResearchState):
    
    """ Retrieve docs from web search """

    # Search query
    query = state.messages[-1]
    structured_llm = llm.with_structured_output(SearchQuery)
    search_query = structured_llm.invoke([SystemMessage(content=SEARCH_PROMPT)] + [query])

    # Search
    tavily_search = TavilySearch(max_results=3)
    search_docs = tavily_search.invoke(search_query.search_query)

     # Format
    formatted_search_docs = "\n\n---\n\n".join(
        [
            f'<Document href="{doc["url"]}"/>\n{doc["content"]}\n</Document>'
            for doc in search_docs
        ]
    )

    return {"context": [formatted_search_docs]} 

def search_wikipedia(state: ResearchState):
    
    """ Retrieve docs from wikipedia """

    # Search query
    query = state.messages[-1]
    structured_llm = llm.with_structured_output(SearchQuery)
    search_query = structured_llm.invoke([SystemMessage(content=SEARCH_PROMPT)] + [query])

    # Search
    search_docs = WikipediaLoader(query=search_query.search_query, 
                                  load_max_docs=2).load()

     # Format
    formatted_search_docs = "\n\n---\n\n".join(
        [
            f'<Document source="{doc.metadata["source"]}" page="{doc.metadata.get("page", "")}"/>\n{doc.page_content}\n</Document>'
            for doc in search_docs
        ]
    )

    return {"context": [formatted_search_docs]} 