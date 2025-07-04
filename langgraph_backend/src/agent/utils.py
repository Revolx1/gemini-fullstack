from typing import Any, Dict, List
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage


def get_research_topic(messages: List[AnyMessage]) -> str:
    """
    Get the research topic from the messages.
    """
    # check if request has a history and combine the messages into a single string
    if len(messages) == 1:
        research_topic = messages[-1].content
    else:
        research_topic = ""
        for message in messages:
            if isinstance(message, HumanMessage):
                research_topic += f"User: {message.content}\n"
            elif isinstance(message, AIMessage):
                research_topic += f"Assistant: {message.content}\n"
    return research_topic


def resolve_urls(urls_to_resolve: List[Any], id: int) -> Dict[str, str]:
    """
    Create a map of the vertex ai search urls (very long) to a short url with a unique id for each url.
    Ensures each original URL gets a consistent shortened form while maintaining uniqueness.
    """
    prefix = f"https://vertexaisearch.cloud.google.com/id/"
    urls = [site.get("web", {}).get("uri") for site in urls_to_resolve]

    # Create a dictionary that maps each unique URL to its first occurrence index
    resolved_map = {}
    for idx, url in enumerate(urls):
        if url and url not in resolved_map:
            resolved_map[url] = f"{prefix}{id}-{idx}"

    return resolved_map


def insert_citation_markers(text, citations_list):
    """
    Inserts citation markers into a text string based on start and end indices.
    """
    sorted_citations = sorted(
        citations_list, key=lambda c: (c["end_index"], c["start_index"]), reverse=True
    )

    modified_text = text
    for citation_info in sorted_citations:
        end_idx = citation_info["end_index"]
        marker_to_insert = ""
        for segment in citation_info["segments"]:
            marker_to_insert += f" [{segment['label']}]"
        # Insert the citation marker at the original end_idx position
        modified_text = (
            modified_text[:end_idx] + marker_to_insert + modified_text[end_idx:]
        )

    return modified_text


def get_citations(response_message: AIMessage, resolved_urls_map: Dict[str, str]):
    """
    Extracts and formats citation information from a ChatVertexAI model's response.
    """
    citations = []
    metadata = response_message.response_metadata.get("grounding_metadata", {})
    grounding_chunks = metadata.get("grounding_chunks", [])
    grounding_supports = metadata.get("grounding_supports", [])
    
    if not grounding_supports:
        return citations

    for support in grounding_supports:
        citation = {}
        segment = support.get("segment", {})
        start_index = segment.get("start_index", 0)
        end_index = segment.get("end_index")

        if end_index is None:
            continue

        citation["start_index"] = start_index
        citation["end_index"] = end_index

        citation["segments"] = []
        chunk_indices = support.get("grounding_chunk_indices", [])
        for ind in chunk_indices:
            try:
                chunk = grounding_chunks[ind]
                uri = chunk.get("web", {}).get("uri")
                title = chunk.get("web", {}).get("title")
                resolved_url = resolved_urls_map.get(uri, None)
                if resolved_url:
                    citation["segments"].append(
                        {
                            "label": str(len(resolved_urls_map) - list(resolved_urls_map.keys()).index(uri)),
                            "short_url": resolved_url,
                            "value": uri,
                            "title": title
                        }
                    )
            except (IndexError, AttributeError, KeyError):
                pass
        citations.append(citation)
    return citations
