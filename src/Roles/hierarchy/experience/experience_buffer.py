"""
多层强化学习智能体系统 - 经验缓冲区
存储和采样强化学习经验
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import random
import math
import heapq

from ..types import Experience, LayerType


@dataclass
class BufferStats:
    """缓冲区统计"""
    total_added: int = 0
    total_sampled: int = 0
    current_size: int = 0
    max_size: int = 0
    avg_reward: float = 0.0
    by_layer: Dict[int, int] = field(default_factory=dict)


class ExperienceBuffer:
    """
    经验回放缓冲区
    存储经验并支持随机采样
    """
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._buffer: List[Experience] = []
        self._position: int = 0  # 循环缓冲区位置
        
        # 统计
        self._stats = BufferStats(max_size=max_size)
    
    def add(self, experience: Experience):
        """添加经验"""
        if len(self._buffer) < self.max_size:
            self._buffer.append(experience)
        else:
            # 循环覆盖
            self._buffer[self._position] = experience
        
        self._position = (self._position + 1) % self.max_size
        
        # 更新统计
        self._stats.total_added += 1
        self._stats.current_size = len(self._buffer)
        self._update_layer_stats(experience)
    
    def add_batch(self, experiences: List[Experience]):
        """批量添加经验"""
        for exp in experiences:
            self.add(exp)
    
    def sample(self, batch_size: int) -> List[Experience]:
        """随机采样"""
        if len(self._buffer) < batch_size:
            return self._buffer.copy()
        
        sampled = random.sample(self._buffer, batch_size)
        self._stats.total_sampled += batch_size
        return sampled
    
    def sample_by_layer(
        self,
        layer: LayerType,
        batch_size: int
    ) -> List[Experience]:
        """按层采样"""
        layer_experiences = [
            exp for exp in self._buffer
            if exp.layer == layer.value
        ]
        
        if len(layer_experiences) < batch_size:
            return layer_experiences
        
        return random.sample(layer_experiences, batch_size)
    
    def get_recent(self, n: int) -> List[Experience]:
        """获取最近的n条经验"""
        return self._buffer[-n:]
    
    def clear(self):
        """清空缓冲区"""
        self._buffer.clear()
        self._position = 0
        self._stats = BufferStats(max_size=self.max_size)
    
    @property
    def size(self) -> int:
        """当前大小"""
        return len(self._buffer)
    
    @property
    def is_full(self) -> bool:
        """是否已满"""
        return len(self._buffer) >= self.max_size
    
    def _update_layer_stats(self, experience: Experience):
        """更新层统计"""
        layer = experience.layer
        self._stats.by_layer[layer] = self._stats.by_layer.get(layer, 0) + 1
        
        # 更新平均奖励
        total_reward = self._stats.avg_reward * (self._stats.total_added - 1)
        total_reward += experience.reward
        self._stats.avg_reward = total_reward / self._stats.total_added
    
    def get_stats(self) -> BufferStats:
        """获取统计信息"""
        return self._stats


class PrioritizedExperienceBuffer(ExperienceBuffer):
    """
    优先经验回放缓冲区
    基于TD误差进行优先采样
    """
    
    def __init__(
        self,
        max_size: int = 10000,
        alpha: float = 0.6,
        beta: float = 0.4,
        beta_increment: float = 0.001
    ):
        super().__init__(max_size)
        
        # PER参数
        self.alpha = alpha  # 优先级指数
        self.beta = beta    # 重要性采样指数
        self.beta_increment = beta_increment
        
        # 优先级存储
        self._priorities: List[float] = []
        self._max_priority: float = 1.0
        
        # Sum tree for efficient sampling
        self._tree_capacity = 1
        while self._tree_capacity < max_size:
            self._tree_capacity *= 2
        self._sum_tree: List[float] = [0.0] * (2 * self._tree_capacity)
        self._min_tree: List[float] = [float('inf')] * (2 * self._tree_capacity)
    
    def add(self, experience: Experience, priority: Optional[float] = None):
        """添加经验（带优先级）"""
        if priority is None:
            priority = self._max_priority
        
        # 添加到缓冲区
        if len(self._buffer) < self.max_size:
            self._buffer.append(experience)
            self._priorities.append(priority)
        else:
            self._buffer[self._position] = experience
            self._priorities[self._position] = priority
        
        # 更新优先级树
        tree_idx = self._position + self._tree_capacity
        self._update_tree(tree_idx, priority ** self.alpha)
        
        self._position = (self._position + 1) % self.max_size
        self._max_priority = max(self._max_priority, priority)
        
        # 更新统计
        self._stats.total_added += 1
        self._stats.current_size = len(self._buffer)
    
    def sample(
        self,
        batch_size: int
    ) -> Tuple[List[Experience], List[int], List[float]]:
        """
        优先采样
        
        Returns:
            experiences: 采样的经验
            indices: 对应的索引（用于更新优先级）
            weights: 重要性采样权重
        """
        if len(self._buffer) < batch_size:
            indices = list(range(len(self._buffer)))
            weights = [1.0] * len(self._buffer)
            return self._buffer.copy(), indices, weights
        
        # 计算采样区间
        total_priority = self._sum_tree[1]
        segment = total_priority / batch_size
        
        indices = []
        priorities = []
        
        # 分层采样
        for i in range(batch_size):
            low = segment * i
            high = segment * (i + 1)
            value = random.uniform(low, high)
            
            idx = self._retrieve(value)
            indices.append(idx)
            priorities.append(self._sum_tree[idx + self._tree_capacity])
        
        # 计算重要性采样权重
        min_priority = self._min_tree[1]
        if min_priority == float('inf'):
            min_priority = 0.01
        
        max_weight = (len(self._buffer) * min_priority) ** (-self.beta)
        
        weights = []
        for priority in priorities:
            if priority == 0:
                priority = 0.01
            weight = (len(self._buffer) * priority) ** (-self.beta) / max_weight
            weights.append(weight)
        
        # 增加beta
        self.beta = min(1.0, self.beta + self.beta_increment)
        
        experiences = [self._buffer[idx] for idx in indices]
        self._stats.total_sampled += batch_size
        
        return experiences, indices, weights
    
    def update_priorities(self, indices: List[int], priorities: List[float]):
        """更新优先级"""
        for idx, priority in zip(indices, priorities):
            if 0 <= idx < len(self._buffer):
                self._priorities[idx] = priority
                self._max_priority = max(self._max_priority, priority)
                
                tree_idx = idx + self._tree_capacity
                self._update_tree(tree_idx, priority ** self.alpha)
    
    def _update_tree(self, idx: int, priority: float):
        """更新优先级树"""
        self._sum_tree[idx] = priority
        self._min_tree[idx] = priority
        
        # 向上传播
        while idx > 1:
            idx //= 2
            left = idx * 2
            right = idx * 2 + 1
            self._sum_tree[idx] = self._sum_tree[left] + self._sum_tree[right]
            self._min_tree[idx] = min(self._min_tree[left], self._min_tree[right])
    
    def _retrieve(self, value: float) -> int:
        """检索经验索引"""
        idx = 1
        
        while idx < self._tree_capacity:
            left = idx * 2
            right = idx * 2 + 1
            
            if value <= self._sum_tree[left]:
                idx = left
            else:
                value -= self._sum_tree[left]
                idx = right
        
        return idx - self._tree_capacity
