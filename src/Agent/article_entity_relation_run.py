import asyncio

import json
from langgraph.graph import StateGraph, END

from Agent.ArticleEntityRelationAgent.entity_word_relationship import (
    KnowledgeGraphState,
    extractor_node,
    parser_node,
)

workflow = StateGraph(KnowledgeGraphState)

# Add the nodes
workflow.add_node("extractor", extractor_node)
workflow.add_node("parser", parser_node)

# Set the entrypoint
workflow.set_entry_point("extractor")

# Add edges
workflow.add_edge("extractor", "parser")
workflow.add_edge("parser", END)

# Compile the graph
app = workflow.compile()

async def run(sample_text):
    print("\n--- Running Knowledge Extraction ---")
    
    # # Sample text for extraction
    # sample_text = (
    #     "Apple Inc., based in Cupertino, California, is a multinational technology company. "
    #     "It was founded by Steve Jobs, Steve Wozniak, and Ronald Wayne in 1976. "
    #     "Tim Cook is the current CEO. The company is famous for designing the iPhone and the Mac computer."
    # )
    
    # Define the input for the graph
    inputs = {"text_input": sample_text}
    
    # Invoke the graph and get the final state
    final_state = app.invoke(inputs)
    
    # Extract and print the structured data
    structured_output = final_state.get("structured_data", {})
    
    if structured_output:
        print("\n--- Extraction Complete ---")
        print("\nKeywords:")
        print(json.dumps(structured_output.get('keywords', []), indent=2))
        
        print("\nEntities:")
        print(json.dumps(structured_output.get('entities', []), indent=2))
        
        print("\nRelations:")
        print(json.dumps(structured_output.get('relations', []), indent=2))
        
        print("\nTriplets:")
        print(json.dumps(structured_output.get('triplets', []), indent=2, ensure_ascii=False))
        print("\n---------------------------\n")
    else:
        print("--- No structured output was generated. ---")
        print("Final state:", final_state)

def run_workflow_sync(text: str):
    """
    Synchronous wrapper for the text analysis workflow.
    """
    # Use asyncio's event loop to run the async function synchronously
    # This is a blocking call that waits for the async task to complete
    # and returns the result.
    # Note: This is not recommended for production code as it can block the event loop.
    # Instead, consider using an async framework like FastAPI or Flask with asyncio support.
    # However, for the sake of this example, we will use it to keep the interface synchronous.
    # asyncio.run(result)  # This is not suitable for nested event loops
    # Use asyncio.get_event_loop() to run the async function synchronously
    # This is a workaround to run the async function in a synchronous context.
    # It is generally not recommended to mix async and sync code like this.
    # However, it can be useful for quick prototyping or testing.
    # Note: This will block the event loop until the async task is complete.
    # This is a blocking call that waits for the async task to complete
    
    result = asyncio.create_task(run(text))
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If the event loop is already running, we need to run the async task in a different way
        result = loop.create_task(run(text))
    else:
        # If the event loop is not running, we can run the async task directly
        result = loop.run_until_complete(run(text))   
    print("Running workflow synchronously.")
    return result  # Wait for the async task to complete and return the result
    
    
