# -*- coding:utf-8 -*-
"""
查询增强智能体
完善用户的问题，生成更详细的查询和计算描述
"""

import json
import re
from typing import Dict, Any, List
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate
from Config.llm_config import get_chat_tongyi


class QueryEnhancementAgent:
    """查询增强智能体：完善用户问题，生成更详细的查询和计算描述"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)
    
    def enhance_query(self, original_query: str, entity_analysis: Dict[str, Any],
                     search_results: List[Dict[str, Any]], 
                     artifact_content: str) -> Dict[str, Any]:
        """
        完善用户问题，生成更详细的查询和计算描述
        
        Args:
            original_query: 原始用户查询
            entity_analysis: 实体分析结果
            search_results: 搜索结果
            artifact_content: Artifact处理后的内容
            
        Returns:
            增强后的查询，包含：
            - enhanced_query: 增强后的查询
            - calculation_descriptions: 计算描述列表
            - detailed_requirements: 详细需求
        """
        try:
            # 提取关键信息
            entities = entity_analysis.get("entities", [])
            metrics = entity_analysis.get("metrics", [])
            attributes = entity_analysis.get("attributes", [])
            
            # 从搜索结果中提取计算逻辑
            calculation_logics = self._extract_calculation_logics(artifact_content)
            
            # 转义花括号
            entities_str = json.dumps(entities, ensure_ascii=False, indent=2).replace("{", "{{").replace("}", "}}")
            metrics_str = json.dumps(metrics, ensure_ascii=False, indent=2).replace("{", "{{").replace("}", "}}")
            calculation_logics_str = json.dumps(calculation_logics, ensure_ascii=False, indent=2).replace("{", "{{").replace("}", "}}")
            
            # 构建Artifact内容摘要（只显示前1000字符）
            artifact_summary = artifact_content[:1000] + "..." if len(artifact_content) > 1000 else artifact_content
            
            system_prompt = """你是一个专业的查询增强专家。你的任务是根据用户原始查询、实体分析和知识库搜索结果，完善用户的问题，生成更详细的查询和计算描述。

**重要原则：**
1. 如果知识库中提到某属性需要两个指标相加计算，要在增强查询中明确说明这个计算逻辑
2. 如果知识库中提到了计算规则，要在增强查询中详细描述
3. 保持原始查询的核心意图，只是增加细节和计算说明
4. 不要改变原始查询的含义

请以JSON格式返回增强结果：
{{
    "enhanced_query": "增强后的查询（包含计算逻辑说明）",
    "calculation_descriptions": [
        {{
            "attribute": "属性名称",
            "calculation": "计算逻辑（如：需要指标A和指标B相加）",
            "description": "计算描述"
        }}
    ],
    "detailed_requirements": "详细需求说明"
}}"""

            user_prompt = f"""**原始用户查询：**
{original_query}

**识别的实体：**
{entities_str}

**识别的指标：**
{metrics_str}

**从知识库中提取的计算逻辑：**
{calculation_logics_str}

**知识库内容摘要：**
{artifact_summary}

请完善用户的问题，生成更详细的查询和计算描述。特别关注：
1. 如果知识库中提到某属性需要计算（如两个指标相加），要在增强查询中明确说明
2. 如果知识库中提到了计算规则，要详细描述
3. 保持原始查询的核心意图

请以JSON格式返回增强结果。"""

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
                        "enhanced_query": result.get("enhanced_query", original_query),
                        "calculation_descriptions": result.get("calculation_descriptions", []),
                        "detailed_requirements": result.get("detailed_requirements", ""),
                        "raw_response": response_text
                    }
                except json.JSONDecodeError:
                    pass
            
            # 如果解析失败，返回原始查询
            return {
                "success": True,
                "enhanced_query": original_query,
                "calculation_descriptions": calculation_logics,
                "detailed_requirements": "基于知识库搜索结果完善查询",
                "raw_response": response_text
            }
                
        except Exception as e:
            import logging
            import traceback
            logging.warning(f"⚠️ 查询增强失败: {e}")
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "enhanced_query": original_query,
                "calculation_descriptions": [],
                "detailed_requirements": ""
            }
    
    def _extract_calculation_logics(self, artifact_content: str) -> List[Dict[str, Any]]:
        """从Artifact内容中提取计算逻辑"""
        calculation_logics = []
        
        # 查找计算相关的关键词
        calculation_keywords = [
            "相加", "相加计算", "需要相加", "等于", "计算", "公式",
            "add", "sum", "calculate", "formula", "等于", "需要"
        ]
        
        content_lower = artifact_content.lower()
        
        # 简单的模式匹配提取计算逻辑
        # 例如："属性A需要指标B和指标C相加"
        patterns = [
            r'([^。，；\n]+(?:相加|等于|计算|需要)[^。，；\n]+)',
            r'([^。，；\n]+(?:add|sum|calculate|formula)[^。，；\n]+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, artifact_content, re.IGNORECASE)
            for match in matches:
                if any(kw in match.lower() for kw in calculation_keywords):
                    calculation_logics.append({
                        "calculation_text": match.strip(),
                        "description": "从知识库中提取的计算逻辑"
                    })
        
        return calculation_logics[:5]  # 最多返回5个
