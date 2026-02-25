# -*- coding: utf-8 -*-
"""
圆桌讨论头脑风暴会议系统
包含所有智能体、工具和协调器的完整实现
"""

# 主要协调器
from .roundtable_discussion import RoundtableDiscussion, DiscussionRound

# 智能体角色
from .personnel.base_agent import BaseAgent, WorkingStyle
from .personnel.scholar import Scholar
from .personnel.moderator import Moderator
from .personnel.domain_expert import DomainExpert
from .personnel.skeptic import Skeptic
from .personnel.synthesizer import Synthesizer
from .personnel.facilitator import Facilitator
from .personnel.data_analyst import DataAnalyst
from .personnel.risk_manager import RiskManager

# 工具系统
from .tools.consensus_tracker import ConsensusTracker, EnhancedConsensusTracker, ConsensusPoint, DivergencePoint
from .tools.topic_profiler import TopicProfiler, TaskAnalysis, TopicProfile
from .tools.base_tool import (
    BaseTool, ToolResult, ToolManager,
    KnowledgeSearchTool, WebSearchTool, DataAnalysisTool, CommunicationTool
)

__all__ = [
    # 主要协调器
    'RoundtableDiscussion',
    'DiscussionRound',

    # 智能体角色
    'BaseAgent',
    'WorkingStyle',
    'Scholar',
    'Moderator',
    'DomainExpert',
    'Skeptic',
    'Synthesizer',
    'Facilitator',
    'DataAnalyst',
    'RiskManager',
    'Scholar',

    # 工具系统
    'ConsensusTracker',
    'EnhancedConsensusTracker',
    'ConsensusPoint',
    'DivergencePoint',
    'TopicProfiler',
    'TaskAnalysis',
    'TopicProfile',
    'BaseTool',
    'ToolResult',
    'ToolManager',
    'KnowledgeSearchTool',
    'WebSearchTool',
    'DataAnalysisTool',
    'CommunicationTool'
]