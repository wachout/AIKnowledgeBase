"""
多层强化学习智能体系统 - 层次化智能体基类
定义层次化系统中智能体的通用接口和行为
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Generator, Set, AsyncGenerator
import asyncio
import logging
import uuid

from ..types import (
    LayerType, AgentState, AgentAction, Policy, Experience,
    AgentMemory, LayerMessage, MessageType
)


logger = logging.getLogger(__name__)


class AgentCapability(Enum):
    """智能体能力枚举"""
    # 通用能力
    REASONING = auto()          # 推理
    PLANNING = auto()           # 规划
    COMMUNICATION = auto()      # 通信
    LEARNING = auto()           # 学习
    
    # 决策层能力
    STRATEGY_FORMULATION = auto()   # 策略制定
    RISK_ASSESSMENT = auto()        # 风险评估
    CONSENSUS_BUILDING = auto()     # 共识构建
    
    # 实施层能力
    DESIGN = auto()             # 设计
    IMPLEMENTATION = auto()     # 实现
    TESTING = auto()            # 测试
    DOCUMENTATION = auto()      # 文档
    COORDINATION = auto()       # 协调
    
    # 检验层能力
    QUALITY_INSPECTION = auto()     # 质量检查
    LOGIC_VALIDATION = auto()       # 逻辑验证
    PERFORMANCE_ANALYSIS = auto()   # 性能分析
    SECURITY_AUDIT = auto()         # 安全审计
    COMPLIANCE_CHECK = auto()       # 合规检查


@dataclass
class HierarchicalAgentConfig:
    """层次化智能体配置"""
    agent_id: str = field(default_factory=lambda: f"agent_{uuid.uuid4().hex[:8]}")
    name: str = ""
    layer: LayerType = LayerType.DECISION
    role: str = ""
    capabilities: Set[AgentCapability] = field(default_factory=set)
    
    # 策略参数
    learning_rate: float = 0.001
    exploration_rate: float = 0.1
    discount_factor: float = 0.99
    
    # 行为参数
    max_actions_per_turn: int = 5
    response_timeout: float = 30.0
    
    # 记忆参数
    max_short_term_memory: int = 100
    enable_long_term_memory: bool = True
    
    # 通信参数
    enable_proactive_communication: bool = True
    communication_priority: int = 5
    
    def __post_init__(self):
        if not self.name:
            self.name = f"{self.layer.name}_{self.role}"


class BaseHierarchicalAgent(ABC):
    """
    层次化智能体基类
    
    所有层次化系统中的智能体都应继承此类，
    实现特定层级的行为和能力。
    """
    
    def __init__(
        self,
        config: HierarchicalAgentConfig,
        llm_adapter=None
    ):
        self.config = config
        self.agent_id = config.agent_id
        self.name = config.name
        self.layer = config.layer
        self.role = config.role
        self.capabilities = config.capabilities
        
        # LLM适配器
        self.llm_adapter = llm_adapter
        
        # 状态
        self._state = AgentState(
            agent_id=self.agent_id,
            agent_type=self.__class__.__name__,
            layer=self.layer.value
        )
        
        # 策略
        self._policy = Policy(
            agent_type=self.__class__.__name__,
            layer=self.layer.value,
            learning_rate=config.learning_rate,
            exploration_rate=config.exploration_rate
        )
        
        # 通信
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._message_handlers: Dict[MessageType, List[callable]] = {}
        
        # 经验
        self._experience_buffer: List[Experience] = []
        
        # 日志
        self._logger = logging.getLogger(f"{__name__}.{self.name}")
        
        # 性能追踪
        self._action_count = 0
        self._success_count = 0
        self._total_reward = 0.0
    
    # ==================== 抽象方法 ====================
    
    @abstractmethod
    async def act(
        self,
        context: Dict[str, Any]
    ) -> Generator[str, None, Dict[str, Any]]:
        """
        执行动作
        
        Args:
            context: 动作上下文
            
        Yields:
            动作过程中的输出
            
        Returns:
            动作结果
        """
        pass
    
    @abstractmethod
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        """
        选择动作（基于当前策略）
        
        Args:
            state: 当前状态
            
        Returns:
            选择的动作
        """
        pass
    
    @abstractmethod
    def get_prompt(self, context: Dict[str, Any]) -> str:
        """
        获取 LLM 提示词
        
        Args:
            context: 上下文信息
            
        Returns:
            提示词字符串
        """
        pass
    
    # ==================== 状态管理 ====================
    
    @property
    def state(self) -> AgentState:
        """获取当前状态"""
        return self._state
    
    def update_state(self, updates: Dict[str, Any]):
        """更新状态"""
        for key, value in updates.items():
            if hasattr(self._state, key):
                setattr(self._state, key, value)
        self._state.last_action_time = datetime.now()
    
    def get_state_features(self) -> Dict[str, Any]:
        """获取状态特征（用于策略学习）"""
        return {
            "agent_id": self.agent_id,
            "layer": self.layer.value,
            "has_task": self._state.current_task is not None,
            "memory_size": len(self._state.memory.short_term),
            "buffer_size": len(self._state.communication_buffer),
            "is_active": self._state.is_active,
            "performance_metrics": self._state.performance_metrics
        }
    
    # ==================== 策略管理 ====================
    
    @property
    def policy(self) -> Policy:
        """获取当前策略"""
        return self._policy
    
    def update_policy(self, gradient: Dict[str, float]):
        """更新策略参数"""
        for param, delta in gradient.items():
            if param in self._policy.parameters:
                self._policy.parameters[param] += self._policy.learning_rate * delta
        self._policy.last_updated = datetime.now()
    
    def get_action_probability(self, action: AgentAction) -> float:
        """获取动作概率"""
        return self._policy.action_preferences.get(action.value, 1.0 / len(AgentAction))
    
    def explore_or_exploit(self, state: Dict[str, Any]) -> AgentAction:
        """
        探索-利用选择
        
        Args:
            state: 当前状态
            
        Returns:
            选择的动作
        """
        import random
        
        if random.random() < self._policy.exploration_rate:
            # 探索：随机选择
            layer_actions = self._get_layer_actions()
            return random.choice(layer_actions)
        else:
            # 利用：使用学到的策略
            return self.select_action(state)
    
    def _get_layer_actions(self) -> List[AgentAction]:
        """获取该层可用的动作"""
        if self.layer == LayerType.DECISION:
            return [
                AgentAction.PROPOSE_STRATEGY,
                AgentAction.EVALUATE_PROPOSAL,
                AgentAction.SYNTHESIZE,
                AgentAction.CHALLENGE
            ]
        elif self.layer == LayerType.IMPLEMENTATION:
            return [
                AgentAction.DESIGN,
                AgentAction.IMPLEMENT,
                AgentAction.TEST,
                AgentAction.COORDINATE,
                AgentAction.DOCUMENT
            ]
        else:  # VALIDATION
            return [
                AgentAction.INSPECT,
                AgentAction.VALIDATE,
                AgentAction.REPORT,
                AgentAction.ESCALATE
            ]
    
    # ==================== 记忆管理 ====================
    
    def remember(self, item: Dict[str, Any], memory_type: str = "short"):
        """
        记忆信息
        
        Args:
            item: 要记忆的信息
            memory_type: 记忆类型 (short/long/working)
        """
        item["timestamp"] = datetime.now().isoformat()
        
        if memory_type == "short":
            self._state.memory.add_short_term(item)
        elif memory_type == "long":
            self._state.memory.long_term.append(item)
        elif memory_type == "working":
            key = item.get("key", f"item_{len(self._state.memory.working)}")
            self._state.memory.working[key] = item
    
    def recall(
        self,
        query: str = "",
        memory_type: str = "short",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        回忆信息
        
        Args:
            query: 查询关键词（简单匹配）
            memory_type: 记忆类型
            limit: 返回数量限制
            
        Returns:
            匹配的记忆列表
        """
        if memory_type == "short":
            memories = self._state.memory.short_term
        elif memory_type == "long":
            memories = self._state.memory.long_term
        else:
            return list(self._state.memory.working.values())
        
        if not query:
            return memories[-limit:]
        
        # 简单关键词匹配
        matched = []
        for mem in memories:
            mem_str = str(mem).lower()
            if query.lower() in mem_str:
                matched.append(mem)
                if len(matched) >= limit:
                    break
        
        return matched
    
    def clear_memory(self, memory_type: str = "short"):
        """清除记忆"""
        if memory_type == "short":
            self._state.memory.short_term.clear()
        elif memory_type == "long":
            self._state.memory.long_term.clear()
        elif memory_type == "working":
            self._state.memory.working.clear()
        elif memory_type == "all":
            self._state.memory.short_term.clear()
            self._state.memory.long_term.clear()
            self._state.memory.working.clear()
    
    # ==================== 通信 ====================
    
    async def send_message(
        self,
        target_layer: int,
        target_agent: str,
        message_type: MessageType,
        payload: Dict[str, Any],
        priority: int = 5
    ) -> LayerMessage:
        """发送消息"""
        message = LayerMessage(
            source_layer=self.layer.value,
            target_layer=target_layer,
            source_agent=self.agent_id,
            target_agent=target_agent,
            message_type=message_type,
            payload=payload,
            priority=priority
        )
        
        # 记录到通信缓冲
        self._state.communication_buffer.append({
            "direction": "out",
            "message_id": message.message_id,
            "target": target_agent,
            "type": message_type.value,
            "timestamp": datetime.now().isoformat()
        })
        
        return message
    
    async def receive_message(self, message: LayerMessage):
        """接收消息"""
        await self._message_queue.put(message)
        
        # 记录到通信缓冲
        self._state.communication_buffer.append({
            "direction": "in",
            "message_id": message.message_id,
            "source": message.source_agent,
            "type": message.message_type.value,
            "timestamp": datetime.now().isoformat()
        })
        
        # 触发处理器
        handlers = self._message_handlers.get(message.message_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                self._logger.error(f"消息处理错误: {e}")
    
    def register_message_handler(
        self,
        message_type: MessageType,
        handler: callable
    ):
        """注册消息处理器"""
        if message_type not in self._message_handlers:
            self._message_handlers[message_type] = []
        self._message_handlers[message_type].append(handler)
    
    # ==================== 经验管理 ====================
    
    def record_experience(
        self,
        state: Dict[str, Any],
        action: AgentAction,
        reward: float,
        next_state: Dict[str, Any],
        done: bool = False
    ) -> Experience:
        """记录经验"""
        exp = Experience(
            layer=self.layer.value,
            agent_id=self.agent_id,
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=done
        )
        
        self._experience_buffer.append(exp)
        self._total_reward += reward
        
        return exp
    
    def get_experiences(self, limit: int = 100) -> List[Experience]:
        """获取经验"""
        return self._experience_buffer[-limit:]
    
    def clear_experiences(self):
        """清除经验缓冲"""
        self._experience_buffer.clear()
    
    # ==================== 能力检查 ====================
    
    def has_capability(self, capability: AgentCapability) -> bool:
        """检查是否具有某项能力"""
        return capability in self.capabilities
    
    def add_capability(self, capability: AgentCapability):
        """添加能力"""
        self.capabilities.add(capability)
    
    def remove_capability(self, capability: AgentCapability):
        """移除能力"""
        self.capabilities.discard(capability)
    
    # ==================== LLM 交互 ====================
    
    async def call_llm(
        self,
        prompt: str,
        stream: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        调用 LLM
        
        Args:
            prompt: 提示词
            stream: 是否流式输出
            
        Yields:
            LLM 输出片段
            
        Note:
            完整响应存储在 self.last_llm_response 属性中
        """
        if not self.llm_adapter:
            yield "[LLM未配置]"
            self.last_llm_response = "[LLM未配置]"
            return
        
        try:
            full_response = []
            
            # 尝试不同的调用方式，兼容 LangChain ChatTongyi/ChatOpenAI
            if stream and hasattr(self.llm_adapter, 'astream'):
                # LangChain 异步流式
                async for chunk in self.llm_adapter.astream(prompt):
                    content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    yield content
                    full_response.append(content)
            elif hasattr(self.llm_adapter, 'ainvoke'):
                # LangChain 异步调用
                response = await self.llm_adapter.ainvoke(prompt)
                content = response.content if hasattr(response, 'content') else str(response)
                yield content
                full_response.append(content)
            elif hasattr(self.llm_adapter, 'invoke'):
                # LangChain 同步调用（在异步上下文中运行）
                import asyncio
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, self.llm_adapter.invoke, prompt)
                content = response.content if hasattr(response, 'content') else str(response)
                yield content
                full_response.append(content)
            elif hasattr(self.llm_adapter, 'chat_stream'):
                # 自定义流式接口
                async for chunk in self.llm_adapter.chat_stream(prompt):
                    yield chunk
                    full_response.append(chunk)
            elif hasattr(self.llm_adapter, 'chat'):
                # 自定义 chat 接口
                response = await self.llm_adapter.chat(prompt)
                yield response
                full_response.append(response)
            else:
                # 最后尝试直接调用
                response = str(self.llm_adapter(prompt))
                yield response
                full_response.append(response)
            
            self.last_llm_response = "".join(full_response)  # 存储结果
            
        except Exception as e:
            error_msg = f"[LLM调用错误: {str(e)}]"
            yield error_msg
            self.last_llm_response = error_msg
    
    def parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        解析 LLM 响应
        
        Args:
            response: LLM 响应文本
            
        Returns:
            解析后的结构化数据
        """
        # 默认实现：返回原始响应
        return {"raw_response": response, "parsed": False}
    
    # ==================== 性能追踪 ====================
    
    def record_action_result(self, success: bool, reward: float = 0.0):
        """记录动作结果"""
        self._action_count += 1
        if success:
            self._success_count += 1
        self._total_reward += reward
        
        # 更新性能指标
        self._state.performance_metrics["action_count"] = self._action_count
        self._state.performance_metrics["success_rate"] = (
            self._success_count / self._action_count
            if self._action_count > 0 else 0.0
        )
        self._state.performance_metrics["total_reward"] = self._total_reward
        self._state.performance_metrics["avg_reward"] = (
            self._total_reward / self._action_count
            if self._action_count > 0 else 0.0
        )
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "layer": self.layer.name,
            "action_count": self._action_count,
            "success_count": self._success_count,
            "success_rate": self._state.performance_metrics.get("success_rate", 0.0),
            "total_reward": self._total_reward,
            "avg_reward": self._state.performance_metrics.get("avg_reward", 0.0)
        }
    
    # ==================== 生命周期 ====================
    
    async def initialize(self):
        """初始化智能体"""
        self._state.is_active = True
        self._logger.info(f"智能体 {self.name} 初始化完成")
    
    async def shutdown(self):
        """关闭智能体"""
        self._state.is_active = False
        
        # 清理消息队列
        while not self._message_queue.empty():
            try:
                self._message_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        self._logger.info(f"智能体 {self.name} 已关闭")
    
    def reset(self):
        """重置智能体状态"""
        self._state = AgentState(
            agent_id=self.agent_id,
            agent_type=self.__class__.__name__,
            layer=self.layer.value
        )
        self._action_count = 0
        self._success_count = 0
        self._total_reward = 0.0
        self._experience_buffer.clear()
    
    # ==================== 配置导出 ====================
    
    def get_system_prompt(self) -> str:
        """
        获取智能体的系统提示词
        
        Returns:
            智能体的完整系统提示词
        """
        capabilities_text = ", ".join(c.name for c in self.capabilities)
        
        prompt = f"""你是一位{self.name}，属于{self.layer.name}层。
角色定位：{self.role}
具备能力：{capabilities_text}

请根据你的角色定位和能力，完成相应的任务。"""
        
        return prompt
    
    def to_config_dict(self) -> Dict[str, Any]:
        """
        导出智能体的完整配置信息
        
        用于持久化保存智能体的配置，包含ID、名称、层级、
        角色、能力、系统提示词等。
        
        Returns:
            智能体配置字典
        """
        config = {
            "agent_id": self.agent_id,
            "agent_name": self.name,
            "layer": self.layer.name if hasattr(self.layer, 'name') else str(self.layer),
            "role": self.role,
            "capabilities": [c.name for c in self.capabilities],
            "system_prompt": self.get_system_prompt(),
            "config": {
                "learning_rate": self.config.learning_rate,
                "exploration_rate": self.config.exploration_rate,
                "discount_factor": self.config.discount_factor,
                "max_actions_per_turn": self.config.max_actions_per_turn,
                "response_timeout": self.config.response_timeout
            },
            "performance": self.get_performance_summary(),
            "created_at": datetime.now().isoformat()
        }
        
        # 添加子类可能定义的额外属性
        if hasattr(self, 'domain'):
            config["domain"] = self.domain
        if hasattr(self, 'expertise'):
            config["expertise"] = self.expertise
        if hasattr(self, 'reason'):
            config["reason"] = self.reason
        
        return config
    
    # ==================== 魔术方法 ====================
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.agent_id}, layer={self.layer.name})>"
    
    def __str__(self) -> str:
        return f"{self.name} ({self.role})"
