"""
沟通协调工具

用于智能体间的通信、消息传递和协调。
"""

from typing import Dict, Any, List, Optional, Callable, TYPE_CHECKING
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from .base_tool import (
    BaseTool, ToolResult, QualityAssessment,
    ParameterSchema, ParameterDefinition, ParameterType
)

if TYPE_CHECKING:
    pass


class CommunicationAction(Enum):
    """通信动作类型"""
    SEND = "send"              # 发送消息
    BROADCAST = "broadcast"    # 广播消息
    REQUEST = "request"        # 请求信息
    RESPOND = "respond"        # 响应请求
    NOTIFY = "notify"          # 通知
    QUERY = "query"            # 查询
    ACKNOWLEDGE = "acknowledge"  # 确认


class MessageType(Enum):
    """消息类型"""
    INFO = "info"              # 信息
    REQUEST = "request"        # 请求
    RESPONSE = "response"      # 响应
    ALERT = "alert"            # 警报
    STATUS = "status"          # 状态更新
    CONSENSUS = "consensus"    # 共识相关
    DIVERGENCE = "divergence"  # 分歧相关
    COORDINATION = "coordination"  # 协调相关


class MessagePriority(Enum):
    """消息优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Message:
    """消息数据类"""
    id: str
    sender: str
    target: Optional[str]  # None 表示广播
    action: CommunicationAction
    message_type: MessageType
    content: Any
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    requires_response: bool = False
    response_timeout: float = 30.0  # 秒
    correlation_id: Optional[str] = None  # 关联ID，用于请求-响应匹配

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sender": self.sender,
            "target": self.target,
            "action": self.action.value,
            "message_type": self.message_type.value,
            "content": self.content,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "requires_response": self.requires_response,
            "response_timeout": self.response_timeout,
            "correlation_id": self.correlation_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        return cls(
            id=data["id"],
            sender=data["sender"],
            target=data.get("target"),
            action=CommunicationAction(data["action"]),
            message_type=MessageType(data["message_type"]),
            content=data["content"],
            priority=MessagePriority(data.get("priority", "normal")),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
            requires_response=data.get("requires_response", False),
            response_timeout=data.get("response_timeout", 30.0),
            correlation_id=data.get("correlation_id")
        )


class CommunicationTool(BaseTool):
    """
    沟通协调工具

    用于智能体间的通信和协调，支持多种通信模式。
    """

    def __init__(
        self,
        communication_channel=None,
        version: str = "1.0.0"
    ):
        # 定义参数模式
        schema = ParameterSchema(version="1.0.0")
        schema.add_parameter(ParameterDefinition(
            name="action",
            param_type=ParameterType.STRING,
            description="通信动作: send, broadcast, request, respond, notify, query, acknowledge",
            required=True,
            constraints={"enum": [a.value for a in CommunicationAction]}
        ))
        schema.add_parameter(ParameterDefinition(
            name="message",
            param_type=ParameterType.ANY,
            description="消息内容",
            required=True
        ))
        schema.add_parameter(ParameterDefinition(
            name="target",
            param_type=ParameterType.STRING,
            description="目标智能体 (广播时可选)",
            required=False
        ))
        schema.add_parameter(ParameterDefinition(
            name="message_type",
            param_type=ParameterType.STRING,
            description="消息类型",
            required=False,
            default="info",
            constraints={"enum": [t.value for t in MessageType]}
        ))
        schema.add_parameter(ParameterDefinition(
            name="priority",
            param_type=ParameterType.STRING,
            description="消息优先级",
            required=False,
            default="normal",
            constraints={"enum": [p.value for p in MessagePriority]}
        ))
        schema.add_parameter(ParameterDefinition(
            name="requires_response",
            param_type=ParameterType.BOOLEAN,
            description="是否需要响应",
            required=False,
            default=False
        ))
        schema.add_parameter(ParameterDefinition(
            name="correlation_id",
            param_type=ParameterType.STRING,
            description="关联ID (用于响应消息)",
            required=False
        ))

        super().__init__(
            name="communication",
            description="智能体间通信、消息传递和协调",
            tool_type="communication",
            version=version,
            parameter_schema=schema
        )

        self.communication_channel = communication_channel
        self.message_history: List[Message] = []
        self._message_handlers: Dict[str, List[Callable]] = {}
        self._pending_responses: Dict[str, Dict[str, Any]] = {}
        self._message_counter = 0

    def register_handler(self, message_type: str, handler: Callable):
        """
        注册消息处理器

        Args:
            message_type: 消息类型
            handler: 处理函数
        """
        if message_type not in self._message_handlers:
            self._message_handlers[message_type] = []
        self._message_handlers[message_type].append(handler)

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        执行通信任务

        Args:
            parameters: 通信参数
                - action: 通信动作
                - message: 消息内容
                - target: 目标智能体
                - message_type: 消息类型
                - priority: 优先级
                - requires_response: 是否需要响应
                - correlation_id: 关联ID

        Returns:
            通信结果
        """
        self._record_usage()

        if not self.validate_parameters(parameters, ["action", "message"]):
            return self.create_error_result(
                "Missing required parameters: action and message"
            )

        action_str = parameters["action"]
        message_content = parameters["message"]
        target = parameters.get("target")
        message_type_str = parameters.get("message_type", "info")
        priority_str = parameters.get("priority", "normal")
        requires_response = parameters.get("requires_response", False)
        correlation_id = parameters.get("correlation_id")

        # 验证action
        try:
            action = CommunicationAction(action_str)
        except ValueError:
            return self.create_error_result(
                f"Invalid action: {action_str}. "
                f"Valid actions: {', '.join(a.value for a in CommunicationAction)}"
            )

        # 验证message_type
        try:
            message_type = MessageType(message_type_str)
        except ValueError:
            message_type = MessageType.INFO

        # 验证priority
        try:
            priority = MessagePriority(priority_str)
        except ValueError:
            priority = MessagePriority.NORMAL

        # 广播需要特殊处理
        if action == CommunicationAction.BROADCAST and target:
            target = None  # 广播忽略目标

        # 请求动作需要目标
        if action in [CommunicationAction.SEND, CommunicationAction.REQUEST] and not target:
            if action == CommunicationAction.SEND:
                return self.create_error_result(
                    "Target is required for 'send' action"
                )

        try:
            # 创建消息对象
            self._message_counter += 1
            message = Message(
                id=f"msg_{self._message_counter}_{datetime.now().strftime('%H%M%S%f')}",
                sender=self.name,
                target=target,
                action=action,
                message_type=message_type,
                content=message_content,
                priority=priority,
                requires_response=requires_response or action == CommunicationAction.REQUEST,
                correlation_id=correlation_id
            )

            # 记录消息
            self.message_history.append(message)

            # 执行实际通信
            if self.communication_channel is not None:
                result = self._execute_real_communication(message)
            else:
                result = self._execute_mock_communication(message)

            # 触发消息处理器
            self._trigger_handlers(message)

            # 生成质量评估
            quality = self._assess_communication_quality(message, result)

            return self.create_success_result(
                result,
                metadata={
                    "message_id": message.id,
                    "action": action.value,
                    "message_type": message_type.value
                },
                quality_assessment=quality
            )

        except Exception as e:
            return self.create_error_result(f"Communication failed: {str(e)}")

    def _execute_real_communication(self, message: Message) -> Dict[str, Any]:
        """执行实际通信"""
        if hasattr(self.communication_channel, 'send'):
            return self.communication_channel.send(message.to_dict())
        return self._execute_mock_communication(message)

    def _execute_mock_communication(self, message: Message) -> Dict[str, Any]:
        """执行模拟通信"""
        result = {
            "message_id": message.id,
            "action": message.action.value,
            "target": message.target,
            "message_delivered": True,
            "delivery_time": datetime.now().isoformat(),
            "response_expected": message.requires_response
        }

        if message.action == CommunicationAction.BROADCAST:
            result["broadcast_scope"] = "all_agents"
            result["estimated_recipients"] = 5

        if message.requires_response:
            result["response_deadline"] = message.response_timeout
            self._pending_responses[message.id] = {
                "message": message,
                "created_at": datetime.now(),
                "timeout": message.response_timeout
            }

        return result

    def _trigger_handlers(self, message: Message):
        """触发消息处理器"""
        handlers = self._message_handlers.get(message.message_type.value, [])
        for handler in handlers:
            try:
                handler(message)
            except Exception as e:
                # 处理器错误不应影响主流程
                pass

    def _assess_communication_quality(
        self,
        message: Message,
        result: Dict[str, Any]
    ) -> QualityAssessment:
        """评估通信质量"""
        # 消息是否成功投递
        delivered = result.get("message_delivered", False)

        # 基于优先级评估相关性
        relevance_map = {
            MessagePriority.URGENT: 1.0,
            MessagePriority.HIGH: 0.9,
            MessagePriority.NORMAL: 0.7,
            MessagePriority.LOW: 0.5
        }
        relevance = relevance_map.get(message.priority, 0.7)

        # 置信度基于投递状态
        confidence = 0.9 if delivered else 0.3

        # 完整性基于消息内容
        completeness = 0.8 if message.content else 0.3

        assessment = QualityAssessment(
            relevance_score=relevance,
            confidence_score=confidence,
            completeness_score=completeness,
            assessment_details={
                "message_id": message.id,
                "delivered": delivered,
                "priority": message.priority.value,
                "requires_response": message.requires_response
            }
        )
        assessment.determine_quality_level()

        return assessment

    def get_message_history(
        self,
        limit: int = 100,
        message_type: str = None,
        target: str = None
    ) -> List[Dict[str, Any]]:
        """
        获取消息历史

        Args:
            limit: 返回数量限制
            message_type: 过滤消息类型
            target: 过滤目标

        Returns:
            消息列表
        """
        messages = self.message_history[-limit:]

        if message_type:
            messages = [m for m in messages if m.message_type.value == message_type]

        if target:
            messages = [m for m in messages if m.target == target]

        return [m.to_dict() for m in messages]

    def get_pending_responses(self) -> List[Dict[str, Any]]:
        """获取待响应的消息"""
        now = datetime.now()
        pending = []

        for msg_id, info in list(self._pending_responses.items()):
            elapsed = (now - info["created_at"]).total_seconds()
            if elapsed < info["timeout"]:
                pending.append({
                    "message_id": msg_id,
                    "elapsed_seconds": elapsed,
                    "timeout": info["timeout"],
                    "remaining": info["timeout"] - elapsed
                })
            else:
                # 超时，移除
                del self._pending_responses[msg_id]

        return pending

    def mark_response_received(self, message_id: str, response: Any = None):
        """
        标记已收到响应

        Args:
            message_id: 消息ID
            response: 响应内容
        """
        if message_id in self._pending_responses:
            del self._pending_responses[message_id]
