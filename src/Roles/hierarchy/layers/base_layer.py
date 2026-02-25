"""
多层强化学习智能体系统 - 层基类
定义所有层的通用接口和基础行为
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Generator, Callable, AsyncGenerator
import asyncio
import logging

from ..types import (
    LayerType, LayerState, LayerMessage, MessageType,
    AgentState, Task, Experience, ExecutionStatus,
    DecisionOutput, ImplementationOutput, ValidationOutput
)


logger = logging.getLogger(__name__)


@dataclass
class LayerConfig:
    """层配置"""
    layer_type: LayerType
    name: str = ""
    max_agents: int = 10
    timeout_seconds: float = 300.0
    retry_attempts: int = 3
    enable_logging: bool = True
    enable_metrics: bool = True
    custom_settings: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.name:
            self.name = self.layer_type.name.lower()


@dataclass
class LayerContext:
    """层执行上下文"""
    session_id: str = ""
    iteration: int = 0
    query: str = ""
    parent_output: Optional[Any] = None  # 上层输出
    feedback: Optional[Any] = None       # 反馈信息
    constraints: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)


class LayerMetrics:
    """层指标收集器"""
    
    def __init__(self):
        self.execution_times: List[float] = []
        self.success_count: int = 0
        self.failure_count: int = 0
        self.agent_contributions: Dict[str, int] = {}
        self.reward_history: List[float] = []
    
    def record_execution(self, duration: float, success: bool, reward: float = 0.0):
        """记录一次执行"""
        self.execution_times.append(duration)
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.reward_history.append(reward)
    
    def record_agent_contribution(self, agent_id: str):
        """记录智能体贡献"""
        self.agent_contributions[agent_id] = self.agent_contributions.get(agent_id, 0) + 1
    
    @property
    def avg_execution_time(self) -> float:
        return sum(self.execution_times) / len(self.execution_times) if self.execution_times else 0.0
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
    
    @property
    def avg_reward(self) -> float:
        return sum(self.reward_history) / len(self.reward_history) if self.reward_history else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "avg_execution_time": self.avg_execution_time,
            "success_rate": self.success_rate,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "avg_reward": self.avg_reward,
            "total_executions": len(self.execution_times),
            "top_contributors": sorted(
                self.agent_contributions.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }


class BaseLayer(ABC):
    """
    层基类
    定义三层架构中每层的通用接口和行为
    """
    
    def __init__(self, config: LayerConfig):
        self.config = config
        self.layer_type = config.layer_type
        self.layer_index = config.layer_type.value
        self.name = config.name
        
        # 状态管理
        self._state = LayerState(
            layer_type=config.layer_type,
            current_phase="initialized"
        )
        
        # 智能体管理
        self._agents: Dict[str, Any] = {}  # 层内智能体
        
        # 通信
        self._message_handlers: Dict[MessageType, List[Callable]] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        
        # 指标
        self._metrics = LayerMetrics()
        
        # 日志
        self._logger = logging.getLogger(f"{__name__}.{self.name}")
    
    # ==================== 抽象方法 ====================
    
    @abstractmethod
    async def process(self, context: LayerContext) -> Any:
        """
        处理层的主要逻辑
        
        Args:
            context: 层执行上下文
            
        Returns:
            层输出（DecisionOutput/ImplementationOutput/ValidationOutput）
        """
        pass
    
    @abstractmethod
    def initialize_agents(self, task_context: Dict[str, Any]) -> List[str]:
        """
        初始化层内智能体
        
        Args:
            task_context: 任务上下文，用于决定创建哪些智能体
            
        Returns:
            创建的智能体ID列表
        """
        pass
    
    @abstractmethod
    def compute_layer_reward(self, output: Any) -> float:
        """
        计算层奖励
        
        Args:
            output: 层输出
            
        Returns:
            奖励值 [-1, 1]
        """
        pass
    
    # ==================== 流式处理 ====================
    
    async def process_stream(self, context: LayerContext) -> AsyncGenerator[str, None]:
        """
        流式处理（支持逐步输出）
        
        Args:
            context: 层执行上下文
            
        Yields:
            处理过程中的中间输出
            
        Note:
            最终结果存储在 self.last_result 属性中
        """
        self._update_phase("processing")
        yield f"[{self.name}] 开始处理..."
        
        try:
            # 默认实现：调用 process 方法
            result = await self.process(context)
            yield f"[{self.name}] 处理完成"
            self.last_result = result  # 存储结果
        except Exception as e:
            yield f"[{self.name}] 处理错误: {str(e)}"
            raise
        finally:
            self._update_phase("completed")
    
    # ==================== 智能体管理 ====================
    
    def register_agent(self, agent_id: str, agent: Any):
        """注册智能体"""
        self._agents[agent_id] = agent
        self._state.agents[agent_id] = AgentState(
            agent_id=agent_id,
            agent_type=type(agent).__name__,
            layer=self.layer_index
        )
        self._logger.debug(f"注册智能体: {agent_id}")
    
    def unregister_agent(self, agent_id: str):
        """注销智能体"""
        if agent_id in self._agents:
            del self._agents[agent_id]
        if agent_id in self._state.agents:
            del self._state.agents[agent_id]
        self._logger.debug(f"注销智能体: {agent_id}")
    
    def get_agent(self, agent_id: str) -> Optional[Any]:
        """获取智能体"""
        return self._agents.get(agent_id)
    
    def get_all_agents(self) -> Dict[str, Any]:
        """获取所有智能体"""
        return self._agents.copy()
    
    def get_agent_ids(self) -> List[str]:
        """获取所有智能体ID"""
        return list(self._agents.keys())
    
    # ==================== 消息处理 ====================
    
    def subscribe(self, message_type: MessageType, handler: Callable):
        """订阅消息类型"""
        if message_type not in self._message_handlers:
            self._message_handlers[message_type] = []
        self._message_handlers[message_type].append(handler)
    
    def unsubscribe(self, message_type: MessageType, handler: Callable):
        """取消订阅"""
        if message_type in self._message_handlers:
            if handler in self._message_handlers[message_type]:
                self._message_handlers[message_type].remove(handler)
    
    async def receive_message(self, message: LayerMessage):
        """接收消息"""
        await self._message_queue.put(message)
        
        # 触发处理器
        handlers = self._message_handlers.get(message.message_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                self._logger.error(f"消息处理器错误: {e}")
    
    async def get_pending_messages(self, timeout: float = 0.1) -> List[LayerMessage]:
        """获取待处理消息"""
        messages = []
        try:
            while True:
                message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=timeout
                )
                messages.append(message)
        except asyncio.TimeoutError:
            pass
        return messages
    
    # ==================== 状态管理 ====================
    
    @property
    def state(self) -> LayerState:
        """获取当前状态"""
        return self._state
    
    def _update_phase(self, phase: str):
        """更新当前阶段"""
        self._state.current_phase = phase
        self._logger.debug(f"阶段更新: {phase}")
    
    def get_state_snapshot(self) -> Dict[str, Any]:
        """获取状态快照"""
        return {
            "layer_type": self.layer_type.name,
            "layer_index": self.layer_index,
            "name": self.name,
            "current_phase": self._state.current_phase,
            "agent_count": len(self._agents),
            "pending_tasks": len(self._state.pending_tasks),
            "completed_tasks": len(self._state.completed_tasks),
            "metrics": self._state.metrics
        }
    
    # ==================== 任务管理 ====================
    
    def add_task(self, task: Task):
        """添加待处理任务"""
        self._state.pending_tasks.append(task)
    
    def complete_task(self, task_id: str):
        """标记任务完成"""
        for i, task in enumerate(self._state.pending_tasks):
            if task.task_id == task_id:
                task.status = ExecutionStatus.COMPLETED
                self._state.completed_tasks.append(task)
                self._state.pending_tasks.pop(i)
                break
    
    def get_pending_tasks(self) -> List[Task]:
        """获取待处理任务"""
        return self._state.pending_tasks.copy()
    
    # ==================== 经验收集 ====================
    
    def collect_experience(
        self,
        agent_id: str,
        state: Dict[str, Any],
        action: Any,
        reward: float,
        next_state: Dict[str, Any],
        done: bool = False
    ) -> Experience:
        """收集经验用于强化学习"""
        from ..types import Experience, AgentAction
        
        exp = Experience(
            layer=self.layer_index,
            agent_id=agent_id,
            state=state,
            action=action if isinstance(action, AgentAction) else None,
            reward=reward,
            next_state=next_state,
            done=done,
            metadata={"layer_name": self.name}
        )
        
        self._metrics.record_agent_contribution(agent_id)
        return exp
    
    # ==================== 指标 ====================
    
    @property
    def metrics(self) -> LayerMetrics:
        """获取指标收集器"""
        return self._metrics
    
    def record_execution_result(self, duration: float, success: bool, reward: float = 0.0):
        """记录执行结果"""
        self._metrics.record_execution(duration, success, reward)
        self._state.metrics["last_execution_time"] = duration
        self._state.metrics["last_reward"] = reward
    
    # ==================== 生命周期 ====================
    
    async def initialize(self):
        """初始化层"""
        self._update_phase("initializing")
        self._logger.info(f"初始化层: {self.name}")
        self._update_phase("ready")
    
    async def shutdown(self):
        """关闭层"""
        self._update_phase("shutting_down")
        self._logger.info(f"关闭层: {self.name}")
        
        # 清理智能体
        for agent_id in list(self._agents.keys()):
            self.unregister_agent(agent_id)
        
        # 清理消息队列
        while not self._message_queue.empty():
            try:
                self._message_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        self._update_phase("stopped")
    
    # ==================== 辅助方法 ====================
    
    def _log(self, level: str, message: str, **kwargs):
        """记录日志"""
        if self.config.enable_logging:
            log_func = getattr(self._logger, level.lower(), self._logger.info)
            log_func(message, extra=kwargs)
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(layer={self.layer_type.name}, agents={len(self._agents)})>"
