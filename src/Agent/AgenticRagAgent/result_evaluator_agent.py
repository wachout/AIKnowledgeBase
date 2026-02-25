"""
结果评估智能体

评估搜索结果质量，决定是否需要扩展搜索。
"""

from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers.json import JsonOutputParser
from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi

# ============================================================================
# 大模型配置
# ============================================================================

llm = ChatTongyi(
    temperature=0.3,
    model="deepseek-v3.2",
    api_key="sk-0270be722a48439e9ed73001e8e2524b",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    streaming=False,
    enable_thinking=False
)

class ResultEvaluatorAgent:
    """结果评估智能体"""
    
    def __init__(self):
        self.llm = llm
        self.parser = JsonOutputParser()
    
    def evaluate_results(self, query: str, search_results: List[Dict[str, Any]], 
                        intent_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估搜索结果质量
        
        Args:
            query: 用户查询
            search_results: 搜索结果
            intent_analysis: 意图分析结果
            
        Returns:
            评估结果，包含：
            - quality_score: 质量评分 (0-1)
            - is_satisfactory: 是否满意
            - should_expand: 是否应该扩展搜索
            - missing_aspects: 缺失的方面
            - expansion_suggestions: 扩展建议
        """
        
        # 计算基础指标
        metrics = self._calculate_metrics(search_results)
        
        # 使用LLM进行语义评估
        semantic_evaluation = self._semantic_evaluate(query, search_results, intent_analysis, metrics)
        
        # 综合评估
        evaluation = {
            **semantic_evaluation,
            "metrics": metrics,
            "results_count": len(search_results)
        }
        
        return evaluation
    
    def _calculate_metrics(self, search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算基础指标"""
        if not search_results:
            return {
                "count": 0,
                "avg_score": 0.0,
                "has_content_ratio": 0.0,
                "source_diversity": 0.0
            }
        
        # 结果数量
        count = len(search_results)
        
        # 平均相关性评分
        scores = [r.get("score", r.get("relevance_score", 0.5)) for r in search_results]
        avg_score = sum(scores) / len(scores) if scores else 0.5
        
        # 有内容的比例
        has_content_count = sum(1 for r in search_results if r.get("content", "").strip())
        has_content_ratio = has_content_count / count if count > 0 else 0
        
        # 来源多样性
        sources = set(r.get("search_engine", "") for r in search_results)
        source_diversity = min(len(sources) / 3.0, 1.0)  # 最多3个来源
        
        return {
            "count": count,
            "avg_score": round(avg_score, 3),
            "has_content_ratio": round(has_content_ratio, 3),
            "source_diversity": round(source_diversity, 3)
        }
    
    def _semantic_evaluate(self, query: str, search_results: List[Dict[str, Any]], 
                          intent_analysis: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
        """使用LLM进行语义评估"""
        
        # 准备搜索结果摘要
        results_summary = self._summarize_results(search_results)
        
        prompt = ChatPromptTemplate.from_template("""
你是一个搜索结果质量评估专家，需要评估搜索结果是否能够充分回答用户的问题。

## 用户查询
{query}

## 意图分析
- 主要意图: {main_intent}
- 查询类型: {query_type}
- 复杂度: {complexity}

## 搜索结果统计
- 结果数量: {results_count}
- 平均相关性评分: {avg_score}
- 有内容比例: {has_content_ratio}
- 来源多样性: {source_diversity}

## 搜索结果摘要
{results_summary}

## 评估任务
请评估：
1. 搜索结果的质量（0-1分）
2. 是否能够充分回答用户问题
3. 是否需要扩展搜索
4. 缺失哪些方面的信息
5. 扩展搜索的建议

## 输出格式
请以JSON格式输出：
{{
    "quality_score": 0.0-1.0,
    "is_satisfactory": true/false,
    "should_expand": true/false,
    "missing_aspects": ["缺失方面1", "缺失方面2"],
    "expansion_suggestions": ["扩展建议1", "扩展建议2"],
    "reasoning": "评估理由"
}}
""")
        
        try:
            chain = prompt | self.llm | self.parser
            result = chain.invoke({
                "query": query,
                "main_intent": intent_analysis.get("main_intent", "未知"),
                "query_type": intent_analysis.get("query_type", "未知"),
                "complexity": intent_analysis.get("complexity", "medium"),
                "results_count": metrics["count"],
                "avg_score": metrics["avg_score"],
                "has_content_ratio": metrics["has_content_ratio"],
                "source_diversity": metrics["source_diversity"],
                "results_summary": results_summary
            })
            
            # 验证和默认值
            if not isinstance(result, dict):
                result = {}
            
            result.setdefault("quality_score", metrics["avg_score"])
            result.setdefault("is_satisfactory", metrics["count"] >= 3 and metrics["avg_score"] >= 0.6)
            result.setdefault("should_expand", not result.get("is_satisfactory", False))
            result.setdefault("missing_aspects", [])
            result.setdefault("expansion_suggestions", [])
            result.setdefault("reasoning", "基于基础指标评估")
            
            return result
            
        except Exception as e:
            print(f"❌ 语义评估失败: {e}")
            import traceback
            traceback.print_exc()
            
            # 基于指标返回默认评估
            return {
                "quality_score": metrics["avg_score"],
                "is_satisfactory": metrics["count"] >= 3 and metrics["avg_score"] >= 0.6,
                "should_expand": metrics["count"] < 3 or metrics["avg_score"] < 0.6,
                "missing_aspects": [],
                "expansion_suggestions": [],
                "reasoning": f"评估过程出错，使用基础指标: {str(e)}"
            }
    
    def _summarize_results(self, search_results: List[Dict[str, Any]]) -> str:
        """总结搜索结果"""
        if not search_results:
            return "无搜索结果"
        
        summary_parts = []
        for i, result in enumerate(search_results[:5], 1):  # 只总结前5个
            title = result.get("title", "无标题")
            content_preview = result.get("content", "")[:200]
            source = result.get("search_engine", "unknown")
            score = result.get("score", result.get("relevance_score", 0.5))
            
            summary_parts.append(
                f"{i}. [{source}] {title} (评分: {score:.2f})\n   {content_preview}..."
            )
        
        return "\n\n".join(summary_parts)
