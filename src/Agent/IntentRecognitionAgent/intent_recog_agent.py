import os
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langchain_openai import ChatOpenAI
from langchain_community.chat_models.tongyi import ChatTongyi
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List, Any
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, AIMessage


def get_predefined_llm(model_type: str = "tongyi", streaming: bool = True) -> Any:
    """
    获取预定义的语言模型实例
    
    Args:
        model_type: 模型类型，支持 "deepseek" 或 "tongyi"
        streaming: 是否启用流式返回
    
    Returns:
        语言模型实例
    """
    if model_type == "tongyi":
        from Config.llm_config import get_chat_tongyi
        return get_chat_tongyi(temperature=0.3, streaming=streaming, enable_thinking=False)
        # return ChatTongyi(
        #     temperature=0.7,
        #     model=os.getenv("GRAPH_MODEL", "qwen3-32b"),
        #     api_key=os.getenv("QWEN_API_KEY"),
        #     base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        #     streaming=streaming
        # )
    else:  # 默认使用deepseek
        from Config.llm_config import get_chat_openai
        return get_chat_openai(temperature=0.7, streaming=streaming)


# Define the state for our graph
class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], lambda x, y: x + y]

# Define the nodes for our graph
def call_model(state: AgentState):
    """Calls the LLM to generate a response."""
    llm = get_predefined_llm(model_type="tongyi", streaming=True)
    response = llm.invoke(state['messages'])
    return {"messages": [response]}



