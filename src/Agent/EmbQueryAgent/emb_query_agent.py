import os

from dotenv import load_dotenv

from typing import List, Optional, TypedDict
from langchain_core.messages import BaseMessage

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.output_parsers.json import JsonOutputParser

from Config.embedding_config import get_embeddings
from Config.llm_config import get_chat_openai
from Control.control_milvus import CControl as MilvusController

load_dotenv()

# 使用中央化的 LLM 配置获取 ChatOpenAI 实例
llm = get_chat_openai(temperature=0.6)

# llm = ChatTongyi(
#         temperature=0.7,
#         model="qwen2-72b-instruct",
#         api_key=os.getenv("TONGYI_API_KEY"),
#         base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
#     )

class AgentState(TypedDict):
    """Represents the state of our agent."""
    chat_history: Optional[List[BaseMessage]]
    question: str
    enhanced_query: str
    topic_classification: dict
    retrieved_docs: List[dict]
    document_relevance: dict
    generation: str
    refinement_attempts: int
    database_code: str
    index_params: dict
    limit: int
    
    
def validate_topic(state: AgentState):
    """
    Validates if the query is in-domain.
    """
    prompt = ChatPromptTemplate.from_template(
        "You are a topic validator. Your knowledge base is about technical support for software. Classify the user's query as either 'in_domain' or 'out_of_domain'. Respond in JSON format with a 'classification' key. Query: {query}"
    )
    parser = JsonOutputParser()
    chain = prompt | llm | parser
    
    classification = chain.invoke({"query": state["enhanced_query"]})
    return {"topic_classification": classification}

def enhance_query(state: AgentState):
    """
    Enhances the user's query with chat history.
    """
    if not state["chat_history"]:
        enhanced_query = state["question"]
    else:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a query enhancer. Your task is to rephrase the user's question to be a standalone question, integrating the context from the chat history."),
            ("user", "Chat History:\n{chat_history}\n\nQuestion:\n{question}")
        ])
        chain = prompt | llm | StrOutputParser()
        
        chat_history_str = "\n".join([f"{msg.role}: {msg.content}" for msg in state["chat_history"]])
        
        enhanced_query = chain.invoke({
            "chat_history": chat_history_str,
            "question": state["question"]
        })
        
    return {"enhanced_query": enhanced_query}

def optimize_query(state: AgentState):
    """
    Optimizes the query for better search results.
    """
    prompt = ChatPromptTemplate.from_template(
        "You are a query optimizer. Your task is to refine the user's query to improve search results. Generate a new, more specific query based on the original. Original Query: {query}"
    )
    chain = prompt | llm | StrOutputParser()
    
    optimized_query = chain.invoke({"query": state["enhanced_query"]})
    
    return {"enhanced_query": optimized_query, "refinement_attempts": state["refinement_attempts"] + 1}

def assess_relevance(state: AgentState):
    """
    Assesses the relevance of retrieved documents.
    """
    prompt = ChatPromptTemplate.from_template(
        "You are a relevance assessor. Your task is to determine if the retrieved documents are relevant to the user's query. Respond in JSON format with 'is_relevant' (boolean) and 'reasoning' (string). Query: {query}\n\nDocuments:\n{documents}"
    )
    parser = JsonOutputParser()
    chain = prompt | llm | parser
    
    # doc_content = "\n".join([doc["content"] for doc in state["retrieved_docs"]])
    
    doc_content = "\n".join([f"Title: {doc['title']}\nContent: {doc['content']}" for doc in state["retrieved_docs"]])
    
    relevance = chain.invoke({"query": state["enhanced_query"], "documents": doc_content})
    
    return {"document_relevance": relevance}

def generate_response(state: AgentState):
    """
    Generates a response based on the context.
    """
    prompt = ChatPromptTemplate.from_template(
        "You are a helpful assistant. Generate a concise and informative answer to the user's query based on the provided context. If the context is not relevant, say so. Query: {query}\n\nContext:\n{context}"
    )
    chain = prompt | llm | StrOutputParser()
    
    # context_str = "\n".join([doc["content"] for doc in state["retrieved_docs"]])
    
    context_str = "\n".join([f"Title: {doc['title']}\nContent: {doc['content']}" for doc in state["retrieved_docs"]])
    generation = chain.invoke({"query": state["enhanced_query"], "context": context_str})
    
    return {"generation": generation}

def retrieve_content(state: AgentState):
    """
    Retrieves relevant documents from the knowledge base.
    """
    from Config.milvus_config import is_milvus_enabled
    
    if not is_milvus_enabled():
        return {"retrieved_docs": []}
    
    milvus_controller = MilvusController()
    database_code = state["database_code"]
    embedding_model = get_embeddings()
    query_text = state["enhanced_query"]
    limit = state["limit"]
    index_params = state["index_params"]
    
    hits = milvus_controller.search_content(database_code, query_text, embedding_model, index_params, limit)
    
    #results = []
    #for hit in hits:
    #    result = {
    #        "title": hit.entity.get("title"),
    #        "content": hit.entity.get("content"),
    #        "score": hit.distance
    #    }
    #    results.append(result)
    print(hits)
    return {"retrieved_docs": hits}





