# -*- coding:utf-8 -*-
"""
表格文件分析智能体主入口
支持 CSV、XLSX、XLS 文件的智能分析
"""

import os
import pandas as pd
import json
import time
import uuid
import logging
import numpy as np
from typing import Dict, Any, Optional, Generator, List
from pathlib import Path

from Config.llm_config import get_chat_tongyi

# 导入所有工作智能体
from .file_understanding_agent import FileUnderstandingAgent
from .data_type_analysis_agent import DataTypeAnalysisAgent
from .statistics_planning_agent import StatisticsPlanningAgent
from .statistics_calculation_agent import StatisticsCalculationAgent
from .correlation_analysis_agent import CorrelationAnalysisAgent
from .semantic_analysis_agent import SemanticAnalysisAgent
from .result_interpretation_agent import ResultInterpretationAgent

# 🎯 统一管理：通过 echarts_run.py 调用 echarts 智能体
from Agent.echarts_run import query_echarts

# 导入辅助智能体流
from .react_agent import ReActAgent
from .code_act_agent import OHCodeActAgent
from .dummy_react_agent import DummyReactAgent
from .supervision_agent import SupervisionAgent

logger = logging.getLogger(__name__)

# 初始化LLM
llm = get_chat_tongyi(temperature=0.3, enable_thinking=False)


def _convert_to_json_serializable(obj: Any) -> Any:
    """
    将对象转换为JSON可序列化的格式
    处理 pandas/numpy 类型（int64, float64等）
    """
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


def _extract_sheet_indicators(sheet_name: str, sheet_stats: Dict[str, Any]) -> List[str]:
    """
    从工作表的统计结果中提取具体的统计指标用于显示
    返回包含具体数值的指标描述列表
    
    Args:
        sheet_name: 工作表名称
        sheet_stats: 工作表的统计结果
        
    Returns:
        包含具体数值的指标描述列表
    """
    indicators = []
    
    if not sheet_stats or not isinstance(sheet_stats, dict):
        return indicators
    
    # 1. 提取描述性统计指标（包含具体数值）
    if "descriptive_statistics" in sheet_stats:
        desc_stats = sheet_stats["descriptive_statistics"]
        for col_name, stats in list(desc_stats.items())[:5]:  # 前5列
            if isinstance(stats, dict):
                mean_val = stats.get("mean")
                median_val = stats.get("median")
                std_val = stats.get("std")
                min_val = stats.get("min")
                max_val = stats.get("max")
                
                if mean_val is not None:
                    # 格式化数值
                    mean_str = f"{mean_val:.2f}" if isinstance(mean_val, (int, float)) else str(mean_val)
                    median_str = f"{median_val:.2f}" if isinstance(median_val, (int, float)) and median_val is not None else str(median_val) if median_val is not None else "N/A"
                    std_str = f"{std_val:.2f}" if isinstance(std_val, (int, float)) and std_val is not None else str(std_val) if std_val is not None else "N/A"
                    min_str = f"{min_val:.2f}" if isinstance(min_val, (int, float)) and min_val is not None else str(min_val) if min_val is not None else "N/A"
                    max_str = f"{max_val:.2f}" if isinstance(max_val, (int, float)) and max_val is not None else str(max_val) if max_val is not None else "N/A"
                    
                    indicators.append(f"{sheet_name}.{col_name}: 均值={mean_str}, 中位数={median_str}, 标准差={std_str}, 范围=[{min_str}, {max_str}]")
    
    # 2. 提取相关性指标（包含具体相关系数）
    if "correlation_analysis" in sheet_stats:
        corr_analysis = sheet_stats["correlation_analysis"]
        if isinstance(corr_analysis, dict):
            strong_corrs = corr_analysis.get("strong_correlations", [])
            for corr in strong_corrs[:3]:  # 前3个强相关
                if isinstance(corr, dict):
                    var1 = corr.get("variable1", "")
                    var2 = corr.get("variable2", "")
                    corr_value = corr.get("correlation", 0)
                    if var1 and var2 and corr_value is not None:
                        indicators.append(f"{sheet_name}: {var1} ↔ {var2} (r={corr_value:.3f})")
    
    # 3. 提取频率指标（包含top值）
    if "frequency_analysis" in sheet_stats:
        freq_analysis = sheet_stats["frequency_analysis"]
        if isinstance(freq_analysis, dict):
            for col_name, freq in list(freq_analysis.items())[:3]:  # 前3列
                if isinstance(freq, dict):
                    unique_count = freq.get("unique_count")
                    total_count = freq.get("total_count")
                    top_10 = freq.get("top_10", {})
                    
                    if unique_count is not None and total_count is not None:
                        top_value = ""
                        if isinstance(top_10, dict) and top_10:
                            top_item = list(top_10.items())[0]
                            top_value = f", 最高频值={top_item[0]} (出现{top_item[1]}次)"
                        
                        indicators.append(f"{sheet_name}.{col_name}: 唯一值数={unique_count}/{total_count}{top_value}")
    
    # 4. 提取分布指标（包含偏度和峰度）
    if "distribution_analysis" in sheet_stats:
        dist_analysis = sheet_stats["distribution_analysis"]
        if isinstance(dist_analysis, dict):
            for col_name, dist in list(dist_analysis.items())[:3]:  # 前3列
                if isinstance(dist, dict):
                    skewness = dist.get("skewness")
                    kurtosis = dist.get("kurtosis")
                    dist_type = dist.get("distribution_type", "")
                    
                    if skewness is not None or kurtosis is not None:
                        skew_str = f"{skewness:.3f}" if isinstance(skewness, (int, float)) and skewness is not None else "N/A"
                        kurt_str = f"{kurtosis:.3f}" if isinstance(kurtosis, (int, float)) and kurtosis is not None else "N/A"
                        dist_type_str = f", 分布类型={dist_type}" if dist_type else ""
                        indicators.append(f"{sheet_name}.{col_name}: 偏度={skew_str}, 峰度={kurt_str}{dist_type_str}")
    
    return indicators


def _extract_chart_indicators(statistics_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    从统计结果中提取用于生成图表的关键指标
    只保留必要的统计指标，不包含完整的数据矩阵
    
    Args:
        statistics_result: 完整的统计计算结果
        
    Returns:
        精简后的统计指标，只包含用于生成图表的关键信息
    """
    try:
        chart_indicators = {
            "calculations": {}
        }
        
        calculations = statistics_result.get("calculations", {})
        
        for sheet_name, sheet_stats in calculations.items():
            if not sheet_stats or isinstance(sheet_stats, dict) and "error" in sheet_stats:
                continue
            
            simplified_sheet = {}
            
            # 1. 描述性统计 - 只保留关键指标
            if "descriptive_statistics" in sheet_stats:
                desc_stats = sheet_stats["descriptive_statistics"]
                simplified_desc = {}
                for col_name, stats in list(desc_stats.items())[:20]:  # 只保留前20列
                    if isinstance(stats, dict):
                        simplified_desc[col_name] = {
                            k: v for k, v in stats.items() 
                            if k in ["mean", "median", "std", "min", "max", "count", "q25", "q50", "q75"]
                        }
                if simplified_desc:
                    simplified_sheet["descriptive_statistics"] = simplified_desc
            
            # 2. 相关性分析 - 只保留强相关关系，不保留完整矩阵
            if "correlation_analysis" in sheet_stats:
                corr_analysis = sheet_stats["correlation_analysis"]
                if isinstance(corr_analysis, dict):
                    simplified_corr = {
                        "strong_correlations": corr_analysis.get("strong_correlations", [])[:20]  # 只保留前20个强相关
                    }
                    # 不包含 correlation_matrix，因为它可能非常大
                    if simplified_corr.get("strong_correlations"):
                        simplified_sheet["correlation_analysis"] = simplified_corr
            
            # 3. 频率分析 - 只保留 top_10 汇总
            if "frequency_analysis" in sheet_stats:
                freq_analysis = sheet_stats["frequency_analysis"]
                simplified_freq = {}
                for col_name, freq in list(freq_analysis.items())[:10]:  # 只保留前10列
                    if isinstance(freq, dict):
                        simplified_freq[col_name] = {
                            "unique_count": freq.get("unique_count"),
                            "total_count": freq.get("total_count"),
                            "top_10": freq.get("top_10", {})  # 只保留 top_10，不保留完整频率分布
                        }
                if simplified_freq:
                    simplified_sheet["frequency_analysis"] = simplified_freq
            
            # 4. 分布分析 - 只保留关键指标
            if "distribution_analysis" in sheet_stats:
                dist_analysis = sheet_stats["distribution_analysis"]
                if isinstance(dist_analysis, dict):
                    simplified_dist = {}
                    for col_name, dist in list(dist_analysis.items())[:10]:  # 只保留前10列
                        if isinstance(dist, dict):
                            simplified_dist[col_name] = {
                                k: v for k, v in dist.items() 
                                if k in ["skewness", "kurtosis", "distribution_type"]
                            }
                    if simplified_dist:
                        simplified_sheet["distribution_analysis"] = simplified_dist
            
            if simplified_sheet:
                chart_indicators["calculations"][sheet_name] = simplified_sheet
        
        logger.info(f"✅ 提取图表指标完成，精简前工作表数: {len(calculations)}, 精简后: {len(chart_indicators['calculations'])}")
        return chart_indicators
        
    except Exception as e:
        logger.error(f"❌ 提取图表指标失败: {e}")
        # 返回空结果，避免影响主流程
        return {"calculations": {}}


def _create_chunk(_id: str, content: str, created: int, model: str, chunk_type: str = "text") -> Dict[str, Any]:
    """创建chunk的辅助方法"""
    return {
        "id": _id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {
                "content": content,
                "type": chunk_type
            },
            "finish_reason": None
        }]
    }


def read_table_file(file_path: str) -> Dict[str, Any]:
    """
    读取表格文件（CSV、XLSX、XLS）
    
    Args:
        file_path: 文件路径
        
    Returns:
        包含文件信息的字典：
        - file_type: 文件类型 (csv/xlsx/xls)
        - sheets: 工作表列表（Excel文件）
        - data: 数据字典 {sheet_name: DataFrame}
        - columns_info: 列信息 {sheet_name: [列名列表]}
    """
    file_extension = Path(file_path).suffix.lower()
    
    result = {
        "file_type": file_extension[1:],  # 去掉点号
        "sheets": [],
        "data": {},
        "columns_info": {},
        "file_path": file_path
    }
    
    try:
        if file_extension == ".csv":
            # 读取CSV文件
            df = pd.read_csv(file_path, encoding='utf-8')
            result["sheets"] = ["Sheet1"]
            result["data"]["Sheet1"] = df
            result["columns_info"]["Sheet1"] = df.columns.tolist()
            
        elif file_extension in [".xlsx", ".xls"]:
            # 读取Excel文件
            excel_file = pd.ExcelFile(file_path)
            result["sheets"] = excel_file.sheet_names
            
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                result["data"][sheet_name] = df
                result["columns_info"][sheet_name] = df.columns.tolist()
        else:
            raise ValueError(f"不支持的文件类型: {file_extension}")
            
        logger.info(f"✅ 成功读取表格文件: {file_path}, 共 {len(result['sheets'])} 个工作表")
        return result
        
    except Exception as e:
        logger.error(f"❌ 读取表格文件失败: {e}")
        raise


def run_table_analysis_stream(file_path: str, query: str = "", 
                              step_callback: Optional[callable] = None) -> Generator[Dict[str, Any], None, None]:
    """
    运行表格文件分析智能体流程（流式返回）
    
    Args:
        file_path: 表格文件路径（CSV、XLSX、XLS）
        query: 用户查询问题（可选）
        step_callback: 步骤回调函数 step_callback(step_name: str, step_data: Dict[str, Any])
        
    Yields:
        OpenAI格式的流式响应块
    """
    _id = f"table-analysis-{uuid.uuid4().hex[:16]}"
    created = int(time.time())
    model = "table-analysis-model"
    
    def _notify_step(step_name: str, step_data: Dict[str, Any]):
        """通知步骤完成"""
        if step_callback:
            try:
                # 转换 step_data 中的 pandas/numpy 类型为 JSON 可序列化类型
                serializable_data = _convert_to_json_serializable(step_data)
                step_callback(step_name, serializable_data)
            except Exception as e:
                logger.error(f"⚠️ 步骤回调失败 ({step_name}): {e}")
    
    def _supervise_step(step_name: str, step_result: Any, previous_steps: List[Dict[str, Any]], 
                       task_context: Dict[str, Any]) -> Dict[str, Any]:
        """监督步骤执行"""
        try:
            # 准备步骤结果（如果是字典，直接使用；否则包装）
            if isinstance(step_result, dict):
                result_dict = step_result
            else:
                result_dict = {"result": step_result}
            
            # 调用监督智能体
            supervision_result = supervision_agent.supervise_step(
                step_name=step_name,
                step_result=result_dict,
                previous_steps=previous_steps,
                task_context=task_context
            )
            
            supervision_results.append({
                "step": step_name,
                "supervision": supervision_result
            })
            
            # 如果发现问题，记录警告
            overall = supervision_result.get("overall", {})
            if overall.get("status") == "fail":
                logger.error(f"❌ 步骤 {step_name} 监督评估失败: {overall.get('summary')}")
            elif overall.get("status") == "warning":
                logger.warning(f"⚠️ 步骤 {step_name} 监督评估警告: {overall.get('summary')}")
            
            return supervision_result
            
        except Exception as e:
            logger.error(f"❌ 监督检查失败 ({step_name}): {e}")
            return {}
    
    try:
        # 步骤0: 读取文件
        _notify_step("step_0_file_reading", {"status": "started"})
        file_info = read_table_file(file_path)
        _notify_step("step_0_file_reading", {
            "success": True,
            "file_type": file_info["file_type"],
            "sheets_count": len(file_info["sheets"]),
            "sheets": file_info["sheets"]
        })
        
        # 生成初始响应
        yield {
            "id": _id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "content": f"📊 开始分析表格文件: {os.path.basename(file_path)}\n",
                    "type": "text"
                },
                "finish_reason": None
            }]
        }
        
        # 初始化所有智能体
        file_understanding_agent = FileUnderstandingAgent()
        data_type_analysis_agent = DataTypeAnalysisAgent()
        statistics_planning_agent = StatisticsPlanningAgent()
        statistics_calculation_agent = StatisticsCalculationAgent()
        correlation_analysis_agent = CorrelationAnalysisAgent()
        semantic_analysis_agent = SemanticAnalysisAgent()
        result_interpretation_agent = ResultInterpretationAgent()
        # 🎯 统一管理：通过 echarts_run.py 调用 echarts 智能体
        # 不需要初始化 echarts_agent，直接使用 echarts_run.py 中的函数
        
        # 辅助智能体流
        react_agent = ReActAgent(max_iterations=3)
        code_act_agent = OHCodeActAgent()
        dummy_react_agent = DummyReactAgent()
        supervision_agent = SupervisionAgent()  # 🎯 监督智能体
        
        step_results = []
        supervision_results = []  # 存储监督结果
        
        # 初始化变量，避免后续步骤因变量未定义而失败
        file_understanding_result = None
        data_type_analysis_result = None
        statistics_plan_result = None
        statistics_result = None
        correlation_analysis_result = None
        semantic_analysis_result = None
        
        # 任务上下文（用于监督智能体）
        task_context = {
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "query": query,
            "file_info": file_info
        }
        
        # 步骤1: 文件理解智能体
        _notify_step("step_1_file_understanding", {"status": "started"})
        yield _create_chunk(_id, "🔍 步骤1: 文件理解智能体 - 分析文件结构和用户需求\n", created, model)
        
        try:
            file_understanding_result = file_understanding_agent.analyze(file_info, query)
            _notify_step("step_1_file_understanding", {"success": True, "result": file_understanding_result})
            step_results.append({"step": "file_understanding", "success": True})
            
            # 🎯 监督检查
            _supervise_step("file_understanding", file_understanding_result, [], task_context)
            
            yield _create_chunk(_id, f"✅ 完成\n- 识别到 {len(file_understanding_result.get('key_columns', []))} 个关键列\n", created, model)
        except Exception as e:
            _notify_step("step_1_file_understanding", {"success": False, "error": str(e)})
            step_results.append({"step": "file_understanding", "success": False, "error": str(e)})
            yield _create_chunk(_id, f"❌ 失败: {str(e)}\n", created, model)
        
        # 步骤2: 数据类型分析智能体
        _notify_step("step_2_data_type_analysis", {"status": "started"})
        yield _create_chunk(_id, "\n📊 步骤2: 数据类型分析智能体 - 分析列的数据类型和数据量\n", created, model)
        
        try:
            data_type_analysis_result = data_type_analysis_agent.analyze(file_info)
            _notify_step("step_2_data_type_analysis", {"success": True, "result": data_type_analysis_result})
            step_results.append({"step": "data_type_analysis", "success": True})
            
            # 🎯 监督检查
            _supervise_step("data_type_analysis", data_type_analysis_result, step_results, task_context)
            
            total_cols = sum(len(s.get("columns_analysis", [])) for s in data_type_analysis_result.get("sheets_analysis", []))
            yield _create_chunk(_id, f"✅ 完成\n- 共分析 {total_cols} 个列\n", created, model)
        except Exception as e:
            _notify_step("step_2_data_type_analysis", {"success": False, "error": str(e)})
            step_results.append({"step": "data_type_analysis", "success": False, "error": str(e)})
            yield _create_chunk(_id, f"❌ 失败: {str(e)}\n", created, model)
        
        # 步骤3: 统计计算规划智能体
        _notify_step("step_3_statistics_planning", {"status": "started"})
        yield _create_chunk(_id, "\n📋 步骤3: 统计计算规划智能体 - 规划统计计算方案\n", created, model)
        
        try:
            if file_understanding_result and data_type_analysis_result:
                statistics_plan_result = statistics_planning_agent.plan(
                    file_understanding_result, data_type_analysis_result
                )
                _notify_step("step_3_statistics_planning", {"success": True, "result": statistics_plan_result})
                step_results.append({"step": "statistics_planning", "success": True})

                # 🎯 监督检查
                _supervise_step("statistics_planning", statistics_plan_result, step_results, task_context)

                plans_count = len(statistics_plan_result.get("statistics_plan", {}).get("sheets_plans", []))
                yield _create_chunk(_id, f"✅ 完成\n- 为 {plans_count} 个工作表制定了统计计划\n", created, model)
            else:
                raise ValueError("缺少前置步骤结果（文件理解或数据类型分析）")
        except Exception as e:
            logger.error(f"❌ 统计计算规划失败: {e}", exc_info=True)
            _notify_step("step_3_statistics_planning", {"success": False, "error": str(e)})
            step_results.append({"step": "statistics_planning", "success": False, "error": str(e)})
            yield _create_chunk(_id, f"❌ 失败: {str(e)}\n", created, model)
            # 创建默认规划，以便后续步骤可以继续
            statistics_plan_result = {
                "statistics_plan": {
                    "overall_strategy": "默认统计策略",
                    "sheets_plans": []
                },
                "recommendations": []
            }
        
        # 步骤4: 数理统计智能体
        _notify_step("step_4_statistics_calculation", {"status": "started"})
        yield _create_chunk(_id, "\n🔢 步骤4: 数理统计智能体 - 执行统计计算\n", created, model)
        
        try:
            if statistics_plan_result:
                # 🎯 传递 file_understanding_result 用于业务语义
                statistics_result = statistics_calculation_agent.calculate(
                    file_info,
                    statistics_plan_result,
                    file_understanding_result
                )

                # 🎯 监督检查
                _supervise_step("statistics_calculation", statistics_result, step_results, task_context)

                # 🎯 数据验证：检查统计计算结果
                calculations = statistics_result.get("calculations", {})
                calc_count = len(calculations)

                # 🎯 检查是否生成了 ECharts 结构
                echarts_structures = statistics_result.get("echarts_structures", {})
                if echarts_structures:
                    echarts_count = sum(len(structs) for structs in echarts_structures.values())
                    logger.info(f"✅ 步骤4生成了 {echarts_count} 个 ECharts 结构")
                    yield _create_chunk(_id, f"- 生成了 {echarts_count} 个 ECharts 结构数据\n", created, model)

                success_message = f"✅ 完成\n- 完成了 {calc_count} 个工作表的统计计算\n"

                if calc_count == 0:
                    logger.warning("⚠️ 统计计算结果为空，calculations 字典为空")
                    yield _create_chunk(_id, "⚠️ 警告：统计计算结果为空\n", created, model)
                else:
                    # 🎯 提取并显示具体的统计指标（不能空显示描述）
                    indicators_summary = []
                    empty_count = 0

                    for sheet_name, sheet_stats in calculations.items():
                        if not sheet_stats or (isinstance(sheet_stats, dict) and len(sheet_stats) == 0):
                            empty_count += 1
                            logger.warning(f"⚠️ 工作表 {sheet_name} 的统计结果为空")
                        elif isinstance(sheet_stats, dict) and "error" in sheet_stats:
                            empty_count += 1
                            logger.error(f"❌ 工作表 {sheet_name} 统计计算出错: {sheet_stats.get('error')}")
                        else:
                            # 🎯 记录每个工作表包含的统计类型
                            stat_types = list(sheet_stats.keys()) if isinstance(sheet_stats, dict) else []
                            logger.info(f"✅ 工作表 {sheet_name} 统计计算完成，包含统计类型: {', '.join(stat_types)}")

                            # 🎯 提取具体的统计指标数值用于显示
                            sheet_indicators = _extract_sheet_indicators(sheet_name, sheet_stats)
                            if sheet_indicators:
                                indicators_summary.extend(sheet_indicators)

                    if empty_count == calc_count:
                        logger.error("❌ 所有工作表的统计结果都为空或出错")
                        success_message = f"⚠️ 部分完成\n- {calc_count} 个工作表中所有统计都失败\n"
                    elif empty_count > 0:
                        logger.warning(f"⚠️ {empty_count}/{calc_count} 个工作表的统计结果为空或出错")
                        success_message = f"⚠️ 部分完成\n- {calc_count - empty_count}/{calc_count} 个工作表统计成功\n"

                    # 🎯 输出具体的统计指标（包含数据依据）
                    if indicators_summary:
                        yield _create_chunk(_id, f"\n📊 关键统计指标：\n", created, model)
                        for indicator in indicators_summary[:10]:  # 最多显示10个关键指标
                            yield _create_chunk(_id, f"- {indicator}\n", created, model)

                # 🎯 成功通知和记录
                _notify_step("step_4_statistics_calculation", {"success": True, "result": statistics_result})
                step_results.append({"step": "statistics_calculation", "success": True})

                yield _create_chunk(_id, success_message, created, model)
            else:
                raise ValueError("缺少统计计算规划结果")
        except Exception as e:
            logger.error(f"❌ 统计计算失败: {e}", exc_info=True)
            _notify_step("step_4_statistics_calculation", {"success": False, "error": str(e)})
            step_results.append({"step": "statistics_calculation", "success": False, "error": str(e)})
            yield _create_chunk(_id, f"❌ 失败: {str(e)}\n", created, model)
            # 创建默认结果，以便后续步骤可以继续
            statistics_result = {"calculations": {}}
        
        # 步骤5: 关联分析智能体
        _notify_step("step_5_correlation_analysis", {"status": "started"})
        yield _create_chunk(_id, "\n🔗 步骤5: 关联分析智能体 - 进行关联分析\n", created, model)
        
        try:
            if statistics_result and data_type_analysis_result:
                correlation_analysis_result = correlation_analysis_agent.analyze(
                    statistics_result, data_type_analysis_result
                )
                _notify_step("step_5_correlation_analysis", {"success": True, "result": correlation_analysis_result})
                step_results.append({"step": "correlation_analysis", "success": True})

                # 🎯 监督检查
                _supervise_step("correlation_analysis", correlation_analysis_result, step_results, task_context)

                strong_corrs = len(correlation_analysis_result.get("strong_correlations", []))
                yield _create_chunk(_id, f"✅ 完成\n- 发现 {strong_corrs} 个强相关关系\n", created, model)
            else:
                raise ValueError("缺少前置步骤结果（统计计算或数据类型分析）")
        except Exception as e:
            logger.error(f"❌ 关联分析失败: {e}", exc_info=True)
            _notify_step("step_5_correlation_analysis", {"success": False, "error": str(e)})
            step_results.append({"step": "correlation_analysis", "success": False, "error": str(e)})
            yield _create_chunk(_id, f"❌ 失败: {str(e)}\n", created, model)
            # 创建默认结果
            correlation_analysis_result = {"strong_correlations": [], "moderate_correlations": []}
        
        # 步骤6: 语义分析智能体
        _notify_step("step_6_semantic_analysis", {"status": "started"})
        yield _create_chunk(_id, "\n🧠 步骤6: 语义分析智能体 - 理解列的语义并进行深度分析\n", created, model)
        
        try:
            if (file_understanding_result and data_type_analysis_result and 
                statistics_result and correlation_analysis_result):
                semantic_analysis_result = semantic_analysis_agent.analyze(
                    file_understanding_result,
                    data_type_analysis_result,
                    statistics_result,
                    correlation_analysis_result
                )
                _notify_step("step_6_semantic_analysis", {"success": True, "result": semantic_analysis_result})
                step_results.append({"step": "semantic_analysis", "success": True})

                # 🎯 监督检查
                _supervise_step("semantic_analysis", semantic_analysis_result, step_results, task_context)

                patterns = len(semantic_analysis_result.get("semantic_analysis", {}).get("business_patterns", []))
                yield _create_chunk(_id, f"✅ 完成\n- 识别了 {patterns} 个业务模式\n", created, model)
            else:
                raise ValueError("缺少前置步骤结果")
        except Exception as e:
            logger.error(f"❌ 语义分析失败: {e}", exc_info=True)
            _notify_step("step_6_semantic_analysis", {"success": False, "error": str(e)})
            step_results.append({"step": "semantic_analysis", "success": False, "error": str(e)})
            yield _create_chunk(_id, f"❌ 失败: {str(e)}\n", created, model)
            # 创建默认结果
            semantic_analysis_result = {"semantic_analysis": {"business_patterns": []}}
        
        # 步骤7: 结果解读智能体
        _notify_step("step_7_result_interpretation", {"status": "started"})
        yield _create_chunk(_id, "\n📝 步骤7: 结果解读智能体 - 综合解读分析结果\n", created, model)
        
        try:
            if (file_understanding_result and data_type_analysis_result and 
                statistics_result and correlation_analysis_result and semantic_analysis_result):
                interpretation_text = result_interpretation_agent.interpret(
                query if query else "分析表格数据",
                file_understanding_result,
                data_type_analysis_result,
                statistics_result,
                correlation_analysis_result,
                semantic_analysis_result
                )
                _notify_step("step_7_result_interpretation", {"success": True, "result": interpretation_text})
                step_results.append({"step": "result_interpretation", "success": True})
                
                # 🎯 监督检查
                _supervise_step("result_interpretation", {"interpretation": interpretation_text}, step_results, task_context)
            
                # 流式输出解读结果
                yield _create_chunk(_id, "✅ 完成\n\n", created, model)
                yield _create_chunk(_id, interpretation_text + "\n\n", created, model)
            else:
                raise ValueError("缺少前置步骤结果")
        except Exception as e:
            logger.error(f"❌ 结果解读失败: {e}", exc_info=True)
            _notify_step("step_7_result_interpretation", {"success": False, "error": str(e)})
            step_results.append({"step": "result_interpretation", "success": False, "error": str(e)})
            yield _create_chunk(_id, f"❌ 失败: {str(e)}\n", created, model)
        
        # 步骤8: ECharts生成智能体（统一使用 EchartsAgent）
        _notify_step("step_8_echarts_generation", {"status": "started"})
        yield _create_chunk(_id, "\n📈 步骤8: ECharts生成智能体 - 生成可视化图表\n", created, model)
        
        try:
            if (statistics_result and correlation_analysis_result and
                semantic_analysis_result):
                # 🎯 数据验证：检查统计结果是否包含实际数据
                calculations = statistics_result.get("calculations", {})
                if not calculations:
                    logger.warning("⚠️ statistics_result.calculations 为空，无法生成图表")
                    yield _create_chunk(_id, "⚠️ 警告：统计计算结果为空，无法生成图表\n", created, model)
                    raise ValueError("统计计算结果为空")
                
                # 检查每个工作表的统计结果是否为空
                empty_sheets = []
                for sheet_name, sheet_stats in calculations.items():
                    if not sheet_stats or (isinstance(sheet_stats, dict) and len(sheet_stats) == 0):
                        empty_sheets.append(sheet_name)
                    elif isinstance(sheet_stats, dict) and "error" in sheet_stats:
                        logger.warning(f"⚠️ 工作表 {sheet_name} 统计计算出错: {sheet_stats.get('error')}")
                        empty_sheets.append(sheet_name)
                
                if len(empty_sheets) == len(calculations):
                    logger.error("❌ 所有工作表的统计结果都为空")
                    yield _create_chunk(_id, "❌ 错误：所有工作表的统计结果都为空，无法生成图表\n", created, model)
                    raise ValueError("所有工作表的统计结果都为空")
                
                if empty_sheets:
                    logger.warning(f"⚠️ 以下工作表的统计结果为空: {', '.join(empty_sheets)}")
                
                charts = []
                
                # 🎯 优先使用步骤4生成的 ECharts 结构（基于统计指标生成，不是原始数据）
                echarts_structures = statistics_result.get("echarts_structures", {})
                if echarts_structures:
                    logger.info(f"✅ 优先使用步骤4生成的 ECharts 结构，共 {sum(len(s) for s in echarts_structures.values())} 个")
                    for sheet_name, structures in echarts_structures.items():
                        for struct in structures:
                            if struct.get("echarts_config"):
                                charts.append({
                                    "type": struct.get("chart_type", "bar"),
                                    "title": struct.get("title", f"{sheet_name} - 图表"),
                                    "description": f"基于统计指标生成（{struct.get('type', 'unknown')}）",
                                    "echarts_config": struct["echarts_config"],
                                    "source": "statistics_calculation"
                                })
                    logger.info(f"✅ 从步骤4添加了 {len(charts)} 个 ECharts 图表")
                
                # 记录已生成的图表标题，避免重复
                existing_titles = {chart.get("title", "") for chart in charts}
                
                # 🎯 提取用于生成图表的关键指标（不包含完整数据矩阵）
                # 只提取统计指标，不包含相关性矩阵、完整频率分布等大数据
                chart_indicators = _extract_chart_indicators(statistics_result)

                # 🎯 检查提取的指标是否包含有效数据
                def _has_valid_chart_data(indicators: Dict[str, Any]) -> bool:
                    """检查图表指标是否包含有效数据"""
                    if not indicators or not isinstance(indicators, dict):
                        return False

                    calculations = indicators.get("calculations", {})
                    if not calculations:
                        return False

                    # 检查是否有任何工作表包含有效数据
                    for sheet_name, sheet_stats in calculations.items():
                        if not sheet_stats or not isinstance(sheet_stats, dict):
                            continue

                        # 检查描述性统计是否有数据
                        desc_stats = sheet_stats.get("descriptive_statistics", {})
                        if desc_stats and isinstance(desc_stats, dict):
                            for col_name, stats in desc_stats.items():
                                if isinstance(stats, dict) and any(stats.get(key) is not None for key in ["mean", "median", "std", "min", "max"]):
                                    return True

                        # 检查相关性分析是否有数据
                        corr_stats = sheet_stats.get("correlation_analysis", {})
                        if corr_stats and isinstance(corr_stats, dict):
                            strong_corrs = corr_stats.get("strong_correlations", [])
                            if strong_corrs and len(strong_corrs) > 0:
                                return True

                        # 检查频率分析是否有数据
                        freq_stats = sheet_stats.get("frequency_analysis", {})
                        if freq_stats and isinstance(freq_stats, dict):
                            for col_name, freq_data in freq_stats.items():
                                if isinstance(freq_data, dict):
                                    total_count = freq_data.get("total_count", 0)
                                    unique_count = freq_data.get("unique_count", 0)
                                    top_10 = freq_data.get("top_10", {})
                                    if total_count > 0 or unique_count > 0 or (top_10 and len(top_10) > 0):
                                        return True

                    return False

                has_valid_data = _has_valid_chart_data(chart_indicators)
                if not has_valid_data:
                    logger.warning("⚠️ 提取的图表指标为空或不包含有效数据，跳过图表生成")
                    # 直接跳转到最终输出，不生成任何图表
                    _notify_step("step_8_echarts_generation", {"success": True, "charts": [], "reason": "no_valid_data"})
                    step_results.append({"step": "echarts_generation", "success": True})

                    yield _create_chunk(_id, f"✅ 完成\n⚠️ 未检测到有效的统计指标数据，跳过图表生成\n", created, model)

                    # 监督智能体检查
                    supervision_result = dummy_react_agent.supervise(
                        f"分析表格文件: {os.path.basename(file_path)}",
                        {"file_info": file_info},
                        step_results
                    )

                    yield _create_chunk(_id, f"\n✅ 表格文件分析完成！进度: {supervision_result.get('progress', 0)*100:.1f}%\n", created, model)

                    # 发送完成标记
                    yield {
                        "id": _id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop"
                        }]
                    }
                    return
                
                # 🎯 验证：确认不包含完整数据矩阵
                for sheet_name, sheet_stats in chart_indicators.get("calculations", {}).items():
                    if "correlation_analysis" in sheet_stats:
                        corr = sheet_stats["correlation_analysis"]
                        if isinstance(corr, dict):
                            if "correlation_matrix" in corr:
                                logger.error(f"❌ 错误：精简后的数据仍包含 correlation_matrix！工作表: {sheet_name}")
                                # 强制移除
                                corr.pop("correlation_matrix", None)
                                logger.warning(f"⚠️ 已强制移除 correlation_matrix")
                            if "strong_correlations" not in corr:
                                logger.warning(f"⚠️ 工作表 {sheet_name} 的相关性分析中没有 strong_correlations")
                    
                    if "frequency_analysis" in sheet_stats:
                        freq = sheet_stats["frequency_analysis"]
                        for col_name, freq_data in freq.items():
                            if isinstance(freq_data, dict) and "frequency" in freq_data:
                                logger.error(f"❌ 错误：精简后的数据仍包含完整 frequency 字典！工作表: {sheet_name}, 列: {col_name}")
                                # 强制移除
                                freq_data.pop("frequency", None)
                                logger.warning(f"⚠️ 已强制移除完整 frequency 字典")
                
                # 🎯 数据序列化：使用 _convert_to_json_serializable 确保数据可序列化
                serializable_indicators = _convert_to_json_serializable(chart_indicators)
                data_str = json.dumps(serializable_indicators, ensure_ascii=False, default=str)
                
                # 🎯 最终验证：确认数据中不包含 correlation_matrix 和完整 frequency
                if "correlation_matrix" in data_str:
                    logger.error("❌ 严重错误：序列化后的数据仍包含 correlation_matrix！")
                    # 尝试移除
                    data_dict = json.loads(data_str)
                    for sheet_stats in data_dict.get("calculations", {}).values():
                        if isinstance(sheet_stats, dict) and "correlation_analysis" in sheet_stats:
                            sheet_stats["correlation_analysis"].pop("correlation_matrix", None)
                    data_str = json.dumps(data_dict, ensure_ascii=False, default=str)
                    logger.warning("⚠️ 已从序列化数据中移除 correlation_matrix")
                
                # 🎯 数据验证：检查序列化后的数据是否为空
                if not data_str or data_str == "{}" or data_str == '{"calculations": {}}':
                    logger.error("❌ 提取的图表指标为空")
                    yield _create_chunk(_id, "❌ 错误：提取的图表指标为空\n", created, model)
                    raise ValueError("提取的图表指标为空")
                
                # 🎯 数据大小检查：如果仍然太大，进一步精简
                if len(data_str) > 50000:  # 50KB（更严格的限制）
                    logger.warning(f"⚠️ 图表指标仍然过大（{len(data_str)}字符），进行进一步精简")
                    # 进一步精简：只保留最关键的指标
                    ultra_simplified = {
                        "calculations": {}
                    }
                    for sheet_name, sheet_stats in chart_indicators.get("calculations", {}).items():
                        ultra_sheet = {}
                        # 只保留描述性统计的关键指标
                        if "descriptive_statistics" in sheet_stats:
                            desc = sheet_stats["descriptive_statistics"]
                            ultra_sheet["descriptive_statistics"] = {
                                col: {k: v for k, v in stats.items() if k in ["mean", "median", "std"]}
                                for col, stats in list(desc.items())[:10]  # 只保留前10列
                            }
                        # 只保留强相关关系
                        if "correlation_analysis" in sheet_stats:
                            corr = sheet_stats["correlation_analysis"]
                            if corr.get("strong_correlations"):
                                ultra_sheet["correlation_analysis"] = {
                                    "strong_correlations": corr["strong_correlations"][:10]  # 只保留前10个
                                }
                        if ultra_sheet:
                            ultra_simplified["calculations"][sheet_name] = ultra_sheet
                    
                    serializable_indicators = _convert_to_json_serializable(ultra_simplified)
                    data_str = json.dumps(serializable_indicators, ensure_ascii=False, default=str)
                    logger.info(f"✅ 进一步精简后长度: {len(data_str)} 字符")
                
                # 🎯 最终确认：记录数据大小和内容摘要
                logger.info(f"📊 准备生成图表，图表指标长度: {len(data_str)} 字符（原始统计结果已精简），工作表数: {len(calculations)}")
                
                # 验证数据内容摘要
                try:
                    data_dict = json.loads(data_str)
                    for sheet_name, sheet_stats in data_dict.get("calculations", {}).items():
                        if "correlation_analysis" in sheet_stats:
                            corr = sheet_stats["correlation_analysis"]
                            has_matrix = "correlation_matrix" in corr if isinstance(corr, dict) else False
                            strong_corr_count = len(corr.get("strong_correlations", [])) if isinstance(corr, dict) else 0
                            logger.info(f"✅ 工作表 {sheet_name} 相关性分析：包含矩阵={has_matrix}，强相关关系数={strong_corr_count}")
                            if has_matrix:
                                logger.error(f"❌ 严重错误：数据中仍包含 correlation_matrix！")
                        if "frequency_analysis" in sheet_stats:
                            freq = sheet_stats["frequency_analysis"]
                            freq_cols = len(freq) if isinstance(freq, dict) else 0
                            logger.info(f"✅ 工作表 {sheet_name} 频率分析：列数={freq_cols}")
                except Exception as e:
                    logger.warning(f"⚠️ 数据验证失败: {e}")
                
                # 1. 🎯 基于统计结果生成智能图表推荐
                # 🎯 性能优化：限制图表生成数量，避免过多 LLM 调用
                # 基于统计结果的类型智能选择图表
                smart_recommendations = []

                # 检查是否有描述性统计
                if any("descriptive_statistics" in sheet_stats for sheet_stats in calculations.values() if sheet_stats):
                    smart_recommendations.append({
                        "title": "描述性统计分析",
                        "description": "展示各列的统计特征",
                        "query": "生成描述性统计的柱状图或箱线图，展示各数值列的均值、中位数、标准差等统计特征",
                        "priority": "high"
                    })

                # 检查是否有相关性分析
                if any("correlation_analysis" in sheet_stats for sheet_stats in calculations.values() if sheet_stats):
                    smart_recommendations.append({
                        "title": "相关性热力图",
                        "description": "展示变量间的相关关系",
                        "query": "生成变量间相关性的热力图，突出显示强相关关系",
                        "priority": "high"
                    })

                # 检查是否有频率分析
                if any("frequency_analysis" in sheet_stats for sheet_stats in calculations.values() if sheet_stats):
                    smart_recommendations.append({
                        "title": "频率分布分析",
                        "description": "展示分类变量的频率分布",
                        "query": "生成分类变量频率分布的柱状图或饼图",
                        "priority": "medium"
                    })

                # 限制为最多2个图表
                selected_recommendations = smart_recommendations[:2]
                logger.info(f"✅ 基于统计结果智能推荐，共 {len(selected_recommendations)} 个图表")

                for rec in selected_recommendations:
                        chart_title = rec.get("title", "图表")
                        # 如果已经存在，跳过
                        if chart_title in existing_titles:
                            logger.info(f"⏭️ 跳过重复图表: {chart_title}（已在步骤4生成）")
                            continue
                        
                        try:
                            # 🎯 使用智能推荐的查询
                            enhanced_query = rec.get("query", "")

                            # 🎯 通过 echarts_run.py 调用 echarts 智能体
                            echarts_result = query_echarts(chart_indicators, enhanced_query)
                            if echarts_result and "echarts_config" in echarts_result:
                                echarts_config = echarts_result["echarts_config"]
                                if echarts_config and isinstance(echarts_config, dict) and len(echarts_config) > 0:
                                    charts.append({
                                        "type": rec.get("chart_type", "bar"),
                                        "title": chart_title,
                                        "description": rec.get("description", ""),
                                        "echarts_config": echarts_config,
                                        "source": "summary_analysis"
                                    })
                                    existing_titles.add(chart_title)
                                    continue
                        except Exception as e:
                            logger.warning(f"⚠️ 调用EChartsAgent生成汇总推荐图表失败: {e}")
                
                # 2. 从关联分析结果生成图表（如果步骤4和汇总分析都没有生成）
                # 🎯 性能优化：只在没有足够图表时才生成关联分析图表
                if len(charts) < 3:  # 如果已有图表少于3个，才生成关联分析图表
                    correlation_charts = correlation_analysis_result.get("recommended_charts", [])[:1]  # 最多1个
                    for chart_rec in correlation_charts:
                        chart_title = chart_rec.get("title", "图表")
                        # 如果已经存在，跳过
                        if chart_title in existing_titles:
                            logger.info(f"⏭️ 跳过重复图表: {chart_title}（已在步骤4生成）")
                            continue
                        try:
                            chart_type = chart_rec.get("chart_type", "")
                            title = chart_rec.get("title", "图表")
                            query = f"生成{title}的{chart_type}图表"

                            # 🎯 通过 echarts_run.py 调用 echarts 智能体
                            echarts_result = query_echarts(chart_indicators, query)
                            if echarts_result and "echarts_config" in echarts_result:
                                echarts_config = echarts_result["echarts_config"]
                                if echarts_config and isinstance(echarts_config, dict) and len(echarts_config) > 0:
                                    charts.append({
                                        "type": chart_type,
                                        "title": title,
                                        "description": chart_rec.get("description", ""),
                                        "echarts_config": echarts_config
                                    })
                                    continue
                        except Exception as e:
                            logger.warning(f"⚠️ 调用EChartsAgent生成推荐图表失败: {e}")

                        # 如果调用失败，返回基本配置
                        charts.append({
                            "type": chart_rec.get("chart_type", ""),
                            "title": chart_rec.get("title", "图表"),
                            "description": chart_rec.get("description", ""),
                            "config": {
                                "chart_type": chart_rec.get("chart_type", ""),
                                "title": chart_rec.get("title", "图表")
                            }
                        })

                # 3. 从语义分析结果生成图表（如果步骤4和汇总分析都没有生成）
                # 🎯 性能优化：只在图表数量不足时才生成语义分析图表
                if len(charts) < 4:  # 如果已有图表少于4个，才生成语义分析图表
                    semantic_analyses = semantic_analysis_result.get("semantic_analysis", {}).get("recommended_analysis", [])[:1]  # 最多1个
                    for analysis_rec in semantic_analyses:
                        chart_type = analysis_rec.get("expected_chart", "bar")
                        title = f"{analysis_rec.get('analysis_type', '分析')} - {', '.join(analysis_rec.get('target_columns', []))}"
                        # 如果已经存在，跳过
                        if title in existing_titles:
                            logger.info(f"⏭️ 跳过重复图表: {title}（已在步骤4生成）")
                            continue

                        try:
                            query = f"生成{title}的{chart_type}图表"

                            # 🎯 通过 echarts_run.py 调用 echarts 智能体
                            echarts_result = query_echarts(chart_indicators, query)
                            if echarts_result and "echarts_config" in echarts_result:
                                echarts_config = echarts_result["echarts_config"]
                                if echarts_config and isinstance(echarts_config, dict) and len(echarts_config) > 0:
                                    charts.append({
                                        "type": chart_type,
                                        "title": title,
                                        "description": analysis_rec.get("reason", ""),
                                        "echarts_config": echarts_config
                                    })
                                    continue
                        except Exception as e:
                            logger.warning(f"⚠️ 调用EChartsAgent生成语义图表失败: {e}")

                        # 如果调用失败，返回基本配置
                        charts.append({
                            "type": analysis_rec.get("expected_chart", "bar"),
                            "title": f"{analysis_rec.get('analysis_type', '分析')} - {', '.join(analysis_rec.get('target_columns', []))}",
                            "description": analysis_rec.get("reason", ""),
                            "config": {
                                "chart_type": analysis_rec.get("expected_chart", "bar"),
                                "title": f"{analysis_rec.get('analysis_type', '分析')} - {', '.join(analysis_rec.get('target_columns', []))}"
                            }
                        })

                # 4. 从统计结果生成默认图表（如果步骤4和汇总分析都没有生成）
                # 🎯 性能优化：只在图表数量不足时才生成默认图表
                if len(charts) < 5:  # 如果已有图表少于5个，才生成默认图表
                    default_sheets = list(statistics_result.get("calculations", {}).items())[:2]  # 最多处理2个工作表
                    for sheet_name, sheet_stats in default_sheets:
                        # 描述性统计 - 柱状图
                        desc_title = f"{sheet_name} - 描述性统计"
                        if desc_title in existing_titles:
                            logger.info(f"⏭️ 跳过重复图表: {desc_title}（已在步骤4生成）")
                        elif "descriptive_statistics" in sheet_stats:
                            try:
                                query = f"生成{sheet_name}的描述性统计柱状图，展示各列的均值、中位数等统计指标"
                                # 🎯 通过 echarts_run.py 调用 echarts 智能体
                                echarts_result = query_echarts(chart_indicators, query)
                                if echarts_result and "echarts_config" in echarts_result:
                                    echarts_config = echarts_result["echarts_config"]
                                    if echarts_config and isinstance(echarts_config, dict) and len(echarts_config) > 0:
                                        charts.append({
                                            "type": "bar",
                                            "title": f"{sheet_name} - 描述性统计",
                                            "description": "展示各列的均值、中位数等统计指标",
                                            "echarts_config": echarts_config
                                        })
                                        continue
                            except Exception as e:
                                logger.warning(f"⚠️ 调用EChartsAgent生成描述性统计图表失败: {e}")

                            charts.append({
                                "type": "bar",
                                "title": f"{sheet_name} - 描述性统计",
                                "description": "展示各列的均值、中位数等统计指标",
                                "config": {
                                    "chart_type": "bar",
                                    "title": f"{sheet_name} - 描述性统计"
                                }
                            })

                        # 相关性分析 - 热力图
                        corr_title = f"{sheet_name} - 相关性热力图"
                        if corr_title in existing_titles:
                            logger.info(f"⏭️ 跳过重复图表: {corr_title}（已在步骤4生成）")
                        elif "correlation_analysis" in sheet_stats:
                            try:
                                query = f"生成{sheet_name}的相关性热力图，展示变量间的相关性"
                                # 🎯 通过 echarts_run.py 调用 echarts 智能体
                                echarts_result = query_echarts(chart_indicators, query)
                                if echarts_result and "echarts_config" in echarts_result:
                                    echarts_config = echarts_result["echarts_config"]
                                    if echarts_config and isinstance(echarts_config, dict) and len(echarts_config) > 0:
                                        charts.append({
                                            "type": "heatmap",
                                            "title": f"{sheet_name} - 相关性热力图",
                                            "description": "展示变量间的相关性",
                                            "echarts_config": echarts_config
                                        })
                                        continue
                            except Exception as e:
                                logger.warning(f"⚠️ 调用EChartsAgent生成相关性热力图失败: {e}")

                            charts.append({
                                "type": "heatmap",
                                "title": f"{sheet_name} - 相关性热力图",
                                "description": "展示变量间的相关性",
                                "config": {
                                    "chart_type": "heatmap",
                                    "title": f"{sheet_name} - 相关性热力图"
                                }
                            })
                
                _notify_step("step_8_echarts_generation", {"success": True, "result": charts})
                step_results.append({"step": "echarts_generation", "success": True})

                # 🎯 监督检查
                _supervise_step("echarts_generation", {"charts": charts, "count": len(charts)}, step_results, task_context)
                
                logger.info(f"✅ ECharts图表生成完成，共生成 {len(charts)} 个图表")
                yield _create_chunk(_id, f"✅ 完成\n- 生成了 {len(charts)} 个图表配置\n", created, model)
                
                # 输出图表配置（以 ECharts 格式）
                if charts:
                    yield _create_chunk(_id, "\n## 📊 生成的图表\n\n", created, model)
                    for i, chart in enumerate(charts, 1):
                        # 先输出图表描述文本
                        chart_desc = f"{i}. **{chart.get('title', '图表')}** ({chart.get('type', 'unknown')})\n"
                        yield _create_chunk(_id, chart_desc, created, model)
                        
                        # 获取图表配置
                        chart_config = chart.get("config", {})
                        echarts_config = chart.get("echarts_config")
                        
                        # 如果已经有完整的 echarts_config，直接使用
                        if echarts_config:
                            echarts_option = echarts_config
                        else:
                            # 否则，从 config 构建基本的 ECharts 配置
                            chart_type = chart.get("type", "bar")
                            title = chart.get("title", "图表")
                            
                            # 构建基本的 ECharts option
                            echarts_option = {
                                "title": {
                                    "text": title,
                                    "left": "center"
                                },
                                "tooltip": {
                                    "trigger": "axis" if chart_type in ["bar", "line"] else "item"
                                },
                                "xAxis": {
                                    "type": "category" if chart_type in ["bar", "line"] else None,
                                    "data": []
                                },
                                "yAxis": {
                                    "type": "value"
                                },
                                "series": [{
                                    "name": title,
                                    "type": chart_type,
                                    "data": []
                                }]
                            }
                        
                        # 将 ECharts 配置转换为 JSON 字符串，使用 option= 格式
                        echarts_json = f"option={json.dumps(echarts_option, ensure_ascii=False)}"
                        
                        # 发送 ECharts chunk（使用 echarts 类型）
                        yield _create_chunk(_id, echarts_json, created, model, chunk_type="echarts")
            else:
                raise ValueError("缺少前置步骤结果")
        except Exception as e:
            logger.error(f"❌ ECharts生成失败: {e}", exc_info=True)
            _notify_step("step_8_echarts_generation", {"success": False, "error": str(e)})
            step_results.append({"step": "echarts_generation", "success": False, "error": str(e)})
            yield _create_chunk(_id, f"❌ 失败: {str(e)}\n", created, model)
        
        # 监督智能体检查
        supervision_result = dummy_react_agent.supervise(
            f"分析表格文件: {os.path.basename(file_path)}",
            {"file_info": file_info},
            step_results
        )
        
        yield _create_chunk(_id, f"\n✅ 表格文件分析完成！进度: {supervision_result.get('progress', 0)*100:.1f}%\n", created, model)
        
        # 发送完成标记
        yield {
            "id": _id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        
    except Exception as e:
        logger.error(f"❌ 表格文件分析失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        error_text = f"❌ 表格文件分析失败: {str(e)}"
        
        yield {
            "id": _id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "content": error_text,
                    "type": "text"
                },
                "finish_reason": "stop"
            }]
        }
