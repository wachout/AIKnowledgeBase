"""多层强化学习智能体系统 - 层模块
包含两层架构的实现：讨论层、实施与专业领域知识划分层

圆桌讨论系统为两层架构：
- 第一层（讨论层）：圆桌讨论与战略决策，形成共识与可执行方案
- 第二层（实施与专业领域知识划分层）：按知识领域划分专家，细化各领域实施步骤，组建专家小组讨论并产出详细方案
"""

from .base_layer import BaseLayer, LayerContext, LayerConfig
from .decision_layer import DecisionLayer
from .implementation_layer import ImplementationLayer
from .validation_layer import ValidationLayer

# 实施层圆桌讨论系统
from .implementation_roundtable import (
    ImplementationDiscussion,
    ImplementationConsensus,
    ImplementationCoordinator,
    ConsensusCategory,
    DiscussionPhase,
    OpinionRecord,
    ConsensusResult,
    PhaseResult,
)

__all__ = [
    # 基础层
    'BaseLayer',
    'LayerContext',
    'LayerConfig',
    
    # 层架构
    'DecisionLayer',
    'ImplementationLayer',
    'ValidationLayer',
    
    # 实施圆桌讨论系统
    'ImplementationDiscussion',
    'ImplementationConsensus',
    'ImplementationCoordinator',
    'ConsensusCategory',
    'DiscussionPhase',
    'OpinionRecord',
    'ConsensusResult',
    'PhaseResult',
]
