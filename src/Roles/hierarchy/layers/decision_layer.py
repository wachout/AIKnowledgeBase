"""
多层强化学习智能体系统 - 决策层
负责高层战略决策，生成可执行方案
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Generator, AsyncGenerator
import asyncio
import logging
import uuid

from .base_layer import BaseLayer, LayerConfig, LayerContext
from ..types import (
    LayerType, DecisionOutput, Task, Objective, Constraint,
    ExecutionStatus, AgentAction, Experience
)


logger = logging.getLogger(__name__)


@dataclass
class StrategyTemplate:
    """策略模板"""
    template_id: str = ""
    name: str = ""
    description: str = ""
    applicable_domains: List[str] = field(default_factory=list)
    default_objectives: List[str] = field(default_factory=list)
    default_constraints: List[str] = field(default_factory=list)


class StrategyGenerator:
    """策略生成器 - 将讨论结果转化为结构化策略"""
    
    def __init__(self):
        self.templates: Dict[str, StrategyTemplate] = {}
        self._initialize_templates()
    
    def _initialize_templates(self):
        """初始化内置模板"""
        self.templates["general"] = StrategyTemplate(
            template_id="general",
            name="通用策略",
            description="适用于一般性任务的策略模板",
            applicable_domains=["*"],
            default_objectives=["完成用户需求", "确保质量", "优化效率"],
            default_constraints=["时间限制", "资源限制"]
        )
        
        self.templates["development"] = StrategyTemplate(
            template_id="development",
            name="开发策略",
            description="适用于软件开发任务",
            applicable_domains=["coding", "development", "programming"],
            default_objectives=["代码实现", "单元测试", "文档编写"],
            default_constraints=["代码规范", "兼容性要求"]
        )
        
        self.templates["analysis"] = StrategyTemplate(
            template_id="analysis",
            name="分析策略",
            description="适用于数据分析任务",
            applicable_domains=["data", "analysis", "research"],
            default_objectives=["数据收集", "数据分析", "报告生成"],
            default_constraints=["数据准确性", "隐私保护"]
        )
    
    def generate_strategy(
        self,
        query: str,
        discussion_summary: str,
        domain: str = "general"
    ) -> DecisionOutput:
        """生成策略"""
        template = self.templates.get(domain, self.templates["general"])
        
        # 创建目标
        objectives = []
        for i, obj_name in enumerate(template.default_objectives):
            objectives.append(Objective(
                name=obj_name,
                description=f"基于讨论的目标: {obj_name}",
                priority=len(template.default_objectives) - i
            ))
        
        # 创建约束
        constraints = []
        for con_name in template.default_constraints:
            constraints.append(Constraint(
                name=con_name,
                description=f"约束条件: {con_name}"
            ))
        
        return DecisionOutput(
            query=query,
            objectives=objectives,
            constraints=constraints,
            discussion_summary=discussion_summary,
            success_criteria=[
                "所有目标达成",
                "无严重问题",
                "用户满意"
            ]
        )


class TaskDecomposer:
    """任务分解器 - 将策略分解为可执行任务"""
    
    def decompose(
        self,
        objectives: List[Objective],
        constraints: List[Constraint]
    ) -> List[Task]:
        """分解目标为任务"""
        tasks = []
        
        for objective in objectives:
            # 每个目标生成一个主任务
            main_task = Task(
                name=f"实现: {objective.name}",
                description=objective.description,
                parent_objective_id=objective.objective_id,
                priority=objective.priority,
                metadata={"objective_criteria": objective.measurable_criteria}
            )
            tasks.append(main_task)
            
            # 根据目标复杂度生成子任务
            if len(objective.measurable_criteria) > 0:
                for criterion in objective.measurable_criteria:
                    sub_task = Task(
                        name=f"验证: {criterion[:30]}...",
                        description=f"验证标准: {criterion}",
                        parent_objective_id=objective.objective_id,
                        dependencies=[main_task.task_id],
                        priority=objective.priority - 1
                    )
                    tasks.append(sub_task)
        
        return tasks


class DecisionRoundtable:
    """
    决策圆桌 - 复用现有圆桌讨论系统
    封装对 RoundtableDiscussion 的调用
    """
    
    def __init__(self, llm_adapter=None):
        self.llm_adapter = llm_adapter
        self._roundtable = None
    
    async def deliberate(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """
        进行讨论审议
        
        Args:
            query: 用户查询
            context: 上下文信息
            
        Yields:
            讨论过程中的输出
            
        Note:
            讨论总结存储在 self.last_summary 属性中
        """
        # 尝试导入圆桌讨论模块
        try:
            from ...roundtable import RoundtableDiscussion
            
            if self._roundtable is None:
                self._roundtable = RoundtableDiscussion(
                    llm_adapter=self.llm_adapter
                )
            
            summary_parts = []
            async for chunk in self._roundtable.run_discussion(query):
                yield chunk
                summary_parts.append(chunk)
            
            self.last_summary = "".join(summary_parts)  # 存储结果
            
        except ImportError:
            # 如果无法导入，使用简化版本
            yield "【决策层讨论】\n"
            yield f"问题: {query}\n"
            yield "正在分析...\n"
            await asyncio.sleep(0.1)
            yield "讨论完成。\n"
            self.last_summary = f"针对'{query}'的讨论总结：建议采用系统化方法解决问题。"


class DecisionLayer(BaseLayer):
    """
    决策层 (Layer 1)
    负责高层战略决策，生成可执行方案
    
    核心组件：
    - DecisionRoundtable: 圆桌讨论系统
    - StrategyGenerator: 策略生成器
    - TaskDecomposer: 任务分解器
    """
    
    def __init__(
        self,
        config: Optional[LayerConfig] = None,
        llm_adapter=None
    ):
        if config is None:
            config = LayerConfig(
                layer_type=LayerType.DECISION,
                name="decision_layer",
                timeout_seconds=600.0  # 决策层允许更长时间
            )
        
        super().__init__(config)
        
        # 核心组件
        self.roundtable = DecisionRoundtable(llm_adapter=llm_adapter)
        self.strategy_generator = StrategyGenerator()
        self.task_decomposer = TaskDecomposer()
        
        # LLM适配器
        self.llm_adapter = llm_adapter
        
        # 决策历史
        self._decision_history: List[DecisionOutput] = []
    
    # ==================== 主处理逻辑 ====================
    
    async def process(self, context: LayerContext) -> DecisionOutput:
        """
        处理决策层逻辑
        
        Args:
            context: 层执行上下文
            
        Returns:
            DecisionOutput 决策输出
        """
        self._update_phase("deliberating")
        start_time = datetime.now()
        
        try:
            # 1. 初始化智能体
            self.initialize_agents({"query": context.query})
            
            # 2. 进行圆桌讨论
            discussion_summary = await self._run_discussion(context.query)
            
            # 3. 生成策略
            self._update_phase("generating_strategy")
            domain = self._detect_domain(context.query)
            decision_output = self.strategy_generator.generate_strategy(
                query=context.query,
                discussion_summary=discussion_summary,
                domain=domain
            )
            
            # 4. 分解任务
            self._update_phase("decomposing_tasks")
            tasks = self.task_decomposer.decompose(
                objectives=decision_output.objectives,
                constraints=decision_output.constraints
            )
            decision_output.tasks = tasks
            
            # 5. 应用反馈调整（如果有）
            if context.feedback:
                decision_output = self._apply_feedback(decision_output, context.feedback)
            
            # 6. 记录历史
            self._decision_history.append(decision_output)
            
            # 7. 记录指标
            duration = (datetime.now() - start_time).total_seconds()
            reward = self.compute_layer_reward(decision_output)
            self.record_execution_result(duration, True, reward)
            
            self._update_phase("completed")
            return decision_output
            
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
        流式处理决策层逻辑
        
        Yields:
            处理过程中的中间输出
            
        Note:
            DecisionOutput 存储在 self.last_output 属性中
        """
        self._update_phase("deliberating")
        start_time = datetime.now()
        
        try:
            yield f"[决策层] 开始处理查询: {context.query[:50]}...\n"
            
            # 1. 初始化智能体
            agent_ids = self.initialize_agents({"query": context.query})
            yield f"[决策层] 初始化 {len(agent_ids)} 个智能体\n"
            
            # 2. 进行圆桌讨论
            yield "[决策层] 开始圆桌讨论...\n"
            discussion_chunks = []
            async for chunk in self.roundtable.deliberate(context.query):
                yield chunk
                discussion_chunks.append(chunk)
            discussion_summary = "".join(discussion_chunks)
            
            # 3. 生成策略
            yield "\n[决策层] 生成策略...\n"
            self._update_phase("generating_strategy")
            domain = self._detect_domain(context.query)
            decision_output = self.strategy_generator.generate_strategy(
                query=context.query,
                discussion_summary=discussion_summary,
                domain=domain
            )
            
            # 4. 分解任务
            yield "[决策层] 分解任务...\n"
            self._update_phase("decomposing_tasks")
            tasks = self.task_decomposer.decompose(
                objectives=decision_output.objectives,
                constraints=decision_output.constraints
            )
            decision_output.tasks = tasks
            yield f"[决策层] 生成 {len(tasks)} 个任务\n"
            
            # 5. 应用反馈
            if context.feedback:
                yield "[决策层] 应用反馈调整...\n"
                decision_output = self._apply_feedback(decision_output, context.feedback)
            
            # 6. 记录
            self._decision_history.append(decision_output)
            
            duration = (datetime.now() - start_time).total_seconds()
            reward = self.compute_layer_reward(decision_output)
            self.record_execution_result(duration, True, reward)
            
            yield f"[决策层] 完成，耗时 {duration:.2f}s，奖励 {reward:.3f}\n"
            self._update_phase("completed")
            
            self.last_output = decision_output  # 存储结果
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.record_execution_result(duration, False, -1.0)
            yield f"[决策层] 错误: {str(e)}\n"
            self._update_phase("failed")
            raise
    
    # ==================== 抽象方法实现 ====================
    
    def initialize_agents(self, task_context: Dict[str, Any]) -> List[str]:
        """初始化决策层智能体"""
        agent_ids = []
        
        # 决策层使用圆桌讨论中的角色
        roles = ["facilitator", "synthesizer", "skeptic", "domain_expert"]
        
        for role in roles:
            agent_id = f"decision_{role}_{uuid.uuid4().hex[:6]}"
            # 这里只创建占位符，实际智能体由圆桌讨论系统管理
            self.register_agent(agent_id, {"role": role, "layer": 1})
            agent_ids.append(agent_id)
        
        return agent_ids
    
    def compute_layer_reward(self, output: DecisionOutput) -> float:
        """
        计算决策层奖励
        
        奖励 = 方案质量 * 0.4 + 可执行性 * 0.4 + 创新性 * 0.2
        """
        quality_score = self._evaluate_quality(output)
        feasibility_score = self._evaluate_feasibility(output)
        innovation_score = self._evaluate_innovation(output)
        
        reward = (
            quality_score * 0.4 +
            feasibility_score * 0.4 +
            innovation_score * 0.2
        )
        
        # 归一化到 [-1, 1]
        return max(-1.0, min(1.0, reward * 2 - 1))
    
    # ==================== 内部方法 ====================
    
    async def _run_discussion(self, query: str) -> str:
        """运行讨论并收集结果"""
        summary_parts = []
        async for chunk in self.roundtable.deliberate(query):
            summary_parts.append(chunk)
        return "".join(summary_parts)
    
    def _detect_domain(self, query: str) -> str:
        """检测查询领域"""
        query_lower = query.lower()
        
        domain_keywords = {
            "development": ["代码", "开发", "编程", "实现", "程序", "coding", "code"],
            "analysis": ["分析", "数据", "统计", "研究", "报告", "analysis", "data"],
            "design": ["设计", "架构", "方案", "规划", "design", "architecture"]
        }
        
        for domain, keywords in domain_keywords.items():
            if any(kw in query_lower for kw in keywords):
                return domain
        
        return "general"
    
    def _evaluate_quality(self, output: DecisionOutput) -> float:
        """评估方案质量"""
        score = 0.5  # 基础分
        
        # 目标完整性
        if len(output.objectives) >= 2:
            score += 0.2
        
        # 有成功标准
        if len(output.success_criteria) >= 2:
            score += 0.15
        
        # 有讨论总结
        if len(output.discussion_summary) > 50:
            score += 0.15
        
        return min(1.0, score)
    
    def _evaluate_feasibility(self, output: DecisionOutput) -> float:
        """评估可执行性"""
        score = 0.5
        
        # 任务分解
        if len(output.tasks) >= 2:
            score += 0.25
        
        # 约束明确
        if len(output.constraints) >= 1:
            score += 0.15
        
        # 优先级设置
        has_priority = any(t.priority > 0 for t in output.tasks)
        if has_priority:
            score += 0.1
        
        return min(1.0, score)
    
    def _evaluate_innovation(self, output: DecisionOutput) -> float:
        """评估创新性（简化版）"""
        # 目前返回固定值，后续可基于历史对比
        return 0.6
    
    def _apply_feedback(
        self,
        output: DecisionOutput,
        feedback: Dict[str, Any]
    ) -> DecisionOutput:
        """应用反馈调整策略"""
        if "adjust_priorities" in feedback:
            # 调整任务优先级
            adjustments = feedback["adjust_priorities"]
            for task in output.tasks:
                if task.task_id in adjustments:
                    task.priority = adjustments[task.task_id]
        
        if "add_constraints" in feedback:
            # 添加新约束
            for con_data in feedback["add_constraints"]:
                output.constraints.append(Constraint(
                    name=con_data.get("name", ""),
                    description=con_data.get("description", "")
                ))
        
        if "remove_tasks" in feedback:
            # 移除任务
            remove_ids = set(feedback["remove_tasks"])
            output.tasks = [t for t in output.tasks if t.task_id not in remove_ids]
        
        return output
    
    # ==================== 经验收集 ====================
    
    def collect_decision_experience(
        self,
        context: LayerContext,
        output: DecisionOutput,
        reward: float
    ) -> Experience:
        """收集决策层经验"""
        state = {
            "query": context.query,
            "iteration": context.iteration,
            "has_feedback": context.feedback is not None
        }
        
        next_state = {
            "strategy_id": output.strategy_id,
            "task_count": len(output.tasks),
            "objective_count": len(output.objectives)
        }
        
        return self.collect_experience(
            agent_id="decision_layer",
            state=state,
            action=AgentAction.SYNTHESIZE,
            reward=reward,
            next_state=next_state
        )
    
    # ==================== 公共接口 ====================
    
    def get_decision_history(self) -> List[DecisionOutput]:
        """获取决策历史"""
        return self._decision_history.copy()
    
    def clear_history(self):
        """清除历史"""
        self._decision_history.clear()
