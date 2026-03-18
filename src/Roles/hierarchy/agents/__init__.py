"""
多层强化学习智能体系统 - 智能体模块
包含层次化智能体基类和各层专用智能体
"""

from .base_hierarchical_agent import (
    BaseHierarchicalAgent,
    HierarchicalAgentConfig,
    AgentCapability
)
from .decision_agents import (
    StrategistAgent,
    AnalystAgent,
    CriticAgent
)
from .implementation_agents import (
    ArchitectAgent,
    DeveloperAgent,
    TesterAgent,
    DocumenterAgent,
    CoordinatorAgent
)

# 新增：动态智能体相关
from .scholar_agent import ScholarAgent
from .dynamic_expert_agent import DynamicExpertAgent
from .dynamic_agent_factory import DynamicAgentFactory
from .synthesizer_agent import SynthesizerAgent

__all__ = [
    # 基类
    'BaseHierarchicalAgent',
    'HierarchicalAgentConfig',
    'AgentCapability',
    # 决策层智能体
    'StrategistAgent',
    'AnalystAgent',
    'CriticAgent',
    # 实施层智能体
    'ArchitectAgent',
    'DeveloperAgent',
    'TesterAgent',
    'DocumenterAgent',
    'CoordinatorAgent',
    # 动态专家模式智能体
    'ScholarAgent',
    'DynamicExpertAgent',
    'DynamicAgentFactory',
    'SynthesizerAgent',
]
