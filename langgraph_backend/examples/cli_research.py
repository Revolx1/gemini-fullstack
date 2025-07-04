import argparse
import os
import asyncio
import logging
from pprint import pformat
from langgraph_sdk.client import get_client
from datetime import datetime

def main():
    """Main function to run the research agent via the LangGraph SDK."""
    parser = argparse.ArgumentParser(description="AI Research Agent Client")
    parser.add_argument(
        "query_or_file",
        type=str,
        help="The research query or a path to a text file containing the query.",
    )
    parser.add_argument(
        "--initial-queries",
        type=int,
        default=3,
        help="Number of initial search queries",
    )
    parser.add_argument(
        "--max-loops",
        type=int,
        default=2,
        help="Maximum number of research loops",
    )
    args = parser.parse_args()

    query = args.query_or_file
    if os.path.isfile(query):
        with open(query, "r", encoding="utf-8") as f:
            query = f.read()

    # --- Setup Logging Paths ---
    start_time = datetime.now()
    date_folder = start_time.strftime("%d%m%Y")
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    output_path = os.path.join(base_path, "outputs", date_folder)
    os.makedirs(output_path, exist_ok=True)
    
    time_filename = start_time.strftime("%H%M%d%m")
    research_base_name = f"research_{time_filename}"
    
    # Define paths for final and temp log files
    final_log_path = os.path.join(output_path, f"{research_base_name}.log")
    client_tmp_log_path = os.path.join(output_path, f"{research_base_name}.client.tmp")
    server_tmp_log_path = os.path.join(output_path, f"{research_base_name}.server.tmp")

    # Setup client-side logger to write to its temp file
    client_logger = logging.getLogger('ClientEventLogger')
    client_logger.setLevel(logging.INFO)
    # Remove any existing handlers to avoid duplicate logging
    if client_logger.hasHandlers():
        client_logger.handlers.clear()
    client_file_handler = logging.FileHandler(client_tmp_log_path)
    client_file_handler.setFormatter(logging.Formatter('%(asctime)s - CLIENT - %(message)s'))
    client_logger.addHandler(client_file_handler)
    client_logger.info("Client logger initialized.")
    # --- End Logging Setup ---

    async def run_agent():
        # Pass the full path for the server's debug log in the config
        config = {"configurable": {"server_log_path": server_tmp_log_path}}
        client = get_client(url="http://127.0.0.1:2024", timeout=None)

        # Create a new thread
        thread = await client.threads.create()
        print(f"--- Running agent on thread {thread['thread_id']} ---")

        # Define the initial state to send to the server
        input_data = {
            "messages": [("user", query)],
            "initial_search_query_count": args.initial_queries,
            "max_research_loops": args.max_loops,
        }

        # The graph ID 'pro-search-agent' is taken from the `name` in graph.py
        print("\n--- Agent is running, waiting for final result... ---")
        
        # Initialize variable to store the final answer from the stream
        final_answer_from_stream = None
        
        # Stream events to execute the run and log them, but we won't assemble the answer here.
        async for event in client.runs.stream(
            thread_id=thread["thread_id"],
            assistant_id="pro-search-agent",
            input=input_data,
            stream_mode="events",
            config=config,
        ):
            client_logger.info(pformat(event))
            if event.event == "events" and (data := event.data) and data.get("event") == "on_chain_end" and data.get("name") == "pro-search-agent":
                 print("\n--- Main graph finished. Fetching final state. ---")
                 # Capture the final answer from the output of the main graph
                 if output := data.get("output"):
                     if messages := output.get("messages"):
                         # Get the last message which should contain the final answer with sources
                         if messages and len(messages) > 0:
                             last_msg = messages[-1]
                             if isinstance(last_msg, dict):
                                 final_answer_from_stream = last_msg.get("content", "")
                             else:
                                 final_answer_from_stream = getattr(last_msg, "content", "")

        # After the run is complete, get the final state of the thread
        final_state = await client.threads.get_state(thread_id=thread["thread_id"])
        client_logger.info("Final state received from server.")
        client_logger.info(pformat(final_state))
        
        # Use the answer from the stream if available, otherwise fall back to state
        final_answer_content = ""
        sources_list = ""
        
        if final_answer_from_stream:
            final_answer_content = final_answer_from_stream
            client_logger.info("Using final answer from stream output")
        else:
            # Fallback: Extract the final answer from the last message in the state
            # The final state is a dict with a 'values' key containing the OverallState
            if final_state and (values := final_state.get('values')) and values.get('messages'):
                last_message = values['messages'][-1]
                if isinstance(last_message, dict):
                    final_answer_content = last_message.get('content', '')
                else: # Handle AIMessage object case
                    final_answer_content = getattr(last_message, 'content', '')
            client_logger.info("Using final answer from state (fallback)")
        
        # Extract sources from the state if not already in the final answer
        if "**Источники:**" not in final_answer_content and final_state and (values := final_state.get('values')):
            sources_gathered = values.get('sources_gathered', [])
            if sources_gathered:
                # Remove duplicates by URL
                unique_sources = {}
                for source in sources_gathered:
                    url = source.get('value', '')
                    if url and url not in unique_sources:
                        unique_sources[url] = source
                
                # Create sources list
                if unique_sources:
                    sources_list = "\n\n**Источники:**\n"
                    for i, (url, source) in enumerate(unique_sources.items(), 1):
                        title = source.get('title', 'Без названия')
                        label = source.get('label', '')
                        # Format: number. [label] title - url
                        if label:
                            sources_list += f"{i}. [{label}] {title} - {url}\n"
                        else:
                            sources_list += f"{i}. {title} - {url}\n"
                    client_logger.info(f"Added {len(unique_sources)} unique sources from state")

        # Extract research completion info from state
        actual_loops = 0
        completion_reason = "Неизвестно"
        if final_state and (values := final_state.get('values')):
            actual_loops = values.get('research_loop_count', 0)
            is_sufficient = values.get('is_sufficient', False)
            
            if is_sufficient:
                completion_reason = "Достаточно информации"
            elif actual_loops >= args.max_loops:
                completion_reason = f"Достигнут лимит циклов ({args.max_loops})"
            else:
                completion_reason = "Неизвестная причина"

        # Process and save the final answer
        print("\n\n--- Final Answer ---")
        print(final_answer_content)
        if sources_list:
            print(sources_list)

        # Create filename for the research result
        file_name = f"{research_base_name}.txt"
        full_path = os.path.join(output_path, file_name)

        # Prepare file content with enhanced header
        file_content = (
            f"Thread ID: {thread['thread_id']}\n"
            f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Initial Queries: {args.initial_queries}\n"
            f"Max Loops: {args.max_loops}\n"
            f"Actual Loops Completed: {actual_loops}\n"
            f"Completion Reason: {completion_reason}\n\n"
            f"--- Research Result ---\n"
            f"{final_answer_content}"
        )
        
        # Add sources if they were extracted separately
        if sources_list:
            file_content += sources_list

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(file_content)

        print(f"\n--- Research saved to {full_path} ---")

        # --- Merge Logs ---
        try:
            with open(final_log_path, "w", encoding="utf-8") as outfile:
                # 1. Write client events
                if os.path.exists(client_tmp_log_path):
                    with open(client_tmp_log_path, "r", encoding="utf-8") as infile:
                        outfile.write(infile.read())
                
                # 2. Append server debug logs
                if os.path.exists(server_tmp_log_path):
                    outfile.write("\n\n" + "="*20 + " SERVER DEBUG LOG " + "="*20 + "\n\n")
                    with open(server_tmp_log_path, "r", encoding="utf-8") as infile:
                        outfile.write(infile.read())
            
            print(f"--- Unified log saved to {final_log_path} ---")

        finally:
            # 3. Clean up temp files
            if os.path.exists(client_tmp_log_path):
                os.remove(client_tmp_log_path)
            if os.path.exists(server_tmp_log_path):
                os.remove(server_tmp_log_path)
        # --- End Merge ---

    asyncio.run(run_agent())


if __name__ == "__main__":
    main()
