import os
import json
from typing import List, TypedDict, Annotated
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END

# --- 1. Load Environment Variables and Initialize LLM ---

# Load API keys from .env file
load_dotenv()

# --- CHOOSE YOUR LLM PROVIDER ---
# Set to "deepseek" or "alibaba"
LLM_PROVIDER = "deepseek" 

# Initialize the chosen LLM
if LLM_PROVIDER == "deepseek":
    print("--- Using DeepSeek LLM ---")
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_URL_BASE")
    model_name = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-reasoner")  # 默认模型
    if not api_key or api_key == "sk-your-key-here":
        raise ValueError("DEEPSEEK_API_KEY not found or is a placeholder in .env file.")
    llm = ChatOpenAI(
        temperature=0.6,
        model=model_name,
        api_key=api_key,
        base_url=base_url,
    )
elif LLM_PROVIDER == "alibaba":
    print("--- Using Alibaba Qwen LLM ---")
    from langchain_community.chat_models import ChatTongyi
    api_key = os.getenv("QWEN_API_KEY")
    model_name = os.getenv("QWEN_MODEL_NAME", "qwen3-max")  # 默认模型
    if not api_key or api_key == "sk-your-key-here":
        raise ValueError("DASHSCOPE_API_KEY not found or is a placeholder in .env file.")
    llm = ChatTongyi(
        temperature=0.7,
        model=model_name, # Using a recommended model
        api_key=api_key,
        # The base_url is often handled by the library, but can be specified if needed
        base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    )
    llm = llm.bind(enable_thinking=False)
else:
    raise ValueError(f"Invalid LLM_PROVIDER: {LLM_PROVIDER}. Choose 'deepseek' or 'alibaba'.")

# --- 2. Define Graph State ---

class KnowledgeGraphState(TypedDict):
    """
    Represents the state of our graph.

    Attributes:
        text_input: The initial text paragraph to be processed.
        raw_extraction: The raw JSON string output from the extractor node.
        structured_data: The final structured data containing entities, relations, etc.
    """
    text_input: str
    raw_extraction: str
    structured_data: dict

# --- 3. Define Graph Nodes (Extractor and Parser) ---

# (Pydantic model is no longer used for the call, but good for validation/structure)
class ExtractedData(BaseModel):
    """
    Pydantic model for validating the extracted data structure.
    
    Attributes:
        keywords: List of important keywords from the text.
        entities: List of named entities found in the text.
        relations: List of relationship types found in the text.
        triplets: List of entity-relation-entity triplets.
    """
    keywords: List[str]
    entities: List[str]
    relations: List[str]
    triplets: List[List[str]]

def extractor_node(state: KnowledgeGraphState):
    """
    Extracts knowledge from the text by prompting the LLM to return a JSON string.
    
    This function sends the input text to the LLM with specific instructions to extract
    keywords, entities, relations, and triplets, returning them in a structured JSON format.
    
    Args:
        state: The current graph state containing the text input.
        
    Returns:
        A dictionary with the raw_extraction key containing the LLM's JSON string response.
    """
    print("--- 1. EXECUTING EXTRACTOR NODE ---")
    text_input = state["text_input"]

    # System prompt now explicitly asks for a JSON string and defines the structure.
    system_prompt = """You are an expert in information extraction. Your task is to analyze the text provided by the user and extract key information.
Please format your entire output as a single, valid JSON object with the following keys: "keywords", "entities", "relations", and "triplets".
- "keywords": A list of the most important keywords.
- "entities": A list of all named entities (people, organizations, locations, etc.).
- "relations": A list of the types of relationships found (e.g., "is based in", "was founded by", "is CEO of").
- "triplets": A list of lists, where each inner list is a [entity1, relation, entity2] triplet.

Do not include any explanatory text or markdown formatting before or after the JSON object."""

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "Please extract the information from the following text:\n\n---\n\n{text}"),
        ]
    )

    # Chain the prompt and the LLM
    chain = prompt | llm

    # Invoke the chain and get the raw string content
    extraction_result = chain.invoke({"text": text_input})
    
    return {"raw_extraction": extraction_result.content}


def parser_node(state: KnowledgeGraphState):
    """
    Parses the raw JSON string from the extractor into a dictionary.
    
    This function takes the raw JSON string output from the LLM, cleans it if needed
    (removing markdown code blocks), and parses it into a Python dictionary. It also
    validates the structure using the ExtractedData Pydantic model.
    
    Args:
        state: The current graph state containing the raw_extraction.
        
    Returns:
        A dictionary with the structured_data key containing the parsed and validated data.
    """
    print("--- 2. EXECUTING PARSER NODE ---")
    raw_extraction_str = state["raw_extraction"]

    try:
        # Clean up potential markdown code blocks
        if raw_extraction_str.startswith("```json"):
            raw_extraction_str = raw_extraction_str[7:-4].strip()
            
        # Parse the JSON string into a Python dictionary
        parsed_data = json.loads(raw_extraction_str)
        
        # (Optional) Validate with Pydantic
        validated_data = ExtractedData(**parsed_data)
        
        return {"structured_data": validated_data.model_dump()}

    except (json.JSONDecodeError, TypeError) as e:
        print(f"--- ERROR: Failed to parse JSON. Error: {e} ---")
        print(f"--- Raw LLM Output:\n{raw_extraction_str}")
        # Return an empty dict or handle the error as needed
        return {"structured_data": {}}


# # --- 5. Build the LangGraph Workflow ---
#
# print("--- Building Knowledge Extraction Graph ---")
# workflow = StateGraph(KnowledgeGraphState)
#
# # Add the nodes
# workflow.add_node("extractor", extractor_node)
# workflow.add_node("parser", parser_node)
#
# # Set the entrypoint
# workflow.set_entry_point("extractor")
#
# # Add edges
# workflow.add_edge("extractor", "parser")
# workflow.add_edge("parser", END)
#
# # Compile the graph
# app = workflow.compile()
#
# print("--- Graph Compiled Successfully ---")


# # --- 6. Main Execution Block ---
# if __name__ == "__main__":
#     print("\n--- Running Knowledge Extraction ---")
#
#     # Sample text for extraction
#     sample_text = (
#         "Apple Inc., based in Cupertino, California, is a multinational technology company. "
#         "It was founded by Steve Jobs, Steve Wozniak, and Ronald Wayne in 1976. "
#         "Tim Cook is the current CEO. The company is famous for designing the iPhone and the Mac computer."
#     )
#
#     # Define the input for the graph
#     inputs = {"text_input": sample_text}
#
#     # Invoke the graph and get the final state
#     final_state = app.invoke(inputs)
#
#     # Extract and print the structured data
#     structured_output = final_state.get("structured_data", {})
#
#     if structured_output:
#         print("\n--- Extraction Complete ---")
#         print("\nKeywords:")
#         print(json.dumps(structured_output.get('keywords', []), indent=2))
#
#         print("\nEntities:")
#         print(json.dumps(structured_output.get('entities', []), indent=2))
#
#         print("\nRelations:")
#         print(json.dumps(structured_output.get('relations', []), indent=2))
#
#         print("\nTriplets:")
#         print(json.dumps(structured_output.get('triplets', []), indent=2, ensure_ascii=False))
#         print("\n---------------------------\n")
#     else:
#         print("--- No structured output was generated. ---")
#         print("Final state:", final_state)