"""
工具结果评估器模块

提供结果质量评估，包括相关性、可信度、完整性评估。
"""

import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ============================================================================
# 质量等级
# ============================================================================

class QualityLevel(Enum):
    """质量等级"""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


# ============================================================================
# 质量指标
# ============================================================================

@dataclass
class QualityMetrics:
    """质量指标数据类"""
    relevance_score: float = 0.0      # 相关性评分 (0-1)
    confidence_score: float = 0.0     # 可信度评分 (0-1)
    completeness_score: float = 0.0   # 完整性评分 (0-1)
    freshness_score: float = 0.0      # 时效性评分 (0-1)
    diversity_score: float = 0.0      # 多样性评分 (0-1)
    accuracy_score: float = 0.0       # 准确性评分 (0-1)

    @property
    def overall_score(self) -> float:
        """计算综合评分"""
        weights = {
            "relevance": 0.30,
            "confidence": 0.25,
            "completeness": 0.20,
            "freshness": 0.10,
            "diversity": 0.05,
            "accuracy": 0.10
        }
        return (
            self.relevance_score * weights["relevance"] +
            self.confidence_score * weights["confidence"] +
            self.completeness_score * weights["completeness"] +
            self.freshness_score * weights["freshness"] +
            self.diversity_score * weights["diversity"] +
            self.accuracy_score * weights["accuracy"]
        )

    @property
    def quality_level(self) -> QualityLevel:
        """确定质量等级"""
        if self.relevance_score >= 0.8 and self.confidence_score >= 0.7:
            return QualityLevel.HIGH
        elif self.relevance_score >= 0.5 and self.confidence_score >= 0.5:
            return QualityLevel.MEDIUM
        elif self.relevance_score > 0 or self.confidence_score > 0:
            return QualityLevel.LOW
        else:
            return QualityLevel.UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relevance_score": self.relevance_score,
            "confidence_score": self.confidence_score,
            "completeness_score": self.completeness_score,
            "freshness_score": self.freshness_score,
            "diversity_score": self.diversity_score,
            "accuracy_score": self.accuracy_score,
            "overall_score": self.overall_score,
            "quality_level": self.quality_level.value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QualityMetrics':
        return cls(
            relevance_score=data.get("relevance_score", 0.0),
            confidence_score=data.get("confidence_score", 0.0),
            completeness_score=data.get("completeness_score", 0.0),
            freshness_score=data.get("freshness_score", 0.0),
            diversity_score=data.get("diversity_score", 0.0),
            accuracy_score=data.get("accuracy_score", 0.0)
        )


# ============================================================================
# 质量阈值
# ============================================================================

@dataclass
class QualityThreshold:
    """质量阈值配置"""
    min_relevance: float = 0.5
    min_confidence: float = 0.5
    min_completeness: float = 0.3
    min_overall: float = 0.5

    def is_satisfied(self, metrics: QualityMetrics) -> bool:
        """检查是否满足阈值"""
        return (
            metrics.relevance_score >= self.min_relevance and
            metrics.confidence_score >= self.min_confidence and
            metrics.completeness_score >= self.min_completeness and
            metrics.overall_score >= self.min_overall
        )

    def get_failing_metrics(self, metrics: QualityMetrics) -> List[str]:
        """获取不满足阈值的指标"""
        failing = []
        if metrics.relevance_score < self.min_relevance:
            failing.append(f"relevance ({metrics.relevance_score:.2f} < {self.min_relevance})")
        if metrics.confidence_score < self.min_confidence:
            failing.append(f"confidence ({metrics.confidence_score:.2f} < {self.min_confidence})")
        if metrics.completeness_score < self.min_completeness:
            failing.append(f"completeness ({metrics.completeness_score:.2f} < {self.min_completeness})")
        if metrics.overall_score < self.min_overall:
            failing.append(f"overall ({metrics.overall_score:.2f} < {self.min_overall})")
        return failing


# ============================================================================
# 评估结果
# ============================================================================

@dataclass
class EvaluationResult:
    """评估结果"""
    metrics: QualityMetrics
    is_satisfactory: bool
    should_expand: bool
    missing_aspects: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    reasoning: str = ""
    evaluated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metrics": self.metrics.to_dict(),
            "is_satisfactory": self.is_satisfactory,
            "should_expand": self.should_expand,
            "missing_aspects": self.missing_aspects,
            "suggestions": self.suggestions,
            "reasoning": self.reasoning,
            "evaluated_at": self.evaluated_at
        }


# ============================================================================
# 评估器基类
# ============================================================================

class ResultQualityEvaluator(ABC):
    """结果质量评估器基类"""

    def __init__(self, threshold: QualityThreshold = None):
        self.threshold = threshold or QualityThreshold()

    @abstractmethod
    def evaluate(self, query: str, results: Any) -> EvaluationResult:
        """
        评估结果质量

        Args:
            query: 原始查询
            results: 工具返回的结果

        Returns:
            评估结果
        """
        pass

    def compute_metrics(self, query: str, results: Any) -> QualityMetrics:
        """计算质量指标"""
        return QualityMetrics()


# ============================================================================
# 搜索结果评估器
# ============================================================================

class SearchResultEvaluator(ResultQualityEvaluator):
    """
    搜索结果评估器

    专门评估知识库搜索和网络搜索结果的质量。
    """

    # 可信来源列表
    TRUSTED_DOMAINS = {
        "wikipedia.org": 0.85,
        "github.com": 0.80,
        "stackoverflow.com": 0.80,
        "arxiv.org": 0.85,
        "ieee.org": 0.90,
        "nature.com": 0.90,
    }

    def __init__(
        self,
        threshold: QualityThreshold = None,
        min_results_for_satisfactory: int = 3,
        min_relevance_for_satisfactory: float = 0.6
    ):
        super().__init__(threshold)
        self.min_results_for_satisfactory = min_results_for_satisfactory
        self.min_relevance_for_satisfactory = min_relevance_for_satisfactory

    def evaluate(self, query: str, results: Any) -> EvaluationResult:
        """评估搜索结果"""
        # 标准化结果格式
        result_list = self._normalize_results(results)

        # 计算指标
        metrics = self.compute_metrics(query, result_list)

        # 判断是否满意
        is_satisfactory = self.threshold.is_satisfied(metrics)

        # 判断是否需要扩展搜索
        should_expand = not is_satisfactory or len(result_list) < self.min_results_for_satisfactory

        # 分析缺失方面
        missing_aspects = self._analyze_missing_aspects(query, result_list, metrics)

        # 生成建议
        suggestions = self._generate_suggestions(metrics, missing_aspects, result_list)

        # 生成理由
        reasoning = self._generate_reasoning(metrics, result_list)

        return EvaluationResult(
            metrics=metrics,
            is_satisfactory=is_satisfactory,
            should_expand=should_expand,
            missing_aspects=missing_aspects,
            suggestions=suggestions,
            reasoning=reasoning
        )

    def compute_metrics(self, query: str, results: List[Dict[str, Any]]) -> QualityMetrics:
        """计算搜索结果的质量指标"""
        if not results:
            return QualityMetrics()

        # 相关性评分：基于结果的 relevance_score 或 score 字段
        relevance_scores = []
        for r in results:
            score = r.get("relevance_score", r.get("score", 0.5))
            relevance_scores.append(score)
        avg_relevance = sum(relevance_scores) / len(relevance_scores)

        # 可信度评分：基于来源和内容质量
        confidence = self._calculate_confidence(results)

        # 完整性评分：基于结果数量和内容覆盖
        completeness = self._calculate_completeness(results, query)

        # 时效性评分：基于发布日期
        freshness = self._calculate_freshness(results)

        # 多样性评分：基于来源多样性
        diversity = self._calculate_diversity(results)

        # 准确性评分：基于内容一致性（简化评估）
        accuracy = min(avg_relevance + 0.1, 1.0)

        return QualityMetrics(
            relevance_score=avg_relevance,
            confidence_score=confidence,
            completeness_score=completeness,
            freshness_score=freshness,
            diversity_score=diversity,
            accuracy_score=accuracy
        )

    def _normalize_results(self, results: Any) -> List[Dict[str, Any]]:
        """标准化结果格式"""
        if isinstance(results, list):
            return results
        elif isinstance(results, dict):
            # 可能是 {"results": [...]} 格式
            if "results" in results:
                return results["results"]
            return [results]
        else:
            return []

    def _calculate_confidence(self, results: List[Dict[str, Any]]) -> float:
        """计算可信度评分"""
        if not results:
            return 0.0

        trust_scores = []
        for result in results:
            url = result.get("url", "")
            source = result.get("source", "")

            # 检查是否为可信来源
            trust = 0.5  # 默认
            for domain, score in self.TRUSTED_DOMAINS.items():
                if domain in url or domain in source:
                    trust = score
                    break

            # 有内容的结果更可信
            if result.get("content") or result.get("snippet"):
                trust = min(trust + 0.1, 1.0)

            trust_scores.append(trust)

        return sum(trust_scores) / len(trust_scores)

    def _calculate_completeness(self, results: List[Dict[str, Any]], query: str) -> float:
        """计算完整性评分"""
        if not results:
            return 0.0

        # 基于结果数量
        count_score = min(len(results) / 5.0, 1.0)

        # 基于内容覆盖
        content_score = 0
        for result in results:
            content = result.get("content", "") or result.get("snippet", "")
            if content and len(content) > 100:
                content_score += 1
        content_score = min(content_score / max(len(results), 1), 1.0)

        return (count_score * 0.4 + content_score * 0.6)

    def _calculate_freshness(self, results: List[Dict[str, Any]]) -> float:
        """计算时效性评分"""
        if not results:
            return 0.5

        now = datetime.now()
        freshness_scores = []

        for result in results:
            pub_date = result.get("published_date", result.get("date", ""))
            if pub_date:
                try:
                    # 尝试解析日期
                    if isinstance(pub_date, str):
                        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"]:
                            try:
                                parsed = datetime.strptime(pub_date[:len(fmt)], fmt)
                                days_old = (now - parsed).days

                                if days_old <= 7:
                                    freshness_scores.append(1.0)
                                elif days_old <= 30:
                                    freshness_scores.append(0.9)
                                elif days_old <= 90:
                                    freshness_scores.append(0.7)
                                elif days_old <= 365:
                                    freshness_scores.append(0.5)
                                else:
                                    freshness_scores.append(0.3)
                                break
                            except ValueError:
                                continue
                except Exception:
                    freshness_scores.append(0.5)
            else:
                freshness_scores.append(0.5)

        return sum(freshness_scores) / len(freshness_scores) if freshness_scores else 0.5

    def _calculate_diversity(self, results: List[Dict[str, Any]]) -> float:
        """计算多样性评分"""
        if not results:
            return 0.0

        # 统计不同来源
        sources = set()
        for result in results:
            source = result.get("source", result.get("search_engine", ""))
            if source:
                sources.add(source)

        # 多样性 = 来源数 / 结果数，最大为1
        if len(results) > 0:
            return min(len(sources) / min(len(results), 5), 1.0)
        return 0.0

    def _analyze_missing_aspects(
        self,
        query: str,
        results: List[Dict[str, Any]],
        metrics: QualityMetrics
    ) -> List[str]:
        """分析缺失的方面"""
        missing = []

        if len(results) < self.min_results_for_satisfactory:
            missing.append("结果数量不足")

        if metrics.relevance_score < self.min_relevance_for_satisfactory:
            missing.append("结果相关性较低")

        if metrics.confidence_score < 0.5:
            missing.append("来源可信度不足")

        if metrics.freshness_score < 0.5:
            missing.append("结果时效性较差")

        if metrics.diversity_score < 0.3:
            missing.append("信息来源单一")

        return missing

    def _generate_suggestions(
        self,
        metrics: QualityMetrics,
        missing_aspects: List[str],
        results: List[Dict[str, Any]]
    ) -> List[str]:
        """生成改进建议"""
        suggestions = []

        if "结果数量不足" in missing_aspects:
            suggestions.append("扩展搜索范围或调整搜索关键词")

        if "结果相关性较低" in missing_aspects:
            suggestions.append("使用更精确的查询词或添加过滤条件")

        if "来源可信度不足" in missing_aspects:
            suggestions.append("优先搜索权威来源或学术数据库")

        if "结果时效性较差" in missing_aspects:
            suggestions.append("限制时间范围获取更新的内容")

        if "信息来源单一" in missing_aspects:
            suggestions.append("使用多个搜索引擎或数据源")

        return suggestions

    def _generate_reasoning(
        self,
        metrics: QualityMetrics,
        results: List[Dict[str, Any]]
    ) -> str:
        """生成评估理由"""
        parts = []

        parts.append(f"共找到 {len(results)} 条结果")
        parts.append(f"平均相关性 {metrics.relevance_score:.2f}")
        parts.append(f"来源可信度 {metrics.confidence_score:.2f}")

        quality = metrics.quality_level.value
        parts.append(f"综合质量等级: {quality}")

        return "；".join(parts)


# ============================================================================
# 数据分析结果评估器
# ============================================================================

class AnalysisResultEvaluator(ResultQualityEvaluator):
    """数据分析结果评估器"""

    def evaluate(self, query: str, results: Any) -> EvaluationResult:
        """评估分析结果"""
        metrics = self.compute_metrics(query, results)
        is_satisfactory = self.threshold.is_satisfied(metrics)

        return EvaluationResult(
            metrics=metrics,
            is_satisfactory=is_satisfactory,
            should_expand=not is_satisfactory,
            missing_aspects=[],
            suggestions=[],
            reasoning=f"数据分析结果质量: {metrics.quality_level.value}"
        )

    def compute_metrics(self, query: str, results: Any) -> QualityMetrics:
        """计算数据分析结果的质量指标"""
        if not results or not isinstance(results, dict):
            return QualityMetrics()

        # 检查结果完整性
        has_statistics = "statistics" in results or "results" in results
        has_insights = "insights" in results or "analysis" in results

        completeness = 0.0
        if has_statistics:
            completeness += 0.5
        if has_insights:
            completeness += 0.5

        # 数据分析结果通常高度相关
        relevance = 0.9 if has_statistics else 0.5

        # 置信度基于数据量
        data_summary = results.get("data_summary", {})
        rows = data_summary.get("rows", 0)
        if isinstance(rows, int):
            if rows >= 100:
                confidence = 0.9
            elif rows >= 30:
                confidence = 0.7
            elif rows >= 10:
                confidence = 0.5
            else:
                confidence = 0.3
        else:
            confidence = 0.5

        return QualityMetrics(
            relevance_score=relevance,
            confidence_score=confidence,
            completeness_score=completeness,
            freshness_score=1.0,  # 分析结果是即时的
            diversity_score=0.7,
            accuracy_score=0.8
        )


# ============================================================================
# 评估器工厂
# ============================================================================

class EvaluatorFactory:
    """评估器工厂"""

    _evaluators: Dict[str, type] = {
        "search": SearchResultEvaluator,
        "analysis": AnalysisResultEvaluator,
    }

    @classmethod
    def create(
        cls,
        evaluator_type: str,
        threshold: QualityThreshold = None,
        **kwargs
    ) -> ResultQualityEvaluator:
        """
        创建评估器

        Args:
            evaluator_type: 评估器类型 (search, analysis)
            threshold: 质量阈值
            **kwargs: 额外参数

        Returns:
            评估器实例
        """
        evaluator_class = cls._evaluators.get(evaluator_type)
        if not evaluator_class:
            raise ValueError(f"Unknown evaluator type: {evaluator_type}")

        return evaluator_class(threshold=threshold, **kwargs)

    @classmethod
    def register(cls, name: str, evaluator_class: type):
        """注册自定义评估器"""
        cls._evaluators[name] = evaluator_class
