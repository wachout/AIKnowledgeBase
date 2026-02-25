"""
结构化辩论引擎模块

提供多阶段、有规则的辩论流程管理。

Classes:
    DebatePhase: 辩论阶段枚举
    DebateArgument: 辩论论点数据类
    DebateRules: 辩论规则数据类
    DebatePosition: 辩论立场数据类
    StructuredDebateEngine: 结构化辩论引擎
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .divergence_point import DivergencePoint


class DebatePhase(Enum):
    """辩论阶段"""
    OPENING = "opening"                     # 开场陈述
    ARGUMENTATION = "argumentation"         # 论证阶段
    CROSS_EXAMINATION = "cross_examination" # 交叉质询
    REBUTTAL = "rebuttal"                   # 反驳阶段
    COMMON_GROUND = "common_ground"         # 寻找共识
    SYNTHESIS = "synthesis"                 # 综合阶段
    CLOSING = "closing"                     # 结束陈述


@dataclass
class DebateArgument:
    """辩论论点"""
    argument_id: str
    speaker: str
    position: str  # 立场标识
    content: str
    evidence: List[str] = field(default_factory=list)
    phase: DebatePhase = DebatePhase.ARGUMENTATION
    round_number: int = 1
    rebutting: Optional[str] = None      # 反驳的论点ID
    supporting: Optional[str] = None     # 支持的论点ID
    created_at: str = None
    quality_score: float = 0.0           # 论点质量分
    relevance_score: float = 0.0         # 相关性分
    evidence_strength: float = 0.0       # 证据强度
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if not self.argument_id:
            self.argument_id = f"arg_{datetime.now().strftime('%H%M%S')}_{id(self) % 1000}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "argument_id": self.argument_id,
            "speaker": self.speaker,
            "position": self.position,
            "content": self.content,
            "evidence": self.evidence,
            "phase": self.phase.value,
            "round_number": self.round_number,
            "rebutting": self.rebutting,
            "supporting": self.supporting,
            "created_at": self.created_at,
            "quality_score": self.quality_score,
            "relevance_score": self.relevance_score,
            "evidence_strength": self.evidence_strength
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DebateArgument':
        return cls(
            argument_id=data.get("argument_id", ""),
            speaker=data.get("speaker", ""),
            position=data.get("position", ""),
            content=data.get("content", ""),
            evidence=data.get("evidence", []),
            phase=DebatePhase(data.get("phase", "argumentation")),
            round_number=data.get("round_number", 1),
            rebutting=data.get("rebutting"),
            supporting=data.get("supporting"),
            created_at=data.get("created_at"),
            quality_score=data.get("quality_score", 0.0),
            relevance_score=data.get("relevance_score", 0.0),
            evidence_strength=data.get("evidence_strength", 0.0)
        )


@dataclass
class DebateRules:
    """辩论规则"""
    max_rounds: int = 4                          # 最大轮次
    time_per_speaker_seconds: int = 300          # 每人发言时间
    min_evidence_per_claim: int = 1              # 每个声明最少证据数
    allow_interruptions: bool = False            # 是否允许打断
    require_rebuttal: bool = True                # 是否要求反驳
    voting_required: bool = False                # 是否需要投票
    min_participants: int = 2                    # 最少参与者
    max_participants: int = 6                    # 最大参与者
    opening_time_limit: int = 120                # 开场陈述时间限制
    closing_time_limit: int = 60                 # 结束陈述时间限制
    evidence_weight: float = 0.3                 # 证据在评分中的权重
    logic_weight: float = 0.4                    # 逻辑在评分中的权重
    persuasion_weight: float = 0.3               # 说服力在评分中的权重
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_rounds": self.max_rounds,
            "time_per_speaker_seconds": self.time_per_speaker_seconds,
            "min_evidence_per_claim": self.min_evidence_per_claim,
            "allow_interruptions": self.allow_interruptions,
            "require_rebuttal": self.require_rebuttal,
            "voting_required": self.voting_required,
            "min_participants": self.min_participants,
            "max_participants": self.max_participants,
            "opening_time_limit": self.opening_time_limit,
            "closing_time_limit": self.closing_time_limit,
            "evidence_weight": self.evidence_weight,
            "logic_weight": self.logic_weight,
            "persuasion_weight": self.persuasion_weight
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DebateRules':
        return cls(
            max_rounds=data.get("max_rounds", 4),
            time_per_speaker_seconds=data.get("time_per_speaker_seconds", 300),
            min_evidence_per_claim=data.get("min_evidence_per_claim", 1),
            allow_interruptions=data.get("allow_interruptions", False),
            require_rebuttal=data.get("require_rebuttal", True),
            voting_required=data.get("voting_required", False),
            min_participants=data.get("min_participants", 2),
            max_participants=data.get("max_participants", 6),
            opening_time_limit=data.get("opening_time_limit", 120),
            closing_time_limit=data.get("closing_time_limit", 60),
            evidence_weight=data.get("evidence_weight", 0.3),
            logic_weight=data.get("logic_weight", 0.4),
            persuasion_weight=data.get("persuasion_weight", 0.3)
        )


@dataclass
class DebatePosition:
    """辩论立场"""
    position_id: str
    name: str
    description: str
    holders: List[str] = field(default_factory=list)  # 持有该立场的参与者
    arguments: List[str] = field(default_factory=list)  # 该立场的论点ID
    total_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "position_id": self.position_id,
            "name": self.name,
            "description": self.description,
            "holders": self.holders,
            "arguments": self.arguments,
            "total_score": self.total_score
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DebatePosition':
        return cls(
            position_id=data.get("position_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            holders=data.get("holders", []),
            arguments=data.get("arguments", []),
            total_score=data.get("total_score", 0.0)
        )


class StructuredDebateEngine:
    """
    结构化辩论引擎
    
    提供多阶段、有规则的辩论流程管理。
    """
    
    # 阶段流转顺序
    PHASE_ORDER = [
        DebatePhase.OPENING,
        DebatePhase.ARGUMENTATION,
        DebatePhase.CROSS_EXAMINATION,
        DebatePhase.REBUTTAL,
        DebatePhase.COMMON_GROUND,
        DebatePhase.SYNTHESIS,
        DebatePhase.CLOSING
    ]
    
    def __init__(self, divergence: 'DivergencePoint', rules: DebateRules = None):
        self.divergence = divergence
        self.rules = rules or DebateRules()
        self.debate_id = f"debate_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.current_phase = DebatePhase.OPENING
        self.current_round = 0
        self.arguments: List[DebateArgument] = []
        self.positions: Dict[str, DebatePosition] = {}
        self.phase_history: List[Dict[str, Any]] = []
        self.evaluation_scores: Dict[str, float] = {}  # participant -> score
        self.common_grounds: List[str] = []
        self.synthesis_result: Optional[Dict[str, Any]] = None
        self.started_at: str = None
        self.ended_at: str = None
        self.is_active: bool = False
        
        # 初始化立场
        self._initialize_positions()
    
    def _initialize_positions(self) -> None:
        """根据分歧点初始化辩论立场"""
        for i, (proponent, position_text) in enumerate(self.divergence.proponents.items()):
            position_id = f"pos_{i}"
            # 尝试合并相似立场
            merged = False
            for existing_pos in self.positions.values():
                if self._are_positions_similar(existing_pos.description, position_text):
                    existing_pos.holders.append(proponent)
                    merged = True
                    break
            
            if not merged:
                self.positions[position_id] = DebatePosition(
                    position_id=position_id,
                    name=f"立场{i+1}",
                    description=position_text,
                    holders=[proponent]
                )
    
    def _are_positions_similar(self, pos1: str, pos2: str) -> bool:
        """判断两个立场是否相似（简化版）"""
        # 简单的相似度检查，实际应用中可使用NLP
        words1 = set(pos1.lower().split())
        words2 = set(pos2.lower().split())
        if not words1 or not words2:
            return False
        overlap = len(words1 & words2) / min(len(words1), len(words2))
        return overlap > 0.7
    
    def start_debate(self) -> Dict[str, Any]:
        """开始辩论会话"""
        self.started_at = datetime.now().isoformat()
        self.is_active = True
        self.current_phase = DebatePhase.OPENING
        self.current_round = 1
        
        # 记录阶段开始
        self._record_phase_event("started")
        
        return {
            "debate_id": self.debate_id,
            "phase": self.current_phase.value,
            "round": self.current_round,
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "speaker_order": self.get_current_speaker_order(),
            "rules": self.rules.to_dict(),
            "message": f"辩论开始，当前阶段: {self.current_phase.value}"
        }
    
    def advance_phase(self) -> DebatePhase:
        """推进到下一阶段"""
        if not self.is_active:
            return self.current_phase
        
        # 记录当前阶段结束
        self._record_phase_event("completed")
        
        current_index = self.PHASE_ORDER.index(self.current_phase)
        
        if current_index < len(self.PHASE_ORDER) - 1:
            self.current_phase = self.PHASE_ORDER[current_index + 1]
            
            # 某些阶段需要增加轮次
            if self.current_phase == DebatePhase.ARGUMENTATION:
                self.current_round += 1
            
            self._record_phase_event("started")
        else:
            # 辩论结束
            self.end_debate()
        
        return self.current_phase
    
    def submit_argument(self, speaker: str, content: str,
                       evidence: List[str] = None,
                       rebutting: str = None,
                       supporting: str = None) -> Dict[str, Any]:
        """提交论点"""
        if not self.is_active:
            return {"success": False, "error": "辩论未开始或已结束"}
        
        # 找到该发言者的立场
        speaker_position = None
        for pos_id, pos in self.positions.items():
            if speaker in pos.holders:
                speaker_position = pos_id
                break
        
        if not speaker_position:
            return {"success": False, "error": "发言者不在辩论参与者中"}
        
        # 创建论点
        argument = DebateArgument(
            argument_id="",
            speaker=speaker,
            position=speaker_position,
            content=content,
            evidence=evidence or [],
            phase=self.current_phase,
            round_number=self.current_round,
            rebutting=rebutting,
            supporting=supporting
        )
        
        # 评估论点
        self._evaluate_argument(argument)
        
        # 添加到论点列表
        self.arguments.append(argument)
        
        # 更新立场分数
        self.positions[speaker_position].arguments.append(argument.argument_id)
        self.positions[speaker_position].total_score += argument.quality_score
        
        # 更新参与者分数
        if speaker not in self.evaluation_scores:
            self.evaluation_scores[speaker] = 0.0
        self.evaluation_scores[speaker] += argument.quality_score
        
        return {
            "success": True,
            "argument": argument.to_dict(),
            "position_score": self.positions[speaker_position].total_score,
            "speaker_score": self.evaluation_scores[speaker]
        }
    
    def _evaluate_argument(self, argument: DebateArgument) -> None:
        """评估论点质量"""
        # 证据强度
        evidence_score = min(1.0, len(argument.evidence) / max(1, self.rules.min_evidence_per_claim))
        argument.evidence_strength = evidence_score
        
        # 相关性评分（基于是否回应其他论点）
        if argument.rebutting or argument.supporting:
            argument.relevance_score = 0.8
        else:
            argument.relevance_score = 0.6
        
        # 内容长度评分（简化）
        content_length = len(argument.content)
        if content_length < 50:
            content_score = 0.4
        elif content_length < 200:
            content_score = 0.7
        elif content_length < 500:
            content_score = 0.9
        else:
            content_score = 0.8  # 过长可能不够精练
        
        # 综合评分
        argument.quality_score = (
            evidence_score * self.rules.evidence_weight +
            argument.relevance_score * self.rules.logic_weight +
            content_score * self.rules.persuasion_weight
        )
    
    def get_current_speaker_order(self) -> List[str]:
        """获取当前阶段的发言顺序"""
        all_participants = []
        for pos in self.positions.values():
            all_participants.extend(pos.holders)
        
        # 根据阶段调整顺序
        if self.current_phase == DebatePhase.OPENING:
            # 开场：按立场顺序
            return all_participants
        elif self.current_phase == DebatePhase.CROSS_EXAMINATION:
            # 交叉质询：交替
            interleaved = []
            position_lists = [pos.holders for pos in self.positions.values()]
            max_len = max(len(lst) for lst in position_lists) if position_lists else 0
            for i in range(max_len):
                for lst in position_lists:
                    if i < len(lst):
                        interleaved.append(lst[i])
            return interleaved
        elif self.current_phase == DebatePhase.REBUTTAL:
            # 反驳：分数低的先发言
            scored = [(p, self.evaluation_scores.get(p, 0)) for p in all_participants]
            scored.sort(key=lambda x: x[1])
            return [p for p, _ in scored]
        else:
            return all_participants
    
    def identify_common_ground(self) -> List[str]:
        """识别各方的共同点"""
        if not self.arguments:
            return []
        
        common_grounds = []
        
        # 收集每个立场的关键词
        position_keywords: Dict[str, set] = {}
        for arg in self.arguments:
            if arg.position not in position_keywords:
                position_keywords[arg.position] = set()
            # 简化的关键词提取
            words = set(arg.content.lower().split())
            position_keywords[arg.position].update(words)
        
        # 找到所有立场的共同关键词
        if len(position_keywords) >= 2:
            common_words = set.intersection(*position_keywords.values())
            # 过滤停用词（简化）
            stop_words = {"the", "a", "an", "is", "are", "was", "were", "be",
                         "的", "是", "在", "和", "了", "与"}
            meaningful_common = common_words - stop_words
            if meaningful_common:
                common_grounds.append(f"共同关注点: {', '.join(list(meaningful_common)[:10])}")
        
        # 检查是否有互相支持的论点
        support_map: Dict[str, List[str]] = {}
        for arg in self.arguments:
            if arg.supporting:
                if arg.supporting not in support_map:
                    support_map[arg.supporting] = []
                support_map[arg.supporting].append(arg.speaker)
        
        for supported_id, supporters in support_map.items():
            if len(supporters) >= 2:
                common_grounds.append(f"多方支持的论点: {supported_id}")
        
        self.common_grounds = common_grounds
        return common_grounds
    
    def generate_synthesis(self) -> Dict[str, Any]:
        """生成综合结论"""
        # 计算各立场得分
        position_scores = {
            pos_id: pos.total_score
            for pos_id, pos in self.positions.items()
        }
        
        # 排序
        sorted_positions = sorted(
            position_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 确定结果类型
        if len(sorted_positions) >= 2:
            top_score = sorted_positions[0][1]
            second_score = sorted_positions[1][1]
            
            if top_score > second_score * 1.5:
                outcome_type = "clear_winner"
            elif abs(top_score - second_score) < 0.1 * max(top_score, second_score):
                outcome_type = "draw"
            else:
                outcome_type = "partial_consensus"
        else:
            outcome_type = "single_position"
        
        # 生成建议
        recommendations = []
        if outcome_type == "clear_winner":
            winner_pos = self.positions[sorted_positions[0][0]]
            recommendations.append(f"采纳立场: {winner_pos.description}")
        elif outcome_type == "draw":
            recommendations.append("建议继续讨论或寻求外部专家意见")
        elif outcome_type == "partial_consensus":
            recommendations.append("建议融合各方观点形成折中方案")
        
        # 添加共同点
        if self.common_grounds:
            recommendations.append(f"基于共同点构建共识: {'; '.join(self.common_grounds)}")
        
        self.synthesis_result = {
            "outcome_type": outcome_type,
            "position_scores": position_scores,
            "sorted_positions": sorted_positions,
            "common_grounds": self.common_grounds,
            "recommendations": recommendations,
            "participant_scores": dict(self.evaluation_scores),
            "total_arguments": len(self.arguments),
            "total_rounds": self.current_round
        }
        
        return self.synthesis_result
    
    def end_debate(self) -> Dict[str, Any]:
        """结束辩论"""
        self.ended_at = datetime.now().isoformat()
        self.is_active = False
        
        # 确保生成综合结论
        if not self.synthesis_result:
            self.identify_common_ground()
            self.generate_synthesis()
        
        return {
            "debate_id": self.debate_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "total_phases": len(self.phase_history),
            "total_arguments": len(self.arguments),
            "synthesis": self.synthesis_result
        }
    
    def get_debate_status(self) -> Dict[str, Any]:
        """获取辩论状态"""
        return {
            "debate_id": self.debate_id,
            "is_active": self.is_active,
            "current_phase": self.current_phase.value,
            "current_round": self.current_round,
            "total_arguments": len(self.arguments),
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "evaluation_scores": dict(self.evaluation_scores),
            "phase_history_count": len(self.phase_history),
            "started_at": self.started_at,
            "ended_at": self.ended_at
        }
    
    def _record_phase_event(self, event_type: str) -> None:
        """记录阶段事件"""
        self.phase_history.append({
            "phase": self.current_phase.value,
            "round": self.current_round,
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
            "arguments_count": len(self.arguments)
        })
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "debate_id": self.debate_id,
            "divergence_content": self.divergence.content if self.divergence else "",
            "rules": self.rules.to_dict(),
            "current_phase": self.current_phase.value,
            "current_round": self.current_round,
            "arguments": [a.to_dict() for a in self.arguments],
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "phase_history": self.phase_history,
            "evaluation_scores": dict(self.evaluation_scores),
            "common_grounds": self.common_grounds,
            "synthesis_result": self.synthesis_result,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "is_active": self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], 
                  divergence: 'DivergencePoint' = None) -> 'StructuredDebateEngine':
        # 延迟导入避免循环依赖
        from .divergence_point import DivergencePoint
        
        # 创建实例（使用空分歧点）
        if divergence is None:
            divergence = DivergencePoint(content=data.get("divergence_content", ""))
        
        rules = DebateRules.from_dict(data.get("rules", {}))
        engine = cls(divergence, rules)
        
        engine.debate_id = data.get("debate_id", engine.debate_id)
        engine.current_phase = DebatePhase(data.get("current_phase", "opening"))
        engine.current_round = data.get("current_round", 0)
        engine.arguments = [
            DebateArgument.from_dict(a) for a in data.get("arguments", [])
        ]
        engine.positions = {
            k: DebatePosition.from_dict(v)
            for k, v in data.get("positions", {}).items()
        }
        engine.phase_history = data.get("phase_history", [])
        engine.evaluation_scores = data.get("evaluation_scores", {})
        engine.common_grounds = data.get("common_grounds", [])
        engine.synthesis_result = data.get("synthesis_result")
        engine.started_at = data.get("started_at")
        engine.ended_at = data.get("ended_at")
        engine.is_active = data.get("is_active", False)
        
        return engine
