"""
决策智能体 (Decision Agent)

作为 Agentic RAG 的核心决策者，自主判断用户问题是调用工具还是检索知识库。
"""

from typing import Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers.json import JsonOutputParser
from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi

# ============================================================================
# 大模型配置
# ============================================================================

llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)

# ============================================================================
# 决策智能体
# ============================================================================

class DecisionAgent:
    """决策智能体：决定是调用工具还是检索知识库"""
    
    def __init__(self):
        self.llm = llm
        self.parser = JsonOutputParser()
        
    def decide_action(self, query: str, knowledge_description: str, 
                     available_tools: list, chat_history: Optional[list] = None) -> Dict[str, Any]:
        """
        决策：判断应该调用工具还是检索知识库
        
        Args:
            query: 用户查询
            knowledge_description: 知识库描述
            available_tools: 可用工具列表
            chat_history: 聊天历史（可选）
            
        Returns:
            决策结果，包含：
            - action: "tool" 或 "search"
            - tool_name: 如果 action 是 "tool"，指定工具名称
            - tool_params: 工具参数
            - reasoning: 决策理由
            - confidence: 置信度 (0-1)
        """
        
        # 构建决策提示
        tools_description = "\n".join([
            f"- {tool['name']}: {tool['description']}" 
            for tool in available_tools
        ])
        
        history_context = ""
        if chat_history:
            recent_history = chat_history[-3:]  # 只使用最近3轮对话
            history_context = "\n".join([
                f"用户: {msg.get('content', '')}" if msg.get('role') == 'user' 
                else f"助手: {msg.get('content', '')[:100]}..."
                for msg in recent_history
            ])
        
        prompt = ChatPromptTemplate.from_template("""
你是一个智能决策系统，需要判断用户的问题应该通过工具直接回答，还是需要在知识库中检索信息。

## 知识库信息
{knowledge_description}

## 可用工具
{tools_description}

## 聊天历史（最近3轮）
{history_context}

## 用户当前问题
{query}

## 决策规则
1. **工具调用场景**：
   - 查询知识库的元信息（文件数量、文件列表、文件基本信息）
   - 不需要深入内容分析的问题
   - 可以通过结构化数据直接回答的问题

2. **知识库检索场景**：
   - 需要从文档内容中提取信息
   - 需要理解文档的语义和上下文
   - 需要综合多个文档的信息
   - 需要分析、解释、总结文档内容

## 输出格式
请以JSON格式输出决策结果：
{{
    "action": "tool" 或 "search",
    "tool_name": "工具名称（如果action是tool）",
    "tool_params": {{"参数名": "参数值"}},
    "reasoning": "决策理由（详细说明为什么选择这个行动）",
    "confidence": 0.0-1.0之间的数值
}}

请仔细分析用户问题，做出最合适的决策。
""")
        
        try:
            chain = prompt | self.llm | self.parser
            result = chain.invoke({
                "query": query,
                "knowledge_description": knowledge_description or "知识库未描述",
                "tools_description": tools_description or "无可用工具",
                "history_context": history_context or "无历史对话"
            })
            
            # 验证结果格式
            if not isinstance(result, dict):
                result = {"action": "search", "reasoning": "决策解析失败，默认使用检索", "confidence": 0.5}
            
            if "action" not in result:
                result["action"] = "search"
            
            if result["action"] == "tool" and "tool_name" not in result:
                result["action"] = "search"
                result["reasoning"] = "工具决策缺少工具名称，改为检索"
            
            return result
            
        except Exception as e:
            print(f"❌ 决策智能体执行失败: {e}")
            import traceback
            traceback.print_exc()
            # 默认返回检索决策
            return {
                "action": "search",
                "reasoning": f"决策过程出错: {str(e)}，默认使用检索",
                "confidence": 0.3
            }
    
    def should_expand_search(self, query: str, initial_results: list, 
                            intent_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        判断是否需要扩展搜索
        
        Args:
            query: 用户查询
            initial_results: 初始搜索结果
            intent_analysis: 意图分析结果
            
        Returns:
            扩展决策结果，包含：
            - should_expand: 是否应该扩展搜索
            - expansion_strategy: 扩展策略
            - reasoning: 决策理由
        """
        
        results_count = len(initial_results)
        results_quality_score = self._evaluate_results_quality(initial_results)
        
        prompt = ChatPromptTemplate.from_template("""
你是一个搜索策略决策系统，需要判断是否需要扩展搜索以获取更多信息。

## 用户查询
{query}

## 意图分析
- 主要意图: {main_intent}
- 查询类型: {query_type}
- 复杂度: {complexity}
- 关键词: {keywords}

## 当前搜索结果
- 结果数量: {results_count}
- 结果质量评分: {quality_score:.2f}/1.0

## 决策规则
1. **需要扩展的情况**：
   - 结果数量少于3个
   - 结果质量评分低于0.6
   - 查询复杂度为"complex"
   - 用户查询涉及多个实体或概念

2. **不需要扩展的情况**：
   - 结果数量充足（>=5个）且质量评分高（>=0.7）
   - 查询复杂度为"simple"
   - 已有结果能够充分回答用户问题

## 输出格式
请以JSON格式输出：
{{
    "should_expand": true/false,
    "expansion_strategy": "entity_expansion" 或 "semantic_expansion" 或 "none",
    "reasoning": "决策理由",
    "suggested_queries": ["扩展查询1", "扩展查询2"]
}}
""")
        
        try:
            chain = prompt | self.llm | self.parser
            result = chain.invoke({
                "query": query,
                "main_intent": intent_analysis.get("main_intent", "未知"),
                "query_type": intent_analysis.get("query_type", "未知"),
                "complexity": intent_analysis.get("complexity", "medium"),
                "keywords": ", ".join(intent_analysis.get("keywords", [])),
                "results_count": results_count,
                "quality_score": results_quality_score
            })
            
            return result
            
        except Exception as e:
            print(f"❌ 扩展搜索决策失败: {e}")
            # 默认不扩展
            return {
                "should_expand": False,
                "expansion_strategy": "none",
                "reasoning": f"决策过程出错: {str(e)}",
                "suggested_queries": []
            }
    
    def _evaluate_results_quality(self, results: list) -> float:
        """
        评估搜索结果质量
        
        Args:
            results: 搜索结果列表
            
        Returns:
            质量评分 (0-1)
        """
        if not results:
            return 0.0
        
        # 简单的质量评估逻辑
        # 1. 检查结果是否有内容
        has_content_count = sum(1 for r in results if r.get("content", "").strip())
        content_ratio = has_content_count / len(results) if results else 0
        
        # 2. 检查结果的平均相关性（如果有score字段）
        scores = [r.get("score", 0.5) for r in results if "score" in r]
        avg_score = sum(scores) / len(scores) if scores else 0.5
        
        # 3. 检查结果多样性（不同来源）
        sources = set(r.get("search_engine", "") for r in results)
        diversity_score = min(len(sources) / 3.0, 1.0)  # 最多3个来源
        
        # 综合评分
        quality_score = (content_ratio * 0.4 + avg_score * 0.4 + diversity_score * 0.2)
        
        return quality_score
