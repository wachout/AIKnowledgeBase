"""
通信系统模块

包含智能体间通信的核心组件:
- MessageType: 消息类型枚举
- MessagePriority: 消息优先级
- AgentMessage: 标准化消息格式
- MessageBus: 消息总线
- CommunicationProtocol: 通信协议管理器
- MessageTypeDefinition: 消息类型定义
- DynamicMessageTypeRegistry: 动态消息类型注册表
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import uuid
import threading
import logging

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """消息类型枚举"""
    QUESTIONING = "questioning"  # 质疑消息
    RESPONSE = "response"       # 回应消息
    COLLABORATION = "collaboration"  # 协作消息
    CONSENSUS_UPDATE = "consensus_update"  # 共识更新
    COORDINATION = "coordination"  # 协调消息
    SYNTHESIS = "synthesis"     # 综合消息
    SYSTEM = "system"          # 系统消息
    DIRECT_DISCUSSION = "direct_discussion"  # 直接讨论消息
    INTER_AGENT_DIALOGUE = "inter_agent_dialogue"  # 智能体间对话


class MessagePriority(Enum):
    """消息优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AgentMessage:
    """标准化智能体间消息"""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""
    receiver: str = ""
    message_type: MessageType = MessageType.SYSTEM
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    content: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    conversation_id: Optional[str] = None
    parent_message_id: Optional[str] = None
    round_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type.value,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "content": self.content,
            "metadata": self.metadata,
            "conversation_id": self.conversation_id,
            "parent_message_id": self.parent_message_id,
            "round_number": self.round_number
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentMessage':
        """从字典创建消息"""
        return cls(
            message_id=data.get("message_id", str(uuid.uuid4())),
            sender=data.get("sender", ""),
            receiver=data.get("receiver", ""),
            message_type=MessageType(data.get("message_type", "system")),
            priority=MessagePriority(data.get("priority", "normal")),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            content=data.get("content", {}),
            metadata=data.get("metadata", {}),
            conversation_id=data.get("conversation_id"),
            parent_message_id=data.get("parent_message_id"),
            round_number=data.get("round_number")
        )


class MessageBus:
    """智能体间消息总线"""

    def __init__(self):
        self.subscribers: Dict[str, List[callable]] = {}
        self.message_history: List[AgentMessage] = []
        self.conversations: Dict[str, List[AgentMessage]] = {}
        self.bus_lock = threading.RLock()

    def subscribe(self, agent_name: str, callback: callable):
        """订阅消息"""
        with self.bus_lock:
            if agent_name not in self.subscribers:
                self.subscribers[agent_name] = []
            if callback not in self.subscribers[agent_name]:
                self.subscribers[agent_name].append(callback)

    def unsubscribe(self, agent_name: str, callback: callable):
        """取消订阅"""
        with self.bus_lock:
            if agent_name in self.subscribers:
                if callback in self.subscribers[agent_name]:
                    self.subscribers[agent_name].remove(callback)

    def send_message(self, message: AgentMessage) -> bool:
        """发送消息"""
        with self.bus_lock:
            try:
                # 记录消息历史
                self.message_history.append(message)

                # 记录到对话
                if message.conversation_id:
                    if message.conversation_id not in self.conversations:
                        self.conversations[message.conversation_id] = []
                    self.conversations[message.conversation_id].append(message)

                # 广播消息
                if message.receiver in self.subscribers:
                    for callback in self.subscribers[message.receiver]:
                        try:
                            callback(message)
                        except Exception as e:
                            logger.error(f"消息处理失败: {e}")

                # 广播给所有订阅者（如果receiver为空）
                if not message.receiver:
                    for agent_name, callbacks in self.subscribers.items():
                        if agent_name != message.sender:  # 不发给自己
                            for callback in callbacks:
                                try:
                                    callback(message)
                                except Exception as e:
                                    logger.error(f"广播消息处理失败: {e}")

                return True
            except Exception as e:
                logger.error(f"发送消息失败: {e}")
                return False

    def get_conversation(self, conversation_id: str) -> List[AgentMessage]:
        """获取对话历史"""
        with self.bus_lock:
            return self.conversations.get(conversation_id, []).copy()

    def get_recent_messages(self, agent_name: str, limit: int = 10) -> List[AgentMessage]:
        """获取智能体的最近消息"""
        with self.bus_lock:
            agent_messages = [
                msg for msg in self.message_history
                if msg.sender == agent_name or msg.receiver == agent_name
            ]
            return sorted(agent_messages, key=lambda x: x.timestamp, reverse=True)[:limit]

    def get_message_chain(self, message_id: str) -> List[AgentMessage]:
        """获取消息链（包括父消息和子消息）"""
        with self.bus_lock:
            chain = []
            current_id = message_id

            # 向上查找父消息
            while current_id:
                parent_msg = None
                for msg in self.message_history:
                    if msg.message_id == current_id:
                        parent_msg = msg
                        chain.insert(0, msg)  # 插入到开头
                        break
                if parent_msg:
                    current_id = parent_msg.parent_message_id
                else:
                    break

            # 向下查找子消息
            def find_children(parent_id: str):
                children = []
                for msg in self.message_history:
                    if msg.parent_message_id == parent_id:
                        children.append(msg)
                        children.extend(find_children(msg.message_id))
                return children

            children = find_children(message_id)
            chain.extend(children)

            return chain


class CommunicationProtocol:
    """智能体间通信协议管理器（增强版）"""

    def __init__(self, message_bus: MessageBus, contract_registry: 'ContractRegistry' = None):
        self.message_bus = message_bus
        self.protocol_version = "1.0"
        self.supported_message_types = set(mt.value for mt in MessageType)
        self.message_handlers: Dict[MessageType, callable] = {}
        
        # 契约注册表 - 支持契约验证
        self._contract_registry = contract_registry
        
        # 消息契约映射
        self._message_contract_mapping: Dict[str, str] = {
            "questioning": "questioning",
            "response": "expert_response",
            "direct_discussion": "direct_debate",
            "collaboration": "collaboration_proposal"
        }
        
        # 待处理的契约响应
        self._pending_responses: Dict[str, Dict[str, Any]] = {}
    
    @property
    def contract_registry(self) -> 'ContractRegistry':
        """获取契约注册表，延迟初始化"""
        if self._contract_registry is None:
            from .contracts import ContractRegistry
            self._contract_registry = ContractRegistry()
        return self._contract_registry
    
    def set_contract_registry(self, registry: 'ContractRegistry'):
        """设置契约注册表"""
        self._contract_registry = registry
    
    def create_contracted_message(self,
                                 contract_name: str,
                                 sender: str,
                                 receiver: str,
                                 content: Dict[str, Any],
                                 round_number: int,
                                 conversation_id: Optional[str] = None,
                                 parent_message_id: Optional[str] = None) -> Optional[AgentMessage]:
        """
        基于契约创建消息
        
        Args:
            contract_name: 契约名称
            sender: 发送者
            receiver: 接收者
            content: 消息内容
            round_number: 轮次号
            conversation_id: 会话 ID
            parent_message_id: 父消息 ID
            
        Returns:
            创建的消息或 None
        """
        contract = self.contract_registry.get(contract_name)
        if not contract:
            logger.error(f"契约 {contract_name} 不存在")
            return None
        
        # 确定消息类型
        message_type = self._get_message_type_for_contract(contract_name)
        
        # 构建完整内容
        full_content = {
            "contract_name": contract_name,
            "contract_version": contract.contract_version,
            "protocol_version": self.protocol_version,
            **content
        }
        
        # 创建消息
        message = AgentMessage(
            sender=sender,
            receiver=receiver,
            message_type=message_type,
            priority=MessagePriority.NORMAL,
            conversation_id=conversation_id or str(uuid.uuid4()),
            parent_message_id=parent_message_id,
            round_number=round_number,
            content=full_content,
            metadata={
                "contract_name": contract_name,
                "requires_response": contract.response_contract is not None,
                "expected_response_contract": contract.response_contract,
                "timeout_seconds": contract.timeout_seconds
            }
        )
        
        # 验证消息符合契约
        is_valid, errors = contract.validate(message)
        if not is_valid:
            logger.error(f"消息不符合契约 {contract_name}: {errors}")
            return None
        
        # 记录待响应的消息
        if contract.response_contract:
            self._pending_responses[message.message_id] = {
                "message_id": message.message_id,
                "contract_name": contract_name,
                "expected_response": contract.response_contract,
                "timeout_seconds": contract.timeout_seconds,
                "created_at": datetime.now().isoformat()
            }
        
        return message
    
    def validate_against_contract(self, message: AgentMessage, contract_name: str = None) -> tuple:
        """
        验证消息符合契约
        
        Args:
            message: 待验证消息
            contract_name: 契约名称（可选，从消息中推断）
            
        Returns:
            (is_valid, errors)
        """
        # 从消息中推断契约名称
        if not contract_name:
            contract_name = message.content.get('contract_name') or \
                           message.metadata.get('contract_name')
        
        if not contract_name:
            return (True, [])  # 没有契约约束时默认通过
        
        return self.contract_registry.validate_message_against_contract(message, contract_name)
    
    def _get_message_type_for_contract(self, contract_name: str) -> MessageType:
        """根据契约名称获取消息类型"""
        contract_to_type = {
            "questioning": MessageType.QUESTIONING,
            "expert_response": MessageType.RESPONSE,
            "direct_debate": MessageType.DIRECT_DISCUSSION,
            "debate_response": MessageType.DIRECT_DISCUSSION,
            "clarification_request": MessageType.DIRECT_DISCUSSION,
            "clarification_response": MessageType.RESPONSE,
            "collaboration_proposal": MessageType.COLLABORATION,
            "collaboration_response": MessageType.COLLABORATION,
            "open_question": MessageType.INTER_AGENT_DIALOGUE,
            "open_question_response": MessageType.INTER_AGENT_DIALOGUE
        }
        return contract_to_type.get(contract_name, MessageType.SYSTEM)
    
    def get_pending_responses(self) -> Dict[str, Dict[str, Any]]:
        """获取待响应的消息"""
        return self._pending_responses.copy()
    
    def mark_response_received(self, original_message_id: str, response_message: AgentMessage) -> bool:
        """
        标记已收到响应
        
        Args:
            original_message_id: 原始消息 ID
            response_message: 响应消息
            
        Returns:
            是否成功标记
        """
        if original_message_id in self._pending_responses:
            pending = self._pending_responses[original_message_id]
            
            # 验证响应符合期望的契约
            expected_contract = pending.get('expected_response')
            if expected_contract:
                is_valid, errors = self.validate_against_contract(response_message, expected_contract)
                if not is_valid:
                    logger.warning(f"响应不符合期望契约 {expected_contract}: {errors}")
            
            del self._pending_responses[original_message_id]
            return True
        
        return False

    def register_handler(self, message_type: MessageType, handler: callable):
        """注册消息处理器"""
        self.message_handlers[message_type] = handler

    def create_questioning_message(self,
                                 sender: str,
                                 receiver: str,
                                 target_expert: str,
                                 questioning_content: str,
                                 round_number: int,
                                 conversation_id: Optional[str] = None) -> AgentMessage:
        """创建质疑消息"""
        return AgentMessage(
            sender=sender,
            receiver=receiver,
            message_type=MessageType.QUESTIONING,
            priority=MessagePriority.NORMAL,
            conversation_id=conversation_id or str(uuid.uuid4()),
            round_number=round_number,
            content={
                "questioning_type": "constructive_criticism",
                "target_expert": target_expert,
                "questioning_content": questioning_content,
                "protocol_version": self.protocol_version
            },
            metadata={
                "requires_response": True,
                "response_deadline": "next_round",
                "communication_protocol": "skeptic_expert_interaction"
            }
        )

    def create_response_message(self,
                              sender: str,
                              receiver: str,
                              response_content: str,
                              parent_message_id: str,
                              round_number: int,
                              conversation_id: str) -> AgentMessage:
        """创建回应消息"""
        return AgentMessage(
            sender=sender,
            receiver=receiver,
            message_type=MessageType.RESPONSE,
            priority=MessagePriority.NORMAL,
            conversation_id=conversation_id,
            parent_message_id=parent_message_id,
            round_number=round_number,
            content={
                "response_type": "expert_reply",
                "response_content": response_content,
                "protocol_version": self.protocol_version
            },
            metadata={
                "response_quality": "good",
                "communication_protocol": "expert_skeptic_interaction"
            }
        )

    def create_collaboration_message(self,
                                   sender: str,
                                   receiver: str,
                                   collaboration_type: str,
                                   collaboration_content: str,
                                   round_number: int,
                                   conversation_id: Optional[str] = None) -> AgentMessage:
        """创建协作消息"""
        return AgentMessage(
            sender=sender,
            receiver=receiver,
            message_type=MessageType.COLLABORATION,
            priority=MessagePriority.NORMAL,
            conversation_id=conversation_id,
            round_number=round_number,
            content={
                "collaboration_type": collaboration_type,
                "collaboration_content": collaboration_content,
                "protocol_version": self.protocol_version
            },
            metadata={
                "collaboration_goal": "joint_problem_solving",
                "communication_protocol": "agent_collaboration"
            }
        )

    def create_consensus_message(self,
                               sender: str,
                               consensus_content: str,
                               consensus_level: float,
                               round_number: int) -> AgentMessage:
        """创建共识更新消息"""
        return AgentMessage(
            sender=sender,
            receiver="",  # 广播消息
            message_type=MessageType.CONSENSUS_UPDATE,
            priority=MessagePriority.HIGH,
            round_number=round_number,
            content={
                "consensus_content": consensus_content,
                "consensus_level": consensus_level,
                "protocol_version": self.protocol_version
            },
            metadata={
                "consensus_type": "progress_update",
                "communication_protocol": "consensus_broadcast"
            }
        )

    def create_direct_discussion_message(self,
                                        sender: str,
                                        receiver: str,
                                        discussion_content: str,
                                        discussion_type: str,
                                        round_number: int,
                                        conversation_id: Optional[str] = None) -> AgentMessage:
        """创建直接讨论消息"""
        return AgentMessage(
            sender=sender,
            receiver=receiver,
            message_type=MessageType.DIRECT_DISCUSSION,
            priority=MessagePriority.NORMAL,
            conversation_id=conversation_id or str(uuid.uuid4()),
            round_number=round_number,
            content={
                "discussion_type": discussion_type,  # "response", "clarification", "debate", "collaboration"
                "discussion_content": discussion_content,
                "protocol_version": self.protocol_version
            },
            metadata={
                "discussion_context": "depth_discussion_phase",
                "interaction_mode": "peer_to_peer",
                "communication_protocol": "inter_agent_direct_discussion"
            }
        )

    def create_inter_agent_dialogue_message(self,
                                           sender: str,
                                           receiver: str,
                                           dialogue_content: str,
                                           dialogue_context: Dict[str, Any],
                                           round_number: int,
                                           conversation_id: Optional[str] = None) -> AgentMessage:
        """创建智能体间对话消息"""
        return AgentMessage(
            sender=sender,
            receiver=receiver,
            message_type=MessageType.INTER_AGENT_DIALOGUE,
            priority=MessagePriority.NORMAL,
            conversation_id=conversation_id or str(uuid.uuid4()),
            round_number=round_number,
            content={
                "dialogue_content": dialogue_content,
                "dialogue_context": dialogue_context,
                "protocol_version": self.protocol_version
            },
            metadata={
                "dialogue_purpose": "peer_interaction",
                "interaction_mode": "conversational",
                "communication_protocol": "inter_agent_dialogue"
            }
        )

    def validate_message(self, message: AgentMessage) -> bool:
        """验证消息格式"""
        try:
            # 基本字段验证
            if not message.sender or not message.message_type:
                return False

            # 消息类型验证
            if message.message_type.value not in self.supported_message_types:
                return False

            # 协议版本验证
            if message.content.get("protocol_version") != self.protocol_version:
                logger.warning(f"消息协议版本不匹配: {message.content.get('protocol_version')} vs {self.protocol_version}")

            return True
        except Exception as e:
            logger.error(f"消息验证失败: {e}")
            return False

    def process_message(self, message: AgentMessage) -> Any:
        """处理消息"""
        if not self.validate_message(message):
            logger.error(f"无效消息: {message.message_id}")
            return None

        # 调用对应的消息处理器
        if message.message_type in self.message_handlers:
            try:
                return self.message_handlers[message.message_type](message)
            except Exception as e:
                logger.error(f"消息处理失败: {e}")
                return None
        else:
            logger.warning(f"未找到消息处理器: {message.message_type}")
            return None

    def get_conversation_summary(self, conversation_id: str) -> Dict[str, Any]:
        """获取对话摘要"""
        conversation = self.message_bus.get_conversation(conversation_id)
        if not conversation:
            return {"error": "conversation_not_found"}

        summary = {
            "conversation_id": conversation_id,
            "message_count": len(conversation),
            "participants": set(),
            "message_types": {},
            "timeline": [],
            "protocol_version": self.protocol_version
        }

        for msg in conversation:
            summary["participants"].add(msg.sender)
            if msg.receiver:
                summary["participants"].add(msg.receiver)

            msg_type = msg.message_type.value
            summary["message_types"][msg_type] = summary["message_types"].get(msg_type, 0) + 1

            summary["timeline"].append({
                "timestamp": msg.timestamp,
                "sender": msg.sender,
                "receiver": msg.receiver,
                "type": msg_type,
                "priority": msg.priority.value
            })

        summary["participants"] = list(summary["participants"])
        return summary


# ============================================================================
# Phase 2: 可扩展消息类型系统
# ============================================================================

@dataclass
class MessageTypeDefinition:
    """
    消息类型定义
    
    用于动态注册新的消息类型
    """
    name: str                          # 消息类型名称
    category: str                      # 类别: questioning, response, collaboration, coordination
    contract_name: Optional[str] = None  # 关联的契约名称
    handlers: List[callable] = field(default_factory=list)  # 处理器链
    allowed_senders: List[str] = field(default_factory=list)  # 允许的发送者角色
    allowed_receivers: List[str] = field(default_factory=list)  # 允许的接收者角色
    priority_default: str = "normal"   # 默认优先级
    description: str = ""              # 描述
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "name": self.name,
            "category": self.category,
            "contract_name": self.contract_name,
            "allowed_senders": self.allowed_senders,
            "allowed_receivers": self.allowed_receivers,
            "priority_default": self.priority_default,
            "description": self.description,
            "created_at": self.created_at
        }


class DynamicMessageTypeRegistry:
    """
    动态消息类型注册表
    
    支持在运行时动态注册新的消息类型，而无需修改核心枚举
    """
    
    def __init__(self):
        # 核心消息类型（不可删除）
        self._core_types: set = {
            "questioning", "response", "collaboration", 
            "consensus_update", "coordination", "synthesis",
            "system", "direct_discussion", "inter_agent_dialogue"
        }
        
        # 扩展的消息类型
        self._extended_types: Dict[str, MessageTypeDefinition] = {}
        
        # 类型注册历史
        self._registration_history: List[Dict[str, Any]] = []
    
    def register_type(self, definition: MessageTypeDefinition) -> bool:
        """
        注册新的消息类型
        
        Args:
            definition: 消息类型定义
            
        Returns:
            是否注册成功
        """
        if definition.name in self._core_types:
            logger.warning(f"无法覆盖核心消息类型: {definition.name}")
            return False
        
        if definition.name in self._extended_types:
            logger.info(f"更新现有消息类型: {definition.name}")
        
        self._extended_types[definition.name] = definition
        self._registration_history.append({
            "action": "register",
            "type_name": definition.name,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"注册消息类型: {definition.name}")
        return True
    
    def unregister_type(self, type_name: str) -> bool:
        """
        注销消息类型
        
        Args:
            type_name: 消息类型名称
            
        Returns:
            是否注销成功
        """
        if type_name in self._core_types:
            logger.warning(f"无法注销核心消息类型: {type_name}")
            return False
        
        if type_name in self._extended_types:
            del self._extended_types[type_name]
            self._registration_history.append({
                "action": "unregister",
                "type_name": type_name,
                "timestamp": datetime.now().isoformat()
            })
            return True
        
        return False
    
    def is_valid_type(self, type_name: str) -> bool:
        """
        检查消息类型是否有效
        
        Args:
            type_name: 消息类型名称
            
        Returns:
            是否有效
        """
        return type_name in self._core_types or type_name in self._extended_types
    
    def get_type_definition(self, type_name: str) -> Optional[MessageTypeDefinition]:
        """
        获取消息类型定义
        
        Args:
            type_name: 消息类型名称
            
        Returns:
            消息类型定义或 None
        """
        return self._extended_types.get(type_name)
    
    def get_handler_chain(self, type_name: str) -> List[callable]:
        """
        获取消息类型的处理器链
        
        Args:
            type_name: 消息类型名称
            
        Returns:
            处理器列表
        """
        definition = self.get_type_definition(type_name)
        if definition:
            return definition.handlers
        return []
    
    def get_all_types(self) -> Dict[str, Any]:
        """
        获取所有消息类型
        
        Returns:
            所有消息类型的字典
        """
        return {
            "core_types": list(self._core_types),
            "extended_types": {name: defn.to_dict() for name, defn in self._extended_types.items()}
        }
    
    def get_types_by_category(self, category: str) -> List[str]:
        """
        按类别获取消息类型
        
        Args:
            category: 类别名称
            
        Returns:
            消息类型列表
        """
        types = []
        for name, defn in self._extended_types.items():
            if defn.category == category:
                types.append(name)
        return types
    
    def can_send(self, type_name: str, sender_role: str) -> bool:
        """
        检查发送者是否可以发送指定类型的消息
        
        Args:
            type_name: 消息类型名称
            sender_role: 发送者角色
            
        Returns:
            是否允许
        """
        if type_name in self._core_types:
            return True  # 核心类型默认允许
        
        definition = self.get_type_definition(type_name)
        if definition:
            if not definition.allowed_senders:
                return True  # 未限制则允许
            return sender_role in definition.allowed_senders
        
        return False
    
    def can_receive(self, type_name: str, receiver_role: str) -> bool:
        """
        检查接收者是否可以接收指定类型的消息
        
        Args:
            type_name: 消息类型名称
            receiver_role: 接收者角色
            
        Returns:
            是否允许
        """
        if type_name in self._core_types:
            return True  # 核心类型默认允许
        
        definition = self.get_type_definition(type_name)
        if definition:
            if not definition.allowed_receivers:
                return True  # 未限制则允许
            return receiver_role in definition.allowed_receivers
        
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "core_types_count": len(self._core_types),
            "extended_types_count": len(self._extended_types),
            "total_types_count": len(self._core_types) + len(self._extended_types),
            "registration_history_count": len(self._registration_history)
        }
