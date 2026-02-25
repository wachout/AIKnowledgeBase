# -*- coding:utf-8 -*-
"""
关联分析智能体
通过数理统计后，进行关联分析，调用第八个智能体，输出echarts图表
"""

import logging
from typing import Dict, Any, List
from Config.llm_config import get_chat_tongyi
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)


class CorrelationAnalysisAgent:
    """关联分析智能体：进行深度关联分析"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, enable_thinking=False)
    
    def analyze(self, statistics_result: Dict[str, Any],
                data_type_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        进行关联分析
        
        Args:
            statistics_result: 统计计算结果
            data_type_analysis: 数据类型分析结果
            
        Returns:
            关联分析结果
        """
        try:
            result = {
                "correlation_insights": [],
                "strong_correlations": [],
                "recommended_charts": []
            }
            
            # 从统计结果中提取相关性信息
            for sheet_name, sheet_stats in statistics_result.get("calculations", {}).items():
                # 提取相关性分析结果
                correlation_data = sheet_stats.get("correlation_analysis", {})
                
                if correlation_data:
                    # 分析强相关关系
                    strong_corrs = correlation_data.get("strong_correlations", [])
                    result["strong_correlations"].extend([
                        {
                            "sheet": sheet_name,
                            "correlation": corr
                        }
                        for corr in strong_corrs
                    ])
                    
                    # 生成洞察
                    insights = self._generate_correlation_insights(correlation_data, sheet_name)
                    result["correlation_insights"].extend(insights)
                    
                    # 推荐图表
                    charts = self._recommend_charts(correlation_data, sheet_name)
                    result["recommended_charts"].extend(charts)
            
            logger.info(f"✅ 关联分析完成，发现 {len(result['strong_correlations'])} 个强相关关系")
            return result
            
        except Exception as e:
            logger.error(f"❌ 关联分析失败: {e}")
            raise
    
    def _generate_correlation_insights(self, correlation_data: Dict[str, Any], 
                                       sheet_name: str) -> List[str]:
        """生成关联分析洞察"""
        insights = []
        
        strong_corrs = correlation_data.get("strong_correlations", [])
        if strong_corrs:
            insights.append(f"在工作表 '{sheet_name}' 中发现 {len(strong_corrs)} 个强相关关系")
            
            # 分析最强的相关关系
            if len(strong_corrs) > 0:
                top_corr = strong_corrs[0]
                insights.append(
                    f"最强的相关关系是 {top_corr.get('column1', '')} 和 {top_corr.get('column2', '')} "
                    f"(相关系数: {top_corr.get('correlation', 0):.3f})"
                )
        
        return insights
    
    def _recommend_charts(self, correlation_data: Dict[str, Any], 
                         sheet_name: str) -> List[Dict[str, Any]]:
        """推荐图表类型"""
        charts = []
        
        # 如果有相关性矩阵，推荐热力图
        if correlation_data.get("correlation_matrix"):
            charts.append({
                "chart_type": "heatmap",
                "title": f"{sheet_name} - 相关性热力图",
                "data_source": "correlation_matrix",
                "description": "展示所有变量之间的相关性强度"
            })
        
        # 如果有强相关关系，推荐散点图
        strong_corrs = correlation_data.get("strong_correlations", [])
        for corr in strong_corrs[:3]:  # 最多推荐3个
            charts.append({
                "chart_type": "scatter",
                "title": f"{corr.get('column1', '')} vs {corr.get('column2', '')}",
                "data_source": {
                    "x": corr.get("column1"),
                    "y": corr.get("column2")
                },
                "description": f"展示两个变量的相关关系（r={corr.get('correlation', 0):.3f}）"
            })
        
        return charts
