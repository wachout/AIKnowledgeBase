import asyncio

from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List, AsyncGenerator
import time
import uuid

from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, AIMessage

from Agent.IntentRecognitionAgent.intent_recog_agent import (
    call_model,
    AgentState
    )


def create_graph():
    # Define the graph
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.set_entry_point("agent")
    workflow.add_edge("agent", END)
    
    # Compile the graph
    app = workflow.compile()
    
    return app

async def get_streaming_response(message: str, history: List[dict]) -> AsyncGenerator[str, None]:
    """
    This function takes a user message and chat history, and yields the streaming response from the agent.
    """
    history_messages = [AIMessage(content=msg['content']) if msg['role'] == 'assistant' else HumanMessage(content=msg['content']) for msg in history]
    
    inputs = {
        "messages": [SystemMessage(content="You are a helpful assistant.")] + history_messages + [HumanMessage(content=message)]
    }
    app_runnable = create_graph()
    async for event in app_runnable.astream_events(inputs, version="v1"):
        kind = event["event"]
        if kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                yield content

# 修改 run_sync_stream 函数，使其真正流式返回而不是等待所有结果
def run_sync_stream(message: str, history: List[dict]):
    """
    This function takes a user message and chat history, and yields the streaming response from the agent.
    """
    
    # 生成统一的ID和基础信息
    _id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    model = "emb-graph-chat-model"
    
    # 创建一个异步函数来处理流式响应
    async def stream_response():
        # 先发送开始块
        start_chunk = {
            "id": _id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": "",
                        "type": "text"
                    },
                    "finish_reason": None
                }
            ]
        }
        yield start_chunk
        
        # 流式发送内容块
        async for chunk in get_streaming_response(message, history):
            # 构造符合 OpenAI 格式的流式响应块
            response_chunk = {
                "id": _id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "content": chunk,
                            "type": "text"
                        },
                        "finish_reason": None
                    }
                ]
            }
            yield response_chunk
        
        # 发送结束块
        finish_chunk = {
            "id": _id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }
            ]
        }
        yield finish_chunk
    
    # 为了真正的流式返回，我们需要直接运行异步生成器
    def sync_generator():
        try:
            # 尝试获取当前事件循环
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # 如果没有事件循环，则创建一个新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        async def async_gen_wrapper():
            async for item in stream_response():
                yield item
        
        # 逐个获取异步生成器的值并在同步环境中返回
        async_gen = async_gen_wrapper()
        
        # 逐个执行异步生成器并返回结果
        while True:
            try:
                # 在事件循环中运行直到获得下一个值
                next_item = loop.run_until_complete(async_gen.__anext__())
                yield next_item
            except StopAsyncIteration:
                break
    
    # 返回生成器对象而不是列表
    return sync_generator()