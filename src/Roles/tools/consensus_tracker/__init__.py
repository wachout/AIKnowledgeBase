"""
共识追踪器模块

提供增强版共识追踪、分歧管理和冲突解决功能。

Submodules:
    types: 基础枚举类型
    decay_model: 时间衰减模型
    consensus_point: 共识点类
    dependency_graph: 层次化依赖图
    weight_calculator: 动态权重计算
    aggregator: 非线性聚合算法
    divergence_point: 分歧点类
    conflict_detection: 冲突检测与触发
    debate_engine: 结构化辩论引擎
    strategy_executor: 策略执行器
    resolution_orchestrator: 解决会话与编排器
    tracker: 主类 EnhancedConsensusTracker
"""

# 基础类型
from .types import (
    ConsensusType,
    ConsensusPriority,
    ConflictSeverity
)

# 衰减模型
from .decay_model import (
    DecayHistory,
    AdaptiveDecayModel
)

# 共识点
from .consensus_point import ConsensusPoint

# 依赖图
from .dependency_graph import (
    DependencyType,
    ConsensusHierarchyLevel,
    ConsensusDependency,
    ConsensusDependencyGraph
)

# 权重计算
from .weight_calculator import (
    DiscussionPhase,
    ExpertAuthorityScore,
    DynamicWeightCalculator
)

# 聚合器
from .aggregator import (
    AggregationStrategy,
    CorrelationType,
    ConsensusCorrelation,
    ConsensusAggregator
)

# 分歧点
from .divergence_point import (
    DivergencePoint,
    ConflictResolutionStrategy,
    ConflictResolution
)

# 冲突检测
from .conflict_detection import (
    ConflictTriggerCondition,
    ConflictAlert,
    ConflictDetector,
    ConflictTriggerManager
)

# 辩论引擎
from .debate_engine import (
    DebatePhase,
    DebateArgument,
    DebateRules,
    DebatePosition,
    StructuredDebateEngine
)

# 策略执行器
from .strategy_executor import (
    ResolutionContext,
    ResolutionOutcomeType,
    ResolutionResult,
    ResolutionStrategyExecutor,
    DebateExecutor,
    VotingExecutor,
    MediationExecutor,
    CompromiseExecutor,
    DataDrivenExecutor
)

# 编排器
from .resolution_orchestrator import (
    SessionState,
    ResolutionSession,
    ResolutionOrchestrator
)

# 主类
from .tracker import (
    EnhancedConsensusTracker,
    ConsensusTracker
)

__all__ = [
    # 基础类型
    "ConsensusType",
    "ConsensusPriority",
    "ConflictSeverity",
    
    # 衰减模型
    "DecayHistory",
    "AdaptiveDecayModel",
    
    # 共识点
    "ConsensusPoint",
    
    # 依赖图
    "DependencyType",
    "ConsensusHierarchyLevel",
    "ConsensusDependency",
    "ConsensusDependencyGraph",
    
    # 权重计算
    "DiscussionPhase",
    "ExpertAuthorityScore",
    "DynamicWeightCalculator",
    
    # 聚合器
    "AggregationStrategy",
    "CorrelationType",
    "ConsensusCorrelation",
    "ConsensusAggregator",
    
    # 分歧点
    "DivergencePoint",
    "ConflictResolutionStrategy",
    "ConflictResolution",
    
    # 冲突检测
    "ConflictTriggerCondition",
    "ConflictAlert",
    "ConflictDetector",
    "ConflictTriggerManager",
    
    # 辩论引擎
    "DebatePhase",
    "DebateArgument",
    "DebateRules",
    "DebatePosition",
    "StructuredDebateEngine",
    
    # 策略执行器
    "ResolutionContext",
    "ResolutionOutcomeType",
    "ResolutionResult",
    "ResolutionStrategyExecutor",
    "DebateExecutor",
    "VotingExecutor",
    "MediationExecutor",
    "CompromiseExecutor",
    "DataDrivenExecutor",
    
    # 编排器
    "SessionState",
    "ResolutionSession",
    "ResolutionOrchestrator",
    
    # 主类
    "EnhancedConsensusTracker",
    "ConsensusTracker",
]
