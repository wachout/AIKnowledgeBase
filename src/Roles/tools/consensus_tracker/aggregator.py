"""
共识追踪系统 - 非线性聚合算法
包含多种聚合策略（加权平均、调和平均、几何平均、OWA等）和相关性计算。
"""

from typing import Dict, Any, List, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import math

if TYPE_CHECKING:
    from .consensus_point import ConsensusPoint
    from .weight_calculator import DiscussionPhase


class AggregationStrategy(Enum):
    """
    共识聚合策略
    
    不同的聚合策略适用于不同场景。
    """
    WEIGHTED_AVERAGE = "weighted_average"     # 加权平均：适用于一般情况
    HARMONIC_MEAN = "harmonic_mean"           # 调和平均：适用于平衡极端值
    GEOMETRIC_MEAN = "geometric_mean"         # 几何平均：适用于乘法关系
    POWER_MEAN = "power_mean"                 # 幂平均：可调参数的广义平均
    CHOQUET_INTEGRAL = "choquet_integral"     # Choquet积分：考虑子集间交互
    OWA = "owa"                               # 有序加权平均：对排序后的值加权
    MIN_MAX_BOUNDED = "min_max_bounded"       # 有界聚合：考虑最小和最大值的影响


class CorrelationType(Enum):
    """共识相关性类型"""
    SEMANTIC = "semantic"           # 语义相关性（基于关键词）
    SUPPORTER = "supporter"         # 支持者相关性（基于支持者重叠）
    TEMPORAL = "temporal"           # 时间相关性（基于创建时间）
    STRUCTURAL = "structural"       # 结构相关性（基于依赖关系）


@dataclass
class ConsensusCorrelation:
    """
    共识相关性
    
    描述两个共识点之间的相关性，用于聚合时避免重复计算。
    """
    consensus_id_1: str
    consensus_id_2: str
    correlation: float              # 相关性系数 (-1.0 到 1.0)
    correlation_type: CorrelationType
    computed_at: str = None
    confidence: float = 0.5         # 相关性计算的置信度
    
    def __post_init__(self):
        if self.computed_at is None:
            self.computed_at = datetime.now().isoformat()
    
    def is_significant(self, threshold: float = 0.3) -> bool:
        """相关性是否显著"""
        return abs(self.correlation) >= threshold
    
    def is_positive(self) -> bool:
        """是否是正相关"""
        return self.correlation > 0
    
    def get_weight_adjustment(self) -> float:
        """
        获取基于相关性的权重调整
        
        高度相关的共识应该减少重复贡献
        """
        if abs(self.correlation) < 0.3:
            return 1.0  # 不显著相关，不调整
        
        # 高度相关时降低权重
        adjustment = 1.0 - abs(self.correlation) * 0.3
        return max(0.5, adjustment)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "consensus_id_1": self.consensus_id_1,
            "consensus_id_2": self.consensus_id_2,
            "correlation": self.correlation,
            "correlation_type": self.correlation_type.value,
            "computed_at": self.computed_at,
            "confidence": self.confidence
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConsensusCorrelation':
        return cls(
            consensus_id_1=data.get("consensus_id_1", ""),
            consensus_id_2=data.get("consensus_id_2", ""),
            correlation=data.get("correlation", 0.0),
            correlation_type=CorrelationType(data.get("correlation_type", "semantic")),
            computed_at=data.get("computed_at"),
            confidence=data.get("confidence", 0.5)
        )


class ConsensusAggregator:
    """
    共识聚合器
    
    支持多种聚合策略，考虑共识间相关性和非线性组合。
    """
    
    def __init__(self):
        self.correlations: List[ConsensusCorrelation] = []
        self._correlation_matrix: Dict[str, Dict[str, float]] = {}
    
    def add_correlation(self, correlation: ConsensusCorrelation) -> None:
        """添加共识相关性"""
        self.correlations.append(correlation)
        
        # 更新矩阵
        id1, id2 = correlation.consensus_id_1, correlation.consensus_id_2
        if id1 not in self._correlation_matrix:
            self._correlation_matrix[id1] = {}
        if id2 not in self._correlation_matrix:
            self._correlation_matrix[id2] = {}
        
        self._correlation_matrix[id1][id2] = correlation.correlation
        self._correlation_matrix[id2][id1] = correlation.correlation
    
    def get_correlation(self, id1: str, id2: str) -> float:
        """获取两个共识之间的相关性"""
        if id1 == id2:
            return 1.0
        return self._correlation_matrix.get(id1, {}).get(id2, 0.0)
    
    def calculate_semantic_correlation(self, cp1: 'ConsensusPoint', 
                                        cp2: 'ConsensusPoint') -> float:
        """
        计算语义相关性（基于关键词重叠）
        
        Args:
            cp1: 共识点1
            cp2: 共识点2
            
        Returns:
            float: 相关性系数 (0.0 - 1.0)
        """
        if not cp1.topic_keywords or not cp2.topic_keywords:
            return 0.0
        
        set1 = set(cp1.topic_keywords)
        set2 = set(cp2.topic_keywords)
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        if union == 0:
            return 0.0
        
        # Jaccard相似度
        return intersection / union
    
    def calculate_supporter_correlation(self, cp1: 'ConsensusPoint',
                                         cp2: 'ConsensusPoint') -> float:
        """
        计算支持者相关性（基于支持者重叠）
        
        Args:
            cp1: 共识点1
            cp2: 共识点2
            
        Returns:
            float: 相关性系数 (0.0 - 1.0)
        """
        if not cp1.supporters or not cp2.supporters:
            return 0.0
        
        set1 = set(cp1.supporters)
        set2 = set(cp2.supporters)
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def calculate_temporal_correlation(self, cp1: 'ConsensusPoint',
                                        cp2: 'ConsensusPoint',
                                        max_round_diff: int = 5) -> float:
        """
        计算时间相关性（基于创建时间）
        
        Args:
            cp1: 共识点1
            cp2: 共识点2
            max_round_diff: 最大轮次差异
            
        Returns:
            float: 相关性系数 (0.0 - 1.0)
        """
        round_diff = abs(cp1.round_created - cp2.round_created)
        
        if round_diff >= max_round_diff:
            return 0.0
        
        # 轮次越接近，相关性越高
        return 1.0 - round_diff / max_round_diff
    
    def aggregate_weighted_average(self, scores: Dict[str, float],
                                    weights: Dict[str, float] = None) -> float:
        """
        加权平均聚合
        
        Args:
            scores: 共识ID到分数的映射
            weights: 共识ID到权重的映射
            
        Returns:
            float: 聚合结果
        """
        if not scores:
            return 0.0
        
        if weights is None:
            weights = {k: 1.0 for k in scores.keys()}
        
        total_weighted = sum(
            scores[k] * weights.get(k, 1.0) 
            for k in scores.keys()
        )
        total_weight = sum(weights.get(k, 1.0) for k in scores.keys())
        
        if total_weight == 0:
            return 0.0
        
        return total_weighted / total_weight
    
    def aggregate_harmonic_mean(self, scores: Dict[str, float],
                                 weights: Dict[str, float] = None) -> float:
        """
        调和平均聚合
        
        适用于平衡极端值，对低值更敏感。
        """
        if not scores:
            return 0.0
        
        if weights is None:
            weights = {k: 1.0 for k in scores.keys()}
        
        # 过滤零值
        non_zero = {k: v for k, v in scores.items() if v > 0}
        if not non_zero:
            return 0.0
        
        total_weight = sum(weights.get(k, 1.0) for k in non_zero.keys())
        if total_weight == 0:
            return 0.0
        
        weighted_sum = sum(
            weights.get(k, 1.0) / v 
            for k, v in non_zero.items()
        )
        
        if weighted_sum == 0:
            return 0.0
        
        return total_weight / weighted_sum
    
    def aggregate_geometric_mean(self, scores: Dict[str, float],
                                  weights: Dict[str, float] = None) -> float:
        """
        几何平均聚合
        
        适用于乘法关系，对比例变化敏感。
        """
        if not scores:
            return 0.0
        
        if weights is None:
            weights = {k: 1.0 for k in scores.keys()}
        
        # 过滤非正值
        positive = {k: v for k, v in scores.items() if v > 0}
        if not positive:
            return 0.0
        
        total_weight = sum(weights.get(k, 1.0) for k in positive.keys())
        if total_weight == 0:
            return 0.0
        
        # 计算加权几何平均
        log_sum = sum(
            weights.get(k, 1.0) * math.log(v) 
            for k, v in positive.items()
        )
        
        return math.exp(log_sum / total_weight)
    
    def aggregate_power_mean(self, scores: Dict[str, float],
                              weights: Dict[str, float] = None,
                              power: float = 2.0) -> float:
        """
        幂平均聚合
        
        power=1: 算术平均
        power=2: 均方根平均
        power=-1: 调和平均
        power→∞: 最大值
        power→-∞: 最小值
        """
        if not scores:
            return 0.0
        
        if weights is None:
            weights = {k: 1.0 for k in scores.keys()}
        
        positive = {k: v for k, v in scores.items() if v > 0}
        if not positive:
            return 0.0
        
        total_weight = sum(weights.get(k, 1.0) for k in positive.keys())
        if total_weight == 0:
            return 0.0
        
        weighted_sum = sum(
            weights.get(k, 1.0) * math.pow(v, power)
            for k, v in positive.items()
        )
        
        return math.pow(weighted_sum / total_weight, 1 / power)
    
    def aggregate_owa(self, scores: Dict[str, float],
                       owa_weights: List[float] = None) -> float:
        """
        有序加权平均（OWA）聚合
        
        先对值排序，然后按位置加权。
        
        Args:
            scores: 共识ID到分数的映射
            owa_weights: OWA权重，长度应与scores相同
            
        Returns:
            float: 聚合结果
        """
        if not scores:
            return 0.0
        
        sorted_values = sorted(scores.values(), reverse=True)
        n = len(sorted_values)
        
        if owa_weights is None:
            # 默认权重：前几个权重较高
            owa_weights = []
            for i in range(n):
                w = (n - i) / sum(range(1, n + 1))
                owa_weights.append(w)
        
        # 调整权重长度
        if len(owa_weights) < n:
            owa_weights.extend([0] * (n - len(owa_weights)))
        elif len(owa_weights) > n:
            owa_weights = owa_weights[:n]
        
        return sum(w * v for w, v in zip(owa_weights, sorted_values))
    
    def aggregate_min_max_bounded(self, scores: Dict[str, float],
                                   weights: Dict[str, float] = None,
                                   alpha: float = 0.2) -> float:
        """
        有界聚合
        
        结合加权平均、最小值和最大值。
        
        Args:
            scores: 共识ID到分数的映射
            weights: 权重
            alpha: 最小/最大值的影响系数
            
        Returns:
            float: 聚合结果
        """
        if not scores:
            return 0.0
        
        values = list(scores.values())
        min_val = min(values)
        max_val = max(values)
        avg_val = self.aggregate_weighted_average(scores, weights)
        
        # 结合三者
        result = (1 - 2 * alpha) * avg_val + alpha * min_val + alpha * max_val
        return result
    
    def aggregate_with_correlation(self, scores: Dict[str, float],
                                    strategy: AggregationStrategy,
                                    weights: Dict[str, float] = None,
                                    **kwargs) -> float:
        """
        相关性感知的聚合
        
        考虑共识间相关性，调整权重以避免重复贡献。
        
        Args:
            scores: 共识ID到分数的映射
            strategy: 聚合策略
            weights: 基础权重
            **kwargs: 其他参数
            
        Returns:
            float: 聚合结果
        """
        if not scores:
            return 0.0
        
        # 调整权重以考虑相关性
        adjusted_weights = self._adjust_weights_for_correlation(
            list(scores.keys()), weights
        )
        
        # 根据策略选择聚合方法
        if strategy == AggregationStrategy.WEIGHTED_AVERAGE:
            return self.aggregate_weighted_average(scores, adjusted_weights)
        elif strategy == AggregationStrategy.HARMONIC_MEAN:
            return self.aggregate_harmonic_mean(scores, adjusted_weights)
        elif strategy == AggregationStrategy.GEOMETRIC_MEAN:
            return self.aggregate_geometric_mean(scores, adjusted_weights)
        elif strategy == AggregationStrategy.POWER_MEAN:
            power = kwargs.get("power", 2.0)
            return self.aggregate_power_mean(scores, adjusted_weights, power)
        elif strategy == AggregationStrategy.OWA:
            owa_weights = kwargs.get("owa_weights")
            return self.aggregate_owa(scores, owa_weights)
        elif strategy == AggregationStrategy.MIN_MAX_BOUNDED:
            alpha = kwargs.get("alpha", 0.2)
            return self.aggregate_min_max_bounded(scores, adjusted_weights, alpha)
        else:
            return self.aggregate_weighted_average(scores, adjusted_weights)
    
    def _adjust_weights_for_correlation(self, consensus_ids: List[str],
                                         base_weights: Dict[str, float] = None
                                         ) -> Dict[str, float]:
        """
        根据相关性调整权重
        
        高度相关的共识会降低权重以避免重复计算。
        """
        if base_weights is None:
            base_weights = {cid: 1.0 for cid in consensus_ids}
        
        adjusted = base_weights.copy()
        
        # 对每对共识计算相关性影响
        for i, id1 in enumerate(consensus_ids):
            correlation_sum = 0.0
            for j, id2 in enumerate(consensus_ids):
                if i != j:
                    corr = self.get_correlation(id1, id2)
                    if abs(corr) > 0.3:  # 显著相关
                        correlation_sum += abs(corr)
            
            # 相关性越高，权重降低越多
            if correlation_sum > 0:
                reduction = min(0.5, correlation_sum * 0.15)
                adjusted[id1] = base_weights.get(id1, 1.0) * (1 - reduction)
        
        return adjusted
    
    def select_strategy_for_phase(self, phase: 'DiscussionPhase') -> AggregationStrategy:
        """
        根据讨论阶段选择合适的聚合策略
        
        Args:
            phase: 讨论阶段
            
        Returns:
            AggregationStrategy: 推荐的聚合策略
        """
        # 延迟导入避免循环依赖
        from .weight_calculator import DiscussionPhase
        
        strategy_mapping = {
            DiscussionPhase.EXPLORATION: AggregationStrategy.WEIGHTED_AVERAGE,
            DiscussionPhase.DEEPENING: AggregationStrategy.POWER_MEAN,
            DiscussionPhase.CONVERGENCE: AggregationStrategy.OWA,
            DiscussionPhase.FINALIZATION: AggregationStrategy.MIN_MAX_BOUNDED
        }
        return strategy_mapping.get(phase, AggregationStrategy.WEIGHTED_AVERAGE)
    
    def compute_all_correlations(self, consensus_points: List['ConsensusPoint']) -> None:
        """
        计算所有共识点之间的相关性
        
        Args:
            consensus_points: 共识点列表
        """
        self.correlations.clear()
        self._correlation_matrix.clear()
        
        for i, cp1 in enumerate(consensus_points):
            for j, cp2 in enumerate(consensus_points):
                if i >= j:
                    continue
                
                id1 = getattr(cp1, 'consensus_id', None) or f"consensus_{i}"
                id2 = getattr(cp2, 'consensus_id', None) or f"consensus_{j}"
                
                # 计算各种相关性
                semantic = self.calculate_semantic_correlation(cp1, cp2)
                supporter = self.calculate_supporter_correlation(cp1, cp2)
                temporal = self.calculate_temporal_correlation(cp1, cp2)
                
                # 综合相关性
                combined = semantic * 0.4 + supporter * 0.4 + temporal * 0.2
                
                if combined > 0.1:  # 只保存有意义的相关性
                    correlation = ConsensusCorrelation(
                        consensus_id_1=id1,
                        consensus_id_2=id2,
                        correlation=combined,
                        correlation_type=CorrelationType.SEMANTIC,
                        confidence=min(1.0, (semantic + supporter) / 2 + 0.3)
                    )
                    self.add_correlation(correlation)
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "correlations": [c.to_dict() for c in self.correlations]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConsensusAggregator':
        """反序列化"""
        aggregator = cls()
        for corr_data in data.get("correlations", []):
            correlation = ConsensusCorrelation.from_dict(corr_data)
            aggregator.add_correlation(correlation)
        return aggregator
