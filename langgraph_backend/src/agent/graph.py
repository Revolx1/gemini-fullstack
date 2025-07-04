import os
import logging
import asyncio
from pprint import pformat
from functools import wraps
import random
import time

from agent.tools_and_schemas import SearchQueryList, Reflection
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langgraph.types import Send
from langgraph.graph import StateGraph
from langgraph.graph import START, END
from langchain_core.runnables import RunnableConfig
from google.genai import Client
from langchain_google_vertexai import ChatVertexAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import ConfigurableField

from agent.state import (
    OverallState,
    QueryGenerationState,
    ReflectionState,
    WebSearchState,
)
from agent.configuration import Configuration
from agent.prompts import (
    get_current_date,
    query_writer_instructions,
    web_searcher_instructions,
    reflection_instructions,
    answer_instructions,
)
from agent.utils import (
    get_citations,
    get_research_topic,
    insert_citation_markers,
    resolve_urls,
)

# Retry decorator with exponential backoff
def retry_with_exponential_backoff(max_retries=5, multiplier=1, max_wait=120):
    """Decorator for retrying async functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        multiplier: Base multiplier for wait time
        max_wait: Maximum wait time in seconds
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if "429" in str(e) or "ResourceExhausted" in str(e):
                        if attempt == max_retries - 1:
                            raise
                        
                        # Calculate wait time with exponential backoff and jitter
                        wait_time = min(
                            multiplier * (2 ** attempt) + random.uniform(0, 1),
                            max_wait
                        )
                        
                        # Log the retry attempt
                        logger = logging.getLogger(__name__)
                        logger.warning(
                            f"Rate limit hit (429). Retrying {func.__name__} in {wait_time:.2f} seconds. "
                            f"Attempt {attempt + 1}/{max_retries}"
                        )
                        
                        await asyncio.sleep(wait_time)
                    else:
                        raise
            return None
        return wrapper
    return decorator

# --- Dynamic Server-Side Debug Logging ---
def get_server_logger(config: RunnableConfig):
    # Default path in case something goes wrong, though it shouldn't be used
    default_log_path = os.path.join(os.path.dirname(__file__), '..', 'default_server_debug.log')
    log_full_path = config.get("configurable", {}).get("server_log_path", default_log_path)
    
    # Use the log path as a unique logger name to avoid handler conflicts
    logger_name = log_full_path
    logger = logging.getLogger(logger_name)
    
    # Avoid adding handlers if they already exist for this logger instance
    if not logger.handlers:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(log_full_path), exist_ok=True)
        file_handler = logging.FileHandler(log_full_path)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - SERVER - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False # Prevent logs from propagating to the root logger

    return logger
# --- End Logging Setup ---


load_dotenv()

# Used for Google Search API
genai_client = Client()

# Semaphore will be created dynamically based on configuration
_semaphore_cache = {}

def get_semaphore(num_parallel_tasks: int) -> asyncio.Semaphore:
    """Get or create a semaphore with the specified number of parallel tasks."""
    if num_parallel_tasks not in _semaphore_cache:
        _semaphore_cache[num_parallel_tasks] = asyncio.Semaphore(num_parallel_tasks)
    return _semaphore_cache[num_parallel_tasks]

# Nodes
@retry_with_exponential_backoff()
async def generate_query(state: OverallState, config: RunnableConfig) -> QueryGenerationState:
    """Generate search queries based on the question."""
    configurable = Configuration.from_runnable_config(config)
    
    # Get the user's question from the state messages
    question = get_research_topic(state["messages"])
    
    # Get number of queries from state or use default
    num_queries = state.get("initial_search_query_count", 5)

    # Create LLM instance in a thread to avoid blocking I/O
    llm = await asyncio.to_thread(
        ChatVertexAI,
        model_name=configurable.query_generator_model,
        temperature=0.6,
    )
    
    # Create structured LLM
    structured_llm = llm.with_structured_output(SearchQueryList)
    
    # Format the prompt with all required parameters
    formatted_prompt = query_writer_instructions.format(
        research_topic=question,
        number_queries=num_queries,
        current_date=get_current_date()
    )
    
    # Generate the search queries
    result = await structured_llm.ainvoke(formatted_prompt)
    return {"search_query": result.query}


def continue_to_web_research(state: QueryGenerationState):
    """LangGraph node that sends the search queries to the web research node.

    This is used to spawn n number of web research nodes, one for each search query.
    """
    return [
        Send("web_research", {"search_query": search_query, "id": int(idx)})
        for idx, search_query in enumerate(state["search_query"])
    ]


@retry_with_exponential_backoff()
async def web_research(state: WebSearchState, config: RunnableConfig) -> OverallState:
    """Perform web research based on the generated queries."""
    configurable = Configuration.from_runnable_config(config)
    num_parallel_tasks = configurable.num_parallel_tasks
    
    async with get_semaphore(num_parallel_tasks):  # Limit parallel tasks
        search_query = state["search_query"]
        
        # Create LLM instance in a thread to avoid blocking I/O
        llm = await asyncio.to_thread(
            ChatVertexAI,
            model_name=configurable.query_generator_model,
            temperature=0.6
        )
        
        # 1. Format prompt
        formatted_prompt = web_searcher_instructions.format(
            current_date=get_current_date(), research_topic=search_query
        )
        
        # 2. Bind tools to LLM
        google_search_tool = {"google_search": {}}
        llm_with_tool = llm.bind_tools([google_search_tool])

        # 3. Invoke model to get text and grounding metadata
        response_message = await llm_with_tool.ainvoke(formatted_prompt)
        
        # 4. Process citations using the two-step principle
        metadata = response_message.response_metadata.get("grounding_metadata", {})
        grounding_chunks = metadata.get("grounding_chunks", [])
        
        # Create temporary markers for citation
        resolved_urls = resolve_urls(grounding_chunks, state["id"])
        citations = get_citations(response_message, resolved_urls)
        
        # Insert temporary markers into the text
        modified_text = insert_citation_markers(response_message.content, citations)
        
        # Prepare sources for the final replacement step
        sources_gathered = [item for citation in citations for item in citation["segments"]]

        return {
            "sources_gathered": sources_gathered,
            "search_query": [search_query],
            "web_research_result": [modified_text],
        }


@retry_with_exponential_backoff()
async def reflection(state: OverallState, config: RunnableConfig) -> ReflectionState:
    """Reflect on the gathered information and decide next steps."""
    configurable = Configuration.from_runnable_config(config)
    state["research_loop_count"] = state.get("research_loop_count", 0) + 1
    reasoning_model = state.get("reasoning_model", configurable.reflection_model)
    
    # Get the user's question from the state messages
    question = get_research_topic(state["messages"])

    # Create LLM instance in a thread to avoid blocking I/O
    llm = await asyncio.to_thread(
        ChatVertexAI,
        model_name=reasoning_model,
        temperature=0.6,
        max_retries=2,
    )
    
    # Format the prompt
    formatted_prompt = reflection_instructions.format(
        research_topic=question,
        summaries="\n\n---\n\n".join(state["web_research_result"]),
    )
    
    # Create structured LLM
    structured_llm = llm.with_structured_output(Reflection)
    result = await structured_llm.ainvoke(formatted_prompt)

    return {
        "is_sufficient": result.is_sufficient,
        "knowledge_gap": result.knowledge_gap,
        "follow_up_queries": result.follow_up_queries,
        "research_loop_count": state["research_loop_count"],
        "number_of_ran_queries": len(state["search_query"]),
    }


def evaluate_research(
    state: ReflectionState,
    config: RunnableConfig,
) -> OverallState:
    """LangGraph routing function that determines the next step in the research flow.
    """
    configurable = Configuration.from_runnable_config(config)
    max_research_loops = (
        state.get("max_research_loops")
        if state.get("max_research_loops") is not None
        else configurable.max_research_loops
    )
    # Use 'research_loop_count' as defined in the state
    if state["is_sufficient"] or state.get("research_loop_count", 0) >= max_research_loops:
        return "finalize_answer"
    else:
        return [
            Send(
                "web_research",
                {
                    "search_query": follow_up_query,
                    "id": state["number_of_ran_queries"] + int(idx),
                },
            )
            for idx, follow_up_query in enumerate(state["follow_up_queries"])
        ]


@retry_with_exponential_backoff()
async def finalize_answer(state: OverallState, config: RunnableConfig):
    """Generate the final answer based on all gathered information."""
    configurable = Configuration.from_runnable_config(config)
    reasoning_model = state.get("reasoning_model") or configurable.answer_model
    
    # Get the user's question from the state messages
    question = get_research_topic(state["messages"])

    # Create LLM instance in a thread to avoid blocking I/O
    llm = await asyncio.to_thread(
        ChatVertexAI,
        model_name=reasoning_model,
        temperature=0,
        max_retries=2,
    )
    
    # Format the prompt with all required parameters
    formatted_prompt = answer_instructions.format(
        research_topic=question,
        summaries="\n\n---\n\n".join(state["web_research_result"]),
        current_date=get_current_date()
    )

    result = await llm.ainvoke(formatted_prompt)

    # The model provides the main text. Now, we append the sources list.
    final_text = result.content
    
    # De-duplicate the sources and format them for the final output
    unique_sources = []
    if sources := state.get("sources_gathered"):
        seen_urls = set()
        for source in sources:
            # Check for URL and that we haven't seen it before
            if source.get("url") and source["url"] not in seen_urls:
                unique_sources.append(source)
                seen_urls.add(source["url"])

    # Create the final list of sources in the format "number - url"
    if unique_sources:
        # Re-number sources to ensure a clean 1, 2, 3... list
        sources_list = "\n\n**Источники:**\n" + "\n".join(
            f'{i+1} - {source["url"]}' for i, source in enumerate(unique_sources)
        )
        final_text += sources_list

    return {
        "messages": [AIMessage(content=final_text)],
        "sources_gathered": unique_sources,
    }


# Create our Agent Graph
builder = StateGraph(OverallState, config_schema=Configuration)

# Define the nodes we will cycle between
builder.add_node("generate_query", generate_query)
builder.add_node("web_research", web_research)
builder.add_node("reflection", reflection)
builder.add_node("finalize_answer", finalize_answer)

# Set the entrypoint as `generate_query`
builder.add_edge(START, "generate_query")
# Add conditional edge to continue with search queries in a parallel branch
builder.add_conditional_edges(
    "generate_query", continue_to_web_research, ["web_research"]
)
# Reflect on the web research
builder.add_edge("web_research", "reflection")
# Evaluate the research
builder.add_conditional_edges(
    "reflection", evaluate_research, ["web_research", "finalize_answer"]
)
# Finalize the answer
builder.add_edge("finalize_answer", END)

graph = builder.compile(name="pro-search-agent")
