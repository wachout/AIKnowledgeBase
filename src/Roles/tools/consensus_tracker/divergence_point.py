"""
共识追踪系统 - 分歧点类
包含分歧点数据结构和冲突解决策略枚举。
"""

from typing import Dict, Any, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from .types import ConsensusType, ConflictSeverity


class ConflictResolutionStrategy(Enum):
    """冲突解决策略"""
    DEBATE = "debate"
    MEDIATION = "mediation"
    VOTING = "voting"
    COMPROMISE = "compromise"
    EXPERT_REVIEW = "expert_review"
    DATA_DRIVEN = "data_driven"
    POSTPONE = "postpone"


@dataclass
class DivergencePoint:
    """增强版分歧点类"""

    content: str
    consensus_type: ConsensusType = ConsensusType.AUXILIARY
    proponents: Dict[str, str] = field(default_factory=dict)
    intensity: float = 0.0
    severity: ConflictSeverity = ConflictSeverity.LOW
    created_at: str = None
    last_updated: str = None
    discussion_history: List[Dict[str, Any]] = field(default_factory=list)
    potential_resolutions: List[str] = field(default_factory=list)
    related_consensus: List[str] = field(default_factory=list)

    round_created: int = 1
    resolution_attempts: int = 0
    last_resolution_attempt_at: str = None
    opposing_positions: List[Tuple[str, str, str, str]] = field(default_factory=list)
    requires_debate: bool = False
    debate_suggested_by: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.last_updated is None:
            self.last_updated = self.created_at
        self._update_intensity()

    def add_proponent(self, proponent: str, position: str) -> bool:
        if proponent not in self.proponents:
            self.proponents[proponent] = position
            self.last_updated = datetime.now().isoformat()
            self._update_intensity()
            self._detect_opposing_positions()
            return True
        return False

    def update_position(self, proponent: str, new_position: str) -> bool:
        if proponent in self.proponents:
            self.proponents[proponent] = new_position
            self.last_updated = datetime.now().isoformat()
            self._update_intensity()
            self._detect_opposing_positions()
            return True
        return False

    def add_discussion(self, discussion: str, speaker: str) -> None:
        self.discussion_history.append({
            "content": discussion,
            "speaker": speaker,
            "timestamp": datetime.now().isoformat()
        })
        self._update_intensity()

    def add_potential_resolution(self, resolution: str) -> bool:
        if resolution and resolution not in self.potential_resolutions:
            self.potential_resolutions.append(resolution)
            return True
        return False

    def mark_for_debate(self, suggested_by: str, reason: str) -> None:
        if suggested_by not in self.debate_suggested_by:
            self.debate_suggested_by.append(suggested_by)
        self.requires_debate = True
        self.severity = ConflictSeverity.HIGH
        self.discussion_history.append({
            "content": f"建议深度辩论: {reason}",
            "speaker": suggested_by,
            "timestamp": datetime.now().isoformat(),
            "type": "debate_suggestion"
        })

    def record_resolution_attempt(self, method: str, result: str) -> None:
        self.resolution_attempts += 1
        self.last_resolution_attempt_at = datetime.now().isoformat()
        self.discussion_history.append({
            "content": f"解决尝试 #{self.resolution_attempts}: {method}",
            "result": result,
            "timestamp": datetime.now().isoformat()
        })

    def _detect_opposing_positions(self) -> None:
        self.opposing_positions.clear()
        positions = list(self.proponents.items())

        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                expert1, pos1 = positions[i]
                expert2, pos2 = positions[j]
                if pos1.strip().lower() != pos2.strip().lower():
                    self.opposing_positions.append((expert1, pos1, expert2, pos2))

        if len(self.opposing_positions) >= 3:
            self.severity = ConflictSeverity.CRITICAL
        elif len(self.opposing_positions) >= 2:
            self.severity = ConflictSeverity.HIGH
        elif self.opposing_positions:
            self.severity = ConflictSeverity.MEDIUM
        else:
            self.severity = ConflictSeverity.LOW

    def _update_intensity(self) -> None:
        if not self.proponents:
            self.intensity = 0.0
            return

        num_positions = len(set(self.proponents.values()))
        num_participants = len(self.proponents)

        position_diversity = num_positions / num_participants if num_participants > 0 else 0
        participation_factor = min(1.0, num_participants / 5.0)
        opposition_factor = min(1.0, len(self.opposing_positions) / 3.0)
        resolution_difficulty = min(1.0, self.resolution_attempts / 5.0)

        self.intensity = (
            position_diversity * 0.35 +
            participation_factor * 0.25 +
            opposition_factor * 0.25 +
            resolution_difficulty * 0.15
        )
        self.intensity = min(1.0, self.intensity)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "consensus_type": self.consensus_type.value,
            "proponents": self.proponents,
            "intensity": self.intensity,
            "severity": self.severity.value,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "discussion_history": self.discussion_history,
            "potential_resolutions": self.potential_resolutions,
            "related_consensus": self.related_consensus,
            "round_created": self.round_created,
            "resolution_attempts": self.resolution_attempts,
            "opposing_positions": self.opposing_positions,
            "requires_debate": self.requires_debate
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DivergencePoint':
        consensus_type_str = data.get("consensus_type", "auxiliary")
        severity_str = data.get("severity", "low")
        
        return cls(
            content=data.get("content", ""),
            consensus_type=ConsensusType(consensus_type_str),
            proponents=data.get("proponents", {}),
            intensity=data.get("intensity", 0.0),
            severity=ConflictSeverity(severity_str),
            created_at=data.get("created_at"),
            last_updated=data.get("last_updated"),
            discussion_history=data.get("discussion_history", []),
            potential_resolutions=data.get("potential_resolutions", []),
            related_consensus=data.get("related_consensus", []),
            round_created=data.get("round_created", 1),
            resolution_attempts=data.get("resolution_attempts", 0),
            last_resolution_attempt_at=data.get("last_resolution_attempt_at"),
            opposing_positions=[tuple(pos) for pos in data.get("opposing_positions", [])],
            requires_debate=data.get("requires_debate", False),
            debate_suggested_by=data.get("debate_suggested_by", [])
        )


@dataclass
class ConflictResolution:
    """冲突解决记录"""
    divergence_id: str
    strategy: ConflictResolutionStrategy
    suggested_approach: str
    participants_involved: List[str]
    expected_outcome: str
    created_at: str = None
    executed: bool = False
    execution_result: str = None
    executed_at: str = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "divergence_id": self.divergence_id,
            "strategy": self.strategy.value,
            "suggested_approach": self.suggested_approach,
            "participants_involved": self.participants_involved,
            "expected_outcome": self.expected_outcome,
            "created_at": self.created_at,
            "executed": self.executed,
            "execution_result": self.execution_result,
            "executed_at": self.executed_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConflictResolution':
        return cls(
            divergence_id=data.get("divergence_id", ""),
            strategy=ConflictResolutionStrategy(data.get("strategy", "debate")),
            suggested_approach=data.get("suggested_approach", ""),
            participants_involved=data.get("participants_involved", []),
            expected_outcome=data.get("expected_outcome", ""),
            created_at=data.get("created_at"),
            executed=data.get("executed", False),
            execution_result=data.get("execution_result"),
            executed_at=data.get("executed_at")
        )
