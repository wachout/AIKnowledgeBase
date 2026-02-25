# -*- coding:utf-8 -*-
"""
数理统计智能体
调用数理统计智能体，逻辑计算规则，开始计算数据
计算统计指标后，结合业务语义生成 ECharts 结构数据方便展示
"""

import os
import json
import logging
from typing import Dict, Any, List
from Math.statistics import StatisticsCalculator
from Agent.echarts_run import query_echarts

logger = logging.getLogger(__name__)


class StatisticsCalculationAgent:
    """数理统计智能体：执行统计计算，并生成 ECharts 结构数据"""
    
    def __init__(self):
        # 🎯 统一管理：通过 echarts_run.py 调用 echarts 智能体
        # 不需要初始化 echarts_agent，直接使用 echarts_run.py 中的函数
        pass
    
    def calculate(self, file_info: Dict[str, Any], 
                  statistics_plan: Dict[str, Any],
                  file_understanding_result: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行统计计算，并生成 ECharts 结构数据
        
        Args:
            file_info: 文件信息
            statistics_plan: 统计计算规划
            file_understanding_result: 文件理解结果（用于业务语义）
            
        Returns:
            统计计算结果，包含统计指标和 ECharts 结构数据
        """
        try:
            result = {
                "calculations": {},
                "echarts_structures": {}  # 新增：存储每个工作表的 ECharts 结构
            }
            
            # 为每个工作表创建临时CSV文件并计算统计
            for sheet_name, df in file_info.get("data", {}).items():
                # 创建临时CSV文件
                temp_csv_path = self._save_to_temp_csv(df, file_info["file_path"], sheet_name)
                
                # 获取该工作表的规划
                sheet_plan = self._find_sheet_plan(sheet_name, statistics_plan)
                
                if sheet_plan:
                    # 执行统计计算
                    sheet_result = self._calculate_for_sheet(
                        temp_csv_path, df, sheet_plan
                    )
                    result["calculations"][sheet_name] = sheet_result
                else:
                    # 如果没有规划，执行默认统计
                    sheet_result = self._calculate_default_statistics(temp_csv_path, df)
                    result["calculations"][sheet_name] = sheet_result
                
                # 🎯 结合业务语义生成 ECharts 结构数据（基于统计指标，不是原始数据）
                if sheet_result and not sheet_result.get("error"):
                    echarts_structures = self._generate_echarts_from_indicators(
                        sheet_name,
                        sheet_result,
                        file_understanding_result,
                        file_info
                    )
                    if echarts_structures:
                        result["echarts_structures"][sheet_name] = echarts_structures
            
            logger.info(f"✅ 统计计算完成，共计算 {len(result['calculations'])} 个工作表")
            logger.info(f"✅ 生成 ECharts 结构 {len(result.get('echarts_structures', {}))} 个工作表")
            return result
            
        except Exception as e:
            logger.error(f"❌ 统计计算失败: {e}")
            raise
    
    def _save_to_temp_csv(self, df, original_file_path: str, sheet_name: str) -> str:
        """保存DataFrame到临时CSV文件"""
        import tempfile
        
        temp_dir = "conf/tmp/table_analysis"
        os.makedirs(temp_dir, exist_ok=True)
        
        base_name = os.path.splitext(os.path.basename(original_file_path))[0]
        temp_csv_path = os.path.join(temp_dir, f"{base_name}_{sheet_name}_temp.csv")
        
        df.to_csv(temp_csv_path, index=False, encoding='utf-8')
        return temp_csv_path
    
    def _find_sheet_plan(self, sheet_name: str, statistics_plan: Dict[str, Any]) -> Dict[str, Any]:
        """查找工作表的规划"""
        for plan in statistics_plan.get("statistics_plan", {}).get("sheets_plans", []):
            if plan.get("sheet_name") == sheet_name:
                return plan
        return None
    
    def _calculate_for_sheet(self, csv_path: str, df, sheet_plan: Dict[str, Any]) -> Dict[str, Any]:
        """根据规划执行统计计算"""
        result = {}
        
        try:
            # 初始化统计计算器
            calculator = StatisticsCalculator(csv_path)
            
            # 获取列类型
            columns_types = []
            for col in df.columns:
                if df[col].dtype in ['int64', 'float64']:
                    columns_types.append('numeric')
                else:
                    columns_types.append('text')
            
            # 执行所有统计计算
            all_stats = calculator.calculate_all_statistics(columns_types)
            
            # 根据规划筛选和整理结果
            for calc in sheet_plan.get("calculations", []):
                calc_type = calc.get("calculation_type", "")
                target_cols = calc.get("target_columns", [])
                
                # 根据计算类型提取相应的统计结果
                if "描述性统计" in calc_type or "descriptive" in calc_type.lower():
                    result["descriptive_statistics"] = all_stats.get("descriptive_statistics", {})
                elif "相关性" in calc_type or "correlation" in calc_type.lower():
                    result["correlation_analysis"] = all_stats.get("correlation_analysis", {})
                elif "频率" in calc_type or "frequency" in calc_type.lower():
                    result["frequency_analysis"] = all_stats.get("frequency_analysis", {})
                elif "分组" in calc_type or "grouped" in calc_type.lower():
                    result["grouped_statistics"] = all_stats.get("grouped_statistics", {})
                elif "分布" in calc_type or "distribution" in calc_type.lower():
                    result["distribution_analysis"] = all_stats.get("distribution_analysis", {})
                elif "趋势" in calc_type or "trend" in calc_type.lower():
                    result["trend_analysis"] = all_stats.get("trend_analysis", {})
            
            # 如果没有匹配到，返回所有统计结果
            if not result:
                result = all_stats
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 工作表统计计算失败: {e}")
            return {"error": str(e)}
    
    def _calculate_default_statistics(self, csv_path: str, df) -> Dict[str, Any]:
        """执行默认统计计算"""
        try:
            calculator = StatisticsCalculator(csv_path)
            columns_types = ['numeric' if df[col].dtype in ['int64', 'float64'] else 'text' 
                           for col in df.columns]
            return calculator.calculate_all_statistics(columns_types)
        except Exception as e:
            logger.error(f"❌ 默认统计计算失败: {e}")
            return {"error": str(e)}
    
    def _generate_echarts_from_indicators(self,
                                         sheet_name: str,
                                         statistics_indicators: Dict[str, Any],
                                         file_understanding_result: Dict[str, Any],
                                         file_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        基于统计指标（不是原始数据）结合业务语义生成 ECharts 结构数据
        
        Args:
            sheet_name: 工作表名称
            statistics_indicators: 统计指标（描述性统计、相关性分析等）
            file_understanding_result: 文件理解结果（业务语义）
            file_info: 文件信息
            
        Returns:
            ECharts 结构数据列表
        """
        try:
            echarts_structures = []
            
            # 🎯 精简统计指标：只保留用于生成图表的关键信息
            # 不包含完整的相关性矩阵、完整频率分布等大数据
            simplified_indicators = self._simplify_indicators(statistics_indicators)
            
            # 🎯 验证：确认不包含完整数据矩阵
            if "correlation_analysis" in simplified_indicators:
                corr = simplified_indicators["correlation_analysis"]
                if isinstance(corr, dict) and "correlation_matrix" in corr:
                    logger.error("❌ 错误：精简后的指标仍包含 correlation_matrix！")
                    corr.pop("correlation_matrix", None)
                    logger.warning("⚠️ 已强制移除 correlation_matrix")
            
            if "frequency_analysis" in simplified_indicators:
                freq = simplified_indicators["frequency_analysis"]
                for col_name, freq_data in freq.items():
                    if isinstance(freq_data, dict) and "frequency" in freq_data:
                        logger.error(f"❌ 错误：精简后的指标仍包含完整 frequency 字典！列: {col_name}")
                        freq_data.pop("frequency", None)
                        logger.warning(f"⚠️ 已强制移除完整 frequency 字典")
            
            indicators_str = json.dumps(simplified_indicators, ensure_ascii=False, default=str)
            
            # 🎯 最终验证：确认序列化后的数据不包含 correlation_matrix
            if "correlation_matrix" in indicators_str:
                logger.error("❌ 严重错误：序列化后的指标仍包含 correlation_matrix！")
                # 尝试移除
                indicators_dict = json.loads(indicators_str)
                if "correlation_analysis" in indicators_dict:
                    indicators_dict["correlation_analysis"].pop("correlation_matrix", None)
                indicators_str = json.dumps(indicators_dict, ensure_ascii=False, default=str)
                logger.warning("⚠️ 已从序列化数据中移除 correlation_matrix")
            
            logger.info(f"✅ 步骤4精简后的指标长度: {len(indicators_str)} 字符，不包含 correlation_matrix")
            
            # 如果仍然太大，进一步精简
            if len(indicators_str) > 50000:  # 50KB
                logger.warning(f"⚠️ 统计指标数据仍然过大（{len(indicators_str)}字符），进行进一步精简")
                # 只保留最关键的指标
                ultra_simplified = {}
                # 描述性统计：只保留关键指标
                if "descriptive_statistics" in simplified_indicators:
                    desc = simplified_indicators["descriptive_statistics"]
                    ultra_simplified["descriptive_statistics"] = {
                        col: {k: v for k, v in stats.items() if k in ["mean", "median", "std", "min", "max"]}
                        for col, stats in list(desc.items())[:10]  # 只保留前10列
                    }
                # 相关性分析：只保留强相关关系
                if "correlation_analysis" in simplified_indicators:
                    corr = simplified_indicators["correlation_analysis"]
                    if isinstance(corr, dict) and corr.get("strong_correlations"):
                        ultra_simplified["correlation_analysis"] = {
                            "strong_correlations": corr["strong_correlations"][:10]  # 只保留前10个
                        }
                # 频率分析：只保留 top_10 汇总
                if "frequency_analysis" in simplified_indicators:
                    freq = simplified_indicators["frequency_analysis"]
                    ultra_simplified["frequency_analysis"] = {
                        col: {
                            "unique_count": stats.get("unique_count"),
                            "top_10": stats.get("top_10", {})
                        }
                        for col, stats in list(freq.items())[:5]  # 只保留前5列
                    }
                simplified_indicators = ultra_simplified
                indicators_str = json.dumps(simplified_indicators, ensure_ascii=False, default=str)
                logger.info(f"✅ 进一步精简后长度: {len(indicators_str)} 字符")
            
            # 获取业务语义信息
            business_context = self._extract_business_context(sheet_name, file_understanding_result)
            
            # 1. 描述性统计 -> 柱状图/箱线图
            if "descriptive_statistics" in statistics_indicators:
                query = f"""基于描述性统计指标生成图表，展示各列的统计特征。
业务背景：{business_context}
统计指标已提供，请根据均值、中位数、标准差等指标生成合适的柱状图或箱线图。"""
                
                try:
                    # 🎯 通过 echarts_run.py 调用 echarts 智能体
                    echarts_result = query_echarts(simplified_indicators, query)
                    if echarts_result and echarts_result.get("echarts_config"):
                        echarts_structures.append({
                            "type": "descriptive_statistics",
                            "chart_type": "bar",
                            "title": f"{sheet_name} - 描述性统计",
                            "echarts_config": echarts_result["echarts_config"]
                        })
                except Exception as e:
                    logger.warning(f"⚠️ 生成描述性统计图表失败: {e}")
            
            # 2. 相关性分析 -> 热力图/散点图
            if "correlation_analysis" in statistics_indicators:
                query = f"""基于相关性分析指标生成图表，展示变量间的相关关系。
业务背景：{business_context}
统计指标已提供，请根据相关性矩阵生成热力图或散点图。"""
                
                try:
                    # 🎯 通过 echarts_run.py 调用 echarts 智能体
                    echarts_result = query_echarts(simplified_indicators, query)
                    if echarts_result and echarts_result.get("echarts_config"):
                        echarts_structures.append({
                            "type": "correlation_analysis",
                            "chart_type": "heatmap",
                            "title": f"{sheet_name} - 相关性分析",
                            "echarts_config": echarts_result["echarts_config"]
                        })
                except Exception as e:
                    logger.warning(f"⚠️ 生成相关性分析图表失败: {e}")
            
            # 3. 频率分析 -> 柱状图/饼图
            if "frequency_analysis" in statistics_indicators:
                query = f"""基于频率分析指标生成图表，展示各类别的频率分布。
业务背景：{business_context}
统计指标已提供，请根据频率分布数据生成柱状图或饼图。"""
                
                try:
                    # 🎯 通过 echarts_run.py 调用 echarts 智能体
                    echarts_result = query_echarts(simplified_indicators, query)
                    if echarts_result and echarts_result.get("echarts_config"):
                        echarts_structures.append({
                            "type": "frequency_analysis",
                            "chart_type": "bar",
                            "title": f"{sheet_name} - 频率分布",
                            "echarts_config": echarts_result["echarts_config"]
                        })
                except Exception as e:
                    logger.warning(f"⚠️ 生成频率分析图表失败: {e}")
            
            logger.info(f"✅ 为工作表 {sheet_name} 生成了 {len(echarts_structures)} 个 ECharts 结构")
            return echarts_structures
            
        except Exception as e:
            logger.error(f"❌ 生成 ECharts 结构失败: {e}")
            return []
    
    def _simplify_indicators(self, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """
        精简统计指标，只保留关键信息
        不包含完整的相关性矩阵、完整频率分布等大数据
        """
        simplified = {}
        
        # 保留描述性统计的关键指标
        if "descriptive_statistics" in indicators:
            desc_stats = indicators["descriptive_statistics"]
            simplified["descriptive_statistics"] = {}
            for col, stats in list(desc_stats.items())[:20]:  # 只保留前20列
                if isinstance(stats, dict):
                    simplified["descriptive_statistics"][col] = {
                        k: v for k, v in stats.items() 
                        if k in ["mean", "median", "std", "min", "max", "count", "q25", "q50", "q75"]
                    }
        
        # 保留相关性分析的关键信息 - ⚠️ 不包含 correlation_matrix（可能非常大）
        if "correlation_analysis" in indicators:
            corr_analysis = indicators["correlation_analysis"]
            if isinstance(corr_analysis, dict):
                simplified["correlation_analysis"] = {
                    "strong_correlations": corr_analysis.get("strong_correlations", [])[:20]  # 只保留前20个强相关
                    # 不包含 correlation_matrix，因为它可能非常大（NxN矩阵）
                }
        
        # 保留频率分析的关键信息 - ⚠️ 不包含完整的 frequency 字典
        if "frequency_analysis" in indicators:
            freq_analysis = indicators["frequency_analysis"]
            simplified["frequency_analysis"] = {}
            for col, freq in list(freq_analysis.items())[:10]:  # 只保留前10列
                if isinstance(freq, dict):
                    simplified["frequency_analysis"][col] = {
                        "unique_count": freq.get("unique_count"),
                        "total_count": freq.get("total_count"),
                        "top_10": freq.get("top_10", {})  # 只保留 top_10，不保留完整的 frequency 字典
                    }
        
        # 保留分布分析的关键指标
        if "distribution_analysis" in indicators:
            dist_analysis = indicators["distribution_analysis"]
            simplified["distribution_analysis"] = {}
            for col, dist in list(dist_analysis.items())[:10]:  # 只保留前10列
                if isinstance(dist, dict):
                    simplified["distribution_analysis"][col] = {
                        k: v for k, v in dist.items() 
                        if k in ["skewness", "kurtosis", "distribution_type"]
                    }
        
        return simplified
    
    def _extract_business_context(self, sheet_name: str, file_understanding_result: Dict[str, Any]) -> str:
        """提取业务语义上下文"""
        if not file_understanding_result:
            return f"工作表 {sheet_name} 的数据分析"
        
        key_columns = file_understanding_result.get("key_columns", [])
        user_intent = file_understanding_result.get("user_intent", "")
        
        context_parts = []
        if user_intent:
            context_parts.append(f"用户意图：{user_intent}")
        if key_columns:
            context_parts.append(f"关键列：{', '.join(key_columns[:5])}")
        
        return "；".join(context_parts) if context_parts else f"工作表 {sheet_name} 的数据分析"

