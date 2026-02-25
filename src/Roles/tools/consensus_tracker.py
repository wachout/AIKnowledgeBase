"""
共识追踪器兼容层

此文件保持向后兼容，实际实现已迁移到 consensus_tracker/ 子模块。

使用方式（保持不变）：
    from .consensus_tracker import ConsensusTracker
    from .consensus_tracker import EnhancedConsensusTracker
    from .consensus_tracker import ConsensusType, ConsensusPriority, ConflictSeverity
"""

# 从子模块重新导出所有公共类

# 基础类型
from .consensus_tracker.types import (
    ConsensusType,
    ConsensusPriority,
    ConflictSeverity
)

# 衰减模型
from .consensus_tracker.decay_model import (
    DecayHistory,
    AdaptiveDecayModel
)

# 共识点
from .consensus_tracker.consensus_point import ConsensusPoint

# 依赖图
from .consensus_tracker.dependency_graph import (
    DependencyType,
    ConsensusHierarchyLevel,
    ConsensusDependency,
    ConsensusDependencyGraph
)

# 权重计算
from .consensus_tracker.weight_calculator import (
    DiscussionPhase,
    ExpertAuthorityScore,
    DynamicWeightCalculator
)

# 聚合器
from .consensus_tracker.aggregator import (
    AggregationStrategy,
    CorrelationType,
    ConsensusCorrelation,
    ConsensusAggregator
)

# 分歧点
from .consensus_tracker.divergence_point import (
    DivergencePoint,
    ConflictResolutionStrategy,
    ConflictResolution
)

# 冲突检测
from .consensus_tracker.conflict_detection import (
    ConflictTriggerCondition,
    ConflictAlert,
    ConflictDetector,
    ConflictTriggerManager
)

# 辩论引擎
from .consensus_tracker.debate_engine import (
    DebatePhase,
    DebateArgument,
    DebateRules,
    DebatePosition,
    StructuredDebateEngine
)

# 策略执行器
from .consensus_tracker.strategy_executor import (
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
from .consensus_tracker.resolution_orchestrator import (
    SessionState,
    ResolutionSession,
    ResolutionOrchestrator
)

# 主类
from .consensus_tracker.tracker import (
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
