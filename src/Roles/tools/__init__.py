"""
智能体工具模块
提供各种工具供智能体使用，包括知识库搜索、网络搜索、数据分析等。

增强功能：
- 工具版本管理与兼容性检查
- 工具流水线/编排能力
- 结果质量评估
- Skills 技能系统
"""

# 共识和话题分析
from .consensus_tracker import ConsensusTracker, EnhancedConsensusTracker
from .topic_profiler import TopicProfiler, TaskAnalysis, TopicProfile

# 基础工具类
from .base_tool import (
    BaseTool, 
    ToolResult, 
    ToolManager,
    ParameterType,
    ParameterDefinition,
    ParameterSchema,
    QualityAssessment
)

# 具体工具类
from .knowledge_search_tool import KnowledgeSearchTool
from .web_search_tool import WebSearchTool
from .data_analysis_tool import DataAnalysisTool
from .communication_tool import CommunicationTool

# 版本管理
from .tool_version import (
    ToolVersion,
    CompatibilityChecker,
    GracefulDegradeHandler,
    ToolVersionRegistry,
    VersionMismatchError
)

# 工具流水线
from .tool_pipeline import (
    ToolPipelineStep,
    ToolPipeline,
    PipelineExecutor,
    FailurePolicy,
    ExecutionStrategy,
    PipelineResult
)

# 增强的工具管理器
from .tool_manager import (
    ToolManager as EnhancedToolManager,
    ToolMetadata,
    ToolDependency,
    ToolLifecycleHooks
)

# 结果质量评估
from .tool_evaluator import (
    QualityMetrics,
    QualityThreshold,
    QualityLevel,
    ResultQualityEvaluator,
    SearchResultEvaluator
)

# 技能系统
from .skill_registry import (
    Skill,
    SkillContext,
    SkillResult,
    SkillRegistry,
    AgentSkillSet,
    KnowledgeQuerySkill,
    WebResearchSkill,
    DataInsightSkill,
    FactCheckSkill,
    CollaborativeCommunicationSkill
)

__all__ = [
    # 共识和话题分析
    'ConsensusTracker',
    'EnhancedConsensusTracker',
    'TopicProfiler',
    'TaskAnalysis',
    'TopicProfile',

    # 基础工具类
    'BaseTool',
    'ToolResult',
    'ToolManager',
    'ParameterType',
    'ParameterDefinition',
    'ParameterSchema',
    'QualityAssessment',
    
    # 具体工具类
    'KnowledgeSearchTool',
    'WebSearchTool',
    'DataAnalysisTool',
    'CommunicationTool',
    
    # 版本管理
    'ToolVersion',
    'CompatibilityChecker',
    'GracefulDegradeHandler',
    'ToolVersionRegistry',
    'VersionMismatchError',
    
    # 工具流水线
    'ToolPipelineStep',
    'ToolPipeline',
    'PipelineExecutor',
    'FailurePolicy',
    'ExecutionStrategy',
    'PipelineResult',
    
    # 增强的工具管理器
    'EnhancedToolManager',
    'ToolMetadata',
    'ToolDependency',
    'ToolLifecycleHooks',
    
    # 结果质量评估
    'QualityMetrics',
    'QualityThreshold',
    'QualityLevel',
    'ResultQualityEvaluator',
    'SearchResultEvaluator',
    
    # 技能系统
    'Skill',
    'SkillContext',
    'SkillResult',
    'SkillRegistry',
    'AgentSkillSet',
    'KnowledgeQuerySkill',
    'WebResearchSkill',
    'DataInsightSkill',
    'FactCheckSkill',
    'CollaborativeCommunicationSkill',
]