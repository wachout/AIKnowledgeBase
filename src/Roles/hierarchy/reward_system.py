"""
多层强化学习智能体系统 - 奖励系统
层次化奖励计算和传播
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import logging
import math

from .types import (
    LayerType, DecisionOutput, ImplementationOutput, ValidationOutput,
    Experience, Issue, IssueSeverity
)


logger = logging.getLogger(__name__)


class RewardComponent(Enum):
    """奖励组成部分"""
    # 决策层
    DECISION_QUALITY = "decision_quality"
    DECISION_FEASIBILITY = "decision_feasibility"
    DECISION_INNOVATION = "decision_innovation"
    
    # 实施层
    IMPLEMENTATION_COMPLETION = "impl_completion"
    IMPLEMENTATION_QUALITY = "impl_quality"
    IMPLEMENTATION_EFFICIENCY = "impl_efficiency"
    
    # 检验层
    VALIDATION_ACCURACY = "val_accuracy"
    VALIDATION_COVERAGE = "val_coverage"
    VALIDATION_FEEDBACK_QUALITY = "val_feedback"
    
    # 全局
    GLOBAL_SUCCESS = "global_success"
    GLOBAL_EFFICIENCY = "global_efficiency"


@dataclass
class RewardSignal:
    """奖励信号"""
    source: str = ""  # 来源（层或智能体）
    component: RewardComponent = RewardComponent.GLOBAL_SUCCESS
    value: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LayerReward:
    """层奖励汇总"""
    layer: LayerType
    total_reward: float = 0.0
    components: Dict[RewardComponent, float] = field(default_factory=dict)
    agent_rewards: Dict[str, float] = field(default_factory=dict)


class RewardShaper:
    """
    奖励塑形器
    处理稀疏奖励问题，提供中间奖励信号
    """
    
    def __init__(self):
        self.potential_function: Optional[Callable] = None
        self.baseline: float = 0.0
        self.scale: float = 1.0
    
    def shape(
        self,
        raw_reward: float,
        state: Dict[str, Any],
        next_state: Dict[str, Any]
    ) -> float:
        """
        奖励塑形
        
        使用势函数方法: F(s, s') = γΦ(s') - Φ(s)
        """
        if self.potential_function is None:
            return raw_reward
        
        gamma = 0.99
        potential_current = self.potential_function(state)
        potential_next = self.potential_function(next_state)
        
        shaping_reward = gamma * potential_next - potential_current
        
        return raw_reward + shaping_reward * self.scale
    
    def set_potential_function(self, func: Callable):
        """设置势函数"""
        self.potential_function = func
    
    def normalize(self, reward: float) -> float:
        """归一化奖励"""
        return max(-1.0, min(1.0, (reward - self.baseline) / max(self.scale, 0.01)))


class HierarchicalRewardSystem:
    """
    层次化奖励系统
    负责计算各层奖励并进行反向传播
    """
    
    def __init__(self):
        # 各层权重
        self.layer_weights = {
            LayerType.DECISION: 0.3,
            LayerType.IMPLEMENTATION: 0.4,
            LayerType.VALIDATION: 0.3
        }
        
        # 奖励组件权重
        self.component_weights = {
            # 决策层
            RewardComponent.DECISION_QUALITY: 0.4,
            RewardComponent.DECISION_FEASIBILITY: 0.4,
            RewardComponent.DECISION_INNOVATION: 0.2,
            # 实施层
            RewardComponent.IMPLEMENTATION_COMPLETION: 0.3,
            RewardComponent.IMPLEMENTATION_QUALITY: 0.4,
            RewardComponent.IMPLEMENTATION_EFFICIENCY: 0.3,
            # 检验层
            RewardComponent.VALIDATION_ACCURACY: 0.4,
            RewardComponent.VALIDATION_COVERAGE: 0.3,
            RewardComponent.VALIDATION_FEEDBACK_QUALITY: 0.3
        }
        
        # 奖励塑形器
        self.shaper = RewardShaper()
        
        # 奖励历史
        self._reward_history: List[RewardSignal] = []
        self._layer_rewards: Dict[LayerType, List[float]] = {
            LayerType.DECISION: [],
            LayerType.IMPLEMENTATION: [],
            LayerType.VALIDATION: []
        }
    
    # ==================== 层奖励计算 ====================
    
    def compute_layer_reward(self, layer: LayerType, output: Any) -> LayerReward:
        """计算单层奖励"""
        if layer == LayerType.DECISION:
            return self._compute_decision_reward(output)
        elif layer == LayerType.IMPLEMENTATION:
            return self._compute_implementation_reward(output)
        elif layer == LayerType.VALIDATION:
            return self._compute_validation_reward(output)
        else:
            return LayerReward(layer=layer)
    
    def _compute_decision_reward(self, output: DecisionOutput) -> LayerReward:
        """决策层奖励 = 方案质量 + 可执行性 + 创新性"""
        components = {}
        
        # 方案质量
        quality = self._evaluate_decision_quality(output)
        components[RewardComponent.DECISION_QUALITY] = quality
        
        # 可执行性
        feasibility = self._evaluate_decision_feasibility(output)
        components[RewardComponent.DECISION_FEASIBILITY] = feasibility
        
        # 创新性
        innovation = self._evaluate_decision_innovation(output)
        components[RewardComponent.DECISION_INNOVATION] = innovation
        
        # 加权求和
        total = sum(
            components[comp] * self.component_weights.get(comp, 1.0)
            for comp in components
        )
        
        reward = LayerReward(
            layer=LayerType.DECISION,
            total_reward=total,
            components=components
        )
        
        self._layer_rewards[LayerType.DECISION].append(total)
        return reward
    
    def _compute_implementation_reward(
        self,
        outputs: List[ImplementationOutput]
    ) -> LayerReward:
        """实施层奖励 = 完成度 + 质量 + 效率"""
        if not outputs:
            return LayerReward(layer=LayerType.IMPLEMENTATION)
        
        components = {}
        
        # 完成度（平均）
        completion_scores = [
            self._evaluate_impl_completion(o) for o in outputs
        ]
        components[RewardComponent.IMPLEMENTATION_COMPLETION] = (
            sum(completion_scores) / len(completion_scores)
        )
        
        # 质量
        quality_scores = [
            self._evaluate_impl_quality(o) for o in outputs
        ]
        components[RewardComponent.IMPLEMENTATION_QUALITY] = (
            sum(quality_scores) / len(quality_scores)
        )
        
        # 效率
        efficiency_scores = [
            self._evaluate_impl_efficiency(o) for o in outputs
        ]
        components[RewardComponent.IMPLEMENTATION_EFFICIENCY] = (
            sum(efficiency_scores) / len(efficiency_scores)
        )
        
        # 加权求和
        total = sum(
            components[comp] * self.component_weights.get(comp, 1.0)
            for comp in components
        )
        
        reward = LayerReward(
            layer=LayerType.IMPLEMENTATION,
            total_reward=total,
            components=components
        )
        
        self._layer_rewards[LayerType.IMPLEMENTATION].append(total)
        return reward
    
    def _compute_validation_reward(self, output: ValidationOutput) -> LayerReward:
        """检验层奖励 = 检测准确性 + 覆盖度 + 反馈质量"""
        components = {}
        
        # 检测准确性
        accuracy = self._evaluate_val_accuracy(output)
        components[RewardComponent.VALIDATION_ACCURACY] = accuracy
        
        # 覆盖度
        coverage = self._evaluate_val_coverage(output)
        components[RewardComponent.VALIDATION_COVERAGE] = coverage
        
        # 反馈质量
        feedback_quality = self._evaluate_val_feedback(output)
        components[RewardComponent.VALIDATION_FEEDBACK_QUALITY] = feedback_quality
        
        # 加权求和
        total = sum(
            components[comp] * self.component_weights.get(comp, 1.0)
            for comp in components
        )
        
        reward = LayerReward(
            layer=LayerType.VALIDATION,
            total_reward=total,
            components=components
        )
        
        self._layer_rewards[LayerType.VALIDATION].append(total)
        return reward
    
    # ==================== 评估函数 ====================
    
    def _evaluate_decision_quality(self, output: DecisionOutput) -> float:
        """评估决策质量"""
        score = 0.5
        
        if len(output.objectives) >= 2:
            score += 0.2
        if len(output.success_criteria) >= 2:
            score += 0.15
        if len(output.discussion_summary) > 50:
            score += 0.15
        
        return min(1.0, score)
    
    def _evaluate_decision_feasibility(self, output: DecisionOutput) -> float:
        """评估决策可执行性"""
        score = 0.5
        
        if len(output.tasks) >= 2:
            score += 0.25
        if len(output.constraints) >= 1:
            score += 0.15
        if any(t.priority > 0 for t in output.tasks):
            score += 0.1
        
        return min(1.0, score)
    
    def _evaluate_decision_innovation(self, output: DecisionOutput) -> float:
        """评估决策创新性"""
        return 0.6  # 简化实现
    
    def _evaluate_impl_completion(self, output: ImplementationOutput) -> float:
        """评估实施完成度"""
        return output.metrics.get("completion_rate", 0.5)
    
    def _evaluate_impl_quality(self, output: ImplementationOutput) -> float:
        """评估实施质量"""
        score = 0.5
        
        if len(output.artifacts) > 0:
            score += 0.3
        if output.status.value == "completed":
            score += 0.2
        
        return min(1.0, score)
    
    def _evaluate_impl_efficiency(self, output: ImplementationOutput) -> float:
        """评估实施效率"""
        exec_time = output.metrics.get("execution_time", 10.0)
        
        if exec_time <= 1.0:
            return 1.0
        elif exec_time <= 5.0:
            return 0.8
        elif exec_time <= 10.0:
            return 0.6
        else:
            return 0.4
    
    def _evaluate_val_accuracy(self, output: ValidationOutput) -> float:
        """评估验证准确性"""
        score = 0.5
        
        if len(output.scores) >= 3:
            score += 0.2
        
        if output.issues:
            severity_dist = {}
            for issue in output.issues:
                severity_dist[issue.severity] = severity_dist.get(issue.severity, 0) + 1
            if len(severity_dist) >= 2:
                score += 0.15
        
        if output.scores:
            avg = sum(output.scores.values()) / len(output.scores)
            if 0.3 <= avg <= 0.9:
                score += 0.15
        
        return min(1.0, score)
    
    def _evaluate_val_coverage(self, output: ValidationOutput) -> float:
        """评估验证覆盖度"""
        score = 0.5
        
        if len(output.scores) >= 4:
            score += 0.3
        elif len(output.scores) >= 2:
            score += 0.15
        
        if len(output.suggestions) >= 2:
            score += 0.2
        
        return min(1.0, score)
    
    def _evaluate_val_feedback(self, output: ValidationOutput) -> float:
        """评估反馈质量"""
        score = 0.5
        
        if output.suggestions:
            linked = sum(1 for s in output.suggestions if s.related_issues)
            if linked > 0:
                score += 0.25
            if any(s.priority > 0 for s in output.suggestions):
                score += 0.15
        
        if len(output.overall_assessment) > 20:
            score += 0.1
        
        return min(1.0, score)
    
    # ==================== 奖励传播 ====================
    
    def compute_total_reward(
        self,
        decision_output: DecisionOutput,
        implementation_outputs: List[ImplementationOutput],
        validation_output: ValidationOutput
    ) -> float:
        """计算总奖励"""
        # 计算各层奖励
        decision_reward = self.compute_layer_reward(
            LayerType.DECISION, decision_output
        )
        impl_reward = self.compute_layer_reward(
            LayerType.IMPLEMENTATION, implementation_outputs
        )
        val_reward = self.compute_layer_reward(
            LayerType.VALIDATION, validation_output
        )
        
        # 加权求和
        total = (
            decision_reward.total_reward * self.layer_weights[LayerType.DECISION] +
            impl_reward.total_reward * self.layer_weights[LayerType.IMPLEMENTATION] +
            val_reward.total_reward * self.layer_weights[LayerType.VALIDATION]
        )
        
        # 使用验证层的奖励信号作为最终调整
        final_reward = total * 0.7 + validation_output.reward_signal * 0.3
        
        # 记录
        signal = RewardSignal(
            source="system",
            component=RewardComponent.GLOBAL_SUCCESS,
            value=final_reward
        )
        self._reward_history.append(signal)
        
        return final_reward
    
    def propagate_reward(
        self,
        final_reward: float,
        discount: float = 0.9
    ) -> Dict[LayerType, float]:
        """
        奖励反向传播到各层
        
        Args:
            final_reward: 最终奖励
            discount: 折扣因子
            
        Returns:
            各层分配的奖励
        """
        layer_rewards = {}
        
        # 从检验层反向传播
        for layer in [LayerType.VALIDATION, LayerType.IMPLEMENTATION, LayerType.DECISION]:
            layer_index = layer.value
            discounted_reward = final_reward * (discount ** (3 - layer_index))
            layer_rewards[layer] = discounted_reward
        
        return layer_rewards
    
    def propagate_to_agents(
        self,
        layer_rewards: Dict[LayerType, float],
        agent_contributions: Dict[str, float]
    ) -> Dict[str, float]:
        """
        将层奖励分配给智能体
        
        Args:
            layer_rewards: 各层奖励
            agent_contributions: 智能体贡献（agent_id -> contribution_weight）
            
        Returns:
            各智能体奖励
        """
        agent_rewards = {}
        
        # 按贡献比例分配
        total_contribution = sum(agent_contributions.values())
        if total_contribution <= 0:
            return agent_rewards
        
        # 假设所有智能体在同一层（简化）
        # 实际应用中需要根据智能体所属层分配
        total_reward = sum(layer_rewards.values())
        
        for agent_id, contribution in agent_contributions.items():
            agent_rewards[agent_id] = (
                total_reward * contribution / total_contribution
            )
        
        return agent_rewards
    
    # ==================== 统计 ====================
    
    def get_reward_stats(self) -> Dict[str, Any]:
        """获取奖励统计"""
        stats = {
            "total_signals": len(self._reward_history),
            "layer_stats": {}
        }
        
        for layer, rewards in self._layer_rewards.items():
            if rewards:
                stats["layer_stats"][layer.name] = {
                    "count": len(rewards),
                    "mean": sum(rewards) / len(rewards),
                    "min": min(rewards),
                    "max": max(rewards)
                }
        
        if self._reward_history:
            recent = self._reward_history[-100:]
            stats["recent_mean"] = sum(s.value for s in recent) / len(recent)
        
        return stats
    
    def clear_history(self):
        """清除历史"""
        self._reward_history.clear()
        for layer in self._layer_rewards:
            self._layer_rewards[layer].clear()
