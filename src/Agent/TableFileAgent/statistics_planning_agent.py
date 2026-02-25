# -*- coding:utf-8 -*-
"""
统计计算规划智能体
深度考虑哪些列需要什么样的数理统计计算，给出结论输出
"""

import json
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from Config.llm_config import get_chat_tongyi

logger = logging.getLogger(__name__)


class StatisticsPlanningAgent:
    """统计计算规划智能体：规划需要进行的统计计算"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, enable_thinking=False)
        
        self.planning_prompt = ChatPromptTemplate.from_template(
            """你是一个专业的统计学家，擅长规划数据分析的统计计算方案。

用户需求: {user_intent}
文件结构: {file_structure}
数据类型分析: {data_type_analysis}
关键列: {key_columns}

请根据以上信息，为每个工作表规划详细的统计计算方案。

可用的统计计算方法：
1. **描述性统计** (descriptive_statistics): 均值、中位数、众数、方差、标准差、最小值、最大值、四分位数等
2. **分布分析** (distribution_analysis): 偏度、峰度、分布类型判断
3. **相关性分析** (correlation_analysis): 皮尔逊相关系数、斯皮尔曼相关系数
4. **频率分析** (frequency_analysis): 频数统计、频率分布、Top N值
5. **分组统计** (grouped_statistics): 按类别分组后的统计指标
6. **趋势分析** (trend_analysis): 时间序列趋势、增长率
7. **时间序列分析** (time_series_analysis): 月度模式、周度模式
8. **列联合分析** (column_joint_analysis): 列之间的交叉分析、卡方检验

请以JSON格式返回规划结果：
{{
    "statistics_plan": {{
        "overall_strategy": "整体统计策略说明",
        "sheets_plans": [
            {{
                "sheet_name": "工作表名称",
                "priority": "high/medium/low",
                "calculations": [
                    {{
                        "calculation_type": "统计计算方法名称",
                        "target_columns": ["列名列表"],
                        "reason": "选择此方法的原因",
                        "expected_insights": "预期获得的洞察"
                    }}
                ],
                "column_combinations": [
                    {{
                        "columns": ["列1", "列2"],
                        "analysis_type": "相关性分析/分组统计/联合分析",
                        "reason": "分析原因"
                    }}
                ]
            }}
        ]
    }},
    "recommendations": [
        "建议1：重点关注...",
        "建议2：建议进行...",
        "建议3：需要注意..."
    ]
}}
"""
        )
    
    def plan(self, file_understanding_result: Dict[str, Any], 
             data_type_analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        规划统计计算方案
        
        Args:
            file_understanding_result: 文件理解结果
            data_type_analysis_result: 数据类型分析结果
            
        Returns:
            统计计算规划结果
        """
        try:
            # 准备输入数据
            user_intent = file_understanding_result.get("user_intent", "")
            
            # 转换 pandas/numpy 类型为 JSON 可序列化类型
            def _convert_to_json_serializable(obj: Any) -> Any:
                """将对象转换为JSON可序列化的格式"""
                if isinstance(obj, (np.integer, pd.Int64Dtype)):
                    return int(obj)
                elif isinstance(obj, (np.floating, pd.Float64Dtype)):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, pd.Series):
                    return obj.tolist()
                elif isinstance(obj, pd.DataFrame):
                    return obj.to_dict(orient='records')
                elif isinstance(obj, dict):
                    return {key: _convert_to_json_serializable(value) for key, value in obj.items()}
                elif isinstance(obj, (list, tuple)):
                    return [_convert_to_json_serializable(item) for item in obj]
                elif pd.isna(obj):
                    return None
                else:
                    return obj
            
            # 转换数据后再序列化
            file_structure_clean = _convert_to_json_serializable(file_understanding_result.get("file_structure", {}))
            data_type_analysis_clean = _convert_to_json_serializable(data_type_analysis_result)
            
            file_structure = json.dumps(file_structure_clean, ensure_ascii=False, indent=2)
            data_type_analysis = json.dumps(data_type_analysis_clean, ensure_ascii=False, indent=2)
            key_columns = ", ".join(file_understanding_result.get("key_columns", []))
            
            # 构建提示
            prompt = self.planning_prompt.format(
                user_intent=user_intent,
                file_structure=file_structure,
                data_type_analysis=data_type_analysis,
                key_columns=key_columns
            )
            
            # 调用LLM
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 解析JSON响应
            try:
                # 尝试提取JSON部分
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
                # 如果解析失败，生成默认规划
                logger.warning("⚠️ LLM返回的不是有效JSON，使用默认规划")
                result = self._generate_default_plan(file_understanding_result, data_type_analysis_result)
            
            logger.info(f"✅ 统计计算规划完成")
            return result
            
        except Exception as e:
            logger.error(f"❌ 统计计算规划失败: {e}")
            raise
    
    def _generate_default_plan(self, file_understanding_result: Dict[str, Any],
                               data_type_analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """生成默认的统计计算规划"""
        sheets_plans = []
        
        for sheet_analysis in data_type_analysis_result.get("sheets_analysis", []):
            sheet_name = sheet_analysis["sheet_name"]
            numeric_cols = []
            text_cols = []
            
            for col_analysis in sheet_analysis.get("columns_analysis", []):
                category = col_analysis.get("data_category", "")
                if "numeric" in category or category in ["integer", "float"]:
                    numeric_cols.append(col_analysis["column_name"])
                elif category in ["text", "categorical_text"]:
                    text_cols.append(col_analysis["column_name"])
            
            calculations = []
            if numeric_cols:
                calculations.append({
                    "calculation_type": "描述性统计",
                    "target_columns": numeric_cols[:5],  # 限制前5个
                    "reason": "数值型列需要进行描述性统计",
                    "expected_insights": "了解数值分布的基本特征"
                })
                if len(numeric_cols) > 1:
                    calculations.append({
                        "calculation_type": "相关性分析",
                        "target_columns": numeric_cols[:5],
                        "reason": "多个数值型列可以分析相关性",
                        "expected_insights": "发现变量间的相关关系"
                    })
            
            if text_cols:
                calculations.append({
                    "calculation_type": "频率分析",
                    "target_columns": text_cols[:3],
                    "reason": "文本型列需要进行频率统计",
                    "expected_insights": "了解各类别的分布情况"
                })
            
            if numeric_cols and text_cols:
                calculations.append({
                    "calculation_type": "分组统计",
                    "target_columns": text_cols[:2] + numeric_cols[:2],
                    "reason": "可以按文本列分组统计数值列",
                    "expected_insights": "了解不同类别下的数值特征"
                })
            
            sheets_plans.append({
                "sheet_name": sheet_name,
                "priority": "high",
                "calculations": calculations,
                "column_combinations": []
            })
        
        return {
            "statistics_plan": {
                "overall_strategy": "基于数据类型自动规划统计计算",
                "sheets_plans": sheets_plans
            },
            "recommendations": [
                "建议重点关注数值型列的分布特征",
                "建议分析类别型列的频率分布",
                "建议探索数值列之间的相关关系"
            ]
        }
