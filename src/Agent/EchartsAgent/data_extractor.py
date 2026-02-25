# -*- coding: utf-8 -*-
"""
统计数据提取器
从统计结果中提取实际的数值数据，用于 ECharts 图表生成
"""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class StatisticsDataExtractor:
    """统计数据提取器：从统计结果中提取图表所需的实际数值数据"""

    @staticmethod
    def extract_chart_data(statistics_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        从统计结果中提取图表数据
        返回包含 xAxis_data 和 series_data 的字典

        Args:
            statistics_result: 统计计算结果

        Returns:
            包含提取数据的字典
        """
        try:
            extracted = {
                "xAxis_data": [],
                "series_data": [],
                "available_data_types": []
            }

            # 从计算结果中提取数据
            calculations = statistics_result.get("calculations", {})

            for sheet_name, sheet_stats in calculations.items():
                if not sheet_stats or isinstance(sheet_stats, dict) and "error" in sheet_stats:
                    continue

                # 1. 从描述性统计中提取数据
                desc_stats = sheet_stats.get("descriptive_statistics", {})
                if desc_stats:
                    extracted["available_data_types"].append("descriptive_statistics")
                    x_data, series_data = StatisticsDataExtractor._extract_from_descriptive(desc_stats)
                    if x_data and series_data:
                        extracted["xAxis_data"].extend(x_data)
                        extracted["series_data"].extend(series_data)

                # 2. 从频率分析中提取数据
                freq_stats = sheet_stats.get("frequency_analysis", {})
                if freq_stats:
                    extracted["available_data_types"].append("frequency_analysis")
                    x_data, series_data = StatisticsDataExtractor._extract_from_frequency(freq_stats)
                    if x_data and series_data:
                        extracted["xAxis_data"].extend(x_data)
                        extracted["series_data"].extend(series_data)

                # 3. 从相关性分析中提取数据（如果有的话）
                corr_stats = sheet_stats.get("correlation_analysis", {})
                if corr_stats and "strong_correlations" in corr_stats:
                    extracted["available_data_types"].append("correlation_analysis")
                    # 相关性数据通常用于热力图，这里可以提取强相关关系的值
                    strong_corrs = corr_stats.get("strong_correlations", [])
                    if strong_corrs:
                        for corr in strong_corrs[:5]:  # 最多提取5个相关关系
                            if isinstance(corr, dict):
                                corr_value = corr.get("correlation", 0)
                                if corr_value != 0:
                                    extracted["series_data"].append(abs(corr_value))

            # 如果没有提取到数据，返回空数据结构
            if not extracted["xAxis_data"] or not extracted["series_data"]:
                logger.warning("⚠️ 未提取到实际数据，不使用示例数据")
                return {
                    "xAxis_data": [],
                    "series_data": [],
                    "available_data_types": [],
                    "note": "无法从统计结果中提取实际数值数据"
                }

            # 限制数据大小
            extracted["xAxis_data"] = extracted["xAxis_data"][:20]  # 最多20个x轴数据点
            extracted["series_data"] = extracted["series_data"][:50]  # 最多50个系列数据点

            logger.info(f"✅ 提取到图表数据: xAxis_data={len(extracted['xAxis_data'])}, series_data={len(extracted['series_data'])}")
            return extracted

        except Exception as e:
            logger.error(f"❌ 数据提取失败: {e}", exc_info=True)
            return {
                "xAxis_data": [],
                "series_data": [],
                "available_data_types": [],
                "note": f"数据提取过程中发生错误: {str(e)}"
            }

    @staticmethod
    def _extract_from_descriptive(desc_stats: Dict[str, Any]) -> tuple:
        """从描述性统计中提取数据"""
        x_data = []
        series_data = []

        for col_name, stats in list(desc_stats.items())[:10]:  # 最多处理10列
            if isinstance(stats, dict):
                mean_val = stats.get("mean")
                median_val = stats.get("median")
                std_val = stats.get("std")

                if mean_val is not None and isinstance(mean_val, (int, float)):
                    x_data.append(col_name)
                    series_data.append(round(mean_val, 2))

                    # 如果有中位数，也添加
                    if median_val is not None and isinstance(median_val, (int, float)):
                        series_data.append(round(median_val, 2))

        return x_data, series_data

    @staticmethod
    def _extract_from_frequency(freq_stats: Dict[str, Any]) -> tuple:
        """从频率分析中提取数据"""
        x_data = []
        series_data = []

        for col_name, freq_data in list(freq_stats.items())[:5]:  # 最多处理5列
            if isinstance(freq_data, dict):
                top_10 = freq_data.get("top_10", {})
                if isinstance(top_10, dict):
                    for key, value in list(top_10.items())[:10]:  # 每个列最多10个值
                        if isinstance(value, (int, float)):
                            x_data.append(f"{col_name}_{key}")
                            series_data.append(value)

        return x_data, series_data

    @staticmethod
    def _extract_from_grouped(grouped_stats: Dict[str, Any]) -> tuple:
        """从分组统计中提取数据"""
        x_data = []
        series_data = []

        # 这里可以根据需要实现分组数据的提取逻辑
        # 目前返回空列表
        return x_data, series_data

    @staticmethod
    def _generate_sample_data() -> Dict[str, Any]:
        """生成示例数据（当无法提取实际数据时使用）"""
        return {
            "xAxis_data": ["A", "B", "C", "D", "E"],
            "series_data": [10, 20, 15, 25, 18],
            "available_data_types": ["sample_data"],
            "note": "使用示例数据，因为无法从统计结果中提取实际数值数据"
        }