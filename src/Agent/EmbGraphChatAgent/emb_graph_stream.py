import asyncio
from typing import Optional, List, Dict, Any, Generator
from langchain_openai import ChatOpenAI
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# 获取预定义的语言模型
def get_predefined_llm(model_type: str = "deepseek", streaming: bool = True) -> Any:
    """
    获取预定义的语言模型实例
    
    Args:
        model_type: 模型类型，支持 "deepseek" 或 "tongyi"
        streaming: 是否启用流式返回
    
    Returns:
        语言模型实例
    """
    if model_type == "tongyi":
        return ChatTongyi(
            temperature=0.7,
            model=os.getenv("GRAPH_MODEL", "qwen3-32b"),
            api_key=os.getenv("QWEN_API_KEY"),
            base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            streaming=streaming
        )
    else:  # 默认使用deepseek
        return ChatOpenAI(
            temperature=0.7,
            model=os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-reasoner"),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_URL_BASE", "https://api.deepseek.com/v1"),
            streaming=streaming
        )

# 处理文本知识库数据
def process_text_knowledge(emb_data: List[Dict[str, str]]) -> str:
    """
    处理文本知识库数据，保留完整内容
    
    Args:
        emb_data: 文本知识库数据列表
    
    Returns:
        处理后的文本内容
    """
    if not emb_data:
        return ""
    
    # processed_texts = []
    # for item in emb_data:
    #     # 保留完整的文本内容，包括其中的表格、图片URL、说明和脚注
    #     if "text" in item:
    #         processed_texts.append(item["text"])
    
    processed_texts = []
    for item in emb_data:
        title = item.get("title", "未知标题")
        content = item.get("content", "")
        score = item.get("score", 0.0)
        
        # 保留完整文本，包括可能包含表格、图片及其说明的内容
        processed_item = f"标题: {title}\n相关度: {score}\n内容:\n{content}"
        processed_texts.append(processed_item)
    
    return "\n\n".join(processed_texts)

    # return "\n\n".join(processed_texts)

# 处理图数据库数据
def process_graph_knowledge(graph_data: Dict[str, Any]) -> str:
    """
    处理图数据库数据
    
    Args:
        graph_data: 图数据库数据
    
    Returns:
        处理后的图数据文本
    """
    if not graph_data:
        return ""
    
    # 提取并格式化图数据库中的信息
    graph_info = []
    
    # 处理chunks信息
    if "chunks" in graph_data:
        chunks_info = []
        for chunk in graph_data["chunks"]:
            if isinstance(chunk, dict) and "text" in chunk:
                chunks_info.append(chunk["text"])
        if chunks_info:
            graph_info.append(f"相关段落信息:\n{chr(10).join(chunks_info)}")
    
    # 处理titles信息
    if "titles" in graph_data:
        titles_info = []
        for title in graph_data["titles"]:
            if isinstance(title, dict) and "text" in title:
                titles_info.append(title["text"])
        if titles_info:
            graph_info.append(f"相关标题信息:\n{chr(10).join(titles_info)}")
    
    # 处理实体关系信息
    if "entities" in graph_data:
        entities_info = []
        for entity in graph_data["entities"]:
            if isinstance(entity, dict):
                entity_text = []
                for key, value in entity.items():
                    entity_text.append(f"{key}: {value}")
                entities_info.append(", ".join(entity_text))
        if entities_info:
            graph_info.append(f"实体信息:\n{chr(10).join(entities_info)}")
    
    # 处理其他可能的信息
    if "relationships" in graph_data:
        relationships_info = []
        for rel in graph_data["relationships"]:
            if isinstance(rel, dict):
                rel_text = []
                for key, value in rel.items():
                    rel_text.append(f"{key}: {value}")
                relationships_info.append(", ".join(rel_text))
        if relationships_info:
            graph_info.append(f"关系信息:\n{chr(10).join(relationships_info)}")
    
    return "\n\n".join(graph_info)

# 定义状态图类型
State = Dict[str, Any]

# 定义检索知识节点
async def retrieve_knowledge(state: State) -> State:
    """
    检索并处理知识
    
    Args:
        state: 当前状态
    
    Returns:
        更新后的状态
    """
    # 获取查询和知识库数据
    query = state.get("query", "")
    graph_data = state.get("graph_data", {})
    emb_data = state.get("emb_data", [])
    
    # 处理文本知识库数据
    text_knowledge = process_text_knowledge(emb_data)
    
    # 处理图数据库数据
    # graph_knowledge = process_graph_knowledge(graph_data)
    graph_knowledge = ""
    for graph_lt in graph_data:
        for graph in graph_lt:
            _knowledge = process_graph_knowledge(graph)
            graph_knowledge = _knowledge + "\n"
    
    # 合并知识
    combined_knowledge = f"文本知识:\n{text_knowledge}\n\n图数据库知识:\n{graph_knowledge}"
    
    # 更新状态
    return {
        **state,
        "text_knowledge": text_knowledge,
        "graph_knowledge": graph_knowledge,
        "combined_knowledge": combined_knowledge
    }

# 定义生成回答节点 - 支持流式生成
async def generate_answer(state: State) -> State:
    """
    生成回答，支持流式返回
    
    Args:
        state: 当前状态
    
    Returns:
        更新后的状态
    """
    # 获取查询、合并知识和语言模型
    query = state.get("query", "")
    combined_knowledge = state.get("combined_knowledge", "")
    llm = state.get("llm")
    stream_mode = state.get("stream_mode", False)
    
    # 定义系统提示
    system_prompt = """
    你是一个智能问答助手，擅长结合提供的知识库信息来回答用户问题。
    
    特别注意：
    1. 请仔细阅读并充分利用提供的文本知识和图数据库知识
    2. 文本知识中可能包含表格、图片URL、说明(caption)和脚注(footnote)，请在回答中适当引用和解释这些内容
    3. 如果某个图片或表格对回答问题很重要，请提及它并解释其相关性
    4. 请确保你的回答基于提供的知识库信息，不要编造事实
    5. 如果知识库中没有足够的信息来回答问题，请明确说明
    """
    
    # 创建提示模板
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "知识库信息：\n{knowledge}\n\n用户问题：\n{query}")
    ])
    
    # 创建处理链
    chain = prompt | llm
    
    # 初始化完整回答
    full_answer = ""
    
    # 处理流式响应
    # 注意：这里是关键部分 - 大模型在生成内容时就会实时返回数据
    async for chunk in chain.astream({
        "knowledge": combined_knowledge,
        "query": query
    }):
        # 获取当前块的内容
        chunk_content = chunk.content
        full_answer += chunk_content
        
        # 如果是流式模式，将当前块添加到状态中的流式响应列表
        if stream_mode and "stream_responses" in state:
            state["stream_responses"].append(chunk_content)
    
    # 更新状态
    return {**state, "answer": full_answer}

# 创建智能体工作流
def create_agent_workflow(llm_type: str = "deepseek") -> StateGraph:
    """
    创建智能体工作流
    
    Args:
        llm_type: 语言模型类型
    
    Returns:
        状态图实例
    """
    # 创建状态图
    graph = StateGraph(State)
    
    # 添加节点
    graph.add_node("retrieve_knowledge", retrieve_knowledge)
    graph.add_node("generate_answer", generate_answer)
    
    # 添加边
    graph.add_edge("retrieve_knowledge", "generate_answer")
    graph.add_edge("generate_answer", END)
    
    # 设置入口点
    graph.set_entry_point("retrieve_knowledge")
    
    # 编译图
    return graph.compile()

# 处理查询 - 支持流式返回
async def process_query(
    query: str,
    graph_data: Dict[str, Any] = None,
    emb_data: List[Dict[str, str]] = None,
    llm_type: str = "deepseek",
    stream: bool = False
) -> Dict[str, Any]:
    """
    处理查询并生成回答
    
    Args:
        query: 用户查询
        graph_data: 图数据库数据
        emb_data: 文本知识库数据
        llm_type: 语言模型类型
        stream: 是否启用流式返回模式
    
    Returns:
        包含回答的字典
    """
    # 初始化参数
    if graph_data is None:
        graph_data = {}
    if emb_data is None:
        emb_data = []
    
    # 获取语言模型，启用流式支持
    llm = get_predefined_llm(llm_type, streaming=True)
    
    # 创建工作流
    workflow = create_agent_workflow(llm_type)
    
    # 准备初始状态
    initial_state = {
        "query": query,
        "graph_data": graph_data,
        "emb_data": emb_data,
        "llm": llm,
        "stream_mode": stream,
        "stream_responses": []  # 用于存储流式响应的列表
    }
    
    # 执行工作流
    result = await workflow.invoke(initial_state)
    
    # 返回结果
    if stream:
        return {
            "answer": result.get("answer", ""),
            "stream_responses": result.get("stream_responses", []),
            "text_knowledge": result.get("text_knowledge", ""),
            "graph_knowledge": result.get("graph_knowledge", "")
        }
    else:
        return {
            "answer": result.get("answer", ""),
            "text_knowledge": result.get("text_knowledge", ""),
            "graph_knowledge": result.get("graph_knowledge", "")
        }

# 流式生成回答 - 直接返回生成器
def stream_answer_sync(
    query: str,
    graph_data: Dict[str, Any] = None,
    emb_data: List[Dict[str, str]] = None,
    llm_type: str = "deepseek"
) -> Generator[str, None, None]:
    """
    同步流式生成回答，直接返回生成器
    
    Args:
        query: 用户查询
        graph_data: 图数据库数据
        emb_data: 文本知识库数据
        llm_type: 语言模型类型
    
    Yields:
        生成的文本片段
    """
    # 初始化参数
    if graph_data is None:
        graph_data = {}
    if emb_data is None:
        emb_data = []
    
    # 处理知识
    text_knowledge = process_text_knowledge(emb_data)
    graph_knowledge = process_graph_knowledge(graph_data)
    combined_knowledge = f"文本知识:\n{text_knowledge}\n\n图数据库知识:\n{graph_knowledge}"
    
    # 获取语言模型
    llm = get_predefined_llm(llm_type, streaming=True)
    
    # 定义系统提示
    system_prompt = """
    你是一个智能问答助手，擅长结合提供的知识库信息来回答用户问题。
    
    特别注意：
    1. 请仔细阅读并充分利用提供的文本知识和图数据库知识
    2. 文本知识中可能包含表格、图片URL、说明(caption)和脚注(footnote)，请在回答中适当引用和解释这些内容
    3. 如果某个图片或表格对回答问题很重要，请提及它并解释其相关性
    4. 请确保你的回答基于提供的知识库信息，不要编造事实
    5. 如果知识库中没有足够的信息来回答问题，请明确说明
    """
    
    # 创建提示模板
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "知识库信息：\n{knowledge}\n\n用户问题：\n{query}")
    ])
    
    # 创建处理链
    chain = prompt | llm
    
    # 使用同步方式流式生成并yield每个片段
    import threading
    import queue
    import json
    
    # 创建队列用于在线程间传递数据
    q = queue.Queue()

    # 定义在独立线程中运行的异步函数
    def run_async_in_thread():
        async def async_part():
            try:
                async for chunk in chain.astream({
                    "knowledge": combined_knowledge,
                    "query": query
                }):
                    # 修改为返回指定格式的数据
                    result = {
                        'content': chunk.content,
                        'additional_kwargs': chunk.additional_kwargs,
                        'id': chunk.id
                    }
                    # q.put(json.dumps(result, ensure_ascii=False) + "\n\n")
                    # q.put(str(json.dumps(result, ensure_ascii=False)))
                    # q.put(f"data: {json.dumps(result, ensure_ascii=False)}\n\n")
                    q.put(result)
                q.put(None)  # 发送结束信号
            except Exception as e:
                q.put(e)
        
        # 在新事件循环中运行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(async_part())
        finally:
            loop.close()
    
    # 启动线程
    t = threading.Thread(target=run_async_in_thread)
    t.daemon = True  # 设置为守护线程
    t.start()
    
    # 从队列中获取结果并yield
    while True:
        try:
            # 使用较小的超时时间以避免阻塞
            item = q.get(timeout=1)
            if item is None:  # 结束信号
                break
            if isinstance(item, Exception):
                yield f"data: Error: {str(item)}\n\n"
                break
            yield item
        except queue.Empty:
            # 检查线程是否还活着
            if not t.is_alive():
                break
            continue
    
    # 等待线程结束
    t.join(timeout=5)  # 设置超时时间避免无限等待

def run_stream_sync(param, model_type: str = "deepseek"):
    """
    同步运行流式处理函数的包装器
    
    Args:
        param: 输入参数
        model_type: 语言模型类型
    
    Returns:
        生成器对象
    """
    query = param.get("query", "")
    graph_data = param.get("graph_data", {})
    emb_data = param.get("emb_data", [])
    
    # 直接返回同步生成器
    return stream_answer_sync(query, graph_data, emb_data, model_type)