"""
多层强化学习智能体系统 - 实施层
接收决策层任务，组建实施小组进行细节讨论和执行
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Generator, Callable, AsyncGenerator
from enum import Enum
import asyncio
import logging
import uuid

from .base_layer import BaseLayer, LayerConfig, LayerContext
from ..types import (
    LayerType, ImplementationOutput, Task, ExecutionStep, Artifact, LogEntry,
    ExecutionStatus, AgentAction, Experience, ImplementationRole, DecisionOutput
)


logger = logging.getLogger(__name__)


# ==================== 实施组相关类 ====================

@dataclass
class ImplementationGroup:
    """实施小组"""
    group_id: str = field(default_factory=lambda: f"group_{uuid.uuid4().hex[:8]}")
    name: str = ""
    task: Optional[Task] = None
    members: Dict[str, ImplementationRole] = field(default_factory=dict)  # agent_id -> role
    status: ExecutionStatus = ExecutionStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    artifacts: List[Artifact] = field(default_factory=list)
    execution_log: List[LogEntry] = field(default_factory=list)


class ImplementGroupScheduler:
    """
    实施组调度器
    根据任务类型动态创建实施小组，分配智能体角色
    """
    
    def __init__(self):
        self._groups: Dict[str, ImplementationGroup] = {}
        self._role_templates: Dict[str, List[ImplementationRole]] = {
            "development": [
                ImplementationRole.ARCHITECT,
                ImplementationRole.DEVELOPER,
                ImplementationRole.TESTER,
                ImplementationRole.COORDINATOR
            ],
            "documentation": [
                ImplementationRole.DOCUMENTER,
                ImplementationRole.DEVELOPER,
                ImplementationRole.COORDINATOR
            ],
            "analysis": [
                ImplementationRole.ARCHITECT,
                ImplementationRole.DEVELOPER,
                ImplementationRole.COORDINATOR
            ],
            "default": [
                ImplementationRole.DEVELOPER,
                ImplementationRole.COORDINATOR
            ]
        }
    
    def create_group(self, task: Task) -> ImplementationGroup:
        """为任务创建实施小组"""
        # 根据任务类型选择角色模板
        task_type = self._detect_task_type(task)
        roles = self._role_templates.get(task_type, self._role_templates["default"])
        
        group = ImplementationGroup(
            name=f"实施组-{task.name[:20]}",
            task=task
        )
        
        # 分配角色
        for role in roles:
            agent_id = f"impl_{role.name.lower()}_{uuid.uuid4().hex[:6]}"
            group.members[agent_id] = role
        
        self._groups[group.group_id] = group
        return group
    
    def _detect_task_type(self, task: Task) -> str:
        """检测任务类型"""
        name_lower = task.name.lower()
        desc_lower = task.description.lower()
        combined = name_lower + " " + desc_lower
        
        if any(kw in combined for kw in ["代码", "实现", "开发", "编程", "code", "implement"]):
            return "development"
        elif any(kw in combined for kw in ["文档", "说明", "document", "doc"]):
            return "documentation"
        elif any(kw in combined for kw in ["分析", "研究", "调查", "analysis", "research"]):
            return "analysis"
        
        return "default"
    
    def get_group(self, group_id: str) -> Optional[ImplementationGroup]:
        """获取实施组"""
        return self._groups.get(group_id)
    
    def get_all_groups(self) -> List[ImplementationGroup]:
        """获取所有实施组"""
        return list(self._groups.values())
    
    def dissolve_group(self, group_id: str):
        """解散实施组"""
        if group_id in self._groups:
            del self._groups[group_id]


class ExecutionEngine:
    """
    执行引擎
    按步骤执行实施方案，记录执行状态和中间结果
    """
    
    def __init__(self, llm_adapter=None):
        self.llm_adapter = llm_adapter
        self._execution_log: List[LogEntry] = []
    
    async def execute_task(
        self,
        task: Task,
        group: ImplementationGroup
    ) -> AsyncGenerator[str, None]:
        """
        执行任务
        
        Args:
            task: 要执行的任务
            group: 实施小组
            
        Yields:
            执行过程的状态更新
            
        Note:
            实施输出存储在 self.last_output 属性中
        """
        output = ImplementationOutput(
            task_id=task.task_id,
            status=ExecutionStatus.IN_PROGRESS,
            started_at=datetime.now()
        )
        
        yield f"[执行引擎] 开始执行任务: {task.name}\n"
        
        try:
            # 生成执行步骤
            steps = self._generate_steps(task, group)
            output.execution_steps = steps
            yield f"[执行引擎] 生成 {len(steps)} 个执行步骤\n"
            
            # 执行每个步骤
            for i, step in enumerate(steps):
                yield f"[执行引擎] 步骤 {i+1}/{len(steps)}: {step.action}\n"
                step.status = ExecutionStatus.IN_PROGRESS
                step.started_at = datetime.now()
                
                # 模拟步骤执行
                await asyncio.sleep(0.1)
                
                # 生成步骤产出
                artifact = self._execute_step(step, group)
                if artifact:
                    output.artifacts.append(artifact)
                    yield f"  -> 产出: {artifact.name}\n"
                
                step.status = ExecutionStatus.COMPLETED
                step.completed_at = datetime.now()
                
                # 记录日志
                self._log(f"步骤完成: {step.action}", step_id=step.step_id)
            
            output.status = ExecutionStatus.COMPLETED
            output.completed_at = datetime.now()
            output.execution_log = self._execution_log.copy()
            
            # 计算指标
            output.metrics = self._compute_metrics(output)
            
            yield f"[执行引擎] 任务完成\n"
            self.last_output = output  # 存储结果
            
        except Exception as e:
            output.status = ExecutionStatus.FAILED
            output.completed_at = datetime.now()
            self._log(f"任务失败: {str(e)}", level="ERROR")
            output.execution_log = self._execution_log.copy()
            yield f"[执行引擎] 任务失败: {str(e)}\n"
            self.last_output = output  # 存储结果
    
    def _generate_steps(self, task: Task, group: ImplementationGroup) -> List[ExecutionStep]:
        """生成执行步骤"""
        steps = []
        
        # 基础步骤
        base_actions = [
            ("分析需求", "理解任务需求和约束"),
            ("设计方案", "制定实施方案"),
            ("执行实施", "执行具体实施工作"),
            ("验证结果", "验证实施结果正确性")
        ]
        
        for i, (action, desc) in enumerate(base_actions):
            step = ExecutionStep(
                task_id=task.task_id,
                sequence=i + 1,
                action=action,
                description=desc
            )
            steps.append(step)
        
        return steps
    
    def _execute_step(
        self,
        step: ExecutionStep,
        group: ImplementationGroup
    ) -> Optional[Artifact]:
        """执行单个步骤，返回产出物"""
        # 根据步骤类型生成产出物
        if "实施" in step.action or "执行" in step.action:
            return Artifact(
                name=f"产出-{step.action}",
                artifact_type="result",
                content={"step_id": step.step_id, "completed": True},
                created_by=list(group.members.keys())[0] if group.members else "system"
            )
        elif "设计" in step.action:
            return Artifact(
                name=f"设计文档-{step.step_id[:8]}",
                artifact_type="document",
                content={"design": "设计方案内容"},
                created_by=list(group.members.keys())[0] if group.members else "system"
            )
        return None
    
    def _compute_metrics(self, output: ImplementationOutput) -> Dict[str, float]:
        """计算执行指标"""
        metrics = {}
        
        # 完成率
        completed_steps = sum(
            1 for s in output.execution_steps
            if s.status == ExecutionStatus.COMPLETED
        )
        total_steps = len(output.execution_steps)
        metrics["completion_rate"] = completed_steps / total_steps if total_steps > 0 else 0.0
        
        # 执行时间
        if output.started_at and output.completed_at:
            duration = (output.completed_at - output.started_at).total_seconds()
            metrics["execution_time"] = duration
        
        # 产出物数量
        metrics["artifact_count"] = len(output.artifacts)
        
        return metrics
    
    def _log(self, message: str, level: str = "INFO", **kwargs):
        """记录日志"""
        entry = LogEntry(
            level=level,
            source="ExecutionEngine",
            message=message,
            details=kwargs
        )
        self._execution_log.append(entry)
    
    def clear_log(self):
        """清除日志"""
        self._execution_log.clear()


class ImplementRoundtable:
    """
    实施圆桌
    专注于实施细节的讨论，生成具体执行步骤
    
    升级版本：使用完整的实施讨论系统，实现四阶段讨论：
    1. 设计方案提出 - 架构师主导
    2. 可行性评审 - 开发者主导
    3. 风险评估 - 测试员主导
    4. 共识构建 - 协调员主导
    """
    
    def __init__(self, llm_adapter=None, use_full_discussion: bool = True):
        self.llm_adapter = llm_adapter
        self.use_full_discussion = use_full_discussion
        
        # 完整的实施讨论系统
        self._full_discussion = None
        if use_full_discussion:
            try:
                from .implementation_roundtable import ImplementationDiscussion
                self._full_discussion = ImplementationDiscussion(llm_adapter)
            except ImportError as e:
                logger.warning(f"无法加载完整实施讨论系统: {e}，使用简化版本")
                self.use_full_discussion = False
    
    async def discuss_implementation(
        self,
        task: Task,
        group: ImplementationGroup
    ) -> AsyncGenerator[str, None]:
        """
        进行实施讨论
        
        Args:
            task: 要讨论的任务
            group: 实施小组
            
        Yields:
            讨论过程的输出
            
        Note:
            讨论总结存储在 self.last_summary 属性中
            讨论结果存储在 self.last_result 属性中
        """
        # 使用完整的实施讨论系统
        if self.use_full_discussion and self._full_discussion:
            async for chunk in self._full_discussion.run_implementation_discussion(task, group):
                yield chunk
            
            # 获取讨论结果
            result = self._full_discussion.get_last_result()
            if result:
                self.last_summary = result.implementation_plan
                self.last_result = result
            else:
                self.last_summary = f"任务'{task.name}'的实施讨论完成。"
                self.last_result = None
            return
        
        # 简化版本（后备方案）
        yield f"[实施圆桌] 开始讨论任务: {task.name}\n"
        yield f"[实施圆桌] 参与成员: {len(group.members)}人\n"
        
        # 模拟各角色发言
        for agent_id, role in group.members.items():
            yield f"[{role.value}] 正在分析...\n"
            await asyncio.sleep(0.05)
        
        yield "[实施圆桌] 讨论完成\n"
        self.last_summary = f"任务'{task.name}'的实施讨论完成，已确定执行步骤。"
        self.last_result = None
    
    def get_consensus_level(self) -> float:
        """获取当前共识度"""
        if self._full_discussion:
            result = self._full_discussion.get_last_result()
            if result:
                return result.final_consensus_level
        return 0.5  # 默认值
    
    def reset(self):
        """重置讨论系统"""
        if self._full_discussion:
            self._full_discussion.reset()


class ImplementationLayer(BaseLayer):
    """
    实施层 (Layer 2)
    接收决策层任务，组建实施小组进行细节讨论和执行
    
    核心组件：
    - ImplementGroupScheduler: 实施组调度器
    - ImplementRoundtable: 实施圆桌讨论
    - ExecutionEngine: 执行引擎
    """
    
    def __init__(
        self,
        config: Optional[LayerConfig] = None,
        llm_adapter=None
    ):
        if config is None:
            config = LayerConfig(
                layer_type=LayerType.IMPLEMENTATION,
                name="implementation_layer",
                timeout_seconds=900.0  # 实施层允许更长时间
            )
        
        super().__init__(config)
        
        # 核心组件
        self.scheduler = ImplementGroupScheduler()
        self.roundtable = ImplementRoundtable(llm_adapter=llm_adapter)
        self.engine = ExecutionEngine(llm_adapter=llm_adapter)
        
        # LLM适配器
        self.llm_adapter = llm_adapter
        
        # 实施历史
        self._implementation_history: List[ImplementationOutput] = []
        
        # 当前活跃的实施组
        self._active_groups: Dict[str, ImplementationGroup] = {}
    
    # ==================== 主处理逻辑 ====================
    
    async def process(self, context: LayerContext) -> List[ImplementationOutput]:
        """
        处理实施层逻辑
        
        Args:
            context: 层执行上下文，parent_output 应为 DecisionOutput
            
        Returns:
            List[ImplementationOutput] 各任务的实施输出
        """
        self._update_phase("preparing")
        start_time = datetime.now()
        
        try:
            # 获取决策层输出
            decision_output: DecisionOutput = context.parent_output
            if not decision_output or not decision_output.tasks:
                return []
            
            # 初始化智能体
            self.initialize_agents({"tasks": decision_output.tasks})
            
            outputs = []
            
            # 处理每个任务
            for task in decision_output.tasks:
                self._update_phase(f"processing_task_{task.task_id}")
                
                # 创建实施组
                group = self.scheduler.create_group(task)
                self._active_groups[group.group_id] = group
                
                # 进行实施讨论
                discussion_summary = await self._run_discussion(task, group)
                
                # 执行任务
                output = await self._execute_task(task, group)
                outputs.append(output)
                
                # 记录历史
                self._implementation_history.append(output)
                
                # 清理实施组
                del self._active_groups[group.group_id]
            
            # 记录指标
            duration = (datetime.now() - start_time).total_seconds()
            avg_reward = sum(self.compute_layer_reward(o) for o in outputs) / len(outputs) if outputs else 0
            self.record_execution_result(duration, True, avg_reward)
            
            self._update_phase("completed")
            return outputs
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.record_execution_result(duration, False, -1.0)
            self._update_phase("failed")
            raise
    
    async def process_stream(
        self,
        context: LayerContext
    ) -> AsyncGenerator[str, None]:
        """
        流式处理实施层逻辑
        
        Yields:
            处理过程中的中间输出
            
        Note:
            List[ImplementationOutput] 存储在 self.last_outputs 属性中
        """
        self._update_phase("preparing")
        start_time = datetime.now()
        
        try:
            yield "[实施层] 开始处理...\n"
            
            # 获取决策层输出
            decision_output: DecisionOutput = context.parent_output
            if not decision_output or not decision_output.tasks:
                yield "[实施层] 没有需要实施的任务\n"
                self.last_outputs = []  # 存储空结果
                return
            
            yield f"[实施层] 接收到 {len(decision_output.tasks)} 个任务\n"
            
            # 初始化智能体
            agent_ids = self.initialize_agents({"tasks": decision_output.tasks})
            yield f"[实施层] 初始化 {len(agent_ids)} 个智能体\n"
            
            outputs = []
            
            # 处理每个任务
            for i, task in enumerate(decision_output.tasks):
                yield f"\n[实施层] === 任务 {i+1}/{len(decision_output.tasks)}: {task.name} ===\n"
                self._update_phase(f"processing_task_{task.task_id}")
                
                # 创建实施组
                group = self.scheduler.create_group(task)
                self._active_groups[group.group_id] = group
                yield f"[实施层] 创建实施组: {len(group.members)} 个成员\n"
                
                # 进行实施讨论
                yield "[实施层] 开始实施讨论...\n"
                async for chunk in self.roundtable.discuss_implementation(task, group):
                    yield chunk
                
                # 执行任务
                yield "[实施层] 开始执行任务...\n"
                output = None
                async for chunk in self.engine.execute_task(task, group):
                    yield chunk
                    # 最后一次迭代会返回 output（通过 generator 的 return）
                
                # 获取最终输出
                output = await self._execute_task(task, group)
                outputs.append(output)
                
                # 记录历史
                self._implementation_history.append(output)
                
                reward = self.compute_layer_reward(output)
                yield f"[实施层] 任务完成，奖励: {reward:.3f}\n"
                
                # 清理实施组
                del self._active_groups[group.group_id]
            
            # 记录指标
            duration = (datetime.now() - start_time).total_seconds()
            avg_reward = sum(self.compute_layer_reward(o) for o in outputs) / len(outputs) if outputs else 0
            self.record_execution_result(duration, True, avg_reward)
            
            yield f"\n[实施层] 全部完成，共处理 {len(outputs)} 个任务，耗时 {duration:.2f}s\n"
            self._update_phase("completed")
            
            self.last_outputs = outputs  # 存储结果
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.record_execution_result(duration, False, -1.0)
            yield f"[实施层] 错误: {str(e)}\n"
            self._update_phase("failed")
            raise
    
    # ==================== 抽象方法实现 ====================
    
    def initialize_agents(self, task_context: Dict[str, Any]) -> List[str]:
        """初始化实施层智能体"""
        agent_ids = []
        
        # 为每种角色创建智能体
        for role in ImplementationRole:
            agent_id = f"impl_{role.name.lower()}_{uuid.uuid4().hex[:6]}"
            self.register_agent(agent_id, {"role": role, "layer": 2})
            agent_ids.append(agent_id)
        
        return agent_ids
    
    def compute_layer_reward(self, output: ImplementationOutput) -> float:
        """
        计算实施层奖励
        
        奖励 = 完成度 * 0.3 + 质量 * 0.4 + 效率 * 0.3
        """
        completion_score = self._evaluate_completion(output)
        quality_score = self._evaluate_quality(output)
        efficiency_score = self._evaluate_efficiency(output)
        
        reward = (
            completion_score * 0.3 +
            quality_score * 0.4 +
            efficiency_score * 0.3
        )
        
        # 归一化到 [-1, 1]
        return max(-1.0, min(1.0, reward * 2 - 1))
    
    # ==================== 内部方法 ====================
    
    async def _run_discussion(self, task: Task, group: ImplementationGroup) -> str:
        """运行实施讨论并收集结果"""
        summary_parts = []
        async for chunk in self.roundtable.discuss_implementation(task, group):
            summary_parts.append(chunk)
        return "".join(summary_parts)
    
    async def _execute_task(
        self,
        task: Task,
        group: ImplementationGroup
    ) -> ImplementationOutput:
        """执行任务并返回输出"""
        output = ImplementationOutput(
            task_id=task.task_id,
            status=ExecutionStatus.IN_PROGRESS,
            started_at=datetime.now()
        )
        
        try:
            # 生成执行步骤
            steps = self.engine._generate_steps(task, group)
            output.execution_steps = steps
            
            # 执行每个步骤
            for step in steps:
                step.status = ExecutionStatus.IN_PROGRESS
                step.started_at = datetime.now()
                
                # 模拟执行
                await asyncio.sleep(0.05)
                
                # 生成产出物
                artifact = self.engine._execute_step(step, group)
                if artifact:
                    output.artifacts.append(artifact)
                
                step.status = ExecutionStatus.COMPLETED
                step.completed_at = datetime.now()
            
            output.status = ExecutionStatus.COMPLETED
            output.completed_at = datetime.now()
            output.metrics = self.engine._compute_metrics(output)
            
        except Exception as e:
            output.status = ExecutionStatus.FAILED
            output.completed_at = datetime.now()
            output.execution_log.append(LogEntry(
                level="ERROR",
                source="ImplementationLayer",
                message=str(e)
            ))
        
        return output
    
    def _evaluate_completion(self, output: ImplementationOutput) -> float:
        """评估完成度"""
        if output.status == ExecutionStatus.COMPLETED:
            return output.metrics.get("completion_rate", 1.0)
        elif output.status == ExecutionStatus.IN_PROGRESS:
            return 0.5
        else:
            return 0.0
    
    def _evaluate_quality(self, output: ImplementationOutput) -> float:
        """评估质量"""
        score = 0.5  # 基础分
        
        # 有产出物
        if len(output.artifacts) > 0:
            score += 0.3
        
        # 有执行日志
        if len(output.execution_log) > 0:
            score += 0.1
        
        # 没有错误
        has_error = any(
            log.level == "ERROR"
            for log in output.execution_log
        )
        if not has_error:
            score += 0.1
        
        return min(1.0, score)
    
    def _evaluate_efficiency(self, output: ImplementationOutput) -> float:
        """评估效率"""
        exec_time = output.metrics.get("execution_time", 0.0)
        
        # 根据执行时间评分
        if exec_time <= 1.0:
            return 1.0
        elif exec_time <= 5.0:
            return 0.8
        elif exec_time <= 10.0:
            return 0.6
        elif exec_time <= 30.0:
            return 0.4
        else:
            return 0.2
    
    # ==================== 经验收集 ====================
    
    def collect_implementation_experience(
        self,
        task: Task,
        output: ImplementationOutput,
        reward: float
    ) -> Experience:
        """收集实施层经验"""
        state = {
            "task_id": task.task_id,
            "task_name": task.name,
            "task_priority": task.priority
        }
        
        next_state = {
            "implementation_id": output.implementation_id,
            "status": output.status.value,
            "artifact_count": len(output.artifacts),
            "completion_rate": output.metrics.get("completion_rate", 0.0)
        }
        
        return self.collect_experience(
            agent_id="implementation_layer",
            state=state,
            action=AgentAction.IMPLEMENT,
            reward=reward,
            next_state=next_state
        )
    
    # ==================== 公共接口 ====================
    
    def get_implementation_history(self) -> List[ImplementationOutput]:
        """获取实施历史"""
        return self._implementation_history.copy()
    
    def get_active_groups(self) -> Dict[str, ImplementationGroup]:
        """获取当前活跃的实施组"""
        return self._active_groups.copy()
    
    def clear_history(self):
        """清除历史"""
        self._implementation_history.clear()
