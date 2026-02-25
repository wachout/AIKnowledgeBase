# -*- coding:utf-8 -*-
"""
语义分析智能体
通过关联，理解列的语义，再进行深度分析，调用第八个智能体，输出echarts图表
"""

import json
import logging
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from Config.llm_config import get_chat_tongyi

logger = logging.getLogger(__name__)


class SemanticAnalysisAgent:
    """语义分析智能体：理解列的语义并进行深度分析"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, enable_thinking=False)
        
        self.semantic_prompt = ChatPromptTemplate.from_template(
            """你是一个专业的数据语义分析专家，擅长理解数据的业务含义和语义关系。

文件理解结果: {file_understanding}
数据类型分析: {data_type_analysis}
统计计算结果: {statistics_result}
关联分析结果: {correlation_analysis}

请进行深度语义分析：
1. 理解每个列的业务含义和语义
2. 分析列之间的语义关系
3. 识别数据中的业务模式和规律
4. 发现潜在的商业洞察

请以JSON格式返回分析结果：
{{
    "semantic_analysis": {{
        "column_semantics": [
            {{
                "column_name": "列名",
                "business_meaning": "业务含义",
                "semantic_category": "类别（如：时间维度/业务指标/分类属性等）",
                "importance": "high/medium/low",
                "business_insights": ["业务洞察1", "业务洞察2"]
            }}
        ],
        "semantic_relationships": [
            {{
                "columns": ["列1", "列2"],
                "relationship_type": "关系类型（如：因果关系/相关关系/层级关系等）",
                "description": "关系描述",
                "business_implication": "业务含义"
            }}
        ],
        "business_patterns": [
            "业务模式1：...",
            "业务模式2：..."
        ],
        "recommended_analysis": [
            {{
                "analysis_type": "分析类型",
                "target_columns": ["列名列表"],
                "reason": "分析原因",
                "expected_chart": "推荐的图表类型"
            }}
        ]
    }}
}}
"""
        )
    
    def analyze(self, file_understanding: Dict[str, Any],
                data_type_analysis: Dict[str, Any],
                statistics_result: Dict[str, Any],
                correlation_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        进行语义分析
        
        Args:
            file_understanding: 文件理解结果
            data_type_analysis: 数据类型分析结果
            statistics_result: 统计计算结果
            correlation_analysis: 关联分析结果
            
        Returns:
            语义分析结果
        """
        try:
            # 准备输入数据（简化JSON以避免token过多）
            file_understanding_summary = {
                "user_intent": file_understanding.get("user_intent", ""),
                "key_columns": file_understanding.get("key_columns", [])
            }
            
            # 构建提示
            prompt = self.semantic_prompt.format(
                file_understanding=json.dumps(file_understanding_summary, ensure_ascii=False),
                data_type_analysis=json.dumps(data_type_analysis, ensure_ascii=False)[:2000],  # 限制长度
                statistics_result=json.dumps(statistics_result, ensure_ascii=False)[:2000],
                correlation_analysis=json.dumps(correlation_analysis, ensure_ascii=False)[:2000]
            )
            
            # 调用LLM
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 解析JSON响应
            try:
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    content = content[json_start:json_end].strip()
                elif "```" in content:
                    json_start = content.find("```") + 3
                    json_end = content.find("```", json_start)
                    content = content[json_start:json_end].strip()
                
                result = json.loads(content)
            except json.JSONDecodeError:
                logger.warning("⚠️ LLM返回的不是有效JSON，使用默认结构")
                result = {
                    "semantic_analysis": {
                        "column_semantics": [],
                        "semantic_relationships": [],
                        "business_patterns": [],
                        "recommended_analysis": []
                    }
                }
            
            logger.info(f"✅ 语义分析完成")
            return result
            
        except Exception as e:
            logger.error(f"❌ 语义分析失败: {e}")
            raise
