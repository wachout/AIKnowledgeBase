"""
共识追踪系统 - 时间衰减模型
包含自适应衰减算法，支持多种衰减模式、激活恢复、峰值保护等特性。
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass
import math

from .types import ConsensusType

if TYPE_CHECKING:
    from .consensus_point import ConsensusPoint


@dataclass
class DecayHistory:
    """衰减历史记录"""
    timestamp: str
    strength: float
    decay_factor: float
    activation_event: Optional[str] = None
    round_number: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "strength": self.strength,
            "decay_factor": self.decay_factor,
            "activation_event": self.activation_event,
            "round_number": self.round_number
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DecayHistory':
        return cls(
            timestamp=data.get("timestamp", ""),
            strength=data.get("strength", 0.0),
            decay_factor=data.get("decay_factor", 1.0),
            activation_event=data.get("activation_event"),
            round_number=data.get("round_number", 0)
        )


class AdaptiveDecayModel:
    """
    自适应时间衰减模型
    
    支持多种衰减模式，考虑激活效应、历史峰值保护和证据加成。
    """
    
    # 衰减模式函数
    DECAY_MODES = {
        "exponential": lambda t, r: math.pow(r, t) if t >= 0 else 1.0,
        "logarithmic": lambda t, r: 1 / (1 + math.log(1 + max(0, t) * (1-r))) if t >= 0 else 1.0,
        "inverse_sqrt": lambda t, r: 1 / math.sqrt(1 + max(0, t) * (1-r)) if t >= 0 else 1.0,
        "linear": lambda t, r: max(0, 1 - t * (1-r)) if t >= 0 else 1.0
    }
    
    # 不同共识类型的默认衰减模式
    TYPE_DECAY_MODES = {
        ConsensusType.CORE: "logarithmic",       # 核心共识衰减慢
        ConsensusType.STRATEGIC: "logarithmic",  # 战略共识衰减慢
        ConsensusType.TECHNICAL: "exponential",  # 技术共识衰减中等
        ConsensusType.TACTICAL: "exponential",   # 战术共识衰减中等
        ConsensusType.PROCEDURAL: "linear",      # 程序共识衰减快
        ConsensusType.AUXILIARY: "linear"        # 辅助共识衰减快
    }
    
    # 不同共识类型的基础衰减率
    TYPE_BASE_DECAY_RATES = {
        ConsensusType.CORE: 0.98,
        ConsensusType.STRATEGIC: 0.95,
        ConsensusType.TECHNICAL: 0.92,
        ConsensusType.TACTICAL: 0.90,
        ConsensusType.PROCEDURAL: 0.88,
        ConsensusType.AUXILIARY: 0.85
    }
    
    # 激活恢复因子
    ACTIVATION_RECOVERY_FACTOR = 0.3
    
    # 峰值保护比例（历史峰值的最小保留比例）
    PEAK_PROTECTION_RATIO = 0.4
    
    # 证据加成上限
    EVIDENCE_BONUS_CAP = 0.25
    
    # 验证加成上限
    VERIFICATION_BONUS_CAP = 0.2
    
    def __init__(self):
        self.decay_histories: Dict[str, List[DecayHistory]] = {}
    
    def get_decay_mode(self, consensus_type: ConsensusType) -> str:
        """获取共识类型对应的衰减模式"""
        return self.TYPE_DECAY_MODES.get(consensus_type, "exponential")
    
    def get_base_decay_rate(self, consensus_type: ConsensusType) -> float:
        """获取共识类型对应的基础衰减率"""
        return self.TYPE_BASE_DECAY_RATES.get(consensus_type, 0.90)
    
    def calculate_adaptive_decay(self, 
                                  consensus: 'ConsensusPoint',
                                  current_round: int,
                                  decay_history: List[DecayHistory] = None) -> float:
        """
        计算自适应衰减因子
        
        综合考虑：
        1. 基础衰减（根据共识类型选择模式和衰减率）
        2. 激活恢复（最近验证/支持时恢复强度）
        3. 历史峰值保护（不低于峰值的某个比例）
        4. 证据加成（有充分证据时减缓衰减）
        5. 验证加成（多次验证时减缓衰减）
        
        Returns:
            float: 衰减后的强度因子 (0.0 - 1.0)
        """
        if decay_history is None:
            decay_history = []
        
        # 1. 计算基础衰减
        rounds_since_creation = max(0, current_round - consensus.round_created)
        if rounds_since_creation == 0:
            return 1.0
        
        decay_mode = self.get_decay_mode(consensus.consensus_type)
        decay_rate = self.get_base_decay_rate(consensus.consensus_type)
        decay_func = self.DECAY_MODES.get(decay_mode, self.DECAY_MODES["exponential"])
        
        # 限制最大衰减轮次以避免数值问题
        effective_rounds = min(rounds_since_creation, 30)
        base_decay = decay_func(effective_rounds, decay_rate)
        
        # 2. 激活恢复
        activation_bonus = 0.0
        last_activation = getattr(consensus, 'last_activation_round', 0)
        if last_activation > 0:
            rounds_since_activation = max(0, current_round - last_activation)
            if rounds_since_activation <= 3:  # 最近3轮内有激活
                # 激活越近，恢复越多
                activation_bonus = self.ACTIVATION_RECOVERY_FACTOR * (1 - rounds_since_activation / 3)
        
        # 3. 历史峰值保护
        peak_strength = getattr(consensus, 'peak_strength', consensus.strength)
        if peak_strength > 0:
            protected_minimum = peak_strength * self.PEAK_PROTECTION_RATIO
            # 确保衰减后不低于保护最小值
            if base_decay < protected_minimum:
                base_decay = max(base_decay, protected_minimum)
        
        # 4. 证据加成
        evidence_bonus = 0.0
        if len(consensus.evidence) > 0:
            evidence_bonus = min(self.EVIDENCE_BONUS_CAP, len(consensus.evidence) * 0.06)
        
        # 5. 验证加成
        verification_bonus = 0.0
        if consensus.verification_count > 0:
            verification_bonus = min(self.VERIFICATION_BONUS_CAP, 
                                     consensus.verification_count * 0.04)
        
        # 综合计算最终衰减因子
        final_decay = base_decay + activation_bonus + evidence_bonus + verification_bonus
        final_decay = max(0.0, min(1.0, final_decay))
        
        # 记录衰减历史
        self._record_decay_history(
            consensus_id=getattr(consensus, 'id', consensus.content[:20]),
            current_round=current_round,
            strength=consensus.strength,
            decay_factor=final_decay,
            activation_event="verification" if consensus.verification_count > 0 else None
        )
        
        return final_decay
    
    def _record_decay_history(self, consensus_id: str, current_round: int,
                              strength: float, decay_factor: float,
                              activation_event: Optional[str] = None) -> None:
        """记录衰减历史"""
        if consensus_id not in self.decay_histories:
            self.decay_histories[consensus_id] = []
        
        history_entry = DecayHistory(
            timestamp=datetime.now().isoformat(),
            strength=strength,
            decay_factor=decay_factor,
            activation_event=activation_event,
            round_number=current_round
        )
        
        self.decay_histories[consensus_id].append(history_entry)
        
        # 保留最近20条历史
        if len(self.decay_histories[consensus_id]) > 20:
            self.decay_histories[consensus_id] = self.decay_histories[consensus_id][-20:]
    
    def get_decay_history(self, consensus_id: str) -> List[DecayHistory]:
        """获取共识的衰减历史"""
        return self.decay_histories.get(consensus_id, [])
    
    def calculate_decay_trend(self, consensus_id: str) -> str:
        """分析衰减趋势"""
        history = self.get_decay_history(consensus_id)
        if len(history) < 3:
            return "stable"
        
        recent_factors = [h.decay_factor for h in history[-5:]]
        if len(recent_factors) < 2:
            return "stable"
        
        avg_recent = sum(recent_factors[-2:]) / 2
        avg_earlier = sum(recent_factors[:-2]) / max(1, len(recent_factors) - 2)
        
        if avg_recent > avg_earlier * 1.1:
            return "recovering"  # 恢复中
        elif avg_recent < avg_earlier * 0.9:
            return "declining"   # 衰减中
        return "stable"          # 稳定
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "decay_histories": {
                k: [h.to_dict() for h in v] 
                for k, v in self.decay_histories.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AdaptiveDecayModel':
        """反序列化"""
        model = cls()
        histories_data = data.get("decay_histories", {})
        for consensus_id, history_list in histories_data.items():
            model.decay_histories[consensus_id] = [
                DecayHistory.from_dict(h) for h in history_list
            ]
        return model
