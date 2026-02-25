# -*- coding:utf-8 -*-
"""
决策智能体
判断用户问题中提到的实体本源、指标、属性、时间、关系等描述事物的数据
"""

import json
import re
from typing import Dict, Any, List
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate
from Config.llm_config import get_chat_tongyi


class DecisionAgent:
    """决策智能体：判断用户问题中提到的实体本源、指标、属性、时间、关系等"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)
    
    def analyze_entities(self, query: str) -> Dict[str, Any]:
        """
        分析用户问题中提到的实体本源、指标、属性、时间、关系等
        
        Args:
            query: 用户查询问题
            
        Returns:
            分析结果，包含：
            - entities: 实体本源列表
            - metrics: 指标列表
            - attributes: 属性列表
            - time_dimensions: 时间维度列表
            - relationships: 关系列表
        """
        try:
            system_prompt = """你是一个专业的问题分析专家。你的任务是从用户问题中识别出实体本源、指标、属性、时间、关系等描述事物的数据。

**核心目标：**
1. **实体本源**：识别问题中涉及的核心实体（如用户、订单、产品、部门等）
2. **指标**：识别问题中涉及的数值型指标（如总数、平均值、最大值、最小值、增长率、销售额等）
3. **属性**：识别问题中涉及的描述性属性（如名称、类型、状态、类别等）
4. **时间维度**：识别问题中涉及的时间相关概念（如日期、时间段、时间范围、时间序列等）
5. **关系**：识别问题中涉及的实体间关系（如属于、包含、关联等）

请仔细分析用户问题，提取这些关键信息，并以JSON格式返回分析结果。"""

            user_prompt = f"""用户查询：{query}

请分析这个问题中提到的实体本源、指标、属性、时间、关系等，以JSON格式返回分析结果：
{{
    "entities": [
        {{
            "entity_name": "实体名称",
            "entity_type": "实体类型",
            "description": "实体描述",
            "confidence": 0.9
        }}
    ],
    "metrics": [
        {{
            "metric_name": "指标名称",
            "metric_type": "指标类型（如count、sum、avg、max、min、growth_rate等）",
            "description": "指标描述",
            "confidence": 0.8
        }}
    ],
    "attributes": [
        {{
            "attribute_name": "属性名称",
            "attribute_type": "属性类型",
            "description": "属性描述",
            "confidence": 0.8
        }}
    ],
    "time_dimensions": [
        {{
            "time_concept": "时间概念（如日期、时间段、时间范围等）",
            "time_type": "时间类型（如date、datetime、period、range等）",
            "description": "时间维度描述",
            "confidence": 0.8
        }}
    ],
    "relationships": [
        {{
            "from_entity": "源实体",
            "to_entity": "目标实体",
            "relationship_type": "关系类型（如belongs_to、contains、related_to等）",
            "description": "关系描述",
            "confidence": 0.7
        }}
    ]
}}

请确保返回有效的JSON格式。"""

            response = self.llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ])
            
            content = response.content.strip()
            
            # 提取JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                return {
                    "success": True,
                    "entities": result.get("entities", []),
                    "metrics": result.get("metrics", []),
                    "attributes": result.get("attributes", []),
                    "time_dimensions": result.get("time_dimensions", []),
                    "relationships": result.get("relationships", []),
                    "raw_response": content
                }
            else:
                return {
                    "success": False,
                    "error": "无法解析大模型返回的JSON",
                    "raw_response": content
                }
                
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON解析失败: {e}",
                "raw_response": content if 'content' in locals() else ""
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"实体分析失败: {str(e)}"
            }
