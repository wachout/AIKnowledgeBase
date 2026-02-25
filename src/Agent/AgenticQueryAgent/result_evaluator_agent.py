# -*- coding:utf-8 -*-
"""
结果评估智能体
分析搜索结果质量，判断是否需要扩展搜索
"""

import json
import re
from typing import Dict, Any, List
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate
from Config.llm_config import get_chat_tongyi


class ResultEvaluatorAgent:
    """结果评估智能体：分析搜索结果质量"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)
    
    def evaluate_results(self, query: str, search_results: List[Dict[str, Any]],
                        entity_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估搜索结果质量
        
        Args:
            query: 用户查询
            search_results: 搜索结果列表
            entity_analysis: 实体分析结果
            
        Returns:
            评估结果，包含：
            - quality_score: 质量评分 (0-1)
            - is_satisfied: 是否满意
            - missing_entities: 缺失的实体
            - missing_metrics: 缺失的指标
            - missing_attributes: 缺失的属性
            - should_expand: 是否应该扩展搜索
            - expansion_suggestions: 扩展搜索建议
        """
        try:
            # 计算基础质量指标
            results_count = len(search_results)
            avg_score = sum(r.get("score", 0.0) for r in search_results) / results_count if results_count > 0 else 0.0
            has_content_count = sum(1 for r in search_results if r.get("content", "").strip())
            content_ratio = has_content_count / results_count if results_count > 0 else 0.0
            
            # 提取实体、指标、属性
            entities = [e.get("entity_name", "") for e in entity_analysis.get("entities", [])]
            metrics = [m.get("metric_name", "") for m in entity_analysis.get("metrics", [])]
            attributes = [a.get("attribute_name", "") for a in entity_analysis.get("attributes", [])]
            
            # 检查搜索结果中是否包含这些实体、指标、属性
            search_content = " ".join([r.get("content", "") + " " + r.get("title", "") for r in search_results])
            search_content_lower = search_content.lower()
            
            found_entities = [e for e in entities if e.lower() in search_content_lower]
            found_metrics = [m for m in metrics if m.lower() in search_content_lower]
            found_attributes = [a for a in attributes if a.lower() in search_content_lower]
            
            missing_entities = [e for e in entities if e not in found_entities]
            missing_metrics = [m for m in metrics if m not in found_metrics]
            missing_attributes = [a for a in attributes if a not in found_attributes]
            
            # 构建评估提示
            entities_str = json.dumps(entities, ensure_ascii=False)
            metrics_str = json.dumps(metrics, ensure_ascii=False)
            attributes_str = json.dumps(attributes, ensure_ascii=False)
            
            # 转义花括号
            entities_str_escaped = entities_str.replace("{", "{{").replace("}", "}}")
            metrics_str_escaped = metrics_str.replace("{", "{{").replace("}", "}}")
            attributes_str_escaped = attributes_str.replace("{", "{{").replace("}", "}}")
            
            # 构建搜索结果摘要（只显示前3个结果的标题和部分内容）
            results_summary = []
            for i, result in enumerate(search_results[:3], 1):
                title = result.get("title", "无标题")
                content = result.get("content", "")[:200]  # 只取前200字符
                score = result.get("score", 0.0)
                results_summary.append(f"结果{i}: {title} (评分: {score:.3f})\n{content}...")
            results_summary_str = "\n\n".join(results_summary)
            
            system_prompt = """你是一个专业的搜索结果质量评估专家。你的任务是根据用户查询和实体分析结果，评估搜索结果的质量。

**评估维度：**
1. 结果数量是否充足
2. 结果相关性评分
3. 结果内容完整性
4. 是否覆盖了用户查询中提到的实体、指标、属性
5. 结果是否能回答用户的问题

请以JSON格式返回评估结果：
{{
    "quality_score": 0.0-1.0之间的数值,
    "is_satisfied": true/false,
    "should_expand": true/false,
    "expansion_suggestions": ["扩展搜索建议1", "扩展搜索建议2"],
    "evaluation_reasoning": "评估理由"
}}"""

            user_prompt = f"""**用户查询：**
{query}

**识别的实体：**
{entities_str_escaped}

**识别的指标：**
{metrics_str_escaped}

**识别的属性：**
{attributes_str_escaped}

**搜索结果摘要（前3个）：**
{results_summary_str}

**搜索结果统计：**
- 结果数量: {results_count}
- 平均评分: {avg_score:.3f}
- 有内容的结果比例: {content_ratio:.2%}
- 找到的实体: {len(found_entities)}/{len(entities)}
- 找到的指标: {len(found_metrics)}/{len(metrics)}
- 找到的属性: {len(found_attributes)}/{len(attributes)}
- 缺失的实体: {missing_entities}
- 缺失的指标: {missing_metrics}
- 缺失的属性: {missing_attributes}

请评估搜索结果质量，判断是否需要扩展搜索。如果结果数量少于3个、平均评分低于0.6、或缺失重要的实体/指标/属性，建议扩展搜索。

请以JSON格式返回评估结果。"""

            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", user_prompt)
            ])
            
            chain = prompt | self.llm
            response = chain.invoke({})
            
            # 解析响应
            response_text = response.content if hasattr(response, 'content') else str(response)
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    return {
                        "success": True,
                        "quality_score": result.get("quality_score", (content_ratio + avg_score) / 2),
                        "is_satisfied": result.get("is_satisfied", results_count >= 3 and avg_score >= 0.6),
                        "should_expand": result.get("should_expand", results_count < 3 or avg_score < 0.6),
                        "expansion_suggestions": result.get("expansion_suggestions", []),
                        "evaluation_reasoning": result.get("evaluation_reasoning", ""),
                        "missing_entities": missing_entities,
                        "missing_metrics": missing_metrics,
                        "missing_attributes": missing_attributes,
                        "results_count": results_count,
                        "avg_score": avg_score,
                        "content_ratio": content_ratio,
                        "raw_response": response_text
                    }
                except json.JSONDecodeError:
                    pass
            
            # 如果解析失败，使用基础评估
            quality_score = (content_ratio * 0.4 + avg_score * 0.4 + (min(results_count / 10.0, 1.0)) * 0.2)
            is_satisfied = results_count >= 3 and avg_score >= 0.6 and content_ratio >= 0.8
            should_expand = not is_satisfied
            
            return {
                "success": True,
                "quality_score": quality_score,
                "is_satisfied": is_satisfied,
                "should_expand": should_expand,
                "expansion_suggestions": missing_entities + missing_metrics + missing_attributes,
                "evaluation_reasoning": f"基础评估：结果数量{results_count}，平均评分{avg_score:.3f}，内容完整度{content_ratio:.2%}",
                "missing_entities": missing_entities,
                "missing_metrics": missing_metrics,
                "missing_attributes": missing_attributes,
                "results_count": results_count,
                "avg_score": avg_score,
                "content_ratio": content_ratio
            }
                
        except Exception as e:
            import logging
            import traceback
            logging.warning(f"⚠️ 结果评估失败: {e}")
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "quality_score": 0.0,
                "is_satisfied": False,
                "should_expand": True
            }
