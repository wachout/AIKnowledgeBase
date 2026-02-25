"""
共识追踪系统 - 动态权重计算
包含讨论阶段检测、专家权威度评分和动态权重计算等功能。
"""

from typing import Dict, Any, List, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from .types import ConsensusType

if TYPE_CHECKING:
    from .consensus_point import ConsensusPoint


class DiscussionPhase(Enum):
    """
    讨论阶段
    
    不同阶段对不同类型共识的权重应该有所不同。
    """
    EXPLORATION = "exploration"        # 探索阶段：广泛收集观点
    DEEPENING = "deepening"            # 深化阶段：深入讨论核心问题
    CONVERGENCE = "convergence"        # 收敛阶段：归纳共识
    FINALIZATION = "finalization"      # 定稿阶段：确认最终结论
    
    @classmethod
    def detect_from_progress(cls, current_round: int, total_rounds: int,
                              consensus_level: float) -> 'DiscussionPhase':
        """
        根据讨论进度自动检测当前阶段
        
        Args:
            current_round: 当前轮次
            total_rounds: 总轮次
            consensus_level: 当前共识水平
            
        Returns:
            DiscussionPhase: 检测到的阶段
        """
        if total_rounds <= 0:
            return cls.EXPLORATION
        
        progress = current_round / total_rounds
        
        # 基于进度和共识水平的综合判断
        if progress < 0.25:
            return cls.EXPLORATION
        elif progress < 0.5:
            if consensus_level >= 0.6:
                return cls.CONVERGENCE  # 共识形成较快，跳过深化
            return cls.DEEPENING
        elif progress < 0.8:
            if consensus_level >= 0.7:
                return cls.FINALIZATION  # 已达到较高共识
            return cls.CONVERGENCE
        else:
            return cls.FINALIZATION


@dataclass
class ExpertAuthorityScore:
    """
    专家权威度评分
    
    用于动态调整专家发言对共识的影响权重。
    """
    expert_id: str
    domain_expertise: float = 0.5       # 领域专业度 (0.0-1.0)
    participation_quality: float = 0.5   # 参与质量 (0.0-1.0)
    consensus_track_record: float = 0.5  # 历史共识达成率 (0.0-1.0)
    influence_score: float = 0.5         # 影响力得分 (0.0-1.0)
    recent_contribution_count: int = 0   # 最近贡献次数
    last_updated: str = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now().isoformat()
    
    def get_overall_authority(self) -> float:
        """
        计算综合权威度
        
        Returns:
            float: 综合权威度 (0.0-1.0)
        """
        return (
            self.domain_expertise * 0.35 +
            self.participation_quality * 0.25 +
            self.consensus_track_record * 0.25 +
            self.influence_score * 0.15
        )
    
    def update_from_contribution(self, contribution_quality: float,
                                  led_to_consensus: bool) -> None:
        """
        根据贡献更新权威度
        
        Args:
            contribution_quality: 贡献质量 (0.0-1.0)
            led_to_consensus: 是否导向了共识
        """
        # 更新参与质量 (移动平均)
        alpha = 0.2
        self.participation_quality = (
            (1 - alpha) * self.participation_quality + 
            alpha * contribution_quality
        )
        
        # 更新共识达成率
        if led_to_consensus:
            self.consensus_track_record = min(1.0, 
                self.consensus_track_record + 0.05)
        else:
            self.consensus_track_record = max(0.0,
                self.consensus_track_record - 0.02)
        
        self.recent_contribution_count += 1
        self.last_updated = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "expert_id": self.expert_id,
            "domain_expertise": self.domain_expertise,
            "participation_quality": self.participation_quality,
            "consensus_track_record": self.consensus_track_record,
            "influence_score": self.influence_score,
            "recent_contribution_count": self.recent_contribution_count,
            "last_updated": self.last_updated
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExpertAuthorityScore':
        return cls(
            expert_id=data.get("expert_id", ""),
            domain_expertise=data.get("domain_expertise", 0.5),
            participation_quality=data.get("participation_quality", 0.5),
            consensus_track_record=data.get("consensus_track_record", 0.5),
            influence_score=data.get("influence_score", 0.5),
            recent_contribution_count=data.get("recent_contribution_count", 0),
            last_updated=data.get("last_updated")
        )


class DynamicWeightCalculator:
    """
    动态权重计算器
    
    根据讨论进展、专家权威度和上下文动态调整共识权重。
    """
    
    # 基础共识类型权重
    BASE_TYPE_WEIGHTS = {
        ConsensusType.CORE: 1.0,
        ConsensusType.STRATEGIC: 0.85,
        ConsensusType.TECHNICAL: 0.75,
        ConsensusType.TACTICAL: 0.65,
        ConsensusType.PROCEDURAL: 0.5,
        ConsensusType.AUXILIARY: 0.4
    }
    
    # 不同讨论阶段的类型权重调整
    PHASE_TYPE_ADJUSTMENTS = {
        DiscussionPhase.EXPLORATION: {
            ConsensusType.CORE: 0.8,
            ConsensusType.STRATEGIC: 0.9,
            ConsensusType.TECHNICAL: 1.0,
            ConsensusType.TACTICAL: 1.0,
            ConsensusType.PROCEDURAL: 1.2,
            ConsensusType.AUXILIARY: 1.3  # 探索阶段辅助共识更重要
        },
        DiscussionPhase.DEEPENING: {
            ConsensusType.CORE: 1.0,
            ConsensusType.STRATEGIC: 1.0,
            ConsensusType.TECHNICAL: 1.1,
            ConsensusType.TACTICAL: 1.0,
            ConsensusType.PROCEDURAL: 0.9,
            ConsensusType.AUXILIARY: 0.9
        },
        DiscussionPhase.CONVERGENCE: {
            ConsensusType.CORE: 1.2,
            ConsensusType.STRATEGIC: 1.1,
            ConsensusType.TECHNICAL: 1.0,
            ConsensusType.TACTICAL: 0.9,
            ConsensusType.PROCEDURAL: 0.8,
            ConsensusType.AUXILIARY: 0.7  # 收敛阶段核心共识更重要
        },
        DiscussionPhase.FINALIZATION: {
            ConsensusType.CORE: 1.3,
            ConsensusType.STRATEGIC: 1.2,
            ConsensusType.TECHNICAL: 1.0,
            ConsensusType.TACTICAL: 0.8,
            ConsensusType.PROCEDURAL: 0.6,
            ConsensusType.AUXILIARY: 0.5  # 定稿阶段核心共识最重要
        }
    }
    
    def __init__(self):
        self.expert_scores: Dict[str, ExpertAuthorityScore] = {}
        self.current_phase: DiscussionPhase = DiscussionPhase.EXPLORATION
        self._context_modifiers: Dict[str, float] = {}
    
    def set_expert_score(self, expert_id: str, score: ExpertAuthorityScore) -> None:
        """设置专家权威度评分"""
        self.expert_scores[expert_id] = score
    
    def get_expert_score(self, expert_id: str) -> ExpertAuthorityScore:
        """获取专家权威度评分，不存在则创建默认"""
        if expert_id not in self.expert_scores:
            self.expert_scores[expert_id] = ExpertAuthorityScore(expert_id=expert_id)
        return self.expert_scores[expert_id]
    
    def set_phase(self, phase: DiscussionPhase) -> None:
        """设置当前讨论阶段"""
        self.current_phase = phase
    
    def calculate_expert_weighted_support(self,
                                          consensus: 'ConsensusPoint',
                                          expert_ids: List[str] = None) -> float:
        """
        计算专家权威度加权的支持强度
        
        Args:
            consensus: 共识点
            expert_ids: 专家ID列表，默认使用共识的支持者列表
            
        Returns:
            float: 加权后的支持因子 (0.0 - 1.5)
        """
        supporters = expert_ids if expert_ids is not None else consensus.supporters
        
        if not supporters:
            return 0.0
        
        total_weight = 0.0
        total_authority = 0.0
        
        for expert_id in supporters:
            expert_score = self.get_expert_score(expert_id)
            authority = expert_score.get_overall_authority()
            total_authority += authority
            total_weight += 1.0
        
        if total_weight == 0:
            return 1.0
        
        # 计算平均权威度
        avg_authority = total_authority / total_weight
        
        # 转换为支持因子 (0.5 - 1.5)
        support_factor = 0.5 + avg_authority
        
        return support_factor
    
    def get_phase_adjusted_type_weights(self,
                                         phase: DiscussionPhase = None
                                         ) -> Dict[ConsensusType, float]:
        """
        获取阶段调整后的类型权重
        
        Args:
            phase: 讨论阶段，默认使用当前阶段
            
        Returns:
            Dict[ConsensusType, float]: 类型到权重的映射
        """
        if phase is None:
            phase = self.current_phase
        
        adjustments = self.PHASE_TYPE_ADJUSTMENTS.get(
            phase, 
            self.PHASE_TYPE_ADJUSTMENTS[DiscussionPhase.EXPLORATION]
        )
        
        result = {}
        for consensus_type in ConsensusType:
            base_weight = self.BASE_TYPE_WEIGHTS.get(consensus_type, 0.5)
            adjustment = adjustments.get(consensus_type, 1.0)
            result[consensus_type] = base_weight * adjustment
        
        return result
    
    def calculate_context_weight_modifier(self,
                                          consensus: 'ConsensusPoint',
                                          discussion_context: Dict[str, Any] = None
                                          ) -> float:
        """
        计算上下文权重修正因子
        
        Args:
            consensus: 共识点
            discussion_context: 讨论上下文
            
        Returns:
            float: 上下文修正因子 (0.8 - 1.2)
        """
        if discussion_context is None:
            discussion_context = {}
        
        modifier = 1.0
        
        # 检查是否与讨论主题相关
        topic_keywords = discussion_context.get("topic_keywords", [])
        if topic_keywords and consensus.topic_keywords:
            overlap = len(set(topic_keywords) & set(consensus.topic_keywords))
            if overlap > 0:
                modifier += min(0.1, overlap * 0.03)  # 相关性加成
        
        # 检查证据充足性
        if len(consensus.evidence) >= 3:
            modifier += 0.05
        
        # 检查验证次数
        if consensus.verification_count >= 2:
            modifier += 0.05
        
        return max(0.8, min(1.2, modifier))
    
    def get_combined_weight(self, consensus: 'ConsensusPoint',
                            phase: DiscussionPhase = None,
                            context: Dict[str, Any] = None) -> float:
        """
        获取综合权重
        
        综合考虑共识类型、讨论阶段、专家权威度和上下文。
        
        Args:
            consensus: 共识点
            phase: 讨论阶段
            context: 讨论上下文
            
        Returns:
            float: 综合权重
        """
        # 类型权重
        type_weights = self.get_phase_adjusted_type_weights(phase)
        type_weight = type_weights.get(consensus.consensus_type, 0.5)
        
        # 专家权威度加权
        expert_factor = self.calculate_expert_weighted_support(consensus)
        
        # 上下文修正
        context_modifier = self.calculate_context_weight_modifier(consensus, context)
        
        # 综合计算
        combined = type_weight * expert_factor * context_modifier
        
        return combined
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "expert_scores": {
                k: v.to_dict() for k, v in self.expert_scores.items()
            },
            "current_phase": self.current_phase.value,
            "context_modifiers": self._context_modifiers
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DynamicWeightCalculator':
        """反序列化"""
        calculator = cls()
        
        for expert_id, score_data in data.get("expert_scores", {}).items():
            calculator.expert_scores[expert_id] = ExpertAuthorityScore.from_dict(
                score_data
            )
        
        phase_value = data.get("current_phase", "exploration")
        calculator.current_phase = DiscussionPhase(phase_value)
        
        calculator._context_modifiers = data.get("context_modifiers", {})
        
        return calculator
