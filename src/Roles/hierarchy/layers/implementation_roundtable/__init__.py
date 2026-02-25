"""
实施层圆桌讨论系统模块

将实施层的简单讨论升级为完整的圆桌会议系统：
- implementation_consensus: 实施共识追踪
- implementation_coordinator: 实施讨论协调器
- implementation_discussion: 实施讨论主类
"""

from .implementation_consensus import (
    ImplementationConsensus,
    ConsensusCategory,
    OpinionRecord,
    ConsensusResult,
)

from .implementation_coordinator import (
    ImplementationCoordinator,
    DiscussionPhase,
    PhaseResult,
)

from .implementation_discussion import (
    ImplementationDiscussion,
)

__all__ = [
    # 共识追踪
    'ImplementationConsensus',
    'ConsensusCategory',
    'OpinionRecord',
    'ConsensusResult',
    
    # 讨论协调
    'ImplementationCoordinator',
    'DiscussionPhase',
    'PhaseResult',
    
    # 主类
    'ImplementationDiscussion',
]
