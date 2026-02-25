"""
对话管理模块

包含对话会话和自由讨论协调:
- DialogueType: 对话类型枚举
- DialogueSession: 对话会话
- InteractionSuggestion: 交互建议
- FreeDiscussionCoordinator: 自由讨论协调器
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import uuid
import logging

from .communication import AgentMessage, MessageBus, CommunicationProtocol

if TYPE_CHECKING:
    from ..personnel.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class DialogueType(Enum):
    """对话类型枚举"""
    DEBATE = "debate"                # 辩论 - 观点交锋
    CLARIFICATION = "clarification"  # 澄清 - 请求解释
    COLLABORATION = "collaboration"  # 协作 - 共同解决问题
    EXPLORATION = "exploration"      # 探索 - 开放式讨论
    CHALLENGE = "challenge"          # 挑战 - 质疑观点
    SUPPORT = "support"              # 支持 - 认同并补充


@dataclass
class DialogueSession:
    """
    智能体间对话会话
    
    用于记录和管理专家间的直接交互
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    initiator: str = ""              # 发起者
    participants: List[str] = field(default_factory=list)  # 参与者列表
    topic: str = ""                  # 讨论主题
    dialogue_type: str = "exploration"  # 对话类型
    messages: List[AgentMessage] = field(default_factory=list)  # 消息列表
    status: str = "active"           # 状态: active, paused, concluded
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    concluded_at: Optional[str] = None
    max_turns: int = 6               # 最大轮次
    current_turn: int = 0            # 当前轮次
    round_number: int = 0            # 所属讨论轮次
    
    # 对话质量指标
    quality_score: float = 0.0
    insights_generated: List[str] = field(default_factory=list)
    consensus_reached: List[str] = field(default_factory=list)
    disagreements: List[str] = field(default_factory=list)
    
    def add_message(self, message: AgentMessage) -> bool:
        """
        添加消息到会话
        
        Args:
            message: 要添加的消息
            
        Returns:
            是否添加成功
        """
        if self.status != "active":
            logger.warning(f"会话 {self.session_id} 不处于活动状态，无法添加消息")
            return False
        
        self.messages.append(message)
        self.current_turn += 1
        
        # 检查是否达到最大轮次
        if self.current_turn >= self.max_turns:
            self.conclude("max_turns_reached")
        
        return True
    
    def can_continue(self) -> bool:
        """
        检查对话是否可以继续
        
        Returns:
            是否可以继续
        """
        return self.status == "active" and self.current_turn < self.max_turns
    
    def conclude(self, reason: str = "completed"):
        """
        结束对话
        
        Args:
            reason: 结束原因
        """
        self.status = "concluded"
        self.concluded_at = datetime.now().isoformat()
        logger.info(f"会话 {self.session_id} 已结束，原因: {reason}")
    
    def pause(self):
        """暂停对话"""
        if self.status == "active":
            self.status = "paused"
    
    def resume(self):
        """恢复对话"""
        if self.status == "paused":
            self.status = "active"
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取会话摘要
        
        Returns:
            会话摘要字典
        """
        return {
            "session_id": self.session_id,
            "initiator": self.initiator,
            "participants": self.participants,
            "topic": self.topic,
            "dialogue_type": self.dialogue_type,
            "status": self.status,
            "message_count": len(self.messages),
            "current_turn": self.current_turn,
            "max_turns": self.max_turns,
            "created_at": self.created_at,
            "concluded_at": self.concluded_at,
            "quality_score": self.quality_score,
            "insights_count": len(self.insights_generated),
            "consensus_count": len(self.consensus_reached),
            "disagreements_count": len(self.disagreements)
        }
    
    def get_last_speaker(self) -> Optional[str]:
        """获取最后发言者"""
        if self.messages:
            return self.messages[-1].sender
        return None
    
    def get_next_expected_speaker(self) -> Optional[str]:
        """
        获取下一个期望的发言者
        
        在辩论模式下，轮流发言
        """
        last_speaker = self.get_last_speaker()
        if not last_speaker or not self.participants:
            return self.participants[0] if self.participants else None
        
        try:
            idx = self.participants.index(last_speaker)
            next_idx = (idx + 1) % len(self.participants)
            return self.participants[next_idx]
        except ValueError:
            return self.participants[0]
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "session_id": self.session_id,
            "initiator": self.initiator,
            "participants": self.participants,
            "topic": self.topic,
            "dialogue_type": self.dialogue_type,
            "messages": [msg.to_dict() for msg in self.messages],
            "status": self.status,
            "created_at": self.created_at,
            "concluded_at": self.concluded_at,
            "max_turns": self.max_turns,
            "current_turn": self.current_turn,
            "round_number": self.round_number,
            "quality_score": self.quality_score,
            "insights_generated": self.insights_generated,
            "consensus_reached": self.consensus_reached,
            "disagreements": self.disagreements
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DialogueSession':
        """从字典创建实例"""
        session = cls(
            session_id=data.get("session_id", str(uuid.uuid4())),
            initiator=data.get("initiator", ""),
            participants=data.get("participants", []),
            topic=data.get("topic", ""),
            dialogue_type=data.get("dialogue_type", "exploration"),
            status=data.get("status", "active"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            concluded_at=data.get("concluded_at"),
            max_turns=data.get("max_turns", 6),
            current_turn=data.get("current_turn", 0),
            round_number=data.get("round_number", 0),
            quality_score=data.get("quality_score", 0.0),
            insights_generated=data.get("insights_generated", []),
            consensus_reached=data.get("consensus_reached", []),
            disagreements=data.get("disagreements", [])
        )
        
        # 恢复消息
        for msg_data in data.get("messages", []):
            session.messages.append(AgentMessage.from_dict(msg_data))
        
        return session


@dataclass
class InteractionSuggestion:
    """交互建议"""
    suggestion_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    initiator: str = ""              # 建议的发起者
    target: str = ""                 # 建议的目标
    interaction_type: str = ""       # 交互类型
    reason: str = ""                 # 建议原因
    context: Dict[str, Any] = field(default_factory=dict)  # 上下文
    priority: float = 0.5            # 优先级 0-1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class FreeDiscussionCoordinator:
    """
    自由讨论协调器 - 支持专家间即时互动
    
    实现去中心化的专家互动机制，允许专家主动发起对话
    """
    
    def __init__(self, message_bus: MessageBus, communication_protocol: CommunicationProtocol, 
                 agents: Dict[str, 'BaseAgent'] = None):
        """
        初始化自由讨论协调器
        
        Args:
            message_bus: 消息总线
            communication_protocol: 通信协议
            agents: 智能体字典
        """
        self.message_bus = message_bus
        self.communication_protocol = communication_protocol
        self.agents = agents or {}
        
        # 活动对话会话
        self.active_dialogues: Dict[str, DialogueSession] = {}
        
        # 已结束的对话会话
        self.concluded_dialogues: List[DialogueSession] = []
        
        # 开放问题广播
        self.open_questions: Dict[str, Dict[str, Any]] = {}
        
        # 交互建议队列
        self.pending_suggestions: List[InteractionSuggestion] = []
        
        # 讨论线程
        self.discussion_threads: Dict[str, List[str]] = {}  # thread_id -> [session_ids]
    
    def set_agents(self, agents: Dict[str, 'BaseAgent']):
        """设置智能体字典"""
        self.agents = agents
    
    def initiate_dialogue(self, initiator: str, target: str, topic: str, 
                         dialogue_type: str = "exploration", 
                         round_number: int = 0) -> Optional[DialogueSession]:
        """
        专家主动发起与另一专家的对话
        
        Args:
            initiator: 发起者名称
            target: 目标专家名称
            topic: 讨论主题
            dialogue_type: 对话类型
            round_number: 所属轮次
            
        Returns:
            创建的对话会话或 None
        """
        # 验证参与者
        if initiator not in self.agents:
            logger.error(f"发起者 {initiator} 不存在")
            return None
        if target not in self.agents:
            logger.error(f"目标专家 {target} 不存在")
            return None
        
        # 创建对话会话
        session = DialogueSession(
            initiator=initiator,
            participants=[initiator, target],
            topic=topic,
            dialogue_type=dialogue_type,
            round_number=round_number
        )
        
        self.active_dialogues[session.session_id] = session
        logger.info(f"创建对话会话: {session.session_id}, 发起者: {initiator}, 目标: {target}, 主题: {topic}")
        
        return session
    
    def broadcast_open_question(self, sender: str, question: str, 
                               context: Dict[str, Any] = None,
                               round_number: int = 0) -> str:
        """
        广播开放问题，允许任意专家回应
        
        Args:
            sender: 发送者
            question: 问题内容
            context: 问题上下文
            round_number: 所属轮次
            
        Returns:
            问题 ID
        """
        question_id = str(uuid.uuid4())
        
        self.open_questions[question_id] = {
            "question_id": question_id,
            "sender": sender,
            "question": question,
            "context": context or {},
            "round_number": round_number,
            "created_at": datetime.now().isoformat(),
            "responses": [],
            "status": "open"
        }
        
        # 通过消息总线广播
        message = self.communication_protocol.create_contracted_message(
            contract_name="open_question",
            sender=sender,
            receiver="",  # 空表示广播
            content={
                "question_content": question,
                "question_context": context or {},
                "seeking_perspectives": "all"
            },
            round_number=round_number
        )
        
        if message:
            self.message_bus.send_message(message)
        
        logger.info(f"广播开放问题: {question_id}, 发送者: {sender}")
        return question_id
    
    def respond_to_open_question(self, question_id: str, responder: str, 
                                response: str) -> bool:
        """
        回应开放问题
        
        Args:
            question_id: 问题 ID
            responder: 回应者
            response: 回应内容
            
        Returns:
            是否成功
        """
        if question_id not in self.open_questions:
            logger.error(f"开放问题 {question_id} 不存在")
            return False
        
        question_data = self.open_questions[question_id]
        if question_data["status"] != "open":
            logger.warning(f"开放问题 {question_id} 已关闭")
            return False
        
        question_data["responses"].append({
            "responder": responder,
            "response": response,
            "timestamp": datetime.now().isoformat()
        })
        
        return True
    
    def create_discussion_thread(self, participants: List[str], topic: str,
                                round_number: int = 0) -> Optional[str]:
        """
        创建多专家讨论线程
        
        Args:
            participants: 参与者列表
            topic: 讨论主题
            round_number: 所属轮次
            
        Returns:
            线程 ID 或 None
        """
        # 验证参与者
        valid_participants = [p for p in participants if p in self.agents]
        if len(valid_participants) < 2:
            logger.error("讨论线程需要至少 2 个有效参与者")
            return None
        
        thread_id = str(uuid.uuid4())
        
        # 创建线程并初始化第一个会话
        first_session = DialogueSession(
            initiator=valid_participants[0],
            participants=valid_participants,
            topic=topic,
            dialogue_type="exploration",
            round_number=round_number
        )
        
        self.active_dialogues[first_session.session_id] = first_session
        self.discussion_threads[thread_id] = [first_session.session_id]
        
        logger.info(f"创建讨论线程: {thread_id}, 参与者: {valid_participants}")
        return thread_id
    
    def get_suggested_interactions(self, current_context: Dict[str, Any] = None) -> List[InteractionSuggestion]:
        """
        基于当前讨论上下文，建议可能的交互
        
        Args:
            current_context: 当前讨论上下文
            
        Returns:
            交互建议列表
        """
        suggestions = []
        context = current_context or {}
        
        # 获取专家列表（排除非专家角色）
        experts = [
            name for name in self.agents.keys()
            if not any(role in name.lower() for role in 
                      ['moderator', 'facilitator', 'synthesizer', 'skeptic', 'scholar'])
        ]
        
        # 分析最近的讨论点
        recent_speeches = context.get('recent_speeches', [])
        divergence_points = context.get('divergence_points', [])
        
        # 基于分歧点建议辩论
        for divergence in divergence_points[:3]:  # 最多 3 个建议
            involved = divergence.get('involved_agents', [])
            if len(involved) >= 2:
                suggestions.append(InteractionSuggestion(
                    initiator=involved[0],
                    target=involved[1],
                    interaction_type="debate",
                    reason=f"存在分歧: {divergence.get('description', 'N/A')}",
                    context=divergence,
                    priority=0.8
                ))
        
        # 基于专家领域相近建议协作
        if len(experts) >= 2:
            for i, expert1 in enumerate(experts[:-1]):
                for expert2 in experts[i+1:]:
                    # 检查是否已有活动对话
                    has_active = any(
                        expert1 in d.participants and expert2 in d.participants
                        for d in self.active_dialogues.values()
                    )
                    if not has_active:
                        suggestions.append(InteractionSuggestion(
                            initiator=expert1,
                            target=expert2,
                            interaction_type="collaboration",
                            reason="专家间可能存在协作机会",
                            priority=0.5
                        ))
        
        # 按优先级排序
        suggestions.sort(key=lambda x: x.priority, reverse=True)
        
        return suggestions[:5]  # 最多返回 5 个建议
    
    def add_message_to_session(self, session_id: str, message: AgentMessage) -> bool:
        """
        向会话添加消息
        
        Args:
            session_id: 会话 ID
            message: 消息
            
        Returns:
            是否成功
        """
        session = self.active_dialogues.get(session_id)
        if not session:
            logger.error(f"会话 {session_id} 不存在")
            return False
        
        return session.add_message(message)
    
    def conclude_session(self, session_id: str, reason: str = "completed") -> Optional[Dict[str, Any]]:
        """
        结束会话
        
        Args:
            session_id: 会话 ID
            reason: 结束原因
            
        Returns:
            会话摘要或 None
        """
        session = self.active_dialogues.get(session_id)
        if not session:
            return None
        
        session.conclude(reason)
        
        # 移动到已结束列表
        del self.active_dialogues[session_id]
        self.concluded_dialogues.append(session)
        
        # 限制历史记录
        if len(self.concluded_dialogues) > 100:
            self.concluded_dialogues = self.concluded_dialogues[-50:]
        
        return session.get_summary()
    
    def get_active_dialogues_for_agent(self, agent_name: str) -> List[DialogueSession]:
        """
        获取智能体参与的所有活动对话
        
        Args:
            agent_name: 智能体名称
            
        Returns:
            对话会话列表
        """
        return [
            session for session in self.active_dialogues.values()
            if agent_name in session.participants
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "active_dialogues_count": len(self.active_dialogues),
            "concluded_dialogues_count": len(self.concluded_dialogues),
            "open_questions_count": len([q for q in self.open_questions.values() if q["status"] == "open"]),
            "discussion_threads_count": len(self.discussion_threads),
            "pending_suggestions_count": len(self.pending_suggestions)
        }
