"""
多层强化学习智能体系统 (Hierarchical Reinforcement Learning Agent System)

圆桌讨论系统为两层架构：
- 第一层（讨论层）：圆桌讨论与战略决策，形成共识与可执行方案
- 第二层（实施与专业领域知识划分层）：按知识领域划分专家，细化实施步骤，各领域专家产出详细方案并保存至 discussion/discussion_id/pro

系统特点：
- 层次化强化学习：每层都有自己的状态、动作空间和奖励函数
- 反馈回路：检验层的结果反馈给决策层，形成强化学习闭环
- 动态智能体：根据任务类型动态创建和配置智能体
- 经验复用：支持经验回放和策略迁移
"""

# 核心类型
from .types import (
    # 枚举
    LayerType,
    EdgeType,
    ExecutionStatus,
    AgentAction,
    ImplementationRole,
    ValidationRole,
    MessageType,
    IssueSeverity,
    # 数据类
    Objective,
    Constraint,
    Task,
    ExecutionStep,
    Artifact,
    LogEntry,
    Issue,
    Suggestion,
    ExecutionMetric,
    # 层输出
    DecisionOutput,
    ImplementationOutput,
    ValidationOutput,
    HierarchicalOutput,
    # 状态
    AgentState,
    AgentMemory,
    LayerState,
    GlobalState,
    HierarchicalState,
    StateTransition,
    # 策略与经验
    Policy,
    Experience,
    # 通信
    LayerMessage,
    # 图结构
    AgentNode,
    Edge
)

# 层实现
from .layers import (
    BaseLayer,
    LayerContext,
    LayerConfig,
    DecisionLayer,
    ImplementationLayer,
    ValidationLayer
)

# 智能体
from .agents import (
    BaseHierarchicalAgent,
    HierarchicalAgentConfig,
    AgentCapability,
    # 决策层智能体
    StrategistAgent,
    AnalystAgent,
    CriticAgent,
    # 实施层智能体
    ArchitectAgent,
    DeveloperAgent,
    TesterAgent,
    DocumenterAgent,
    CoordinatorAgent,
    # 检验层智能体
    QualityInspectorAgent,
    LogicValidatorAgent,
    PerformanceAnalystAgent,
    SecurityAuditorAgent,
    ComplianceCheckerAgent
)

# 强化学习组件
from .rl_graph import RLGraph, GraphBuilder
from .reward_system import HierarchicalRewardSystem, RewardComponent, LayerReward
from .policy_updater import HierarchicalPolicyUpdater, AdamOptimizer

# 经验管理
from .experience import (
    ExperienceBuffer,
    PrioritizedExperienceBuffer,
    Trajectory,
    TrajectoryRecorder
)

# 通信
from .communication import (
    LayerCommunicationBus,
    TaskDispatcher,
    FeedbackLoop,
    CommunicationCoordinator
)

# 主协调器
from .orchestrator import HierarchicalOrchestrator, OrchestratorConfig

__all__ = [
    # === 类型 ===
    'LayerType',
    'EdgeType',
    'ExecutionStatus',
    'AgentAction',
    'ImplementationRole',
    'ValidationRole',
    'MessageType',
    'IssueSeverity',
    'Objective',
    'Constraint',
    'Task',
    'ExecutionStep',
    'Artifact',
    'LogEntry',
    'Issue',
    'Suggestion',
    'ExecutionMetric',
    'DecisionOutput',
    'ImplementationOutput',
    'ValidationOutput',
    'HierarchicalOutput',
    'AgentState',
    'AgentMemory',
    'LayerState',
    'GlobalState',
    'HierarchicalState',
    'StateTransition',
    'Policy',
    'Experience',
    'LayerMessage',
    'AgentNode',
    'Edge',
    
    # === 层 ===
    'BaseLayer',
    'LayerContext',
    'LayerConfig',
    'DecisionLayer',
    'ImplementationLayer',
    'ValidationLayer',
    
    # === 智能体 ===
    'BaseHierarchicalAgent',
    'HierarchicalAgentConfig',
    'AgentCapability',
    'StrategistAgent',
    'AnalystAgent',
    'CriticAgent',
    'ArchitectAgent',
    'DeveloperAgent',
    'TesterAgent',
    'DocumenterAgent',
    'CoordinatorAgent',
    'QualityInspectorAgent',
    'LogicValidatorAgent',
    'PerformanceAnalystAgent',
    'SecurityAuditorAgent',
    'ComplianceCheckerAgent',
    
    # === 强化学习 ===
    'RLGraph',
    'GraphBuilder',
    'HierarchicalRewardSystem',
    'RewardComponent',
    'LayerReward',
    'HierarchicalPolicyUpdater',
    'AdamOptimizer',
    
    # === 经验 ===
    'ExperienceBuffer',
    'PrioritizedExperienceBuffer',
    'Trajectory',
    'TrajectoryRecorder',
    
    # === 通信 ===
    'LayerCommunicationBus',
    'TaskDispatcher',
    'FeedbackLoop',
    'CommunicationCoordinator',
    
    # === 协调器 ===
    'HierarchicalOrchestrator',
    'OrchestratorConfig'
]

__version__ = '1.0.0'
