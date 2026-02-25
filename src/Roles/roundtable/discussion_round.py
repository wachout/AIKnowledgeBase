"""
讨论轮次模块

包含讨论轮次相关组件:
- DiscussionRound: 讨论轮次
- CommunicationProtocolExtension: 通信协议扩展
"""

from typing import Dict, Any, List
from datetime import datetime
import logging

from .communication import MessageType, CommunicationProtocol

logger = logging.getLogger(__name__)


class DiscussionRound:
    """讨论轮次"""

    def __init__(self, round_number: int, topic: str):
        self.round_number = round_number
        self.topic = topic
        self.start_time = datetime.now().isoformat()
        self.end_time = None
        self.participants = []
        self.speeches = []
        self.consensus_updates = []
        self.divergence_updates = []
        self.coordination_notes = []
        self.round_summary = ""

    def add_speech(self, speaker: str, content: str, speech_type: str = "normal"):
        """添加发言"""
        speech = {
            "speaker": speaker,
            "content": content,
            "speech_type": speech_type,
            "timestamp": datetime.now().isoformat(),
            "round": self.round_number
        }
        self.speeches.append(speech)

    def add_consensus_update(self, update: Dict[str, Any]):
        """添加共识更新"""
        self.consensus_updates.append(update)

    def add_divergence_update(self, update: Dict[str, Any]):
        """添加分歧更新"""
        self.divergence_updates.append(update)

    def set_summary(self, summary: str):
        """设置轮次总结"""
        self.round_summary = summary
        self.end_time = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "round_number": self.round_number,
            "topic": self.topic,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "participants": self.participants,
            "speeches": self.speeches,
            "consensus_updates": self.consensus_updates,
            "divergence_updates": self.divergence_updates,
            "coordination_notes": self.coordination_notes,
            "round_summary": self.round_summary
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DiscussionRound':
        """
        从字典创建 DiscussionRound 实例
        
        Args:
            data: 包含轮次数据的字典
            
        Returns:
            新的 DiscussionRound 实例
        """
        round_number = data.get("round_number", 0)
        topic = data.get("topic", "")
        
        instance = cls(round_number, topic)
        instance.start_time = data.get("start_time", instance.start_time)
        instance.end_time = data.get("end_time")
        instance.participants = data.get("participants", [])
        instance.speeches = data.get("speeches", [])
        instance.consensus_updates = data.get("consensus_updates", [])
        instance.divergence_updates = data.get("divergence_updates", [])
        instance.coordination_notes = data.get("coordination_notes", [])
        instance.round_summary = data.get("round_summary", "")
        
        return instance

    def update_from_dict(self, data: Dict[str, Any]):
        """
        从字典更新当前实例
        
        Args:
            data: 包含更新数据的字典
        """
        if "topic" in data:
            self.topic = data["topic"]
        if "start_time" in data:
            self.start_time = data["start_time"]
        if "end_time" in data:
            self.end_time = data["end_time"]
        if "participants" in data:
            self.participants = data["participants"]
        if "speeches" in data:
            self.speeches = data["speeches"]
        if "consensus_updates" in data:
            self.consensus_updates = data["consensus_updates"]
        if "divergence_updates" in data:
            self.divergence_updates = data["divergence_updates"]
        if "coordination_notes" in data:
            self.coordination_notes = data["coordination_notes"]
        if "round_summary" in data:
            self.round_summary = data["round_summary"]

    def merge_speeches(self, new_speeches: List[Dict[str, Any]]):
        """
        合并新的发言记录，避免重复
        
        Args:
            new_speeches: 新的发言列表
        """
        existing_timestamps = {s.get("timestamp") for s in self.speeches}
        for speech in new_speeches:
            if speech.get("timestamp") not in existing_timestamps:
                self.speeches.append(speech)

    def get_status(self) -> str:
        """
        获取轮次状态
        
        Returns:
            状态字符串: pending, in_progress, completed
        """
        if self.end_time:
            return "completed"
        elif self.speeches:
            return "in_progress"
        else:
            return "pending"


class CommunicationProtocolExtension:
    """
    通信协议扩展类
    负责管理自定义消息类型和协议扩展
    """

    def __init__(self, communication_protocol: CommunicationProtocol):
        self.protocol = communication_protocol
        self.supported_message_types = set(mt.value for mt in MessageType)
        self.message_handlers: Dict[MessageType, callable] = {}

    def register_custom_message_type(self, message_type: str, validation_func: callable = None, processing_func: callable = None):
        """注册自定义消息类型"""
        if message_type not in self.supported_message_types:
            self.supported_message_types.add(message_type)

        if processing_func:
            try:
                self.message_handlers[MessageType(message_type)] = processing_func
            except ValueError:
                logger.warning(f"无法将 {message_type} 转换为 MessageType 枚举")

        logger.info(f"已注册自定义消息类型: {message_type}")

    def extend_protocol(self, extension_name: str, extension_config: Dict[str, Any]):
        """扩展通信协议"""
        try:
            extension_type = extension_config.get('type', '')

            if extension_type == 'message_type':
                # 添加新的消息类型
                new_type = extension_config.get('message_type', '')
                validation_func = extension_config.get('validation_func')
                processing_func = extension_config.get('processing_func')

                self.register_custom_message_type(new_type, validation_func, processing_func)

            elif extension_type == 'communication_pattern':
                # 添加新的通信模式
                pattern_name = extension_config.get('pattern_name', '')
                pattern_logic = extension_config.get('pattern_logic')

                if pattern_logic:
                    setattr(self.protocol, f"create_{pattern_name}_message", pattern_logic)
                    logger.info(f"已添加通信模式: {pattern_name}")

            elif extension_type == 'middleware':
                # 添加中间件
                middleware_func = extension_config.get('middleware_func')
                if middleware_func:
                    # 在消息处理前应用中间件
                    original_handlers = self.message_handlers.copy()
                    for msg_type, handler in original_handlers.items():
                        def wrapped_handler(message, original_handler=handler, middleware=middleware_func):
                            processed_message = middleware(message)
                            return original_handler(processed_message)
                        self.message_handlers[msg_type] = wrapped_handler

                    logger.info("已添加消息处理中间件")

            logger.info(f"通信协议扩展完成: {extension_name}")

        except Exception as e:
            logger.error(f"通信协议扩展失败: {e}")

    def create_extension_template(self) -> Dict[str, Any]:
        """创建扩展模板"""
        return {
            "message_type_extension": {
                "type": "message_type",
                "message_type": "custom_type",
                "validation_func": None,  # 验证函数
                "processing_func": None   # 处理函数
            },
            "communication_pattern_extension": {
                "type": "communication_pattern",
                "pattern_name": "custom_pattern",
                "pattern_logic": None  # 创建消息的逻辑函数
            },
            "middleware_extension": {
                "type": "middleware",
                "middleware_func": None  # 中间件函数
            }
        }
