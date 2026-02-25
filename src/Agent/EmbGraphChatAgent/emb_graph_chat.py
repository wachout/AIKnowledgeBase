import asyncio
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_predefined_llm(model_type: str = "deepseek"):
    """获取预定义的大语言模型
    
    根据指定的模型类型返回相应的LLM实例
    
    Args:
        model_type: 模型类型，支持"deepseek"和"tongyi"
        
    Returns:
        对应的LLM实例
        
    Raises:
        ValueError: 当model_type不被支持时抛出
    """
    if model_type == "deepseek":
        return ChatOpenAI(
            temperature=0.6,
            model=os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-reasoner"),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_URL_BASE", "https://api.deepseek.com/v1"),
        )
    elif model_type == "tongyi":
        llm = ChatTongyi(
            temperature=0.7,
            model=os.getenv("GRAPH_MODEL", "qwen3-30b-a3b"),
            api_key=os.getenv("QWEN_API_KEY"),
            base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        )
        return llm.bind(enable_thinking=False)
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")


# 定义智能体状态类
class AgentState(BaseModel):
    """智能体状态类，用于在LangGraph工作流中传递状态
    
    Attributes:
        query: 用户的问题
        text_knowledge: 文本知识库数据
        graph_knowledge: 图数据库知识
        processed_knowledge: 处理后的知识内容
        answer: 生成的回答
        model_type: 使用的模型类型
    """
    query: str = Field(description="用户的问题")
    text_knowledge: List[Dict[str, Any]] = Field(
        default_factory=list, description="文本知识库数据"
    )
    graph_knowledge: List[List[Dict[str, Any]]] = Field(
        default_factory=list, description="图数据库知识"
    )
    processed_knowledge: str = Field(
        default="", description="处理后的知识内容"
    )
    answer: Optional[str] = Field(
        default=None, description="生成的回答"
    )
    model_type: str = Field(
        default="deepseek", description="使用的模型类型"
    )


def process_text_knowledge(text_knowledge: List[Dict[str, Any]]) -> str:
    """处理文本知识库数据 - 保留完整文本段落
    
    将文本知识库中的数据转换为格式化的字符串，保留标题、内容和相关度信息
    
    Args:
        text_knowledge: 文本知识库数据列表
        
    Returns:
        格式化后的文本内容
    """
    processed_content = []
    for item in text_knowledge:
        title = item.get("title", "未知标题")
        content = item.get("content", "")
        score = item.get("score", 0.0)
        
        # 保留完整文本，包括可能包含表格、图片及其说明的内容
        processed_item = f"标题: {title}\n相关度: {score}\n内容:\n{content}"
        processed_content.append(processed_item)
    
    return "\n\n".join(processed_content)

def process_graph_knowledge(graph_knowledge: List[List[Dict[str, Any]]]) -> str:
    """处理图数据库知识
    
    将图数据库中的实体关系数据转换为格式化的字符串描述
    
    Args:
        graph_knowledge: 图数据库知识数据
        
    Returns:
        格式化后的图数据库知识内容
    """
    processed_content = []
    
    for edge_group in graph_knowledge:
        for edge in edge_group:
            # 提取实体信息
            start_node = edge.get("start_node", {})
            end_node = edge.get("end_node", {})
            relation = edge.get("relation", {})
            
            # 构建实体关系表示
            start_entity = f"实体1: {start_node.get('entity_id', '未知')} ({start_node.get('entity_type', '未知类型')})"
            end_entity = f"实体2: {end_node.get('entity_id', '未知')} ({end_node.get('entity_type', '未知类型')})"
            
            # 提取关系描述
            relation_desc = relation.get('description', '')
            relation_keywords = relation.get('keywords', '')
            
            # 合并节点描述信息
            start_desc = start_node.get('description', '')
            end_desc = end_node.get('description', '')
            
            # 如果存在chunks信息，将其添加到处理后的内容中
            start_chunks = start_node.get('chunks', [])
            end_chunks = end_node.get('chunks', [])
            start_titles = start_node.get('titles', [])
            end_titles = end_node.get('titles', [])
            
            # 构建完整的关系表示
            graph_item = (
                f"{start_entity}\n{end_entity}\n关系描述: {relation_desc}\n"
                f"关系关键词: {relation_keywords}\n"
            )
            
            # 添加节点描述
            if start_desc:
                graph_item += f"实体1描述: {start_desc}\n"
            if end_desc:
                graph_item += f"实体2描述: {end_desc}\n"
            
            # 添加chunks信息 - 可能包含表格和图片信息
            if start_chunks:
                graph_item += f"实体1相关文本段落: {', '.join(start_chunks)}\n"
            if end_chunks:
                graph_item += f"实体2相关文本段落: {', '.join(end_chunks)}\n"
            if start_titles:
                graph_item += f"实体1相关文档标题: {', '.join(start_titles)}\n"
            if end_titles:
                graph_item += f"实体2相关文档标题: {', '.join(end_titles)}\n"
            
            processed_content.append(graph_item)
    
    return "\n\n".join(processed_content)

async def retrieve_knowledge(state: AgentState) -> AgentState:
    """检索并处理知识数据
    
    处理来自文本知识库和图数据库的知识数据，将其格式化为可理解的文本
    
    Args:
        state: 当前智能体状态
        
    Returns:
        更新后的智能体状态，包含处理后的知识内容
    """
    print("---处理知识库数据---")
    
    start_time = asyncio.get_event_loop().time()
    # 处理文本知识库
    text_knowledge_text = process_text_knowledge(state.text_knowledge)
    
    # 处理图数据库知识
    # graph_knowledge_text = process_graph_knowledge(state.graph_knowledge)
    graph_knowledge_text = ""
    for graph_lt in state.graph_knowledge:
        for graph in graph_lt:
            _knowledge = process_graph_knowledge(graph)
            graph_knowledge_text = _knowledge + "\n"

    end_time = asyncio.get_event_loop().time()
    print(f"知识处理耗时: {end_time - start_time:.2f} 秒")
    # 合并两种知识源
    state.processed_knowledge = (
        "=== 文本知识库信息 ===\n"
        f"{text_knowledge_text}\n\n"
        "=== 图数据库知识信息 ===\n"
        f"{graph_knowledge_text}"
    )
    
    return state


async def generate_answer(state: AgentState) -> AgentState:
    """生成回答
    
    使用预定义的LLM基于处理后的知识内容生成对用户问题的回答
    
    Args:
        state: 当前智能体状态，包含用户问题和处理后的知识
        
    Returns:
        更新后的智能体状态，包含生成的回答
    """
    print("---生成回答---")
    
    # 获取预定义的LLM
    llm = get_predefined_llm(state.model_type)
    
    # 创建提示模板 - 特别强调关注表格和图片信息
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """
        你是一个智能助手，负责根据提供的知识库信息回答用户问题。
        
        特别注意：
        1. 文本段落中可能包含表格、图片URL、表格说明(caption)和表格脚注(footnote)信息
        2. 在回答相关问题时，请务必关注并参考这些表格和图片信息
        3. 如果用户的问题与表格或图片相关，请在回答中明确引用相关的表格和图片内容
        4. 请完整保留表格的结构和图片URL信息
        5. 如有表格说明(caption)和脚注(footnote)，请将其与表格内容一起考虑
        
        请结合文本知识库和图数据库知识，给出全面、准确的回答。
        回答应当基于提供的知识，不要编造信息。
        """),
        ("human", """
        用户问题: {query}
        
        知识库信息:
        {knowledge}
        
        请根据以上知识库信息，回答用户的问题。
        请特别注意文本中的表格、图片及其相关说明(caption)和脚注(footnote)信息。
        """),
    ])
    
    start_time = asyncio.get_event_loop().time()
    # 创建回答生成链
    answer_chain = prompt_template | llm | StrOutputParser()
    
    # 生成回答
    state.answer = await answer_chain.ainvoke({
        "query": state.query,
        "knowledge": state.processed_knowledge
    })
    end_time = asyncio.get_event_loop().time()
    print(f"回答生成耗时: {end_time - start_time:.2f} 秒")
    
    return state

def create_agent_workflow() -> StateGraph:
    """创建智能体工作流
    
    构建LangGraph工作流，定义节点和边的关系
    
    Returns:
        编译后的工作流图
    """
    # 创建状态图
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("retrieve_knowledge", retrieve_knowledge)
    workflow.add_node("generate_answer", generate_answer)
    
    # 设置边
    workflow.add_edge("retrieve_knowledge", "generate_answer")
    workflow.add_edge("generate_answer", END)
    
    # 设置入口点
    workflow.set_entry_point("retrieve_knowledge")
    
    # app = workflow.compile()
    # return app
    
    return workflow.compile()

async def process_query(param: Dict[str, Any], model_type: str = "deepseek") -> Dict[str, str]:
    """
    处理查询的主函数
    
    Args:
        param: 包含query、graph_data和emb_data的参数字典
        model_type: 使用的模型类型，可以是"deepseek"或"tongyi"
    
    Returns:
        包含回答的字典
    """
    # 创建工作流
    app = create_agent_workflow()
    
    # 准备状态数据
    initial_state = AgentState(
        query=param.get("query", ""),
        text_knowledge=param.get("emb_data", []),
        graph_knowledge=param.get("graph_data", []),
        model_type=model_type
    )
    
    # 执行工作流
    result = await app.ainvoke(initial_state)
    
    # 返回结果
    return {
        "query": result.get('query', ''),
        "answer": result.get('answer', '无法生成回答，请检查输入参数。')
    }
    
def run_sync(param: Dict[str, Any], model_type: str = "deepseek") -> Dict[str, str]:
    """同步运行处理查询的主函数
    
    Args:
        param: 包含查询参数的字典
        model_type: 使用的模型类型
        
    Returns:
        包含查询和回答的字典
    """
    return asyncio.run(process_query(param, model_type))