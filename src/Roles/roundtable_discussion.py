"""
圆桌讨论系统 - 兼容层

所有类已迁移至 roundtable/ 子模块，此文件保留用于向后兼容。
原代码已拆分为以下模块:
- roundtable/communication.py: 通信系统
- roundtable/contracts.py: 消息契约
- roundtable/dialogue.py: 对话管理
- roundtable/interaction_mode.py: 交互模式
- roundtable/state_management.py: 状态管理
- roundtable/exception_context.py: 异常上下文
- roundtable/discussion_round.py: 讨论轮次
- roundtable/main.py: 主类 RoundtableDiscussion
"""

# 从 roundtable 子模块重新导出所有类，保持向后兼容
from .roundtable import (
    # 通信系统
    MessageType,
    MessagePriority,
    AgentMessage,
    MessageBus,
    CommunicationProtocol,
    MessageTypeDefinition,
    DynamicMessageTypeRegistry,
    
    # 消息契约
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
    
    # 对话管理
    DialogueType,
    DialogueSession,
    InteractionSuggestion,
    FreeDiscussionCoordinator,
    
    # 交互模式
    InteractionMode,
    InteractionModeManager,
    
    # 状态管理
    CheckpointStrategy,
    StateHealthMonitor,
    StateManager,
    
    # 异常上下文
    AgentExceptionContext,
    
    # 讨论轮次
    DiscussionRound,
    CommunicationProtocolExtension,
    
    # 主类
    RoundtableDiscussion,
)

# 保持 __all__ 导出
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
