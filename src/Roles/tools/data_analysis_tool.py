"""
数据分析工具

用于执行数据分析、统计计算和可视化建议。
"""

from typing import Dict, Any, List, Optional, Union, TYPE_CHECKING
from datetime import datetime
from .base_tool import (
    BaseTool, ToolResult, QualityAssessment,
    ParameterSchema, ParameterDefinition, ParameterType
)

if TYPE_CHECKING:
    pass


class DataAnalysisTool(BaseTool):
    """
    数据分析工具

    用于执行数据分析任务，包括统计分析、相关性分析、趋势分析等。
    """

    # 支持的分析类型
    ANALYSIS_TYPES = [
        "statistics",      # 统计分析
        "correlation",     # 相关性分析
        "trend",          # 趋势分析
        "distribution",   # 分布分析
        "anomaly",        # 异常检测
        "clustering",     # 聚类分析
        "summary"         # 摘要统计
    ]

    def __init__(
        self,
        analysis_engine=None,
        version: str = "1.0.0"
    ):
        # 定义参数模式
        schema = ParameterSchema(version="1.0.0")
        schema.add_parameter(ParameterDefinition(
            name="data",
            param_type=ParameterType.ANY,
            description="要分析的数据 (列表、字典或数据框)",
            required=True
        ))
        schema.add_parameter(ParameterDefinition(
            name="analysis_type",
            param_type=ParameterType.STRING,
            description="分析类型: statistics, correlation, trend, distribution, anomaly, clustering, summary",
            required=True,
            constraints={"enum": DataAnalysisTool.ANALYSIS_TYPES}
        ))
        schema.add_parameter(ParameterDefinition(
            name="options",
            param_type=ParameterType.DICT,
            description="分析选项",
            required=False,
            default={}
        ))
        schema.add_parameter(ParameterDefinition(
            name="columns",
            param_type=ParameterType.LIST,
            description="要分析的列名列表",
            required=False
        ))
        schema.add_parameter(ParameterDefinition(
            name="group_by",
            param_type=ParameterType.STRING,
            description="分组字段",
            required=False
        ))

        super().__init__(
            name="data_analysis",
            description="执行数据分析、统计计算和可视化建议",
            tool_type="analysis",
            version=version,
            parameter_schema=schema
        )

        self.analysis_engine = analysis_engine

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        执行数据分析

        Args:
            parameters: 分析参数
                - data: 要分析的数据
                - analysis_type: 分析类型
                - options: 分析选项
                - columns: 要分析的列名
                - group_by: 分组字段

        Returns:
            分析结果
        """
        self._record_usage()

        if not self.validate_parameters(parameters, ["data", "analysis_type"]):
            return self.create_error_result(
                "Missing required parameters: data and analysis_type"
            )

        data = parameters["data"]
        analysis_type = parameters["analysis_type"]
        options = parameters.get("options", {})
        columns = parameters.get("columns")
        group_by = parameters.get("group_by")

        # 验证分析类型
        if analysis_type not in self.ANALYSIS_TYPES:
            return self.create_error_result(
                f"Invalid analysis_type: {analysis_type}. "
                f"Supported types: {', '.join(self.ANALYSIS_TYPES)}"
            )

        try:
            # 如果有实际的分析引擎，调用它
            if self.analysis_engine is not None:
                analysis_result = self._execute_real_analysis(
                    data, analysis_type, options, columns, group_by
                )
            else:
                # 执行基础分析
                analysis_result = self._execute_basic_analysis(
                    data, analysis_type, options, columns, group_by
                )

            # 生成质量评估
            quality_assessment = self._assess_analysis_quality(
                data, analysis_type, analysis_result
            )

            return self.create_success_result(
                analysis_result,
                metadata={
                    "analysis_type": analysis_type,
                    "data_shape": self._get_data_shape(data)
                },
                quality_assessment=quality_assessment
            )

        except Exception as e:
            return self.create_error_result(f"Data analysis failed: {str(e)}")

    def _execute_real_analysis(
        self,
        data: Any,
        analysis_type: str,
        options: Dict[str, Any],
        columns: Optional[List[str]],
        group_by: Optional[str]
    ) -> Dict[str, Any]:
        """执行实际分析"""
        if hasattr(self.analysis_engine, 'analyze'):
            return self.analysis_engine.analyze(
                data=data,
                analysis_type=analysis_type,
                options=options,
                columns=columns,
                group_by=group_by
            )
        return self._execute_basic_analysis(data, analysis_type, options, columns, group_by)

    def _execute_basic_analysis(
        self,
        data: Any,
        analysis_type: str,
        options: Dict[str, Any],
        columns: Optional[List[str]],
        group_by: Optional[str]
    ) -> Dict[str, Any]:
        """执行基础分析"""
        # 数据预处理
        processed_data = self._preprocess_data(data, columns)

        result = {
            "analysis_type": analysis_type,
            "data_summary": self._get_data_summary(processed_data),
            "timestamp": datetime.now().isoformat()
        }

        if analysis_type == "statistics":
            result["results"] = self._compute_statistics(processed_data)
        elif analysis_type == "correlation":
            result["results"] = self._compute_correlation(processed_data)
        elif analysis_type == "trend":
            result["results"] = self._compute_trend(processed_data)
        elif analysis_type == "distribution":
            result["results"] = self._compute_distribution(processed_data)
        elif analysis_type == "summary":
            result["results"] = self._compute_summary(processed_data)
        else:
            result["results"] = {
                "message": f"Analysis type '{analysis_type}' requires advanced engine",
                "basic_stats": self._compute_statistics(processed_data)
            }

        # 添加可视化建议
        result["visualization_suggestions"] = self._suggest_visualizations(
            analysis_type, processed_data
        )

        return result

    def _preprocess_data(
        self,
        data: Any,
        columns: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """预处理数据"""
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                # 列表字典格式
                if columns:
                    return [{k: row.get(k) for k in columns} for row in data]
                return data
            else:
                # 简单列表
                return [{"value": v} for v in data]
        elif isinstance(data, dict):
            # 单个字典
            return [data]
        else:
            return [{"value": data}]

    def _get_data_shape(self, data: Any) -> Dict[str, Any]:
        """获取数据形状"""
        if isinstance(data, list):
            rows = len(data)
            if data and isinstance(data[0], dict):
                cols = len(data[0])
            else:
                cols = 1
        elif isinstance(data, dict):
            rows = 1
            cols = len(data)
        else:
            rows = 1
            cols = 1

        return {"rows": rows, "columns": cols}

    def _get_data_summary(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取数据摘要"""
        if not data:
            return {"rows": 0, "columns": 0}

        return {
            "rows": len(data),
            "columns": len(data[0]) if data else 0,
            "column_names": list(data[0].keys()) if data else []
        }

    def _compute_statistics(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算统计数据"""
        if not data:
            return {}

        stats = {}
        for key in data[0].keys():
            values = [row.get(key) for row in data if row.get(key) is not None]
            numeric_values = [v for v in values if isinstance(v, (int, float))]

            if numeric_values:
                n = len(numeric_values)
                mean = sum(numeric_values) / n
                sorted_vals = sorted(numeric_values)
                median = sorted_vals[n // 2]
                variance = sum((x - mean) ** 2 for x in numeric_values) / n
                std = variance ** 0.5

                stats[key] = {
                    "count": n,
                    "mean": round(mean, 4),
                    "median": median,
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "std": round(std, 4),
                    "variance": round(variance, 4)
                }
            else:
                stats[key] = {
                    "count": len(values),
                    "unique": len(set(str(v) for v in values)),
                    "type": "categorical"
                }

        return stats

    def _compute_correlation(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算相关性"""
        if not data or len(data) < 2:
            return {"message": "Insufficient data for correlation analysis"}

        # 简化的相关性计算
        numeric_columns = []
        for key in data[0].keys():
            values = [row.get(key) for row in data]
            if all(isinstance(v, (int, float)) for v in values if v is not None):
                numeric_columns.append(key)

        if len(numeric_columns) < 2:
            return {"message": "Need at least 2 numeric columns for correlation"}

        correlations = {}
        for i, col1 in enumerate(numeric_columns):
            for col2 in numeric_columns[i+1:]:
                vals1 = [row.get(col1, 0) for row in data]
                vals2 = [row.get(col2, 0) for row in data]

                # 简化的皮尔逊相关系数
                n = len(vals1)
                mean1 = sum(vals1) / n
                mean2 = sum(vals2) / n

                numerator = sum((v1 - mean1) * (v2 - mean2) for v1, v2 in zip(vals1, vals2))
                denom1 = sum((v - mean1) ** 2 for v in vals1) ** 0.5
                denom2 = sum((v - mean2) ** 2 for v in vals2) ** 0.5

                if denom1 > 0 and denom2 > 0:
                    corr = numerator / (denom1 * denom2)
                else:
                    corr = 0

                correlations[f"{col1}_vs_{col2}"] = round(corr, 4)

        return {"correlations": correlations, "columns": numeric_columns}

    def _compute_trend(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算趋势"""
        if not data:
            return {"message": "No data for trend analysis"}

        trends = {}
        for key in data[0].keys():
            values = [row.get(key) for row in data if row.get(key) is not None]
            numeric_values = [v for v in values if isinstance(v, (int, float))]

            if len(numeric_values) >= 3:
                # 简单的趋势判断
                first_third = sum(numeric_values[:len(numeric_values)//3]) / (len(numeric_values)//3)
                last_third = sum(numeric_values[-len(numeric_values)//3:]) / (len(numeric_values)//3)

                if last_third > first_third * 1.1:
                    trend = "increasing"
                elif last_third < first_third * 0.9:
                    trend = "decreasing"
                else:
                    trend = "stable"

                trends[key] = {
                    "trend": trend,
                    "change_rate": round((last_third - first_third) / first_third * 100, 2) if first_third != 0 else 0
                }

        return {"trends": trends}

    def _compute_distribution(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算分布"""
        if not data:
            return {}

        distributions = {}
        for key in data[0].keys():
            values = [row.get(key) for row in data if row.get(key) is not None]
            numeric_values = [v for v in values if isinstance(v, (int, float))]

            if numeric_values:
                min_val = min(numeric_values)
                max_val = max(numeric_values)
                range_val = max_val - min_val

                if range_val > 0:
                    # 简单的分箱
                    bins = 5
                    bin_size = range_val / bins
                    histogram = [0] * bins

                    for v in numeric_values:
                        bin_idx = min(int((v - min_val) / bin_size), bins - 1)
                        histogram[bin_idx] += 1

                    distributions[key] = {
                        "histogram": histogram,
                        "bin_edges": [min_val + i * bin_size for i in range(bins + 1)],
                        "skewness": "unknown"
                    }
            else:
                # 类别分布
                value_counts = {}
                for v in values:
                    v_str = str(v)
                    value_counts[v_str] = value_counts.get(v_str, 0) + 1
                distributions[key] = {"value_counts": value_counts}

        return distributions

    def _compute_summary(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算综合摘要"""
        return {
            "statistics": self._compute_statistics(data),
            "trends": self._compute_trend(data),
            "insights": self._generate_insights(data)
        }

    def _generate_insights(self, data: List[Dict[str, Any]]) -> List[str]:
        """生成数据洞察"""
        insights = []

        if not data:
            return ["数据集为空"]

        insights.append(f"数据集包含 {len(data)} 条记录")

        stats = self._compute_statistics(data)
        for col, stat in stats.items():
            if isinstance(stat, dict) and "std" in stat:
                cv = stat["std"] / stat["mean"] if stat.get("mean", 0) != 0 else 0
                if cv > 0.5:
                    insights.append(f"'{col}' 列变异系数较大 ({cv:.2f})，数据分散度高")

        return insights

    def _suggest_visualizations(
        self,
        analysis_type: str,
        data: List[Dict[str, Any]]
    ) -> List[str]:
        """建议可视化方式"""
        suggestions = []

        if analysis_type == "statistics":
            suggestions = ["柱状图", "箱线图", "直方图"]
        elif analysis_type == "correlation":
            suggestions = ["热力图", "散点图矩阵"]
        elif analysis_type == "trend":
            suggestions = ["折线图", "面积图", "移动平均图"]
        elif analysis_type == "distribution":
            suggestions = ["直方图", "密度图", "QQ图"]
        elif analysis_type == "clustering":
            suggestions = ["散点图", "树状图", "轮廓图"]
        else:
            suggestions = ["柱状图", "折线图", "散点图"]

        return suggestions

    def _assess_analysis_quality(
        self,
        data: Any,
        analysis_type: str,
        result: Dict[str, Any]
    ) -> QualityAssessment:
        """评估分析质量"""
        data_shape = self._get_data_shape(data)
        rows = data_shape.get("rows", 0)

        # 基于数据量评估完整性
        if rows >= 100:
            completeness = 1.0
        elif rows >= 30:
            completeness = 0.8
        elif rows >= 10:
            completeness = 0.6
        else:
            completeness = 0.3

        # 基于分析结果评估置信度
        results = result.get("results", {})
        if results and not isinstance(results, str):
            confidence = 0.8
        else:
            confidence = 0.5

        # 相关性分析需要足够数据
        if analysis_type == "correlation" and rows < 30:
            confidence *= 0.7

        assessment = QualityAssessment(
            relevance_score=0.9,  # 分析结果通常高度相关
            confidence_score=confidence,
            completeness_score=completeness,
            assessment_details={
                "data_rows": rows,
                "analysis_type": analysis_type,
                "has_results": bool(results)
            }
        )
        assessment.determine_quality_level()

        return assessment
