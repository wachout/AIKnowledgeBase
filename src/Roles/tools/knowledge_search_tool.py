"""
知识库搜索工具

用于在知识库中搜索相关信息和文档。
"""

from typing import Dict, Any, Optional, TYPE_CHECKING
from .base_tool import (
    BaseTool, ToolResult, QualityAssessment,
    ParameterSchema, ParameterDefinition, ParameterType
)

if TYPE_CHECKING:
    from .tool_evaluator import SearchResultEvaluator


class KnowledgeSearchTool(BaseTool):
    """
    知识库搜索工具

    用于在知识库中搜索相关信息，支持结果质量评估。
    """

    def __init__(
        self,
        knowledge_base_interface=None,
        evaluator: 'SearchResultEvaluator' = None,
        version: str = "1.0.0"
    ):
        # 定义参数模式
        schema = ParameterSchema(version="1.0.0")
        schema.add_parameter(ParameterDefinition(
            name="query",
            param_type=ParameterType.STRING,
            description="搜索查询字符串",
            required=True
        ))
        schema.add_parameter(ParameterDefinition(
            name="limit",
            param_type=ParameterType.INTEGER,
            description="返回结果数量限制",
            required=False,
            default=10,
            constraints={"min": 1, "max": 100}
        ))
        schema.add_parameter(ParameterDefinition(
            name="filters",
            param_type=ParameterType.DICT,
            description="搜索过滤器",
            required=False,
            default={}
        ))
        schema.add_parameter(ParameterDefinition(
            name="knowledge_id",
            param_type=ParameterType.STRING,
            description="知识库ID",
            required=False
        ))
        schema.add_parameter(ParameterDefinition(
            name="search_type",
            param_type=ParameterType.STRING,
            description="搜索类型: semantic, keyword, hybrid",
            required=False,
            default="hybrid",
            constraints={"enum": ["semantic", "keyword", "hybrid"]}
        ))

        super().__init__(
            name="knowledge_search",
            description="在知识库中搜索相关信息和文档",
            tool_type="search",
            version=version,
            parameter_schema=schema
        )

        self.knowledge_base = knowledge_base_interface
        self._evaluator = evaluator

    def set_evaluator(self, evaluator: 'SearchResultEvaluator'):
        """设置结果评估器"""
        self._evaluator = evaluator

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        执行知识库搜索

        Args:
            parameters: 搜索参数
                - query: 搜索查询
                - limit: 返回结果数量限制 (默认10)
                - filters: 搜索过滤器
                - knowledge_id: 知识库ID
                - search_type: 搜索类型

        Returns:
            搜索结果
        """
        self._record_usage()

        if not self.validate_parameters(parameters, ["query"]):
            return self.create_error_result("Missing required parameter: query")

        query = parameters["query"]
        limit = parameters.get("limit", 10)
        filters = parameters.get("filters", {})
        knowledge_id = parameters.get("knowledge_id")
        search_type = parameters.get("search_type", "hybrid")

        try:
            # 如果有实际的知识库接口，调用它
            if self.knowledge_base is not None:
                search_results = self._execute_real_search(
                    query, limit, filters, knowledge_id, search_type
                )
            else:
                # 返回模拟结果
                search_results = self._execute_mock_search(query, limit)

            # 评估结果质量
            quality_assessment = self._assess_quality(query, search_results)

            return self.create_success_result(
                search_results,
                metadata={
                    "query": query,
                    "limit": limit,
                    "knowledge_id": knowledge_id,
                    "search_type": search_type
                },
                quality_assessment=quality_assessment
            )

        except Exception as e:
            return self.create_error_result(f"Knowledge search failed: {str(e)}")

    def _execute_real_search(
        self,
        query: str,
        limit: int,
        filters: Dict[str, Any],
        knowledge_id: Optional[str],
        search_type: str
    ) -> Dict[str, Any]:
        """执行实际搜索"""
        # 调用实际的知识库搜索接口
        # 这里预留接口，由具体实现填充
        if hasattr(self.knowledge_base, 'search'):
            results = self.knowledge_base.search(
                query=query,
                limit=limit,
                filters=filters,
                knowledge_id=knowledge_id,
                search_type=search_type
            )
            return results

        return self._execute_mock_search(query, limit)

    def _execute_mock_search(self, query: str, limit: int) -> Dict[str, Any]:
        """执行模拟搜索"""
        return {
            "query": query,
            "total_results": min(limit, 5),
            "results": [
                {
                    "id": f"doc_{i+1}",
                    "title": f"相关文档 {i+1}",
                    "content": f"这是关于 '{query}' 的搜索结果 {i+1}",
                    "relevance_score": 0.9 - i * 0.1,
                    "source": f"source_{i+1}",
                    "metadata": {"type": "document"}
                }
                for i in range(min(limit, 5))
            ]
        }

    def _assess_quality(
        self,
        query: str,
        search_results: Dict[str, Any]
    ) -> QualityAssessment:
        """评估搜索结果质量"""
        results = search_results.get("results", [])

        if not results:
            return QualityAssessment(
                relevance_score=0.0,
                confidence_score=0.0,
                completeness_score=0.0,
                quality_level="LOW",
                assessment_details={"reason": "No results found"}
            )

        # 如果有评估器，使用评估器
        if self._evaluator:
            try:
                return self._evaluator.evaluate(query, results)
            except Exception:
                pass

        # 基础评估逻辑
        avg_relevance = sum(
            r.get("relevance_score", 0.5) for r in results
        ) / len(results)

        # 根据结果数量评估完整性
        completeness = min(len(results) / 5.0, 1.0)

        # 根据相关性分布评估置信度
        scores = [r.get("relevance_score", 0.5) for r in results]
        score_variance = sum((s - avg_relevance) ** 2 for s in scores) / len(scores)
        confidence = max(0, 1 - score_variance * 2)

        assessment = QualityAssessment(
            relevance_score=avg_relevance,
            confidence_score=confidence,
            completeness_score=completeness,
            assessment_details={
                "results_count": len(results),
                "avg_relevance": avg_relevance,
                "score_variance": score_variance
            }
        )
        assessment.determine_quality_level()

        return assessment
