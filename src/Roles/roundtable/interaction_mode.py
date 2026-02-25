"""
交互模式管理模块

包含交互模式相关组件:
- InteractionMode: 交互模式枚举
- InteractionModeManager: 交互模式管理器
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime
from enum import Enum
import logging

if TYPE_CHECKING:
    from .main import RoundtableDiscussion

logger = logging.getLogger(__name__)


class InteractionMode(Enum):
    """交互模式枚举"""
    STRUCTURED = "structured"        # 结构化：Moderator 主导
    SEMI_FREE = "semi_free"          # 半自由：有引导的专家互动
    FREE_DISCUSSION = "free"         # 自由讨论：专家主导
    DEBATE = "debate"                # 辩论模式：对立观点交锋
    COLLABORATIVE = "collaborative"  # 协作模式：共同解决问题


class InteractionModeManager:
    """
    交互模式管理器
    
    管理讨论的交互模式，支持动态切换
    """
    
    def __init__(self, discussion: 'RoundtableDiscussion' = None):
        """
        初始化交互模式管理器
        
        Args:
            discussion: 关联的讨论实例
        """
        self.discussion = discussion
        self.current_mode = InteractionMode.STRUCTURED
        self.mode_history: List[Dict[str, Any]] = []
        
        # 模式切换规则
        self.mode_switch_rules: Dict[str, Dict[str, Any]] = {
            "high_divergence": {
                "target_mode": InteractionMode.DEBATE,
                "threshold": 3,  # 3个以上分歧点
                "reason": "存在较多分歧点，建议进入辩论模式"
            },
            "consensus_reached": {
                "target_mode": InteractionMode.COLLABORATIVE,
                "threshold": 0.7,  # 共识度 70%
                "reason": "已达成较高共识，建议进入协作模式"
            },
            "experts_active": {
                "target_mode": InteractionMode.FREE_DISCUSSION,
                "threshold": 5,  # 专家发言超过 5 次
                "reason": "专家讨论热烈，建议进入自由讨论模式"
            }
        }
        
        # 模式允许的交互类型
        self._mode_allowed_interactions = {
            InteractionMode.STRUCTURED: [
                "moderator_guided", "sequential_speech", "skeptic_question"
            ],
            InteractionMode.SEMI_FREE: [
                "moderator_guided", "sequential_speech", "skeptic_question",
                "expert_clarification", "expert_comment"
            ],
            InteractionMode.FREE_DISCUSSION: [
                "direct_dialogue", "open_question", "peer_challenge",
                "collaboration_proposal", "expert_debate"
            ],
            InteractionMode.DEBATE: [
                "position_statement", "rebuttal", "evidence_presentation",
                "counter_argument", "concession"
            ],
            InteractionMode.COLLABORATIVE: [
                "solution_proposal", "idea_building", "resource_sharing",
                "task_division", "synthesis_contribution"
            ]
        }
    
    def set_discussion(self, discussion: 'RoundtableDiscussion'):
        """设置关联的讨论实例"""
        self.discussion = discussion
    
    def switch_mode(self, new_mode: InteractionMode, reason: str = "") -> bool:
        """
        切换交互模式
        
        Args:
            new_mode: 新模式
            reason: 切换原因
            
        Returns:
            是否切换成功
        """
        if new_mode == self.current_mode:
            return True
        
        old_mode = self.current_mode
        self.current_mode = new_mode
        
        # 记录切换历史
        self.mode_history.append({
            "from_mode": old_mode.value,
            "to_mode": new_mode.value,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"交互模式切换: {old_mode.value} -> {new_mode.value}, 原因: {reason}")
        return True
    
    def get_allowed_interactions(self) -> List[str]:
        """
        获取当前模式允许的交互类型
        
        Returns:
            允许的交互类型列表
        """
        return self._mode_allowed_interactions.get(self.current_mode, [])
    
    def is_interaction_allowed(self, interaction_type: str) -> bool:
        """
        检查交互类型是否允许
        
        Args:
            interaction_type: 交互类型
            
        Returns:
            是否允许
        """
        return interaction_type in self.get_allowed_interactions()
    
    def suggest_mode_switch(self, context: Dict[str, Any] = None) -> Optional[InteractionMode]:
        """
        基于上下文建议模式切换
        
        Args:
            context: 讨论上下文
            
        Returns:
            建议的模式或 None
        """
        if not context:
            return None
        
        # 检查分歧点数量
        divergence_count = context.get('divergence_count', 0)
        if divergence_count >= self.mode_switch_rules["high_divergence"]["threshold"]:
            if self.current_mode != InteractionMode.DEBATE:
                return InteractionMode.DEBATE
        
        # 检查共识度
        consensus_level = context.get('consensus_level', 0.0)
        if consensus_level >= self.mode_switch_rules["consensus_reached"]["threshold"]:
            if self.current_mode != InteractionMode.COLLABORATIVE:
                return InteractionMode.COLLABORATIVE
        
        # 检查专家发言活跃度
        expert_speech_count = context.get('expert_speech_count', 0)
        if expert_speech_count >= self.mode_switch_rules["experts_active"]["threshold"]:
            if self.current_mode == InteractionMode.STRUCTURED:
                return InteractionMode.SEMI_FREE
        
        return None
    
    def get_mode_description(self, mode: InteractionMode = None) -> str:
        """
        获取模式描述
        
        Args:
            mode: 模式（默认为当前模式）
            
        Returns:
            模式描述
        """
        mode = mode or self.current_mode
        descriptions = {
            InteractionMode.STRUCTURED: "结构化模式 - 由主持人引导，专家按顺序发言",
            InteractionMode.SEMI_FREE: "半自由模式 - 有引导的专家互动，允许补充和澄清",
            InteractionMode.FREE_DISCUSSION: "自由讨论模式 - 专家可主动发起对话和讨论",
            InteractionMode.DEBATE: "辩论模式 - 对立观点交锋，旨在深入探讨分歧",
            InteractionMode.COLLABORATIVE: "协作模式 - 共同解决问题，构建综合方案"
        }
        return descriptions.get(mode, "未知模式")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        mode_counts = {}
        for record in self.mode_history:
            mode = record["to_mode"]
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
        
        return {
            "current_mode": self.current_mode.value,
            "mode_switch_count": len(self.mode_history),
            "mode_distribution": mode_counts,
            "allowed_interactions": self.get_allowed_interactions()
        }
