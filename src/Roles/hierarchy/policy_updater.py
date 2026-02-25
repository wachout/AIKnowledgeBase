"""
多层强化学习智能体系统 - 策略更新器
基于经验的策略梯度更新
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
import logging
import math
import random

from .types import LayerType, Experience, Policy, AgentAction


logger = logging.getLogger(__name__)


@dataclass
class GradientInfo:
    """梯度信息"""
    parameter: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class UpdateResult:
    """更新结果"""
    layer: LayerType
    agent_id: str
    old_params: Dict[str, float]
    new_params: Dict[str, float]
    loss: float
    timestamp: datetime = field(default_factory=datetime.now)


class Optimizer:
    """优化器基类"""
    
    def __init__(self, learning_rate: float = 0.001):
        self.learning_rate = learning_rate
    
    def compute_update(
        self,
        gradient: float,
        param_name: str
    ) -> float:
        """计算参数更新量"""
        return self.learning_rate * gradient


class AdamOptimizer(Optimizer):
    """Adam优化器"""
    
    def __init__(
        self,
        learning_rate: float = 0.001,
        beta1: float = 0.9,
        beta2: float = 0.999,
        epsilon: float = 1e-8
    ):
        super().__init__(learning_rate)
        self.beta1 = beta1
        self.beta2 = beta2
        self.epsilon = epsilon
        
        # 动量
        self._m: Dict[str, float] = {}  # 一阶矩
        self._v: Dict[str, float] = {}  # 二阶矩
        self._t: int = 0  # 时间步
    
    def compute_update(
        self,
        gradient: float,
        param_name: str
    ) -> float:
        """计算Adam更新量"""
        self._t += 1
        
        # 初始化动量
        if param_name not in self._m:
            self._m[param_name] = 0.0
            self._v[param_name] = 0.0
        
        # 更新一阶和二阶矩估计
        self._m[param_name] = (
            self.beta1 * self._m[param_name] + (1 - self.beta1) * gradient
        )
        self._v[param_name] = (
            self.beta2 * self._v[param_name] + (1 - self.beta2) * gradient ** 2
        )
        
        # 偏差校正
        m_hat = self._m[param_name] / (1 - self.beta1 ** self._t)
        v_hat = self._v[param_name] / (1 - self.beta2 ** self._t)
        
        # 计算更新量
        update = self.learning_rate * m_hat / (math.sqrt(v_hat) + self.epsilon)
        
        return update
    
    def reset(self):
        """重置优化器状态"""
        self._m.clear()
        self._v.clear()
        self._t = 0


class AdvantageEstimator:
    """
    优势函数估计器
    用于计算策略梯度中的优势
    """
    
    def __init__(self, gamma: float = 0.99, lambda_gae: float = 0.95):
        self.gamma = gamma
        self.lambda_gae = lambda_gae
    
    def compute_advantages(
        self,
        experiences: List[Experience],
        value_estimates: Optional[Dict[str, float]] = None
    ) -> List[float]:
        """
        计算GAE (Generalized Advantage Estimation)
        
        A_t = δ_t + (γλ)δ_{t+1} + (γλ)²δ_{t+2} + ...
        其中 δ_t = r_t + γV(s_{t+1}) - V(s_t)
        """
        if not experiences:
            return []
        
        advantages = []
        gae = 0.0
        
        # 如果没有价值估计，使用奖励作为近似
        if value_estimates is None:
            value_estimates = {}
        
        # 反向遍历计算GAE
        for i in reversed(range(len(experiences))):
            exp = experiences[i]
            
            # 获取价值估计
            state_key = str(exp.state)
            next_state_key = str(exp.next_state)
            
            v_current = value_estimates.get(state_key, 0.0)
            v_next = value_estimates.get(next_state_key, 0.0) if not exp.done else 0.0
            
            # TD误差
            delta = exp.reward + self.gamma * v_next - v_current
            
            # GAE
            gae = delta + self.gamma * self.lambda_gae * gae * (0 if exp.done else 1)
            
            advantages.insert(0, gae)
        
        return advantages
    
    def normalize_advantages(self, advantages: List[float]) -> List[float]:
        """标准化优势"""
        if not advantages:
            return []
        
        mean = sum(advantages) / len(advantages)
        variance = sum((a - mean) ** 2 for a in advantages) / len(advantages)
        std = math.sqrt(variance + 1e-8)
        
        return [(a - mean) / std for a in advantages]


class HierarchicalPolicyUpdater:
    """
    层次化策略更新器
    基于PPO/A2C风格的策略更新
    """
    
    def __init__(
        self,
        learning_rate: float = 0.001,
        batch_size: int = 32,
        clip_epsilon: float = 0.2,
        entropy_coef: float = 0.01,
        value_coef: float = 0.5
    ):
        # 优化器
        self.optimizer = AdamOptimizer(learning_rate)
        
        # 超参数
        self.batch_size = batch_size
        self.clip_epsilon = clip_epsilon  # PPO裁剪参数
        self.entropy_coef = entropy_coef
        self.value_coef = value_coef
        
        # 优势估计器
        self.advantage_estimator = AdvantageEstimator()
        
        # 策略缓存
        self._policies: Dict[str, Policy] = {}
        
        # 更新历史
        self._update_history: List[UpdateResult] = []
    
    def register_policy(self, agent_id: str, policy: Policy):
        """注册策略"""
        self._policies[agent_id] = policy
    
    def update(self, experiences: List[Experience]) -> List[UpdateResult]:
        """
        基于经验更新策略
        
        Args:
            experiences: 经验列表
            
        Returns:
            更新结果列表
        """
        if not experiences:
            return []
        
        results = []
        
        # 按层分组
        layer_experiences = self._group_by_layer(experiences)
        
        for layer, layer_exp in layer_experiences.items():
            if len(layer_exp) >= self.batch_size:
                # 采样批次
                batch = self._sample_batch(layer_exp)
                
                # 更新该层策略
                layer_results = self._update_layer_policies(layer, batch)
                results.extend(layer_results)
        
        return results
    
    def _group_by_layer(
        self,
        experiences: List[Experience]
    ) -> Dict[LayerType, List[Experience]]:
        """按层分组经验"""
        groups = {
            LayerType.DECISION: [],
            LayerType.IMPLEMENTATION: [],
            LayerType.VALIDATION: []
        }
        
        for exp in experiences:
            layer = LayerType(exp.layer) if exp.layer in [1, 2, 3] else LayerType.DECISION
            groups[layer].append(exp)
        
        return groups
    
    def _sample_batch(self, experiences: List[Experience]) -> List[Experience]:
        """采样批次"""
        if len(experiences) <= self.batch_size:
            return experiences
        return random.sample(experiences, self.batch_size)
    
    def _update_layer_policies(
        self,
        layer: LayerType,
        experiences: List[Experience]
    ) -> List[UpdateResult]:
        """更新单层所有智能体的策略"""
        results = []
        
        # 按智能体分组
        agent_experiences: Dict[str, List[Experience]] = {}
        for exp in experiences:
            if exp.agent_id not in agent_experiences:
                agent_experiences[exp.agent_id] = []
            agent_experiences[exp.agent_id].append(exp)
        
        # 更新每个智能体
        for agent_id, agent_exp in agent_experiences.items():
            if agent_id in self._policies:
                result = self._update_agent_policy(
                    layer, agent_id, agent_exp
                )
                if result:
                    results.append(result)
                    self._update_history.append(result)
        
        return results
    
    def _update_agent_policy(
        self,
        layer: LayerType,
        agent_id: str,
        experiences: List[Experience]
    ) -> Optional[UpdateResult]:
        """更新单个智能体策略"""
        policy = self._policies.get(agent_id)
        if not policy:
            return None
        
        # 保存旧参数
        old_params = dict(policy.parameters)
        
        # 计算优势
        advantages = self.advantage_estimator.compute_advantages(experiences)
        advantages = self.advantage_estimator.normalize_advantages(advantages)
        
        if not advantages:
            return None
        
        # 计算策略梯度
        gradients = self._compute_policy_gradient(
            policy, experiences, advantages
        )
        
        # 应用更新
        total_loss = 0.0
        for param_name, gradient in gradients.items():
            update = self.optimizer.compute_update(gradient, param_name)
            
            if param_name in policy.parameters:
                policy.parameters[param_name] += update
            else:
                policy.parameters[param_name] = update
            
            total_loss += abs(gradient)
        
        # 更新动作偏好
        self._update_action_preferences(policy, experiences, advantages)
        
        policy.last_updated = datetime.now()
        
        return UpdateResult(
            layer=layer,
            agent_id=agent_id,
            old_params=old_params,
            new_params=dict(policy.parameters),
            loss=total_loss / len(gradients) if gradients else 0.0
        )
    
    def _compute_policy_gradient(
        self,
        policy: Policy,
        experiences: List[Experience],
        advantages: List[float]
    ) -> Dict[str, float]:
        """
        计算策略梯度
        
        使用PPO的裁剪目标：
        L = min(r_t * A_t, clip(r_t, 1-ε, 1+ε) * A_t)
        其中 r_t = π(a|s) / π_old(a|s)
        """
        gradients = {}
        
        for i, (exp, adv) in enumerate(zip(experiences, advantages)):
            if exp.action is None:
                continue
            
            action_name = exp.action.value if hasattr(exp.action, 'value') else str(exp.action)
            
            # 获取动作概率（简化：使用偏好值）
            current_prob = policy.action_preferences.get(action_name, 0.5)
            
            # 计算比率（简化实现）
            ratio = 1.0 + adv * 0.1  # 简化的比率估计
            
            # PPO裁剪
            clipped_ratio = max(
                1 - self.clip_epsilon,
                min(1 + self.clip_epsilon, ratio)
            )
            
            # 选择较小值（悲观估计）
            objective = min(ratio * adv, clipped_ratio * adv)
            
            # 累积梯度
            grad_key = f"action_{action_name}"
            gradients[grad_key] = gradients.get(grad_key, 0.0) + objective
        
        # 平均
        if experiences:
            for key in gradients:
                gradients[key] /= len(experiences)
        
        return gradients
    
    def _update_action_preferences(
        self,
        policy: Policy,
        experiences: List[Experience],
        advantages: List[float]
    ):
        """更新动作偏好"""
        action_updates: Dict[str, List[float]] = {}
        
        for exp, adv in zip(experiences, advantages):
            if exp.action is None:
                continue
            
            action_name = exp.action.value if hasattr(exp.action, 'value') else str(exp.action)
            
            if action_name not in action_updates:
                action_updates[action_name] = []
            action_updates[action_name].append(adv)
        
        # 更新偏好
        for action_name, advs in action_updates.items():
            avg_adv = sum(advs) / len(advs)
            current = policy.action_preferences.get(action_name, 0.5)
            
            # 使用软更新
            updated = current + policy.learning_rate * avg_adv * 0.1
            
            # 限制范围
            policy.action_preferences[action_name] = max(0.1, min(0.9, updated))
    
    # ==================== 探索率调整 ====================
    
    def decay_exploration(
        self,
        agent_id: str,
        decay_rate: float = 0.995,
        min_rate: float = 0.01
    ):
        """衰减探索率"""
        if agent_id in self._policies:
            policy = self._policies[agent_id]
            policy.exploration_rate = max(
                min_rate,
                policy.exploration_rate * decay_rate
            )
    
    def set_exploration_rate(self, agent_id: str, rate: float):
        """设置探索率"""
        if agent_id in self._policies:
            self._policies[agent_id].exploration_rate = max(0.0, min(1.0, rate))
    
    # ==================== 统计 ====================
    
    def get_update_stats(self) -> Dict[str, Any]:
        """获取更新统计"""
        if not self._update_history:
            return {"total_updates": 0}
        
        stats = {
            "total_updates": len(self._update_history),
            "by_layer": {},
            "avg_loss": sum(u.loss for u in self._update_history) / len(self._update_history)
        }
        
        for layer in LayerType:
            layer_updates = [u for u in self._update_history if u.layer == layer]
            if layer_updates:
                stats["by_layer"][layer.name] = {
                    "count": len(layer_updates),
                    "avg_loss": sum(u.loss for u in layer_updates) / len(layer_updates)
                }
        
        return stats
    
    def reset(self):
        """重置更新器"""
        self.optimizer.reset()
        self._update_history.clear()
