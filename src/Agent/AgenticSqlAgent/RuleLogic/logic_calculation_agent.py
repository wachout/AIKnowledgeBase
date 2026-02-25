# -*- coding:utf-8 -*-
"""
逻辑计算智能体
根据CSV数据、逻辑计算规则、列信息等，选择合适的统计工具进行分析
"""

import json
import re
import csv
import os
import pandas as pd
from typing import Dict, Any, List
from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi
from langchain_core.prompts import ChatPromptTemplate
from Math.statistics import StatisticsCalculator


class LogicCalculationAgent:
    """逻辑计算智能体：根据逻辑计算规则选择合适的统计工具分析CSV数据"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)
        
        
        # 可用的统计工具列表
        self.available_tools = {
            "descriptive_statistics": {
                "name": "描述性统计",
                "description": "计算总数、均值、中位数、众数、方差、标准差、最小值、最大值、四分位数等",
                "method": "descriptive_statistics",
                "requires": ["numeric_cols"]
            },
            "frequency_analysis": {
                "name": "频率统计",
                "description": "统计各类别的出现频率、出现次数等",
                "method": "frequency_analysis",
                "requires": ["string_cols"]
            },
            "grouped_statistics": {
                "name": "分组统计",
                "description": "按不同维度进行分组统计（分组总数、分组均值、分组中位数等）",
                "method": "grouped_statistics",
                "requires": ["group_cols", "numeric_cols"]
            },
            "correlation_analysis": {
                "name": "相关性分析",
                "description": "分析变量间的相关关系",
                "method": "correlation_analysis",
                "requires": ["numeric_cols"]
            },
            "distribution_analysis": {
                "name": "分布分析",
                "description": "分析数据分布特征、偏度、峰度等",
                "method": "distribution_analysis",
                "requires": ["numeric_cols"]
            },
            "trend_analysis": {
                "name": "趋势分析",
                "description": "分析时间序列趋势、变化率等",
                "method": "trend_analysis",
                "requires": ["datetime_cols", "numeric_cols"]
            },
            "time_series_analysis": {
                "name": "时间序列分析",
                "description": "时间序列数据的统计分析",
                "method": "time_series_analysis",
                "requires": ["datetime_cols", "numeric_cols"]
            },
            "column_correlation": {
                "name": "列相关性匹配",
                "description": "文本列与数值列的关联分析",
                "method": "column_correlation_matching",
                "requires": ["string_cols", "numeric_cols"]
            }
        }
    
    def calculate_logic(self, csv_file_path: str, query: str, logical_calculations: List[Dict[str, Any]],
                       columns_desc: List[str], columns_types: List[str], sql: str) -> Dict[str, Any]:
        """
        执行逻辑计算：根据逻辑计算规则选择合适的统计工具分析CSV数据
        
        Args:
            csv_file_path: CSV文件路径
            query: 用户查询问题
            logical_calculations: 逻辑计算规则列表，格式: [{
                "logical_operation": "逻辑运算（如AND、OR、NOT、IF-THEN等）",
                "operands": ["操作数列表"],
                "description": "逻辑计算描述"
            }]
            columns_desc: 列描述列表（table.col 格式）
            columns_types: 列类型列表
            sql: 原始SQL语句
            
        Returns:
            逻辑计算结果，包含：
            - success: 是否成功
            - calculation_result: 统计计算结果
            - calculation_summary: 计算摘要
            - tools_used: 使用的统计工具列表
            - error: 错误信息（如果有）
        """
        try:
            # 检查CSV文件是否存在
            if not os.path.exists(csv_file_path):
                return {
                    "success": False,
                    "error": f"CSV文件不存在: {csv_file_path}"
                }
            
            # 如果没有逻辑计算规则，直接返回
            if not logical_calculations:
                return {
                    "success": True,
                    "calculation_result": None,
                    "calculation_summary": "无需执行逻辑计算",
                    "tools_used": [],
                    "message": "用户查询中未识别出需要逻辑计算的内容"
                }
            
            # 步骤1: 根据逻辑计算规则中明确提到的计算要求选择合适的统计工具（不扩展）
            selected_tools = self._select_statistics_tools_from_requirements(logical_calculations, columns_desc, columns_types)
            
            # 步骤2: 初始化统计计算器
            calculator = StatisticsCalculator(csv_file_path)
            
            # 步骤3: 识别列类型（数值型、字符串型、日期时间型）
            numeric_cols = []
            string_cols = []
            datetime_cols = []
            
            for i, (desc, col_type) in enumerate(zip(columns_desc, columns_types)):
                if i < len(calculator.df.columns):
                    col_name = calculator.df.columns[i]
                    col_type_str = str(col_type).lower().strip()
                    
                    # 判断列类型
                    numeric_keywords = ['int', 'integer', 'bigint', 'smallint', 'tinyint', 'mediumint',
                                       'float', 'double', 'decimal', 'numeric', 'number', 'real',
                                       'money', 'smallmoney', 'bit', 'serial', 'bigserial']
                    datetime_keywords = ['date', 'time', 'datetime', 'timestamp', 'year',
                                        'datetime2', 'datetimeoffset', 'smalldatetime']
                    string_keywords = ['varchar', 'char', 'text', 'nvarchar', 'nchar', 'ntext',
                                      'string', 'clob', 'blob', 'binary', 'varbinary']
                    
                    is_numeric = any(keyword in col_type_str for keyword in numeric_keywords)
                    is_datetime = any(keyword in col_type_str for keyword in datetime_keywords)
                    is_string = any(keyword in col_type_str for keyword in string_keywords)
                    
                    if is_datetime:
                        datetime_cols.append(col_name)
                    elif is_numeric:
                        numeric_cols.append(col_name)
                    elif is_string:
                        string_cols.append(col_name)
                    else:
                        # 根据实际数据推断
                        if col_name in calculator.df.columns:
                            if pd.api.types.is_numeric_dtype(calculator.df[col_name]):
                                numeric_cols.append(col_name)
                            elif pd.api.types.is_datetime64_any_dtype(calculator.df[col_name]):
                                datetime_cols.append(col_name)
                            else:
                                string_cols.append(col_name)
            
            # 如果没有自动识别，使用统计计算器的自动识别
            if not numeric_cols and not string_cols and not datetime_cols:
                numeric_cols = list(calculator.df.select_dtypes(include=['number']).columns)
                string_cols = list(calculator.df.select_dtypes(include=['object']).columns)
                for col in calculator.df.columns:
                    if pd.api.types.is_datetime64_any_dtype(calculator.df[col]):
                        datetime_cols.append(col)
            
            # 步骤4: 根据选择的工具调用相应的统计方法
            statistics_results = {}
            tools_executed = []
            
            for tool_name in selected_tools:
                if tool_name not in self.available_tools:
                    continue
                
                tool_info = self.available_tools[tool_name]
                method_name = tool_info["method"]
                requires = tool_info["requires"]
                
                try:
                    # 检查所需参数是否满足
                    can_execute = True
                    method_args = {}
                    
                    if "numeric_cols" in requires and not numeric_cols:
                        can_execute = False
                    if "string_cols" in requires and not string_cols:
                        can_execute = False
                    if "datetime_cols" in requires and not datetime_cols:
                        can_execute = False
                    if "group_cols" in requires and not string_cols:
                        can_execute = False
                    
                    if not can_execute:
                        continue
                    
                    # 准备方法参数
                    if method_name == "descriptive_statistics":
                        method_args = {"numeric_cols": numeric_cols}
                    elif method_name == "frequency_analysis":
                        method_args = {"string_cols": string_cols}
                    elif method_name == "grouped_statistics":
                        method_args = {"group_cols": string_cols, "numeric_cols": numeric_cols}
                    elif method_name == "correlation_analysis":
                        method_args = {"numeric_cols": numeric_cols}
                    elif method_name == "distribution_analysis":
                        method_args = {"numeric_cols": numeric_cols}
                    elif method_name == "trend_analysis":
                        method_args = {"datetime_cols": datetime_cols, "numeric_cols": numeric_cols}
                    elif method_name == "time_series_analysis":
                        method_args = {"datetime_cols": datetime_cols, "numeric_cols": numeric_cols}
                    elif method_name == "column_correlation_matching":
                        method_args = {"string_cols": string_cols, "numeric_cols": numeric_cols}
                    
                    # 调用统计方法
                    if hasattr(calculator, method_name):
                        method = getattr(calculator, method_name)
                        result = method(**method_args)
                        if result:
                            statistics_results[tool_name] = result
                            tools_executed.append(tool_name)
                except Exception as e:
                    import logging
                    logging.warning(f"⚠️ 执行统计工具 {tool_name} 失败: {e}")
                    continue
            
            # 步骤5: 构建返回结果
            if not statistics_results:
                # 如果没有匹配到统计工具，说明logical_calculations中没有明确提到需要统计计算
                if not selected_tools:
                    return {
                        "success": True,
                        "calculation_result": {},
                        "calculation_summary": "逻辑计算规则中未明确提到需要统计计算",
                        "tools_used": [],
                        "message": "logical_calculations中未包含需要统计工具的计算要求"
                    }
                else:
                    return {
                        "success": True,
                        "calculation_result": {},
                        "calculation_summary": "已尝试执行统计计算，但未获得有效结果",
                        "tools_used": [],
                        "message": "可能需要检查数据格式或逻辑计算规则"
                    }
            
            # 生成计算摘要
            calculation_summary = f"已执行 {len(tools_executed)} 个统计工具: {', '.join([self.available_tools[t]['name'] for t in tools_executed])}"
            
            # 步骤6: 解读统计结果
            interpretation_result = self._interpret_statistics_results(
                query=query,
                logical_calculations=logical_calculations,
                statistics_results=statistics_results,
                tools_used=tools_executed,
                columns_desc=columns_desc
            )
            
            return {
                "success": True,
                "calculation_result": statistics_results,
                "calculation_summary": calculation_summary,
                "tools_used": tools_executed,
                "interpretation": interpretation_result,  # 添加解读结果
                "columns_info": {
                    "numeric_cols": numeric_cols,
                    "string_cols": string_cols,
                    "datetime_cols": datetime_cols
                }
            }
                
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            return {
                "success": False,
                "error": f"逻辑计算执行失败: {str(e)}",
                "traceback": error_traceback
            }
    
    def _select_statistics_tools_from_requirements(self, logical_calculations: List[Dict[str, Any]],
                                                   columns_desc: List[str], columns_types: List[str]) -> List[str]:
        """
        根据逻辑计算规则中明确提到的计算要求选择合适的统计工具（不扩展）
        
        Args:
            logical_calculations: 逻辑计算规则列表
            columns_desc: 列描述列表
            columns_types: 列类型列表
            
        Returns:
            选择的统计工具名称列表（只基于logical_calculations中明确提到的要求）
        """
        if not logical_calculations:
            return []
        
        selected_tools = []
        
        # 分析 logical_calculations 中明确提到的计算要求
        for calc in logical_calculations:
            logical_operation = calc.get("logical_operation", "").lower()
            description = calc.get("description", "").lower()
            operands = calc.get("operands", [])
            
            # 根据逻辑操作和描述，匹配对应的统计工具
            # 只匹配明确提到的计算要求，不做扩展
            
            # 统计总数、计数
            if any(kw in logical_operation or kw in description for kw in ['count', '总数', '数量', '计数', 'sum', '总计']):
                if "descriptive_statistics" not in selected_tools:
                    selected_tools.append("descriptive_statistics")
            
            # 统计平均值、均值
            if any(kw in logical_operation or kw in description for kw in ['mean', 'average', '平均', '均值', 'avg']):
                if "descriptive_statistics" not in selected_tools:
                    selected_tools.append("descriptive_statistics")
            
            # 统计频率、频次
            if any(kw in logical_operation or kw in description for kw in ['frequency', '频率', '频次', '出现次数']):
                if "frequency_analysis" not in selected_tools:
                    selected_tools.append("frequency_analysis")
            
            # 分组统计
            if any(kw in logical_operation or kw in description for kw in ['group', '分组', '类别', 'category', '按']):
                if "grouped_statistics" not in selected_tools:
                    selected_tools.append("grouped_statistics")
            
            # 相关性分析
            if any(kw in logical_operation or kw in description for kw in ['correlation', '相关', '关联', 'correlate']):
                if "correlation_analysis" not in selected_tools:
                    selected_tools.append("correlation_analysis")
            
            # 分布分析
            if any(kw in logical_operation or kw in description for kw in ['distribution', '分布', 'distribute']):
                if "distribution_analysis" not in selected_tools:
                    selected_tools.append("distribution_analysis")
            
            # 趋势分析
            if any(kw in logical_operation or kw in description for kw in ['trend', '趋势', '变化率']):
                if "trend_analysis" not in selected_tools:
                    selected_tools.append("trend_analysis")
            
            # 时间序列分析
            if any(kw in logical_operation or kw in description for kw in ['time series', '时间序列', '时序']):
                if "time_series_analysis" not in selected_tools:
                    selected_tools.append("time_series_analysis")
        
        # 如果没有匹配到任何工具，说明logical_calculations中没有明确提到需要统计计算
        # 返回空列表，表示不需要执行统计计算
        return selected_tools
    
    def _interpret_statistics_results(self, query: str, logical_calculations: List[Dict[str, Any]],
                                     statistics_results: Dict[str, Any], tools_used: List[str],
                                     columns_desc: List[str]) -> Dict[str, Any]:
        """
        解读统计结果
        
        Args:
            query: 用户查询
            logical_calculations: 逻辑计算规则列表
            statistics_results: 统计结果字典
            tools_used: 使用的工具列表
            columns_desc: 列描述列表
            
        Returns:
            解读结果，包含：
            - interpretation_summary: 解读摘要
            - key_insights: 关键洞察
            - detailed_interpretation: 详细解读
        """
        try:
            if not statistics_results:
                return {
                    "interpretation_summary": "暂无统计结果需要解读",
                    "key_insights": [],
                    "detailed_interpretation": ""
                }
            
            # 构建统计结果摘要（限制大小，避免提示过长）
            stats_summary = {}
            for tool_name, tool_result in statistics_results.items():
                # 只保留关键信息，避免数据过大
                if tool_name == "descriptive_statistics":
                    # 描述性统计：只保留每个列的关键指标
                    stats_summary[tool_name] = {}
                    for col_name, col_stats in tool_result.items():
                        stats_summary[tool_name][col_name] = {
                            "count": col_stats.get("count"),
                            "mean": col_stats.get("mean"),
                            "median": col_stats.get("median"),
                            "std": col_stats.get("std"),
                            "min": col_stats.get("min"),
                            "max": col_stats.get("max")
                        }
                elif tool_name == "frequency_analysis":
                    # 频率分析：只保留前5个最常见的值
                    stats_summary[tool_name] = {}
                    for col_name, col_stats in tool_result.items():
                        freq = col_stats.get("frequency", {})
                        top_5 = dict(list(freq.items())[:5]) if isinstance(freq, dict) else {}
                        stats_summary[tool_name][col_name] = {
                            "unique_count": col_stats.get("unique_count"),
                            "total_count": col_stats.get("total_count"),
                            "top_5_frequency": top_5
                        }
                elif tool_name == "grouped_statistics":
                    # 分组统计：只保留前3个组的信息
                    stats_summary[tool_name] = {}
                    for group_col, group_data in tool_result.items():
                        group_sizes = group_data.get("group_sizes", {})
                        top_3_groups = dict(list(group_sizes.items())[:3]) if isinstance(group_sizes, dict) else {}
                        stats_summary[tool_name][group_col] = {
                            "unique_groups": group_data.get("unique_groups"),
                            "top_3_groups": top_3_groups,
                            "has_statistics": bool(group_data.get("statistics"))
                        }
                else:
                    # 其他统计类型：保留基本信息
                    stats_summary[tool_name] = {
                        "result_type": tool_name,
                        "has_data": bool(tool_result)
                    }
            
            # 构建逻辑计算规则描述
            logical_calcs_str = json.dumps(logical_calculations, ensure_ascii=False, indent=2)
            # 转义花括号以避免被模板引擎解析
            logical_calcs_str_escaped = logical_calcs_str.replace("{", "{{").replace("}", "}}")
            
            # 构建列信息
            columns_info_str = "\n".join([f"  {i+1}. {desc}" for i, desc in enumerate(columns_desc)])
            
            # 构建工具描述
            tools_description = [self.available_tools[t]['name'] for t in tools_used]
            tools_description_str = ", ".join(tools_description)
            
            system_prompt = """你是一个专业的数据分析解读专家。你的任务是根据用户查询、逻辑计算规则和统计结果，对统计指标进行深入解读。

重要提示：
1. 你已经收到了统计结果，这些结果是通过各种统计工具计算得出的
2. 你需要解读这些统计指标的含义，找出关键洞察
3. 解读应该结合用户查询和逻辑计算规则，说明统计结果如何回答用户的问题
4. 要关注异常值、趋势、分布特征、相关性等重要发现
5. 用通俗易懂的语言解释统计指标的含义

请以JSON格式返回解读结果：
{{
    "interpretation_summary": "解读摘要（2-3句话概括主要发现）",
    "key_insights": [
        "关键洞察1（具体的发现和意义）",
        "关键洞察2",
        ...
    ],
    "detailed_interpretation": "详细解读（逐项解读各类统计指标，说明其含义和发现）"
}}"""

            # 构建统计结果摘要的JSON字符串，并转义花括号以避免被模板引擎解析
            stats_summary_json = json.dumps(stats_summary, ensure_ascii=False, indent=2)
            # 转义花括号：{ -> {{, } -> }}
            stats_summary_json_escaped = stats_summary_json.replace("{", "{{").replace("}", "}}")
            
            user_prompt = f"""**用户查询：**
{query}

**逻辑计算规则：**
{logical_calcs_str_escaped}

**使用的统计工具：**
{tools_description_str}

**列信息（共{len(columns_desc)}列）：**
{columns_info_str}

**统计结果摘要：**
{stats_summary_json_escaped}

请对以上统计结果进行深入解读，重点关注：
1. 各类统计指标的含义和发现
2. 数据分布特征、异常值、趋势等
3. 统计结果如何回答用户查询
4. 关键洞察和业务意义

请以JSON格式返回解读结果。"""

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
                        "interpretation_summary": result.get("interpretation_summary", ""),
                        "key_insights": result.get("key_insights", []),
                        "detailed_interpretation": result.get("detailed_interpretation", ""),
                        "raw_response": response_text
                    }
                except json.JSONDecodeError:
                    # 如果JSON解析失败，返回原始响应
                    return {
                        "interpretation_summary": "统计结果解读完成",
                        "key_insights": [],
                        "detailed_interpretation": response_text,
                        "raw_response": response_text
                    }
            else:
                # 如果没有找到JSON，返回原始响应
                return {
                    "interpretation_summary": "统计结果解读完成",
                    "key_insights": [],
                    "detailed_interpretation": response_text,
                    "raw_response": response_text
                }
                
        except Exception as e:
            import logging
            import traceback
            logging.warning(f"⚠️ 统计结果解读失败: {e}")
            traceback.print_exc()
            return {
                "interpretation_summary": "统计结果解读失败",
                "key_insights": [],
                "detailed_interpretation": f"解读过程出现错误: {str(e)}",
                "error": str(e)
            }
    
    def interpret_final_result(self, query: str, logical_calculations: List[Dict[str, Any]],
                              calculation_result: Dict[str, Any], interpretation: Dict[str, Any],
                              tools_used: List[str], columns_desc: List[str]) -> Dict[str, Any]:
        """
        对最终分析结果进行综合解读
        
        Args:
            query: 用户查询问题
            logical_calculations: 逻辑计算规则列表
            calculation_result: 统计计算结果
            interpretation: 统计结果解读
            tools_used: 使用的工具列表
            columns_desc: 列描述列表
            
        Returns:
            最终综合解读结果
        """
        try:
            # 构建解读提示
            logical_calcs_str = json.dumps(logical_calculations, ensure_ascii=False, indent=2)
            # 转义花括号
            logical_calcs_str_escaped = logical_calcs_str.replace("{", "{{").replace("}", "}}")
            
            # 提取解读摘要
            interpretation_summary = interpretation.get("interpretation_summary", "")
            key_insights = interpretation.get("key_insights", [])
            detailed_interpretation = interpretation.get("detailed_interpretation", "")
            
            # 构建工具描述
            tools_description = ", ".join([self.available_tools.get(t, {}).get('name', t) for t in tools_used])
            
            system_prompt = """你是一个专业的数据分析解读专家。你的任务是对整个逻辑计算流程和最终结果进行综合解读。

**任务目标：**
1. 综合评估逻辑计算流程是否成功回答了用户的问题
2. 总结关键发现和洞察
3. 提供业务建议或下一步行动建议
4. 指出可能存在的局限性或需要注意的事项

请以JSON格式返回综合解读结果：
{{
    "overall_summary": "整体总结（2-3句话概括整个分析过程和主要发现）",
    "question_answer": "问题回答（说明分析结果如何回答用户的问题）",
    "key_findings": [
        "关键发现1",
        "关键发现2",
        ...
    ],
    "business_insights": [
        "业务洞察1（对业务决策的建议）",
        "业务洞察2",
        ...
    ],
    "limitations": "局限性说明（如果有）",
    "next_steps": "下一步建议（如果需要进一步分析）"
}}"""

            user_prompt = f"""**用户查询：**
{query}

**逻辑计算规则：**
{logical_calcs_str_escaped}

**使用的统计工具：**
{tools_description}

**列信息（共{len(columns_desc)}列）：**
{chr(10).join([f"  {i+1}. {desc}" for i, desc in enumerate(columns_desc)])}

**统计结果解读摘要：**
{interpretation_summary}

**关键洞察：**
{chr(10).join([f"{i+1}. {insight}" for i, insight in enumerate(key_insights)]) if key_insights else "无"}

**详细解读：**
{detailed_interpretation}

请对整个逻辑计算流程和最终结果进行综合解读，重点关注：
1. 分析结果是否成功回答了用户的问题
2. 关键发现和业务价值
3. 可能的局限性
4. 下一步建议

请以JSON格式返回综合解读结果。"""

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
                        "overall_summary": result.get("overall_summary", ""),
                        "question_answer": result.get("question_answer", ""),
                        "key_findings": result.get("key_findings", []),
                        "business_insights": result.get("business_insights", []),
                        "limitations": result.get("limitations", ""),
                        "next_steps": result.get("next_steps", ""),
                        "raw_response": response_text
                    }
                except json.JSONDecodeError:
                    # 如果JSON解析失败，返回原始响应
                    return {
                        "overall_summary": "综合解读完成",
                        "question_answer": response_text,
                        "key_findings": [],
                        "business_insights": [],
                        "limitations": "",
                        "next_steps": "",
                        "raw_response": response_text
                    }
            else:
                # 如果没有找到JSON，返回原始响应
                return {
                    "overall_summary": "综合解读完成",
                    "question_answer": response_text,
                    "key_findings": [],
                    "business_insights": [],
                    "limitations": "",
                    "next_steps": "",
                    "raw_response": response_text
                }
                
        except Exception as e:
            import logging
            import traceback
            logging.warning(f"⚠️ 最终结果解读失败: {e}")
            traceback.print_exc()
            return {
                "overall_summary": "最终结果解读失败",
                "question_answer": f"解读过程出现错误: {str(e)}",
                "key_findings": [],
                "business_insights": [],
                "limitations": "",
                "next_steps": "",
                "error": str(e)
            }

