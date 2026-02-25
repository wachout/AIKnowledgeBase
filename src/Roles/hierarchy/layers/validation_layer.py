"""
多层强化学习智能体系统 - 检验层
评估实施结果，生成反馈信号
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Generator, Callable, Set, AsyncGenerator
from enum import Enum
import asyncio
import logging
import uuid

from .base_layer import BaseLayer, LayerConfig, LayerContext
from ..types import (
    LayerType, ValidationOutput, Issue, Suggestion, IssueSeverity,
    ExecutionStatus, AgentAction, Experience, ValidationRole,
    DecisionOutput, ImplementationOutput
)


logger = logging.getLogger(__name__)


# ==================== 验证相关类 ====================

@dataclass
class ValidationCriterion:
    """验证标准"""
    criterion_id: str = field(default_factory=lambda: f"crit_{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    weight: float = 1.0
    validator_role: ValidationRole = ValidationRole.QUALITY_INSPECTOR
    check_func: Optional[str] = None  # 检查函数名


@dataclass
class ValidationResult:
    """单项验证结果"""
    criterion: ValidationCriterion
    passed: bool = False
    score: float = 0.0
    details: str = ""
    issues_found: List[Issue] = field(default_factory=list)


class ValidatorFactory:
    """
    检验智能体工厂
    根据方案动态创建检验角色
    """
    
    def __init__(self):
        # 角色到验证标准的映射
        self._role_criteria: Dict[ValidationRole, List[ValidationCriterion]] = {
            ValidationRole.QUALITY_INSPECTOR: [
                ValidationCriterion(
                    name="完整性检查",
                    description="检查产出物是否完整",
                    weight=1.0
                ),
                ValidationCriterion(
                    name="一致性检查",
                    description="检查产出物之间的一致性",
                    weight=0.8
                )
            ],
            ValidationRole.LOGIC_VALIDATOR: [
                ValidationCriterion(
                    name="逻辑正确性",
                    description="验证逻辑推理的正确性",
                    weight=1.0
                ),
                ValidationCriterion(
                    name="边界条件",
                    description="检查边界条件处理",
                    weight=0.6
                )
            ],
            ValidationRole.PERFORMANCE_ANALYST: [
                ValidationCriterion(
                    name="效率分析",
                    description="分析执行效率",
                    weight=1.0
                ),
                ValidationCriterion(
                    name="资源使用",
                    description="评估资源使用情况",
                    weight=0.7
                )
            ],
            ValidationRole.SECURITY_AUDITOR: [
                ValidationCriterion(
                    name="安全漏洞",
                    description="检查潜在安全漏洞",
                    weight=1.0
                ),
                ValidationCriterion(
                    name="权限控制",
                    description="验证权限控制正确性",
                    weight=0.9
                )
            ],
            ValidationRole.COMPLIANCE_CHECKER: [
                ValidationCriterion(
                    name="规范合规",
                    description="检查是否符合规范",
                    weight=1.0
                ),
                ValidationCriterion(
                    name="最佳实践",
                    description="评估是否遵循最佳实践",
                    weight=0.7
                )
            ]
        }
    
    def create_validators(
        self,
        decision_output: DecisionOutput,
        implementation_outputs: List[ImplementationOutput]
    ) -> Dict[str, ValidationRole]:
        """
        根据方案创建检验角色
        
        Args:
            decision_output: 决策层输出
            implementation_outputs: 实施层输出列表
            
        Returns:
            Dict[agent_id, role] 检验智能体映射
        """
        validators = {}
        
        # 基础检验员始终创建
        base_roles = [
            ValidationRole.QUALITY_INSPECTOR,
            ValidationRole.LOGIC_VALIDATOR
        ]
        
        for role in base_roles:
            agent_id = f"val_{role.name.lower()}_{uuid.uuid4().hex[:6]}"
            validators[agent_id] = role
        
        # 根据产出物类型动态添加检验员
        has_code = any(
            any(art.artifact_type == "code" for art in output.artifacts)
            for output in implementation_outputs
        )
        if has_code:
            agent_id = f"val_security_{uuid.uuid4().hex[:6]}"
            validators[agent_id] = ValidationRole.SECURITY_AUDITOR
        
        # 如果有性能相关约束，添加性能分析员
        has_performance_constraint = any(
            "性能" in con.name or "performance" in con.name.lower()
            for con in decision_output.constraints
        )
        if has_performance_constraint:
            agent_id = f"val_performance_{uuid.uuid4().hex[:6]}"
            validators[agent_id] = ValidationRole.PERFORMANCE_ANALYST
        
        # 合规检查员
        agent_id = f"val_compliance_{uuid.uuid4().hex[:6]}"
        validators[agent_id] = ValidationRole.COMPLIANCE_CHECKER
        
        return validators
    
    def get_criteria(self, role: ValidationRole) -> List[ValidationCriterion]:
        """获取角色的验证标准"""
        return self._role_criteria.get(role, [])


class FeedbackGenerator:
    """
    反馈生成器
    将评估结果转化为强化学习信号，生成改进建议
    """
    
    def __init__(self):
        self._issue_weights = {
            IssueSeverity.CRITICAL: 0.4,
            IssueSeverity.HIGH: 0.2,
            IssueSeverity.MEDIUM: 0.1,
            IssueSeverity.LOW: 0.05
        }
    
    def generate_reward_signal(
        self,
        scores: Dict[str, float],
        issues: List[Issue]
    ) -> float:
        """
        生成奖励信号
        
        Args:
            scores: 各维度评分
            issues: 发现的问题列表
            
        Returns:
            奖励信号 [-1, 1]
        """
        if not scores:
            return 0.0
        
        # 基础分数（各维度平均）
        base_score = sum(scores.values()) / len(scores)
        
        # 问题扣分
        issue_penalty = sum(
            self._issue_weights.get(issue.severity, 0.05)
            for issue in issues
        )
        
        # 限制扣分上限
        issue_penalty = min(issue_penalty, 0.8)
        
        # 计算最终奖励
        reward = base_score - issue_penalty
        
        # 归一化到 [-1, 1]
        return max(-1.0, min(1.0, reward * 2 - 1))
    
    def generate_suggestions(
        self,
        issues: List[Issue],
        scores: Dict[str, float]
    ) -> List[Suggestion]:
        """生成改进建议"""
        suggestions = []
        
        # 根据问题生成建议
        for issue in issues:
            if issue.severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH]:
                suggestion = Suggestion(
                    title=f"修复: {issue.title}",
                    description=f"建议立即处理: {issue.description}",
                    target_layer=issue.source_layer,
                    priority=10 if issue.severity == IssueSeverity.CRITICAL else 8,
                    impact_estimate=0.3 if issue.severity == IssueSeverity.CRITICAL else 0.2,
                    related_issues=[issue.issue_id]
                )
                suggestions.append(suggestion)
        
        # 根据低分维度生成建议
        for dimension, score in scores.items():
            if score < 0.6:
                suggestion = Suggestion(
                    title=f"改进: {dimension}",
                    description=f"{dimension}评分较低({score:.2f})，建议重点关注改进",
                    target_layer=2,  # 通常建议实施层改进
                    priority=5,
                    impact_estimate=0.6 - score
                )
                suggestions.append(suggestion)
        
        # 按优先级排序
        suggestions.sort(key=lambda s: s.priority, reverse=True)
        
        return suggestions
    
    def should_escalate(
        self,
        issues: List[Issue],
        reward_signal: float
    ) -> bool:
        """判断是否需要升级处理"""
        # 有严重问题
        has_critical = any(
            issue.severity == IssueSeverity.CRITICAL
            for issue in issues
        )
        if has_critical:
            return True
        
        # 奖励信号过低
        if reward_signal < -0.5:
            return True
        
        # 高严重度问题过多
        high_severity_count = sum(
            1 for issue in issues
            if issue.severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH]
        )
        if high_severity_count >= 3:
            return True
        
        return False


class ValidationRoundtable:
    """
    检验圆桌
    多检验角色协作讨论，生成综合评估报告
    
    升级版本：使用完整的检验讨论系统，实现四阶段讨论：
    1. 初步检验 - 各检验员独立检查
    2. 交叉验证 - 检验员相互验证发现
    3. 问题辩论 - 针对分歧问题深度讨论
    4. 共识裁定 - 形成最终检验结论
    
    特色：
    - 基于LLM的真正检验（替代随机评分）
    - 交叉验证确保结果可靠
    - 问题分歧深度辩论
    """
    
    def __init__(self, llm_adapter=None, use_full_discussion: bool = True):
        self.llm_adapter = llm_adapter
        self.validator_factory = ValidatorFactory()
        self.use_full_discussion = use_full_discussion
        
        # 完整的检验讨论系统
        self._full_discussion = None
        if use_full_discussion:
            try:
                from .validation_roundtable import ValidationDiscussion
                self._full_discussion = ValidationDiscussion(llm_adapter)
            except ImportError as e:
                logger.warning(f"无法加载完整检验讨论系统: {e}，使用简化版本")
                self.use_full_discussion = False
    
    async def validate(
        self,
        decision_output: DecisionOutput,
        implementation_outputs: List[ImplementationOutput],
        validators: Dict[str, ValidationRole]
    ) -> AsyncGenerator[str, None]:
        """
        进行验证讨论
        
        Args:
            decision_output: 决策层输出
            implementation_outputs: 实施层输出列表
            validators: 检验智能体映射
            
        Yields:
            验证过程的输出
            
        Note:
            各验证结果存储在 self.last_results 属性中
            讨论结果存储在 self.last_discussion_result 属性中
        """
        # 使用完整的检验讨论系统
        if self.use_full_discussion and self._full_discussion:
            async for chunk in self._full_discussion.run_validation_discussion(
                decision_output, implementation_outputs, validators
            ):
                yield chunk
            
            # 获取讨论结果
            result = self._full_discussion.get_last_result()
            if result:
                self.last_discussion_result = result
                # 转换为兼容格式
                self.last_results = {
                    "final_verdict": result.final_verdict.value if hasattr(result.final_verdict, 'value') else str(result.final_verdict),
                    "final_score": result.final_score,
                    "reward_signal": result.reward_signal,
                    "critical_issues": result.critical_issues,
                    "required_actions": result.required_actions
                }
            else:
                self.last_results = {}
                self.last_discussion_result = None
            return
        
        # 简化版本（后备方案）
        yield "[检验圆桌] 开始验证讨论\n"
        yield f"[检验圆桌] 参与检验员: {len(validators)}人\n"
        
        results = {}
        
        for agent_id, role in validators.items():
            yield f"\n[{role.value}] 开始检验...\n"
            
            # 获取该角色的验证标准
            criteria = self.validator_factory.get_criteria(role)
            
            for criterion in criteria:
                yield f"  - 检查: {criterion.name}\n"
                await asyncio.sleep(0.05)
                
                # 执行验证
                result = self._validate_criterion(
                    criterion,
                    decision_output,
                    implementation_outputs
                )
                results[f"{agent_id}_{criterion.criterion_id}"] = result
                
                status = "通过" if result.passed else "需关注"
                yield f"    结果: {status} (分数: {result.score:.2f})\n"
        
        yield "\n[检验圆桌] 验证讨论完成\n"
        self.last_results = results
        self.last_discussion_result = None
    
    def _validate_criterion(
        self,
        criterion: ValidationCriterion,
        decision_output: DecisionOutput,
        implementation_outputs: List[ImplementationOutput]
    ) -> ValidationResult:
        """执行单项验证（简化版本）"""
        # 简化版本：基于规则的评分
        score = 0.7  # 默认基础分
        
        # 根据实施产出物调整评分
        if implementation_outputs:
            completed_count = sum(
                1 for o in implementation_outputs
                if hasattr(o, 'status') and str(o.status) == 'completed'
            )
            completion_rate = completed_count / len(implementation_outputs)
            score = 0.5 + 0.4 * completion_rate
        
        passed = score >= 0.6
        
        issues = []
        if not passed:
            issues.append(Issue(
                title=f"{criterion.name}未通过",
                description=f"验证标准'{criterion.name}'未满足要求",
                severity=IssueSeverity.MEDIUM,
                source_layer=3,
                detected_by="ValidationRoundtable"
            ))
        
        return ValidationResult(
            criterion=criterion,
            passed=passed,
            score=score,
            details=f"验证完成，得分{score:.2f}",
            issues_found=issues
        )
    
    def get_reward_signal(self) -> float:
        """获取奖励信号"""
        if self._full_discussion:
            return self._full_discussion.get_reward_signal()
        return 0.5  # 默认值
    
    def get_final_verdict(self) -> str:
        """获取最终裁定"""
        if self.last_discussion_result:
            return self.last_discussion_result.final_verdict.value if hasattr(self.last_discussion_result.final_verdict, 'value') else str(self.last_discussion_result.final_verdict)
        return "pending"
    
    def reset(self):
        """重置检验系统"""
        if self._full_discussion:
            self._full_discussion.reset()
        self.last_results = None
        self.last_discussion_result = None


class ValidationLayer(BaseLayer):
    """
    检验层 (Layer 3)
    评估实施结果，生成反馈信号
    
    核心组件：
    - ValidatorFactory: 检验智能体工厂
    - ValidationRoundtable: 检验圆桌讨论
    - FeedbackGenerator: 反馈生成器
    """
    
    def __init__(
        self,
        config: Optional[LayerConfig] = None,
        llm_adapter=None
    ):
        if config is None:
            config = LayerConfig(
                layer_type=LayerType.VALIDATION,
                name="validation_layer",
                timeout_seconds=300.0
            )
        
        super().__init__(config)
        
        # 核心组件
        self.validator_factory = ValidatorFactory()
        self.roundtable = ValidationRoundtable(llm_adapter=llm_adapter)
        self.feedback_generator = FeedbackGenerator()
        
        # LLM适配器
        self.llm_adapter = llm_adapter
        
        # 验证历史
        self._validation_history: List[ValidationOutput] = []
        
        # 阈值配置
        self.reward_threshold = 0.6  # 通过阈值
    
    # ==================== 主处理逻辑 ====================
    
    async def process(self, context: LayerContext) -> ValidationOutput:
        """
        处理检验层逻辑
        
        Args:
            context: 层执行上下文
                - parent_output: (DecisionOutput, List[ImplementationOutput])
            
        Returns:
            ValidationOutput 检验输出
        """
        self._update_phase("preparing")
        start_time = datetime.now()
        
        try:
            # 解析输入
            decision_output, implementation_outputs = self._parse_input(context)
            
            # 初始化检验智能体
            validators = self.initialize_agents({
                "decision_output": decision_output,
                "implementation_outputs": implementation_outputs
            })
            
            # 进行检验讨论
            self._update_phase("validating")
            validation_results = await self._run_validation(
                decision_output,
                implementation_outputs,
                validators
            )
            
            # 汇总评分
            scores = self._aggregate_scores(validation_results)
            
            # 收集问题
            issues = self._collect_issues(validation_results)
            
            # 生成反馈
            self._update_phase("generating_feedback")
            reward_signal = self.feedback_generator.generate_reward_signal(scores, issues)
            suggestions = self.feedback_generator.generate_suggestions(issues, scores)
            escalation_required = self.feedback_generator.should_escalate(issues, reward_signal)
            
            # 创建输出
            output = ValidationOutput(
                target_strategy_id=decision_output.strategy_id,
                target_implementation_ids=[o.implementation_id for o in implementation_outputs],
                scores=scores,
                issues=issues,
                suggestions=suggestions,
                reward_signal=reward_signal,
                escalation_required=escalation_required,
                overall_assessment=self._generate_assessment(scores, issues, reward_signal)
            )
            
            # 记录历史
            self._validation_history.append(output)
            
            # 记录指标
            duration = (datetime.now() - start_time).total_seconds()
            reward = self.compute_layer_reward(output)
            self.record_execution_result(duration, True, reward)
            
            self._update_phase("completed")
            return output
            
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
        流式处理检验层逻辑
        
        Yields:
            处理过程中的中间输出
            
        Note:
            ValidationOutput 存储在 self.last_output 属性中
        """
        self._update_phase("preparing")
        start_time = datetime.now()
        
        try:
            yield "[检验层] 开始验证...\n"
            
            # 解析输入
            decision_output, implementation_outputs = self._parse_input(context)
            yield f"[检验层] 验证决策: {decision_output.strategy_id}\n"
            yield f"[检验层] 验证实施: {len(implementation_outputs)} 个\n"
            
            # 初始化检验智能体
            validators = self.validator_factory.create_validators(
                decision_output,
                implementation_outputs
            )
            
            # 注册智能体
            for agent_id, role in validators.items():
                self.register_agent(agent_id, {"role": role, "layer": 3})
            
            yield f"[检验层] 创建 {len(validators)} 个检验员\n"
            
            # 进行检验讨论
            self._update_phase("validating")
            yield "\n[检验层] 开始检验讨论...\n"
            
            validation_results = {}
            async for chunk in self.roundtable.validate(
                decision_output,
                implementation_outputs,
                validators
            ):
                yield chunk
            
            # 手动执行验证以获取结果
            validation_results = await self._run_validation(
                decision_output,
                implementation_outputs,
                validators
            )
            
            # 汇总评分
            scores = self._aggregate_scores(validation_results)
            yield f"\n[检验层] 评分汇总:\n"
            for dim, score in scores.items():
                yield f"  - {dim}: {score:.2f}\n"
            
            # 收集问题
            issues = self._collect_issues(validation_results)
            if issues:
                yield f"\n[检验层] 发现 {len(issues)} 个问题:\n"
                for issue in issues[:5]:  # 最多显示5个
                    yield f"  - [{issue.severity.value}] {issue.title}\n"
            
            # 生成反馈
            self._update_phase("generating_feedback")
            yield "\n[检验层] 生成反馈...\n"
            
            reward_signal = self.feedback_generator.generate_reward_signal(scores, issues)
            suggestions = self.feedback_generator.generate_suggestions(issues, scores)
            escalation_required = self.feedback_generator.should_escalate(issues, reward_signal)
            
            yield f"[检验层] 奖励信号: {reward_signal:.3f}\n"
            yield f"[检验层] 需要升级处理: {'是' if escalation_required else '否'}\n"
            
            if suggestions:
                yield f"\n[检验层] 改进建议 ({len(suggestions)}):\n"
                for sug in suggestions[:3]:
                    yield f"  - {sug.title}\n"
            
            # 创建输出
            output = ValidationOutput(
                target_strategy_id=decision_output.strategy_id,
                target_implementation_ids=[o.implementation_id for o in implementation_outputs],
                scores=scores,
                issues=issues,
                suggestions=suggestions,
                reward_signal=reward_signal,
                escalation_required=escalation_required,
                overall_assessment=self._generate_assessment(scores, issues, reward_signal)
            )
            
            # 记录
            self._validation_history.append(output)
            
            duration = (datetime.now() - start_time).total_seconds()
            layer_reward = self.compute_layer_reward(output)
            self.record_execution_result(duration, True, layer_reward)
            
            yield f"\n[检验层] 完成，耗时 {duration:.2f}s\n"
            yield f"[检验层] 总体评估: {output.overall_assessment}\n"
            
            self._update_phase("completed")
            self.last_output = output  # 存储结果
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.record_execution_result(duration, False, -1.0)
            yield f"[检验层] 错误: {str(e)}\n"
            self._update_phase("failed")
            raise
    
    # ==================== 抽象方法实现 ====================
    
    def initialize_agents(self, task_context: Dict[str, Any]) -> Dict[str, ValidationRole]:
        """初始化检验层智能体"""
        decision_output = task_context.get("decision_output")
        implementation_outputs = task_context.get("implementation_outputs", [])
        
        if not decision_output:
            # 创建默认检验员
            validators = {}
            for role in [ValidationRole.QUALITY_INSPECTOR, ValidationRole.LOGIC_VALIDATOR]:
                agent_id = f"val_{role.name.lower()}_{uuid.uuid4().hex[:6]}"
                validators[agent_id] = role
            return validators
        
        validators = self.validator_factory.create_validators(
            decision_output,
            implementation_outputs
        )
        
        # 注册智能体
        for agent_id, role in validators.items():
            self.register_agent(agent_id, {"role": role, "layer": 3})
        
        return validators
    
    def compute_layer_reward(self, output: ValidationOutput) -> float:
        """
        计算检验层奖励
        
        奖励 = 检测准确性 * 0.5 + 建议有效性 * 0.5
        """
        detection_score = self._evaluate_detection_accuracy(output)
        suggestion_score = self._evaluate_suggestion_effectiveness(output)
        
        reward = (
            detection_score * 0.5 +
            suggestion_score * 0.5
        )
        
        # 归一化到 [-1, 1]
        return max(-1.0, min(1.0, reward * 2 - 1))
    
    # ==================== 内部方法 ====================
    
    def _parse_input(
        self,
        context: LayerContext
    ) -> tuple:
        """解析输入"""
        parent_output = context.parent_output
        
        if isinstance(parent_output, tuple) and len(parent_output) == 2:
            return parent_output
        
        # 尝试从 metadata 获取
        if context.metadata:
            decision_output = context.metadata.get("decision_output")
            implementation_outputs = context.metadata.get("implementation_outputs", [])
            if decision_output:
                return decision_output, implementation_outputs
        
        # 返回空默认值
        return DecisionOutput(), []
    
    async def _run_validation(
        self,
        decision_output: DecisionOutput,
        implementation_outputs: List[ImplementationOutput],
        validators: Dict[str, ValidationRole]
    ) -> Dict[str, ValidationResult]:
        """运行验证并收集结果"""
        results = {}
        
        for agent_id, role in validators.items():
            criteria = self.validator_factory.get_criteria(role)
            
            for criterion in criteria:
                result = self.roundtable._validate_criterion(
                    criterion,
                    decision_output,
                    implementation_outputs
                )
                results[f"{agent_id}_{criterion.criterion_id}"] = result
        
        return results
    
    def _aggregate_scores(
        self,
        validation_results: Dict[str, ValidationResult]
    ) -> Dict[str, float]:
        """汇总评分"""
        scores = {}
        role_scores: Dict[str, List[float]] = {}
        
        for key, result in validation_results.items():
            role_name = result.criterion.validator_role.value
            if role_name not in role_scores:
                role_scores[role_name] = []
            role_scores[role_name].append(result.score * result.criterion.weight)
        
        for role_name, score_list in role_scores.items():
            scores[role_name] = sum(score_list) / len(score_list) if score_list else 0.0
        
        # 添加总体评分
        if scores:
            scores["总体"] = sum(scores.values()) / len(scores)
        
        return scores
    
    def _collect_issues(
        self,
        validation_results: Dict[str, ValidationResult]
    ) -> List[Issue]:
        """收集所有问题"""
        issues = []
        seen_ids: Set[str] = set()
        
        for result in validation_results.values():
            for issue in result.issues_found:
                if issue.issue_id not in seen_ids:
                    issues.append(issue)
                    seen_ids.add(issue.issue_id)
        
        # 按严重程度排序
        severity_order = {
            IssueSeverity.CRITICAL: 0,
            IssueSeverity.HIGH: 1,
            IssueSeverity.MEDIUM: 2,
            IssueSeverity.LOW: 3
        }
        issues.sort(key=lambda i: severity_order.get(i.severity, 4))
        
        return issues
    
    def _generate_assessment(
        self,
        scores: Dict[str, float],
        issues: List[Issue],
        reward_signal: float
    ) -> str:
        """生成总体评估"""
        overall_score = scores.get("总体", 0.0)
        
        if reward_signal >= 0.5:
            status = "优秀"
        elif reward_signal >= 0.0:
            status = "良好"
        elif reward_signal >= -0.3:
            status = "需改进"
        else:
            status = "不合格"
        
        critical_count = sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL)
        high_count = sum(1 for i in issues if i.severity == IssueSeverity.HIGH)
        
        assessment = f"总体评估: {status} (得分: {overall_score:.2f})"
        
        if critical_count > 0:
            assessment += f"，发现{critical_count}个严重问题"
        if high_count > 0:
            assessment += f"，{high_count}个高优先级问题"
        
        return assessment
    
    def _evaluate_detection_accuracy(self, output: ValidationOutput) -> float:
        """评估检测准确性"""
        # 基于评分覆盖度和问题分类评估
        score = 0.5
        
        # 评分维度覆盖
        if len(output.scores) >= 3:
            score += 0.2
        
        # 有合理的问题分类
        if output.issues:
            severity_distribution = {}
            for issue in output.issues:
                severity_distribution[issue.severity] = severity_distribution.get(issue.severity, 0) + 1
            
            # 分布合理性
            if len(severity_distribution) >= 2:
                score += 0.15
        
        # 评分在合理范围
        if output.scores:
            avg_score = sum(output.scores.values()) / len(output.scores)
            if 0.3 <= avg_score <= 0.9:
                score += 0.15
        
        return min(1.0, score)
    
    def _evaluate_suggestion_effectiveness(self, output: ValidationOutput) -> float:
        """评估建议有效性"""
        score = 0.5
        
        # 有建议
        if output.suggestions:
            score += 0.2
        
        # 建议与问题关联
        if output.suggestions and output.issues:
            linked_count = sum(
                1 for sug in output.suggestions
                if sug.related_issues
            )
            if linked_count > 0:
                score += 0.15
        
        # 建议有优先级
        if output.suggestions:
            has_priority = any(sug.priority > 0 for sug in output.suggestions)
            if has_priority:
                score += 0.15
        
        return min(1.0, score)
    
    # ==================== 经验收集 ====================
    
    def collect_validation_experience(
        self,
        context: LayerContext,
        output: ValidationOutput,
        reward: float
    ) -> Experience:
        """收集检验层经验"""
        state = {
            "strategy_id": output.target_strategy_id,
            "implementation_count": len(output.target_implementation_ids)
        }
        
        next_state = {
            "validation_id": output.validation_id,
            "reward_signal": output.reward_signal,
            "issue_count": len(output.issues),
            "suggestion_count": len(output.suggestions),
            "escalation_required": output.escalation_required
        }
        
        return self.collect_experience(
            agent_id="validation_layer",
            state=state,
            action=AgentAction.VALIDATE,
            reward=reward,
            next_state=next_state
        )
    
    # ==================== 公共接口 ====================
    
    def get_validation_history(self) -> List[ValidationOutput]:
        """获取验证历史"""
        return self._validation_history.copy()
    
    def is_passing(self, output: ValidationOutput) -> bool:
        """判断是否通过验证"""
        return output.reward_signal >= self.reward_threshold and not output.escalation_required
    
    def clear_history(self):
        """清除历史"""
        self._validation_history.clear()
