"""
圆桌讨论系统模块

将原 roundtable_discussion.py 拆分为多个模块:
- communication: 通信系统
- contracts: 消息契约
- dialogue: 对话管理
- interaction_mode: 交互模式
- state_management: 状态管理
- exception_context: 异常上下文
- discussion_round: 讨论轮次
- main: 主类 RoundtableDiscussion
"""

from .communication import (
    MessageType,
    MessagePriority,
    AgentMessage,
    MessageBus,
    CommunicationProtocol,
    MessageTypeDefinition,
    DynamicMessageTypeRegistry,
)

from .contracts import (
    MessageContract,
    QuestioningContract,
    ExpertResponseContract,
    DirectDebateContract,
    DebateResponseContract,
    ClarificationRequestContract,
    ClarificationResponseContract,
    CollaborationProposalContract,
    CollaborationResponseContract,
    OpenQuestionContract,
    OpenQuestionResponseContract,
    ContractRegistry,
)

from .dialogue import (
    DialogueType,
    DialogueSession,
    InteractionSuggestion,
    FreeDiscussionCoordinator,
)

from .interaction_mode import (
    InteractionMode,
    InteractionModeManager,
)

from .state_management import (
    CheckpointStrategy,
    StateHealthMonitor,
    StateManager,
)

from .exception_context import (
    AgentExceptionContext,
)

from .discussion_round import (
    DiscussionRound,
    CommunicationProtocolExtension,
)

from .main import (
    RoundtableDiscussion,
)

__all__ = [
    # 通信系统
    'MessageType',
    'MessagePriority',
    'AgentMessage',
    'MessageBus',
    'CommunicationProtocol',
    'MessageTypeDefinition',
    'DynamicMessageTypeRegistry',
    
    # 消息契约
    'MessageContract',
    'QuestioningContract',
    'ExpertResponseContract',
    'DirectDebateContract',
    'DebateResponseContract',
    'ClarificationRequestContract',
    'ClarificationResponseContract',
    'CollaborationProposalContract',
    'CollaborationResponseContract',
    'OpenQuestionContract',
    'OpenQuestionResponseContract',
    'ContractRegistry',
    
    # 对话管理
    'DialogueType',
    'DialogueSession',
    'InteractionSuggestion',
    'FreeDiscussionCoordinator',
    
    # 交互模式
    'InteractionMode',
    'InteractionModeManager',
    
    # 状态管理
    'CheckpointStrategy',
    'StateHealthMonitor',
    'StateManager',
    
    # 异常上下文
    'AgentExceptionContext',
    
    # 讨论轮次
    'DiscussionRound',
    'CommunicationProtocolExtension',
    
    # 主类
    'RoundtableDiscussion',
]
