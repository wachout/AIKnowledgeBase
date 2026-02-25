"""
网络搜索工具

用于在互联网上搜索最新信息和资源。
"""

from typing import Dict, Any, Optional, List, TYPE_CHECKING
from datetime import datetime
from .base_tool import (
    BaseTool, ToolResult, QualityAssessment,
    ParameterSchema, ParameterDefinition, ParameterType
)

if TYPE_CHECKING:
    from .tool_evaluator import SearchResultEvaluator


class WebSearchTool(BaseTool):
    """
    网络搜索工具

    用于在互联网上搜索最新信息，支持结果质量评估和来源可信度分析。
    """

    # 已知可信来源及其可信度评分
    TRUSTED_SOURCES = {
        "wikipedia.org": 0.85,
        "github.com": 0.80,
        "stackoverflow.com": 0.80,
        "docs.python.org": 0.90,
        "developer.mozilla.org": 0.90,
        "arxiv.org": 0.85,
        "ieee.org": 0.90,
        "nature.com": 0.90,
        "science.org": 0.90,
    }

    def __init__(
        self,
        search_engine_interface=None,
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
            default=5,
            constraints={"min": 1, "max": 50}
        ))
        schema.add_parameter(ParameterDefinition(
            name="time_range",
            param_type=ParameterType.STRING,
            description="时间范围: day, week, month, year, all",
            required=False,
            default="month",
            constraints={"enum": ["day", "week", "month", "year", "all"]}
        ))
        schema.add_parameter(ParameterDefinition(
            name="language",
            param_type=ParameterType.STRING,
            description="搜索语言",
            required=False,
            default="zh"
        ))
        schema.add_parameter(ParameterDefinition(
            name="safe_search",
            param_type=ParameterType.BOOLEAN,
            description="是否启用安全搜索",
            required=False,
            default=True
        ))

        super().__init__(
            name="web_search",
            description="在互联网上搜索最新信息和资源",
            tool_type="search",
            version=version,
            parameter_schema=schema
        )

        self.search_engine = search_engine_interface
        self._evaluator = evaluator

    def set_evaluator(self, evaluator: 'SearchResultEvaluator'):
        """设置结果评估器"""
        self._evaluator = evaluator

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        执行网络搜索

        Args:
            parameters: 搜索参数
                - query: 搜索查询
                - limit: 返回结果数量限制 (默认5)
                - time_range: 时间范围 (day, week, month, year, all)
                - language: 搜索语言
                - safe_search: 是否启用安全搜索

        Returns:
            搜索结果
        """
        self._record_usage()

        if not self.validate_parameters(parameters, ["query"]):
            return self.create_error_result("Missing required parameter: query")

        query = parameters["query"]
        limit = parameters.get("limit", 5)
        time_range = parameters.get("time_range", "month")
        language = parameters.get("language", "zh")
        safe_search = parameters.get("safe_search", True)

        try:
            # 如果有实际的搜索引擎接口，调用它
            if self.search_engine is not None:
                search_results = self._execute_real_search(
                    query, limit, time_range, language, safe_search
                )
            else:
                # 返回模拟结果
                search_results = self._execute_mock_search(query, limit, time_range)

            # 评估结果质量和可信度
            quality_assessment = self._assess_quality(query, search_results)

            return self.create_success_result(
                search_results,
                metadata={
                    "query": query,
                    "time_range": time_range,
                    "language": language,
                    "safe_search": safe_search
                },
                quality_assessment=quality_assessment
            )

        except Exception as e:
            return self.create_error_result(f"Web search failed: {str(e)}")

    def _execute_real_search(
        self,
        query: str,
        limit: int,
        time_range: str,
        language: str,
        safe_search: bool
    ) -> Dict[str, Any]:
        """执行实际搜索"""
        if hasattr(self.search_engine, 'search'):
            results = self.search_engine.search(
                query=query,
                limit=limit,
                time_range=time_range,
                language=language,
                safe_search=safe_search
            )
            return results

        return self._execute_mock_search(query, limit, time_range)

    def _execute_mock_search(
        self,
        query: str,
        limit: int,
        time_range: str
    ) -> Dict[str, Any]:
        """执行模拟搜索"""
        mock_domains = [
            "example.com", "docs.example.org", "blog.example.net",
            "news.example.io", "research.example.edu"
        ]

        return {
            "query": query,
            "time_range": time_range,
            "total_results": 10,
            "results": [
                {
                    "id": f"web_{i+1}",
                    "title": f"网络搜索结果 {i+1}",
                    "url": f"https://{mock_domains[i % len(mock_domains)]}/result{i+1}",
                    "snippet": f"这是关于 '{query}' 的网络搜索摘要 {i+1}",
                    "source": mock_domains[i % len(mock_domains)],
                    "published_date": f"2024-01-{(i+1):02d}",
                    "relevance_score": 0.85 - i * 0.08
                }
                for i in range(min(limit, 10))
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

        # 计算平均相关性
        relevance_scores = [
            r.get("relevance_score", 0.5) for r in results
        ]
        avg_relevance = sum(relevance_scores) / len(relevance_scores)

        # 计算来源可信度
        source_scores = []
        for result in results:
            url = result.get("url", "")
            source = result.get("source", "")
            trust_score = self._get_source_trust_score(url, source)
            source_scores.append(trust_score)

        avg_trust = sum(source_scores) / len(source_scores) if source_scores else 0.5

        # 计算时效性 (基于发布日期)
        freshness_scores = []
        now = datetime.now()
        for result in results:
            pub_date = result.get("published_date", "")
            freshness = self._calculate_freshness(pub_date, now)
            freshness_scores.append(freshness)

        avg_freshness = sum(freshness_scores) / len(freshness_scores) if freshness_scores else 0.5

        # 综合置信度 = 来源可信度 * 0.6 + 时效性 * 0.4
        confidence = avg_trust * 0.6 + avg_freshness * 0.4

        # 完整性 = 结果数量 / 期望数量
        completeness = min(len(results) / 5.0, 1.0)

        assessment = QualityAssessment(
            relevance_score=avg_relevance,
            confidence_score=confidence,
            completeness_score=completeness,
            assessment_details={
                "results_count": len(results),
                "avg_relevance": avg_relevance,
                "avg_source_trust": avg_trust,
                "avg_freshness": avg_freshness,
                "trusted_sources_count": sum(1 for s in source_scores if s >= 0.8)
            }
        )
        assessment.determine_quality_level()

        return assessment

    def _get_source_trust_score(self, url: str, source: str) -> float:
        """获取来源可信度评分"""
        # 从URL中提取域名
        domain = ""
        if url:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
                # 移除 www. 前缀
                if domain.startswith("www."):
                    domain = domain[4:]
            except Exception:
                domain = source.lower() if source else ""

        # 检查是否为已知可信来源
        for trusted_domain, score in self.TRUSTED_SOURCES.items():
            if trusted_domain in domain:
                return score

        # 默认可信度
        return 0.5

    def _calculate_freshness(self, pub_date: str, now: datetime) -> float:
        """计算内容时效性评分"""
        if not pub_date:
            return 0.5

        try:
            # 尝试解析日期
            if isinstance(pub_date, str):
                # 支持多种日期格式
                for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"]:
                    try:
                        pub_datetime = datetime.strptime(pub_date[:len(fmt)], fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return 0.5

            days_old = (now - pub_datetime).days

            # 时效性评分: 越新越高
            if days_old <= 7:
                return 1.0
            elif days_old <= 30:
                return 0.9
            elif days_old <= 90:
                return 0.7
            elif days_old <= 365:
                return 0.5
            else:
                return 0.3

        except Exception:
            return 0.5

    def add_trusted_source(self, domain: str, trust_score: float):
        """添加可信来源"""
        self.TRUSTED_SOURCES[domain.lower()] = min(max(trust_score, 0.0), 1.0)
