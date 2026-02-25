"""
层间通信模块
管理三层架构之间的消息传递、任务分发和反馈回路
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Set
from collections import defaultdict
import uuid

from .types import LayerMessage, MessageType, LayerType

logger = logging.getLogger(__name__)


class LayerCommunicationBus:
    """
    层间通信总线
    负责消息的路由、缓冲和投递
    """
    
    def __init__(self):
        self._message_queues: Dict[int, asyncio.Queue] = {
            1: asyncio.Queue(),  # 决策层
            2: asyncio.Queue(),  # 实施层
            3: asyncio.Queue(),  # 检验层
        }
        self._subscribers: Dict[int, Dict[MessageType, List[Callable]]] = defaultdict(lambda: defaultdict(list))
        self._message_history: List[LayerMessage] = []
        self._pending_responses: Dict[str, asyncio.Event] = {}
        self._response_data: Dict[str, Any] = {}
        self._is_running = False
        self._dispatcher_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动通信总线"""
        self._is_running = True
        self._dispatcher_task = asyncio.create_task(self._message_dispatcher())
        logger.info("层间通信总线已启动")
    
    async def stop(self):
        """停止通信总线"""
        self._is_running = False
        if self._dispatcher_task:
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except asyncio.CancelledError:
                pass
        logger.info("层间通信总线已停止")
    
    async def _message_dispatcher(self):
        """消息分发器"""
        while self._is_running:
            for layer in [1, 2, 3]:
                try:
                    # 非阻塞检查队列
                    if not self._message_queues[layer].empty():
                        message = await asyncio.wait_for(
                            self._message_queues[layer].get(),
                            timeout=0.1
                        )
                        await self._dispatch_message(layer, message)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"消息分发错误: {e}")
            
            await asyncio.sleep(0.01)  # 避免CPU占用过高
    
    async def _dispatch_message(self, layer: int, message: LayerMessage):
        """分发消息给订阅者"""
        subscribers = self._subscribers[layer].get(message.message_type, [])
        
        for handler in subscribers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"消息处理错误: {e}, 消息: {message.message_id}")
    
    async def send(self, message: LayerMessage) -> bool:
        """
        发送消息
        
        Args:
            message: 层间消息
        
        Returns:
            是否发送成功
        """
        try:
            target_layer = message.target_layer
            if target_layer not in self._message_queues:
                logger.error(f"无效的目标层: {target_layer}")
                return False
            
            # 记录消息历史
            self._message_history.append(message)
            
            # 放入目标层的队列
            await self._message_queues[target_layer].put(message)
            
            logger.debug(f"消息已发送: {message.source_layer} -> {message.target_layer}, 类型: {message.message_type.value}")
            return True
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False
    
    async def send_and_wait(self, message: LayerMessage, timeout: float = 30.0) -> Optional[Any]:
        """
        发送消息并等待响应
        
        Args:
            message: 层间消息
            timeout: 超时时间（秒）
        
        Returns:
            响应数据
        """
        message.requires_response = True
        response_event = asyncio.Event()
        self._pending_responses[message.message_id] = response_event
        
        try:
            await self.send(message)
            
            # 等待响应
            await asyncio.wait_for(response_event.wait(), timeout=timeout)
            
            return self._response_data.pop(message.message_id, None)
        except asyncio.TimeoutError:
            logger.warning(f"等待响应超时: {message.message_id}")
            return None
        finally:
            self._pending_responses.pop(message.message_id, None)
    
    async def respond(self, original_message_id: str, response_data: Any):
        """
        响应消息
        
        Args:
            original_message_id: 原始消息ID
            response_data: 响应数据
        """
        if original_message_id in self._pending_responses:
            self._response_data[original_message_id] = response_data
            self._pending_responses[original_message_id].set()
    
    async def receive(self, layer: int, timeout: float = None) -> Optional[LayerMessage]:
        """
        接收消息
        
        Args:
            layer: 接收层
            timeout: 超时时间
        
        Returns:
            接收到的消息
        """
        try:
            if timeout:
                message = await asyncio.wait_for(
                    self._message_queues[layer].get(),
                    timeout=timeout
                )
            else:
                message = await self._message_queues[layer].get()
            return message
        except asyncio.TimeoutError:
            return None
    
    def subscribe(self, layer: int, message_type: MessageType, handler: Callable):
        """
        订阅特定类型的消息
        
        Args:
            layer: 目标层
            message_type: 消息类型
            handler: 处理函数
        """
        self._subscribers[layer][message_type].append(handler)
        logger.debug(f"订阅注册: 层{layer}, 类型: {message_type.value}")
    
    def unsubscribe(self, layer: int, message_type: MessageType, handler: Callable):
        """取消订阅"""
        if handler in self._subscribers[layer][message_type]:
            self._subscribers[layer][message_type].remove(handler)
    
    def get_message_history(self, 
                           source_layer: Optional[int] = None,
                           target_layer: Optional[int] = None,
                           message_type: Optional[MessageType] = None,
                           limit: int = 100) -> List[LayerMessage]:
        """获取消息历史"""
        filtered = self._message_history
        
        if source_layer is not None:
            filtered = [m for m in filtered if m.source_layer == source_layer]
        if target_layer is not None:
            filtered = [m for m in filtered if m.target_layer == target_layer]
        if message_type is not None:
            filtered = [m for m in filtered if m.message_type == message_type]
        
        return filtered[-limit:]
    
    def get_queue_stats(self) -> Dict[int, int]:
        """获取各层队列状态"""
        return {
            layer: queue.qsize() 
            for layer, queue in self._message_queues.items()
        }


class TaskDispatcher:
    """
    任务分发器
    负责将任务从上层分发到下层
    """
    
    def __init__(self, comm_bus: LayerCommunicationBus):
        self.comm_bus = comm_bus
        self._task_assignments: Dict[str, str] = {}  # task_id -> assigned_agent
        self._task_status: Dict[str, str] = {}  # task_id -> status
    
    async def dispatch_to_implementation(self, 
                                         tasks: List[Dict[str, Any]], 
                                         from_agent: str) -> Dict[str, bool]:
        """
        将任务分发到实施层
        
        Args:
            tasks: 任务列表
            from_agent: 来源智能体
        
        Returns:
            任务分发结果 {task_id: success}
        """
        results = {}
        
        for task in tasks:
            task_id = task.get("task_id", str(uuid.uuid4()))
            
            message = LayerMessage(
                source_layer=1,
                target_layer=2,
                source_agent=from_agent,
                message_type=MessageType.TASK_DISPATCH,
                payload={
                    "task": task,
                    "dispatch_time": datetime.now().isoformat()
                },
                priority=task.get("priority", 0)
            )
            
            success = await self.comm_bus.send(message)
            results[task_id] = success
            
            if success:
                self._task_status[task_id] = "dispatched"
        
        return results
    
    async def report_to_validation(self, 
                                   implementation_results: List[Dict[str, Any]],
                                   from_agent: str) -> bool:
        """
        将实施结果报告到检验层
        """
        message = LayerMessage(
            source_layer=2,
            target_layer=3,
            source_agent=from_agent,
            message_type=MessageType.RESULT_REPORT,
            payload={
                "results": implementation_results,
                "report_time": datetime.now().isoformat()
            }
        )
        
        return await self.comm_bus.send(message)
    
    async def send_feedback(self, 
                           feedback: Dict[str, Any],
                           from_layer: int,
                           to_layer: int,
                           from_agent: str) -> bool:
        """
        发送反馈信息
        """
        message = LayerMessage(
            source_layer=from_layer,
            target_layer=to_layer,
            source_agent=from_agent,
            message_type=MessageType.FEEDBACK,
            payload=feedback
        )
        
        return await self.comm_bus.send(message)
    
    async def escalate_issue(self,
                            issue: Dict[str, Any],
                            from_layer: int,
                            from_agent: str) -> bool:
        """
        问题升级
        """
        # 默认升级到上一层
        target_layer = max(1, from_layer - 1)
        
        message = LayerMessage(
            source_layer=from_layer,
            target_layer=target_layer,
            source_agent=from_agent,
            message_type=MessageType.ESCALATION,
            payload=issue,
            priority=issue.get("severity", 5)  # 高优先级
        )
        
        return await self.comm_bus.send(message)


class FeedbackLoop:
    """
    反馈回路管理器
    管理从检验层到决策层的反馈流程
    """
    
    def __init__(self, comm_bus: LayerCommunicationBus):
        self.comm_bus = comm_bus
        self._feedback_history: List[Dict[str, Any]] = []
        self._aggregated_feedback: Dict[str, Any] = {}
    
    async def process_validation_feedback(self, validation_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理检验层的反馈，生成结构化反馈信息
        
        Args:
            validation_output: 检验层输出
        
        Returns:
            结构化反馈
        """
        feedback = {
            "feedback_id": f"fb_{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now().isoformat(),
            "reward_signal": validation_output.get("reward_signal", 0.0),
            "scores": validation_output.get("scores", {}),
            "issues": validation_output.get("issues", []),
            "suggestions": validation_output.get("suggestions", []),
            "target_layers": self._determine_target_layers(validation_output)
        }
        
        self._feedback_history.append(feedback)
        
        return feedback
    
    def _determine_target_layers(self, validation_output: Dict[str, Any]) -> List[int]:
        """确定反馈应该发送到哪些层"""
        target_layers = []
        
        # 根据问题类型确定目标层
        issues = validation_output.get("issues", [])
        for issue in issues:
            category = issue.get("category", "")
            if "strategy" in category.lower() or "decision" in category.lower():
                target_layers.append(1)
            elif "implementation" in category.lower() or "execution" in category.lower():
                target_layers.append(2)
        
        # 默认反馈到决策层
        if not target_layers:
            target_layers = [1, 2]
        
        return list(set(target_layers))
    
    async def send_feedback_to_layers(self, feedback: Dict[str, Any]) -> Dict[int, bool]:
        """
        发送反馈到各目标层
        """
        results = {}
        target_layers = feedback.get("target_layers", [1])
        
        for layer in target_layers:
            message = LayerMessage(
                source_layer=3,
                target_layer=layer,
                message_type=MessageType.FEEDBACK,
                payload=feedback
            )
            
            success = await self.comm_bus.send(message)
            results[layer] = success
        
        return results
    
    async def send_reward_signal(self, reward: float, session_id: str) -> bool:
        """
        发送奖励信号到所有层
        """
        message = LayerMessage(
            source_layer=3,
            target_layer=1,  # 先发给决策层
            message_type=MessageType.REWARD_SIGNAL,
            payload={
                "reward": reward,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        return await self.comm_bus.send(message)
    
    def get_feedback_summary(self, limit: int = 10) -> Dict[str, Any]:
        """获取反馈摘要"""
        recent = self._feedback_history[-limit:]
        
        if not recent:
            return {"count": 0, "avg_reward": 0.0, "common_issues": []}
        
        avg_reward = sum(f.get("reward_signal", 0) for f in recent) / len(recent)
        
        # 统计常见问题
        issue_counts = defaultdict(int)
        for fb in recent:
            for issue in fb.get("issues", []):
                issue_counts[issue.get("category", "unknown")] += 1
        
        common_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "count": len(recent),
            "avg_reward": avg_reward,
            "common_issues": common_issues
        }


class CommunicationCoordinator:
    """
    通信协调器
    整合所有通信组件，提供统一接口
    """
    
    def __init__(self):
        self.bus = LayerCommunicationBus()
        self.dispatcher = TaskDispatcher(self.bus)
        self.feedback_loop = FeedbackLoop(self.bus)
        self._is_initialized = False
    
    async def initialize(self):
        """初始化通信系统"""
        if self._is_initialized:
            return
        
        await self.bus.start()
        self._is_initialized = True
        logger.info("通信协调器已初始化")
    
    async def shutdown(self):
        """关闭通信系统"""
        await self.bus.stop()
        self._is_initialized = False
        logger.info("通信协调器已关闭")
    
    async def dispatch_decision_to_implementation(self, 
                                                  decision_output: Dict[str, Any],
                                                  from_agent: str = "decision_layer") -> Dict[str, bool]:
        """
        将决策层输出分发到实施层
        """
        tasks = decision_output.get("tasks", [])
        return await self.dispatcher.dispatch_to_implementation(tasks, from_agent)
    
    async def report_implementation_results(self,
                                           results: List[Dict[str, Any]],
                                           from_agent: str = "implementation_layer") -> bool:
        """
        报告实施结果到检验层
        """
        return await self.dispatcher.report_to_validation(results, from_agent)
    
    async def process_and_send_feedback(self,
                                        validation_output: Dict[str, Any]) -> Dict[int, bool]:
        """
        处理检验结果并发送反馈
        """
        feedback = await self.feedback_loop.process_validation_feedback(validation_output)
        return await self.feedback_loop.send_feedback_to_layers(feedback)
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取通信系统状态"""
        return {
            "is_initialized": self._is_initialized,
            "queue_stats": self.bus.get_queue_stats(),
            "feedback_summary": self.feedback_loop.get_feedback_summary()
        }
