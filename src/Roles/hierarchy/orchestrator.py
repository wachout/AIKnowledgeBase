"""
多层强化学习智能体系统 - 主协调器
负责协调三层架构的完整执行流程
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Generator, AsyncGenerator
import asyncio
import logging
import uuid

from .types import (
    LayerType, HierarchicalOutput, DecisionOutput, ImplementationOutput,
    ValidationOutput, GlobalState, Experience
)
from .layers import DecisionLayer, ImplementationLayer, ValidationLayer
from .layers.base_layer import LayerContext
from .rl_graph import RLGraph
from .communication import CommunicationCoordinator
from .reward_system import HierarchicalRewardSystem
from .policy_updater import HierarchicalPolicyUpdater
from .experience.experience_buffer import ExperienceBuffer
from .experience.trajectory import TrajectoryRecorder


logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """协调器配置"""
    max_iterations: int = 3          # 最大迭代次数
    reward_threshold: float = 0.6    # 奖励阈值（满足则提前退出）
    timeout_seconds: float = 1800.0  # 总超时时间
    enable_learning: bool = True     # 是否启用策略学习
    enable_streaming: bool = True    # 是否启用流式输出
    experience_buffer_size: int = 10000
    batch_size: int = 32


class HierarchicalOrchestrator:
    """
    层次化协调器 - 主控制器
    
    负责:
    1. 协调三层架构的执行
    2. 管理强化学习图
    3. 处理奖励计算和策略更新
    4. 收集和存储经验
    """
    
    def __init__(
        self,
        config: Optional[OrchestratorConfig] = None,
        llm_adapter=None
    ):
        self.config = config or OrchestratorConfig()
        self.llm_adapter = llm_adapter
        
        # 三层架构
        self.decision_layer = DecisionLayer(llm_adapter=llm_adapter)
        self.implementation_layer = ImplementationLayer(llm_adapter=llm_adapter)
        self.validation_layer = ValidationLayer(llm_adapter=llm_adapter)
        
        # 强化学习组件
        self.rl_graph = RLGraph()
        self.reward_system = HierarchicalRewardSystem()
        self.policy_updater = HierarchicalPolicyUpdater()
        
        # 经验管理
        self.experience_buffer = ExperienceBuffer(
            max_size=self.config.experience_buffer_size
        )
        self.trajectory_recorder = TrajectoryRecorder()
        
        # 通信协调
        self.communication = CommunicationCoordinator()
        
        # 全局状态
        self._global_state = GlobalState()
        
        # 日志
        self._logger = logging.getLogger(__name__)
    
    # ==================== 主执行流程 ====================
    
    async def execute(self, query: str) -> HierarchicalOutput:
        """
        执行完整的三层流程
        
        Args:
            query: 用户查询
            
        Returns:
            HierarchicalOutput 最终输出
        """
        start_time = datetime.now()
        self._global_state = GlobalState(current_query=query)
        
        # 开始轨迹记录
        self.trajectory_recorder.start_trajectory(
            session_id=self._global_state.session_id,
            query=query
        )
        
        iteration = 0
        decision_output = None
        impl_outputs = []
        validation_output = None
        
        try:
            while iteration < self.config.max_iterations:
                self._global_state.iteration = iteration
                
                # === 第一层：决策 ===
                decision_context = LayerContext(
                    session_id=self._global_state.session_id,
                    iteration=iteration,
                    query=query,
                    feedback=validation_output.to_dict() if validation_output else None
                )
                
                decision_output = await self.decision_layer.process(decision_context)
                self.trajectory_recorder.record_decision(decision_output)
                
                # === 第二层：实施 ===
                impl_context = LayerContext(
                    session_id=self._global_state.session_id,
                    iteration=iteration,
                    query=query,
                    parent_output=decision_output
                )
                
                impl_outputs = await self.implementation_layer.process(impl_context)
                for output in impl_outputs:
                    self.trajectory_recorder.record_implementation(output)
                
                # === 第三层：检验 ===
                val_context = LayerContext(
                    session_id=self._global_state.session_id,
                    iteration=iteration,
                    query=query,
                    parent_output=(decision_output, impl_outputs)
                )
                
                validation_output = await self.validation_layer.process(val_context)
                self.trajectory_recorder.record_validation(validation_output)
                
                # === 计算奖励 ===
                reward = self.reward_system.compute_total_reward(
                    decision_output, impl_outputs, validation_output
                )
                self._global_state.reward_history.append(reward)
                self._global_state.total_reward = reward
                
                # === 收集经验并更新策略 ===
                if self.config.enable_learning:
                    experiences = self._collect_experiences(
                        decision_output, impl_outputs, validation_output, reward
                    )
                    self.experience_buffer.add_batch(experiences)
                    
                    # 批量更新策略
                    if self.experience_buffer.size >= self.config.batch_size:
                        batch = self.experience_buffer.sample(self.config.batch_size)
                        self.policy_updater.update(batch)
                
                # === 检查退出条件 ===
                if validation_output.reward_signal >= self.config.reward_threshold:
                    self._logger.info(f"迭代 {iteration}: 达到奖励阈值，提前结束")
                    break
                
                # === 根据反馈调整 ===
                query = self._incorporate_feedback(query, validation_output)
                iteration += 1
            
            # 结束轨迹
            trajectory = self.trajectory_recorder.end_trajectory(
                success=validation_output.reward_signal >= self.config.reward_threshold
                        if validation_output else False
            )
            
            # 编译最终输出
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return HierarchicalOutput(
                session_id=self._global_state.session_id,
                query=query,
                decision_output=decision_output,
                implementation_outputs=impl_outputs,
                validation_output=validation_output,
                total_iterations=iteration + 1,
                final_reward=self._global_state.total_reward,
                execution_time_seconds=execution_time,
                success=validation_output.reward_signal >= self.config.reward_threshold
                        if validation_output else False,
                summary=self._generate_summary(
                    decision_output, impl_outputs, validation_output
                )
            )
            
        except Exception as e:
            self._logger.error(f"执行错误: {e}")
            self.trajectory_recorder.end_trajectory(success=False)
            raise
    
    async def execute_stream(
        self,
        query: str
    ) -> AsyncGenerator[str, None]:
        """
        流式执行三层流程
        
        Args:
            query: 用户查询
            
        Yields:
            执行过程中的输出
            
        Note:
            最终结果存储在 self.last_output 属性中
        """
        start_time = datetime.now()
        self._global_state = GlobalState(current_query=query)
        
        yield f"[协调器] 开始处理: {query[:50]}...\n"
        yield f"[协调器] 会话ID: {self._global_state.session_id}\n"
        
        # 开始轨迹记录
        self.trajectory_recorder.start_trajectory(
            session_id=self._global_state.session_id,
            query=query
        )
        
        iteration = 0
        decision_output = None
        impl_outputs = []
        validation_output = None
        
        try:
            while iteration < self.config.max_iterations:
                self._global_state.iteration = iteration
                yield f"\n{'='*50}\n"
                yield f"[协调器] === 迭代 {iteration + 1}/{self.config.max_iterations} ===\n"
                yield f"{'='*50}\n"
                
                # === 第一层：决策 ===
                yield "\n[协调器] 【第一层：决策层】\n"
                decision_context = LayerContext(
                    session_id=self._global_state.session_id,
                    iteration=iteration,
                    query=query,
                    feedback=validation_output.to_dict() if validation_output else None
                )
                
                async for chunk in self.decision_layer.process_stream(decision_context):
                    yield chunk
                
                decision_output = await self.decision_layer.process(decision_context)
                self.trajectory_recorder.record_decision(decision_output)
                
                # === 第二层：实施 ===
                yield "\n[协调器] 【第二层：实施层】\n"
                impl_context = LayerContext(
                    session_id=self._global_state.session_id,
                    iteration=iteration,
                    query=query,
                    parent_output=decision_output
                )
                
                async for chunk in self.implementation_layer.process_stream(impl_context):
                    yield chunk
                
                impl_outputs = await self.implementation_layer.process(impl_context)
                for output in impl_outputs:
                    self.trajectory_recorder.record_implementation(output)
                
                # === 第三层：检验 ===
                yield "\n[协调器] 【第三层：检验层】\n"
                val_context = LayerContext(
                    session_id=self._global_state.session_id,
                    iteration=iteration,
                    query=query,
                    parent_output=(decision_output, impl_outputs)
                )
                
                async for chunk in self.validation_layer.process_stream(val_context):
                    yield chunk
                
                validation_output = await self.validation_layer.process(val_context)
                self.trajectory_recorder.record_validation(validation_output)
                
                # === 计算奖励 ===
                reward = self.reward_system.compute_total_reward(
                    decision_output, impl_outputs, validation_output
                )
                self._global_state.reward_history.append(reward)
                self._global_state.total_reward = reward
                
                yield f"\n[协调器] 本轮奖励: {reward:.3f}\n"
                
                # === 策略更新 ===
                if self.config.enable_learning:
                    experiences = self._collect_experiences(
                        decision_output, impl_outputs, validation_output, reward
                    )
                    self.experience_buffer.add_batch(experiences)
                    
                    if self.experience_buffer.size >= self.config.batch_size:
                        batch = self.experience_buffer.sample(self.config.batch_size)
                        self.policy_updater.update(batch)
                        yield "[协调器] 策略已更新\n"
                
                # === 检查退出条件 ===
                if validation_output.reward_signal >= self.config.reward_threshold:
                    yield f"[协调器] 达到奖励阈值 ({self.config.reward_threshold})，提前结束\n"
                    break
                
                # === 根据反馈调整 ===
                if iteration < self.config.max_iterations - 1:
                    yield "[协调器] 根据反馈调整，进入下一轮...\n"
                    query = self._incorporate_feedback(query, validation_output)
                
                iteration += 1
            
            # 结束轨迹
            success = (
                validation_output.reward_signal >= self.config.reward_threshold
                if validation_output else False
            )
            self.trajectory_recorder.end_trajectory(success=success)
            
            # 编译最终输出
            execution_time = (datetime.now() - start_time).total_seconds()
            
            yield f"\n{'='*50}\n"
            yield f"[协调器] 执行完成\n"
            yield f"[协调器] 总迭代: {iteration + 1}\n"
            yield f"[协调器] 最终奖励: {self._global_state.total_reward:.3f}\n"
            yield f"[协调器] 总耗时: {execution_time:.2f}s\n"
            yield f"[协调器] 结果: {'成功' if success else '需改进'}\n"
            
            # 存储最终结果到实例属性
            self.last_output = HierarchicalOutput(
                session_id=self._global_state.session_id,
                query=query,
                decision_output=decision_output,
                implementation_outputs=impl_outputs,
                validation_output=validation_output,
                total_iterations=iteration + 1,
                final_reward=self._global_state.total_reward,
                execution_time_seconds=execution_time,
                success=success,
                summary=self._generate_summary(
                    decision_output, impl_outputs, validation_output
                )
            )
            
        except Exception as e:
            yield f"[协调器] 错误: {str(e)}\n"
            self.trajectory_recorder.end_trajectory(success=False)
            raise
    
    # ==================== 内部方法 ====================
    
    def _collect_experiences(
        self,
        decision_output: DecisionOutput,
        impl_outputs: List[ImplementationOutput],
        validation_output: ValidationOutput,
        reward: float
    ) -> List[Experience]:
        """收集经验"""
        experiences = []
        
        # 决策层经验
        exp = self.decision_layer.collect_decision_experience(
            context=LayerContext(query=self._global_state.current_query),
            output=decision_output,
            reward=reward * 0.3
        )
        experiences.append(exp)
        
        # 实施层经验
        for impl_output in impl_outputs:
            from .types import Task
            task = Task(task_id=impl_output.task_id)
            exp = self.implementation_layer.collect_implementation_experience(
                task=task,
                output=impl_output,
                reward=reward * 0.4 / max(len(impl_outputs), 1)
            )
            experiences.append(exp)
        
        # 检验层经验
        exp = self.validation_layer.collect_validation_experience(
            context=LayerContext(query=self._global_state.current_query),
            output=validation_output,
            reward=reward * 0.3
        )
        experiences.append(exp)
        
        return experiences
    
    def _incorporate_feedback(
        self,
        query: str,
        validation_output: ValidationOutput
    ) -> str:
        """根据反馈调整查询"""
        if not validation_output.suggestions:
            return query
        
        # 提取高优先级建议
        high_priority = [
            s for s in validation_output.suggestions
            if s.priority >= 7
        ]
        
        if high_priority:
            feedback_text = "; ".join([s.title for s in high_priority[:3]])
            return f"{query}\n\n【反馈调整】请特别注意: {feedback_text}"
        
        return query
    
    def _generate_summary(
        self,
        decision_output: Optional[DecisionOutput],
        impl_outputs: List[ImplementationOutput],
        validation_output: Optional[ValidationOutput]
    ) -> str:
        """生成执行摘要"""
        parts = []
        
        if decision_output:
            parts.append(f"决策: 生成{len(decision_output.tasks)}个任务")
        
        if impl_outputs:
            completed = sum(
                1 for o in impl_outputs
                if o.status.value == "completed"
            )
            parts.append(f"实施: 完成{completed}/{len(impl_outputs)}个任务")
        
        if validation_output:
            parts.append(f"检验: {validation_output.overall_assessment}")
        
        return "; ".join(parts) if parts else "执行完成"
    
    # ==================== 状态和统计 ====================
    
    @property
    def global_state(self) -> GlobalState:
        """获取全局状态"""
        return self._global_state
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "reward_system": self.reward_system.get_reward_stats(),
            "policy_updater": self.policy_updater.get_update_stats(),
            "experience_buffer": self.experience_buffer.get_stats().__dict__,
            "trajectory": self.trajectory_recorder.get_stats(),
            "rl_graph": {
                "node_count": len(self.rl_graph.nodes),
                "edge_count": len(self.rl_graph.edges)
            }
        }
    
    # ==================== 生命周期 ====================
    
    async def initialize(self):
        """初始化协调器"""
        await self.decision_layer.initialize()
        await self.implementation_layer.initialize()
        await self.validation_layer.initialize()
        self._logger.info("协调器初始化完成")
    
    async def shutdown(self):
        """关闭协调器"""
        await self.decision_layer.shutdown()
        await self.implementation_layer.shutdown()
        await self.validation_layer.shutdown()
        self._logger.info("协调器已关闭")
    
    def reset(self):
        """重置协调器状态"""
        self._global_state = GlobalState()
        self.experience_buffer.clear()
        self.trajectory_recorder.clear()
        self.reward_system.clear_history()
        self.policy_updater.reset()
