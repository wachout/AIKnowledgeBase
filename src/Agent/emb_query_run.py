from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from langchain_core.messages import AIMessage

from Agent.EmbQueryAgent.emb_query_agent import (
    enhance_query,
    validate_topic,
    retrieve_content,
    assess_relevance,
    generate_response,
    optimize_query,
    AgentState,
    )

def should_retrieve(state: AgentState):
    if state["topic_classification"]["classification"] == "out_of_domain":
        return "end"
    return "retrieve_content"

def is_relevant(state: AgentState):
    if state["document_relevance"]["is_relevant"]:
        return "generate_response"
    elif state["refinement_attempts"] >= 2:
        return "end"
    else:
        return "optimize_query"

def create_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("enhance_query", enhance_query)
    workflow.add_node("validate_topic", validate_topic)
    workflow.add_node("retrieve_content", retrieve_content)
    workflow.add_node("assess_relevance", assess_relevance)
    workflow.add_node("generate_response", generate_response)
    workflow.add_node("optimize_query", optimize_query)

    # Add edges
    workflow.set_entry_point("enhance_query")
    workflow.add_edge("enhance_query", "validate_topic")
    workflow.add_conditional_edges("validate_topic", should_retrieve, {
        "retrieve_content": "retrieve_content",
        "end": END
    })
    workflow.add_edge("retrieve_content", "assess_relevance")
    workflow.add_conditional_edges("assess_relevance", is_relevant, {
        "generate_response": "generate_response",
        "optimize_query": "optimize_query",
        "end": END
    })
    workflow.add_edge("generate_response", END)
    workflow.add_edge("optimize_query", "retrieve_content") # Loop back to retrieve

    app = workflow.compile()
    return app

def run_agent(query, chat_history, 
              database_code, index_params, limit) -> str:
    app = create_graph()
    initial_state = {
        "question": query,
        "chat_history": chat_history,
        "enhanced_query": "",
        "topic_classification": {},
        "retrieved_docs": [],
        "document_relevance": {},
        "refinement_attempts": 0,
        "final_response": "",
        "database_code": database_code,
        "index_params": index_params,
        "limit": limit
    }
    final_state = app.invoke(initial_state)
    
    # inputs = {
    #     "query": query,
    #     "chat_history": [HumanMessage(content=msg["content"]) if msg["role"] == "user" else AIMessage(content=msg["content"]) for msg in chat_history]
    # }
    # result = {
    #     "inputs": inputs,
    #     "outputs": {
    #         "response": final_state["final_response"]
    #     }
    # }
    return final_state
    #return final_state["final_response"]

