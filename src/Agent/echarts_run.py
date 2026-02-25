import sys
import os
import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd

# Add the parent directory to the Python path to allow importing the agent
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Agent.EchartsAgent.echarts_agent import EchartsAgent, llm
from Agent.EchartsAgent.statistics_analysis_agent import StatisticsAnalysisAgent

def _convert_numpy_types(obj):
    """
    递归地将numpy类型转换为Python原生类型，以便JSON序列化
    
    Args:
        obj: 需要转换的对象
    
    Returns:
        转换后的对象
    """
    try:
        if isinstance(obj, (np.integer, np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float_, np.float16, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: _convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [_convert_numpy_types(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(_convert_numpy_types(item) for item in obj)
        elif isinstance(obj, (pd.Timestamp, np.datetime64)):
            return str(obj)
        elif hasattr(pd, 'api') and hasattr(pd.api, 'types'):
            try:
                if pd.api.types.is_datetime64_any_dtype(type(obj)):
                    return str(obj)
            except:
                pass
        return obj
    except Exception as e:
        # 如果转换失败，尝试直接转换为字符串
        try:
            return str(obj)
        except:
            return obj

# 初始化智能体（全局实例，避免重复创建）
_echarts_agent = None
_statistics_analysis_agent = None

def _get_agents():
    """获取智能体实例（单例模式）"""
    global _echarts_agent, _statistics_analysis_agent
    if _echarts_agent is None:
        _echarts_agent = EchartsAgent(llm_instance=llm)
    if _statistics_analysis_agent is None:
        _statistics_analysis_agent = StatisticsAnalysisAgent(llm_instance=llm)
    return _echarts_agent, _statistics_analysis_agent

def _limit_data_to_top_10(data: Dict[str, Any], max_items: int = 20) -> Dict[str, Any]:
    """
    限制数据到前N个指标（如果指标过多）
    
    Args:
        data: 统计数据字典
        max_items: 最大显示数量，默认20
    
    Returns:
        限制后的数据字典
    """
    if not isinstance(data, dict):
        return data
    
    limited_data = {}
    for key, value in data.items():
        if isinstance(value, dict):
            # 如果是字典，检查是否有需要限制的列表
            limited_value = {}
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, list) and len(sub_value) > max_items:
                    # 限制列表到前N个
                    limited_value[sub_key] = sub_value[:max_items]
                elif isinstance(sub_value, dict):
                    # 如果是字典，递归处理
                    limited_value[sub_key] = _limit_dict_to_top_10(sub_value, max_items)
                else:
                    limited_value[sub_key] = sub_value
            limited_data[key] = limited_value
        elif isinstance(value, list) and len(value) > max_items:
            # 如果是列表，限制到前N个
            limited_data[key] = value[:max_items]
        else:
            limited_data[key] = value
    
    return limited_data

def _limit_dict_to_top_10(data: Dict[str, Any], max_items: int = 10) -> Dict[str, Any]:
    """
    限制字典中的数据到前N个（用于嵌套字典）
    
    Args:
        data: 字典数据
        max_items: 最大显示数量，默认10
    
    Returns:
        限制后的字典
    """
    if not isinstance(data, dict):
        return data
    
    limited_data = {}
    count = 0
    for key, value in data.items():
        if count >= max_items:
            break
        if isinstance(value, (list, dict)):
            # 对于列表或字典，保持原样（在外部处理）
            limited_data[key] = value
        else:
            limited_data[key] = value
        count += 1
    
    return limited_data

def query_echarts(statistics_result, query):
    """
    根据统计指标和用户查询生成ECharts配置和统计分析汇总（并行执行）
    
    Args:
        statistics_result: 统计结果字典，包含各种统计指标
        query: 用户查询，用于了解用户要求的报表格式
    
    Returns:
        包含echarts_config和statistics_summary的字典
    """
    # Initialize agents
    echarts_agent = EchartsAgent(llm_instance=llm)
    statistics_analysis_agent = StatisticsAnalysisAgent(llm_instance=llm)
    
    try:
        # 准备传递给智能体的数据（只包含统计指标）
        statistics_data_str = json.dumps(statistics_result, ensure_ascii=False, indent=2)
        
        # 定义并行执行的函数
        def generate_echarts():
            """生成ECharts配置"""
            try:
                return echarts_agent.generate_echarts_config(statistics_data_str, query)
            except Exception as e:
                print(f"生成ECharts配置失败: {e}")
                traceback.print_exc()
                return {"echarts_config": {}}
        
        def generate_statistics_summary():
            """生成统计分析汇总"""
            try:
                return statistics_analysis_agent.generate_statistics_summary(statistics_data_str, query)
            except Exception as e:
                print(f"生成统计分析汇总失败: {e}")
                traceback.print_exc()
                return {
                    "statistics_summary": {
                        "summary": "统计分析汇总",
                        "key_insights": [],
                        "statistical_characteristics": {
                            "distribution": "",
                            "central_tendency": "",
                            "variability": "",
                            "correlations": "",
                            "trends": "",
                            "group_patterns": ""
                        },
                        "anomalies": "",
                        "statistical_summary": ""
                    }
                }
        
        # 使用线程池并行执行两个智能体
        echarts_result = None
        statistics_summary_result = None
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            echarts_future = executor.submit(generate_echarts)
            statistics_future = executor.submit(generate_statistics_summary)
            
            # 等待两个任务完成
            echarts_result = echarts_future.result()
            statistics_summary_result = statistics_future.result()
        
        print("\n✅ 并行执行完成：ECharts配置和统计分析汇总已生成")
        
        # 返回结果（包含echarts_config和statistics_summary）
        result = {
            "echarts_config": echarts_result.get("echarts_config", {}),
            "statistics_summary": statistics_summary_result.get("statistics_summary", {
                "summary": "",
                "key_insights": [],
                "statistical_characteristics": {},
                "anomalies": "",
                "statistical_summary": ""
            })
        }
        
        return result
    except ValueError as e:
        print(f"\n❌ Error generating Echarts config or statistics summary: {e}")
        return {
            "echarts_config": {},
            "statistics_summary": {
                "summary": "",
                "key_insights": [],
                "statistical_characteristics": {},
                "anomalies": "",
                "statistical_summary": ""
            }
        }
    except json.JSONDecodeError as e:
        print(f"\n❌ Generated output is not valid JSON: {e}")
        return {
            "echarts_config": {},
            "statistics_summary": {
                "summary": "",
                "key_insights": [],
                "statistical_characteristics": {},
                "anomalies": "",
                "statistical_summary": ""
            }
        }
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")
        traceback.print_exc()
        return {
            "echarts_config": {},
            "statistics_summary": {
                "summary": "",
                "key_insights": [],
                "statistical_characteristics": {},
                "anomalies": "",
                "statistical_summary": ""
            }
        }
        
def _generate_echarts_and_summary(statistics_data: Dict[str, Any], query: str, data_type: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """通用的ECharts和统计分析汇总生成函数"""
    echarts_agent, statistics_analysis_agent = _get_agents()
    try:
        limited_data = _limit_data_to_top_10(statistics_data, max_items=20)
        # print("limited_data:", limited_data)
        # 转换numpy类型为Python原生类型
        limited_data = _convert_numpy_types(limited_data)
        # print("converted limited_data:", limited_data)
        statistics_data_str = json.dumps(limited_data, ensure_ascii=False, indent=2)
        def generate_echarts():
            try:
                result = echarts_agent.generate_echarts_config(statistics_data_str, query)
                # 校验：检查返回的 echarts_config 是否为空或无效
                echarts_config = result.get("echarts_config", {})
                if not echarts_config or not isinstance(echarts_config, dict):
                    # 如果 echarts_config 为空或不是字典，返回空对象
                    return {"echarts_config": {}}
                
                # 检查是否有必要的图表组件（至少要有 series 或 title）
                has_series = "series" in echarts_config and echarts_config.get("series")
                has_title = "title" in echarts_config and echarts_config.get("title")
                
                # 如果既没有 series 也没有 title，或者 series 为空列表，返回空对象
                if not has_series and not has_title:
                    return {"echarts_config": {}}
                
                # 如果 series 存在但是空列表，返回空对象
                if has_series and isinstance(echarts_config.get("series"), list) and len(echarts_config.get("series", [])) == 0:
                    return {"echarts_config": {}}
                
                return result
            except Exception as e:
                print(f"生成{data_type}的ECharts配置失败: {e}")
                traceback.print_exc()
                return {"echarts_config": {}}
        def generate_summary():
            try:
                return statistics_analysis_agent.generate_statistics_summary(statistics_data_str, query)
            except Exception as e:
                print(f"生成{data_type}的统计分析汇总失败: {e}")
                traceback.print_exc()
                return {"statistics_summary": {"summary": "", "key_insights": [], "statistical_characteristics": {}, "anomalies": "", "statistical_summary": ""}}
        with ThreadPoolExecutor(max_workers=2) as executor:
            echarts_future = executor.submit(generate_echarts)
            summary_future = executor.submit(generate_summary)
            echarts_result = echarts_future.result()
            summary_result = summary_future.result()
        echarts_config = echarts_result.get("echarts_config", {})
        
        # 最终校验：确保 echarts_config 不为空且有效
        if not echarts_config or not isinstance(echarts_config, dict):
            echarts_config = {}
        else:
            # 检查是否有必要的图表组件
            has_series = "series" in echarts_config and echarts_config.get("series")
            has_title = "title" in echarts_config and echarts_config.get("title")
            
            # 如果既没有 series 也没有 title，或者 series 为空列表，设置为空对象
            if not has_series and not has_title:
                echarts_config = {}
            elif has_series and isinstance(echarts_config.get("series"), list) and len(echarts_config.get("series", [])) == 0:
                echarts_config = {}
        
        statistics_summary = summary_result.get("statistics_summary", {"summary": "", "key_insights": [], "statistical_characteristics": {}, "anomalies": "", "statistical_summary": ""})
        return echarts_config, statistics_summary
    except Exception as e:
        print(f"生成{data_type}的ECharts和统计分析汇总失败: {e}")
        traceback.print_exc()
        return {}, {"summary": "", "key_insights": [], "statistical_characteristics": {}, "anomalies": "", "statistical_summary": ""}

def descriptive_statistics_echarts(descriptive_statistics: Dict[str, Any], query: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """生成描述性统计的ECharts配置和统计分析汇总"""
    return _generate_echarts_and_summary(descriptive_statistics, query, "描述性统计")

def distribution_analysis_echarts(distribution_analysis: Dict[str, Any], query: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """生成分布分析的ECharts配置和统计分析汇总"""
    return _generate_echarts_and_summary(distribution_analysis, query, "分布分析")

def frequency_analysis_echarts(frequency_analysis: Dict[str, Any], query: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """生成频率分析的ECharts配置和统计分析汇总"""
    limited_frequency = {}
    for col, data in frequency_analysis.items():
        if isinstance(data, dict):
            limited_col_data = {}
            if "top_10" in data:
                limited_col_data["top_10"] = dict(list(data["top_10"].items())[:20])
            if "frequency" in data:
                limited_col_data["frequency"] = dict(list(data["frequency"].items())[:20])
            for key, value in data.items():
                if key not in ["top_10", "frequency"]:
                    limited_col_data[key] = value
            limited_frequency[col] = limited_col_data
        else:
            limited_frequency[col] = data
    return _generate_echarts_and_summary(limited_frequency, query, "频率分析")

def text_analysis_echarts(text_analysis: Dict[str, Any], query: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """生成文本分析的ECharts配置和统计分析汇总"""
    limited_text = {}
    for col, data in text_analysis.items():
        if isinstance(data, dict) and "top_keywords" in data:
            limited_col_data = data.copy()
            if isinstance(data["top_keywords"], dict):
                limited_col_data["top_keywords"] = dict(list(data["top_keywords"].items())[:20])
            limited_text[col] = limited_col_data
        else:
            limited_text[col] = data
    return _generate_echarts_and_summary(limited_text, query, "文本分析")

def string_analysis_echarts(string_analysis: Dict[str, Any], query: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """生成字符串分析的ECharts配置和统计分析汇总"""
    return _generate_echarts_and_summary(string_analysis, query, "字符串分析")

def grouped_statistics_echarts(grouped_statistics: Dict[str, Any], query: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """生成分组统计的ECharts配置和统计分析汇总"""
    limited_grouped = {}
    for group_col, data in grouped_statistics.items():
        if isinstance(data, dict):
            limited_group_data = {}
            if "group_sizes" in data:
                limited_group_data["group_sizes"] = dict(list(data["group_sizes"].items())[:20])
            if "statistics" in data and isinstance(data["statistics"], dict):
                limited_stats = {}
                for stat_col, stat_data in data["statistics"].items():
                    if isinstance(stat_data, dict):
                        limited_stat_col_data = {}
                        for stat_key, stat_values in stat_data.items():
                            if isinstance(stat_values, dict):
                                limited_stat_col_data[stat_key] = dict(list(stat_values.items())[:20])
                            else:
                                limited_stat_col_data[stat_key] = stat_values
                        limited_stats[stat_col] = limited_stat_col_data
                    else:
                        limited_stats[stat_col] = stat_data
                limited_group_data["statistics"] = limited_stats
            for key, value in data.items():
                if key not in ["group_sizes", "statistics"]:
                    limited_group_data[key] = value
            limited_grouped[group_col] = limited_group_data
        else:
            limited_grouped[group_col] = data
    return _generate_echarts_and_summary(limited_grouped, query, "分组统计")

def column_correlation_echarts(column_correlation: Dict[str, Any], query: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """生成列相关匹配的ECharts配置和统计分析汇总"""
    limited_correlation = {}
    count = 0
    for key, value in column_correlation.items():
        if count >= 20:
            break
        limited_correlation[key] = value
        count += 1
    return _generate_echarts_and_summary(limited_correlation, query, "列相关匹配")

def column_joint_analysis_echarts(column_joint_analysis: Dict[str, Any], query: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """生成两列联合分析的ECharts配置和统计分析汇总"""
    limited_joint = {}
    for analysis_type, analysis_data in column_joint_analysis.items():
        if isinstance(analysis_data, dict):
            limited_analysis = {}
            count = 0
            for key, value in analysis_data.items():
                if count >= 20:
                    break
                if analysis_type == "joint_frequency" and isinstance(value, dict):
                    if "joint_frequency" in value and isinstance(value["joint_frequency"], list):
                        value["joint_frequency"] = value["joint_frequency"][:20]
                limited_analysis[key] = value
                count += 1
            limited_joint[analysis_type] = limited_analysis
        else:
            limited_joint[analysis_type] = analysis_data
    return _generate_echarts_and_summary(limited_joint, query, "两列联合分析")
