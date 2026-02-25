# -*- coding:utf-8 -*-
"""
结果解读智能体
通过以上智能体分析结果，进行解读，输出结果
"""

import json
import logging
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from Config.llm_config import get_chat_tongyi

logger = logging.getLogger(__name__)


class ResultInterpretationAgent:
    """结果解读智能体：综合解读所有分析结果"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.7, enable_thinking=False)  # 提高temperature以获得更好的解读
        
        self.interpretation_prompt = ChatPromptTemplate.from_template(
            """你是一个专业的数据分析报告撰写专家，擅长将复杂的分析结果转化为清晰、易懂的解读报告。

用户需求: {user_intent}

分析结果汇总:
1. 文件理解: {file_understanding_summary}
2. 数据类型分析: {data_type_summary}
3. 统计计算结果: {statistics_summary}
4. 关联分析: {correlation_summary}
5. 语义分析: {semantic_summary}

请撰写一份完整的数据分析解读报告，重点包含具体的指标值分析：

1. **执行摘要** (Executive Summary)
   - 数据概况（包含具体的数据量、列数、行数等指标）
   - 主要发现（包含具体的数值指标）
   - 关键洞察

2. **详细分析** (Detailed Analysis)
   - 数据质量评估（包含缺失值率、异常值数量等具体指标）
   - 统计特征分析（包含均值、中位数、标准差、分布特征等具体数值）
   - 关联关系解读（包含相关系数、强相关关系对等具体指标）
   - 业务模式识别

3. **关键发现** (Key Findings)
   - 列出3-7个最重要的发现
   - **每个发现必须包含具体的数据指标值**，不能空谈
   - 示例：年龄字段的平均值为35.2岁，标准差为8.5；收入与教育水平的相关系数为0.723

4. **指标汇总分析** (Statistical Summary)
   - 汇总所有重要的统计指标
   - 包括描述性统计、分布特征、相关性分析等具体数值
   - 提取数据洞察和业务含义

5. **业务建议** (Business Recommendations)
   - 基于具体指标值的分析结果
   - 提出数据驱动的业务建议

6. **结论** (Conclusion)
   - 基于具体指标值的总结分析结果
   - 指出数据价值

请以结构化的文本格式返回，使用Markdown格式。
"""
        )
    
    def interpret(self, user_intent: str,
                  file_understanding: Dict[str, Any],
                  data_type_analysis: Dict[str, Any],
                  statistics_result: Dict[str, Any],
                  correlation_analysis: Dict[str, Any],
                  semantic_analysis: Dict[str, Any]) -> str:
        """
        解读分析结果
        
        Args:
            user_intent: 用户意图
            file_understanding: 文件理解结果
            data_type_analysis: 数据类型分析结果
            statistics_result: 统计计算结果
            correlation_analysis: 关联分析结果
            semantic_analysis: 语义分析结果
            
        Returns:
            解读报告文本
        """
        try:
            # 准备摘要信息
            file_summary = f"文件包含 {len(file_understanding.get('file_structure', {}).get('sheets_info', []))} 个工作表"
            data_type_summary = f"共分析了 {sum(len(s.get('columns_analysis', [])) for s in data_type_analysis.get('sheets_analysis', []))} 个列"
            statistics_summary = f"执行了 {len(statistics_result.get('calculations', {}))} 个工作表的统计计算"
            correlation_summary = f"发现 {len(correlation_analysis.get('strong_correlations', []))} 个强相关关系"
            semantic_summary = f"识别了 {len(semantic_analysis.get('semantic_analysis', {}).get('business_patterns', []))} 个业务模式"
            
            # 构建提示
            prompt = self.interpretation_prompt.format(
                user_intent=user_intent,
                file_understanding_summary=file_summary,
                data_type_summary=data_type_summary,
                statistics_summary=statistics_summary,
                correlation_summary=correlation_summary,
                semantic_summary=semantic_summary
            )
            
            # 调用LLM
            response = self.llm.invoke(prompt)
            interpretation = response.content if hasattr(response, 'content') else str(response)
            
            logger.info(f"✅ 结果解读完成，报告长度: {len(interpretation)} 字符")
            return interpretation
            
        except Exception as e:
            logger.error(f"❌ 结果解读失败: {e}")
            return f"## 分析结果解读\n\n⚠️ 解读过程出现错误: {str(e)}\n\n请查看详细的分析结果。"
