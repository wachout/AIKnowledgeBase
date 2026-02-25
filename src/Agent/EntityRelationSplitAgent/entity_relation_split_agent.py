from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from pydantic import BaseModel, Field

from Agent.EntityRelationSplitAgent.prompts import (
    decompose_question_prompt,
    generate_query_prompt,
    critique_query_prompt,
    revise_query_prompt,
)

from dotenv import load_dotenv
from Config.llm_config import get_chat_tongyi

load_dotenv()

# 使用中央化的 LLM 配置获取 ChatTongyi 实例
# 确保在 .env 文件中有正确的 LLM_MODEL_ID、LLM_API_KEY、LLM_BASE_URL 配置
# 注意：如果需要使用特定模型如 qwen-plus，请在 .env 文件中设置 LLM_MODEL_ID=qwen-plus
# enable_thinking=False 用于禁用思考过程，有助于改善结构化输出生成
llm = get_chat_tongyi(temperature=0.7, enable_thinking=False)

# Pydantic schema for structured output
class DecomposedQuerySchema(BaseModel):
    """Pydantic schema for the decomposed query components."""
    entities: List[str] = Field(description="Specific nouns or proper nouns (e.g., people, places)")
    keywords: List[str] = Field(description="Important terms describing the topic or intent")
    search_conditions: List[str] = Field(description="Constraints like timeframes or locations")

class AgentState(TypedDict):
    """Represents the state of our agent."""
    original_query: str
    decomposed_query: Optional[DecomposedQuerySchema]
    search_query: Optional[str]
    critique: Optional[str]
    revision_count: int
    error: Optional[str]

# Set up the Pydantic output parser
pydantic_parser = PydanticOutputParser(pydantic_object=DecomposedQuerySchema)

# Inject format instructions into the prompt
format_instructions = pydantic_parser.get_format_instructions()
decompose_prompt_with_format = decompose_question_prompt.partial(format_instructions=format_instructions)

# Define the chains for each node
decompose_chain = decompose_prompt_with_format | llm | pydantic_parser
generate_chain = generate_query_prompt | llm | StrOutputParser()
critique_chain = critique_query_prompt | llm | StrOutputParser()
revise_chain = revise_query_prompt | llm | StrOutputParser()

# Define the nodes
def decompose_question_node(state: AgentState):
    print("---DECOMPOSING QUESTION---")
    try:
        result = decompose_chain.invoke({"query": state["original_query"]})
        # Convert Pydantic model to dict for state compatibility
        return {"decomposed_query": result.model_dump(), "revision_count": 0}
    except Exception as e:
        return {"error": f"Failed to decompose question: {e}"}

def generate_query_node(state: AgentState):
    print("---GENERATING SEARCH QUERY---")
    try:
        decomposed = state["decomposed_query"]
        if not decomposed:
            return {"error": "Decomposed query is missing."}
        
        search_query = generate_chain.invoke({
            "entities": ", ".join(decomposed["entities"]),
            "phrases": ", ".join(decomposed["phrases"]),
            "keywords": ", ".join(decomposed["keywords"]),
            "search_conditions": ", ".join(decomposed["search_conditions"]),
        })
        return {"search_query": search_query.strip()}
    except Exception as e:
        return {"error": f"Failed to generate query: {e}"}

def critique_query_node(state: AgentState):
    print("---CRITIQUING SEARCH QUERY---")
    try:
        critique = critique_chain.invoke({
            "original_query": state["original_query"],
            "search_query": state["search_query"],
        })
        return {"critique": critique.strip()}
    except Exception as e:
        return {"error": f"Failed to critique query: {e}"}

def revise_query_node(state: AgentState):
    print("---REVISING SEARCH QUERY---")
    try:
        revision_count = state.get("revision_count", 0) + 1
        if revision_count > 3: # Safety break to prevent infinite loops
            return {"error": "Exceeded maximum revision attempts."}

        revised_query = revise_chain.invoke({
            "original_query": state["original_query"],
            "search_query": state["search_query"],
            "critique": state["critique"],
        })
        return {"search_query": revised_query.strip(), "revision_count": revision_count}
    except Exception as e:
        return {"error": f"Failed to revise query: {e}"}


def run_graph():
    # Define the graph
    workflow = StateGraph(AgentState)
    workflow.add_node("decompose_question", decompose_question_node)
    workflow.add_node("generate_query", generate_query_node)
    workflow.add_node("critique_query", critique_query_node)
    workflow.add_node("revise_query", revise_query_node)
    
    # Define the edges
    workflow.set_entry_point("decompose_question")
    workflow.add_edge("decompose_question", "generate_query")
    workflow.add_edge("generate_query", "critique_query")
    
    def should_revise(state: AgentState) -> str:
        print("---CHECKING IF REVISION IS NEEDED---")
        if state.get("error"):
            return END
        
        critique = state.get("critique", "").strip()
        # Check for the specific success phrase at the end of the critique
        if critique.endswith("The query is perfect."):
            print("---DECISION: QUERY IS GOOD, END---")
            # Clean up the critique message for final output
            state["critique"] = critique.replace("The query is perfect.", "").strip()
            return END
        else:
            print("---DECISION: REVISION NEEDED---")
            return "revise_query"
    
    workflow.add_conditional_edges(
        "critique_query",
        should_revise,
        {
            "revise_query": "revise_query",
            END: END,
        },
    )
    
    workflow.add_edge("revise_query", "critique_query")
    
    # Compile the graph
    app = workflow.compile()
    return app
