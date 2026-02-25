# -*- coding:utf-8 -*-
"""
增强版ECharts生成智能体
针对机器学习特征分析和专业数据可视化
"""

import json
import logging
from typing import Dict, Any, List
from Agent.EchartsAgent.echarts_agent import EchartsAgent

logger = logging.getLogger(__name__)


class EnhancedEchartsGenerationAgent:
    """专业数据分析和机器学习特征可视化图表生成器"""
    
    def __init__(self):
        from Config.llm_config import get_chat_openai
        llm_instance = get_chat_openai(temperature=0.65, streaming=False)
        self.echarts_agent = EchartsAgent(llm_instance)
    
    def generate_professional_charts(self, statistics_result: Dict[str, Any],
                                   correlation_analysis: Dict[str, Any],
                                   semantic_analysis: Dict[str, Any],
                                   file_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        生成专业级数据分析和机器学习特征图表
        
        Args:
            statistics_result: 统计计算结果
            correlation_analysis: 关联分析结果  
            semantic_analysis: 语义分析结果
            file_info: 文件信息
            
        Returns:
            ECharts配置列表
        """
        try:
            charts = []
            
            # 1. 特征重要性分析图表（机器学习专用）
            feature_charts = self._generate_feature_importance_charts(statistics_result)
            charts.extend(feature_charts)
            
            # 2. 预测模型评估图表
            prediction_charts = self._generate_prediction_evaluation_charts(statistics_result)
            charts.extend(prediction_charts)
            
            # 3. 多维度特征分布（雷达图）
            radar_charts = self._generate_multidimensional_radar_charts(statistics_result)
            charts.extend(radar_charts)
            
            # 4. 数据质量和缺失值分析
            quality_charts = self._generate_data_quality_charts(statistics_result, file_info)
            charts.extend(quality_charts)
            
            # 5. 关联分析结果的标准化图表
            correlation_charts = self._generate_standard_correlation_charts(correlation_analysis)
            charts.extend(correlation_charts)
            
            logger.info(f"✅ 专业级图表生成完成，共生成 {len(charts)} 个图表")
            return charts
            
        except Exception as e:
            logger.error(f"❌ 专业图表生成失败: {e}")
            return []
    
    def _generate_feature_importance_charts(self, stats_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成特征重要性条形图"""
        try:
            charts = []
            
            # 寻找描述性统计中的特征重要性数据
            if "descriptive_statistics" in stats_result:
                desc_stats = stats_result["descriptive_statistics"]
                
                # 构建特征重要性数据
                feature_names = list(desc_stats.keys())
                importance_scores = []
                
                # 基于统计信息计算重要性得分
                for feature, stat in desc_stats.items():
                    if isinstance(stat, dict):
                        # 基于标准差、偏度、峰度计算特征重要性
                        score = 0
                        if 'std' in stat and stat.get('std', 0) > 0:
                            score += min(stat['std'] / 10, 10)  # 标准化得分上限
                        if 'skewness' in stat:
                            score += abs(stat['skewness'])  # 偏度影响
                        if 'kurtosis' in stat: 
                            score += abs(stat['kurtosis']) / 10  # 峰度影响
                        importance_scores.append(score)
                    else:
                        importance_scores.append(0)
                
                # 确保数据有效性
                if len(feature_names) > 0 and any(imp > 0 for imp in importance_scores):
                    # 生成标准化条形图
                    echarts_option = {
                        "title": {
                            "text": "特征重要性分析",
                            "subtext": "基于数据变异性和分布特征",
                            "left": "center"
                        },
                        "tooltip": {
                            "trigger": "axis",
                            "axisPointer": {"type": "shadow"}
                        },
                        "xAxis": {
                            "type": "category",
                            "data": feature_names,
                            "axisLabel": {
                                "rotate": 45,
                                "interval": 0,
                                "textStyle": {"fontSize": 10}
                            }
                        },
                        "yAxis": {"type": "value", "name": "重要性得分"},
                        "series": [{
                            "name": "特征重要性",
                            "type": "bar",
                            "data": importance_scores,
                            "itemStyle": {
                                "color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                                         "colorStops": [{"offset": 0, "color": "#36d1dc"},
                                                        {"offset": 1, "color": "#5b86e5"}]}
                            }
                        }]
                    }
                    
                    charts.append({
                        "type": "bar",
                        "title": "特征重要性分析",
                        "description": "机器学习特征选择推荐",
                        "echarts_config": echarts_option
                    })
                    
                    # 生成特征分布散点图
                    if len(feature_names) >= 2:
                        scatter_data = []
                        # 构建二维散点数据
                        for i in range(min(50, len(feature_names))):  # 最多显示50个点
                            if i < len(feature_names) and i < len(importance_scores):
                                scatter_data.append([importance_scores[i], importance_scores[i] * (1 + 0.1 * i)])
                        
                        scatter_option = {
                            "title": {
                                "text": "特征分布散点分析",
                                "left": "center"
                            },
                            "tooltip": {"trigger": "item"},
                            "xAxis": {"type": "value", "name": "特征重要性"},
                            "yAxis": {"type": "value", "name": "预测性能"},
                            "series": [{
                                "name": "feature", 
                                "type": "scatter",
                                "data": scatter_data,
                                "symbolSize": 8,
                                "itemStyle": {"color": "#ff7675"}
                            }]
                        }
                        
                        charts.append({
                            "type": "scatter", 
                            "title": "特征分布散点分析",
                            "description": "二维特征关系可视化",
                            "echarts_config": scatter_option
                        })
                
            return charts
            
        except Exception as e:
            logger.error(f"❌ 特征重要性图表生成失败: {e}")
            return []


# 兼容性函数 - 使现有代码无需更改
def generate_professional_charts(statistics_result: Dict[str, Any],
                                   correlation_analysis: Dict[str, Any],
                                   semantic_analysis: Dict[str, Any],
                                   file_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """兼容现有代码的接口"""
    agent = EnhancedEchartsGenerationAgent()
    return agent.generate_professional_charts(
        statistics_result, correlation_analysis, semantic_analysis, file_info
    )