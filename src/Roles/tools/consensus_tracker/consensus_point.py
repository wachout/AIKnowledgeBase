"""
共识追踪系统 - 共识点类
包含共识点的数据结构和相关操作方法。
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
import math

from .types import ConsensusType, ConsensusPriority


# 衰减模型常量（避免循环导入）
TYPE_DECAY_MODES = {
    ConsensusType.CORE: "logarithmic",
    ConsensusType.STRATEGIC: "logarithmic",
    ConsensusType.TECHNICAL: "exponential",
    ConsensusType.TACTICAL: "exponential",
    ConsensusType.PROCEDURAL: "linear",
    ConsensusType.AUXILIARY: "linear"
}

PEAK_PROTECTION_RATIO = 0.4


@dataclass
class ConsensusPoint:
    """增强版共识点类"""

    content: str
    consensus_type: ConsensusType = ConsensusType.AUXILIARY
    priority: ConsensusPriority = ConsensusPriority.MEDIUM
    supporters: List[str] = field(default_factory=list)
    strength: float = 0.0
    created_at: str = None
    last_updated: str = None
    evidence: List[str] = field(default_factory=list)
    related_divergences: List[str] = field(default_factory=list)

    topic_keywords: List[str] = field(default_factory=list)
    round_created: int = 1
    verification_count: int = 0
    last_verified_at: str = None
    importance_score: float = 0.5
    stability_score: float = 0.5
    
    # Phase 1 新增字段: 激活和峰值保护
    peak_strength: float = 0.0              # 历史峰值
    activation_history: List[str] = field(default_factory=list)  # 激活历史
    last_activation_round: int = 0          # 最后激活轮次
    decay_mode: str = "exponential"         # 衰减模式
    consensus_id: str = None                # 共识ID

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.last_updated is None:
            self.last_updated = self.created_at
        # 初始化峰值为当前强度
        if self.peak_strength == 0.0 and self.strength > 0:
            self.peak_strength = self.strength
        # 根据共识类型设置默认衰减模式
        if self.decay_mode == "exponential":
            self.decay_mode = TYPE_DECAY_MODES.get(
                self.consensus_type, "exponential"
            )

    def add_supporter(self, supporter: str, round_number: int = 0) -> bool:
        if supporter not in self.supporters:
            self.supporters.append(supporter)
            self.last_updated = datetime.now().isoformat()
            self._update_strength()
            # 新支持者触发激活
            if round_number > 0:
                self.activate("new_supporter", round_number)
            return True
        return False

    def remove_supporter(self, supporter: str) -> bool:
        if supporter in self.supporters:
            self.supporters.remove(supporter)
            self.last_updated = datetime.now().isoformat()
            self._update_strength()
            return True
        return False

    def add_evidence(self, evidence: str, round_number: int = 0) -> bool:
        if evidence and evidence not in self.evidence:
            self.evidence.append(evidence)
            self.last_updated = datetime.now().isoformat()
            self._update_strength()
            # 新证据触发激活
            if round_number > 0:
                self.activate("new_evidence", round_number)
            return True
        return False

    def verify(self, round_number: int = 0) -> None:
        self.verification_count += 1
        self.last_verified_at = datetime.now().isoformat()
        self._update_strength()
        # 验证触发激活
        if round_number > 0:
            self.activate("verification", round_number)
    
    def activate(self, event_type: str, round_number: int) -> None:
        """
        激活共识（验证、新支持者、新证据时调用）
        
        激活会影响时间衰减计算，最近激活的共识衰减较慢。
        
        Args:
            event_type: 激活事件类型 (verification/new_supporter/new_evidence/reinforcement)
            round_number: 当前轮次
        """
        self.last_activation_round = round_number
        activation_record = f"{event_type}@round_{round_number}@{datetime.now().isoformat()}"
        self.activation_history.append(activation_record)
        
        # 保留最近10条激活记录
        if len(self.activation_history) > 10:
            self.activation_history = self.activation_history[-10:]
        
        self.last_updated = datetime.now().isoformat()
    
    def get_protected_minimum(self) -> float:
        """
        获取受保护的最小强度（基于历史峰值）
        
        共识的强度不应该低于历史峰值的某个比例，
        以保护曾经建立的强共识不会完全衰减。
        
        Returns:
            float: 受保护的最小强度
        """
        return self.peak_strength * PEAK_PROTECTION_RATIO
    
    def get_activation_frequency(self, recent_rounds: int = 5) -> float:
        """
        获取最近N轮的激活频率
        
        Args:
            recent_rounds: 考察的最近轮次数
            
        Returns:
            float: 激活频率 (0.0 - 1.0)
        """
        if not self.activation_history or recent_rounds <= 0:
            return 0.0
        
        # 解析激活记录中的轮次
        recent_activations = 0
        for record in self.activation_history[-recent_rounds:]:
            try:
                parts = record.split("@")
                if len(parts) >= 2 and parts[1].startswith("round_"):
                    recent_activations += 1
            except (IndexError, ValueError):
                continue
        
        return recent_activations / recent_rounds

    def _update_strength(self) -> None:
        if not self.supporters:
            self.strength = 0.0
            return

        supporter_factor = min(1.0, len(self.supporters) / 5.0)
        evidence_factor = min(1.0, len(self.evidence) / 3.0)
        verification_factor = min(1.0, self.verification_count / 5.0)
        stability_factor = self.stability_score
        importance_factor = self.importance_score

        self.strength = (
            supporter_factor * 0.40 +
            evidence_factor * 0.25 +
            verification_factor * 0.15 +
            stability_factor * 0.10 +
            importance_factor * 0.10
        )
        self.strength = min(1.0, self.strength)
        
        # 更新峰值
        if self.strength > self.peak_strength:
            self.peak_strength = self.strength

    def calculate_time_decay(self, current_round: int, decay_factor: float = 0.95) -> float:
        rounds_since_creation = current_round - self.round_created
        if rounds_since_creation <= 0:
            return 1.0
        return math.pow(decay_factor, min(rounds_since_creation, 20))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "consensus_type": self.consensus_type.value,
            "priority": self.priority.value,
            "supporters": self.supporters,
            "strength": self.strength,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "evidence": self.evidence,
            "related_divergences": self.related_divergences,
            "topic_keywords": self.topic_keywords,
            "round_created": self.round_created,
            "verification_count": self.verification_count,
            "importance_score": self.importance_score,
            "stability_score": self.stability_score,
            # Phase 1 新增字段
            "peak_strength": self.peak_strength,
            "activation_history": self.activation_history,
            "last_activation_round": self.last_activation_round,
            "decay_mode": self.decay_mode,
            "consensus_id": self.consensus_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConsensusPoint':
        consensus_type_str = data.get("consensus_type", "auxiliary")
        priority_value = data.get("priority", 3)
        
        return cls(
            content=data.get("content", ""),
            consensus_type=ConsensusType(consensus_type_str),
            priority=ConsensusPriority(priority_value),
            supporters=data.get("supporters", []),
            strength=data.get("strength", 0.0),
            created_at=data.get("created_at"),
            last_updated=data.get("last_updated"),
            evidence=data.get("evidence", []),
            related_divergences=data.get("related_divergences", []),
            topic_keywords=data.get("topic_keywords", []),
            round_created=data.get("round_created", 1),
            verification_count=data.get("verification_count", 0),
            last_verified_at=data.get("last_verified_at"),
            importance_score=data.get("importance_score", 0.5),
            stability_score=data.get("stability_score", 0.5),
            peak_strength=data.get("peak_strength", 0.0),
            activation_history=data.get("activation_history", []),
            last_activation_round=data.get("last_activation_round", 0),
            decay_mode=data.get("decay_mode", "exponential"),
            consensus_id=data.get("consensus_id")
        )
