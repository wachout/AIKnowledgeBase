"""
分歧化解策略执行器模块

提供多种分歧化解策略的实现。

Classes:
    ResolutionContext: 解决上下文数据类
    ResolutionOutcomeType: 解决结果类型枚举
    ResolutionResult: 解决结果数据类
    ResolutionStrategyExecutor: 解决策略执行器基类
    DebateExecutor: 辩论策略执行器
    VotingExecutor: 投票策略执行器
    MediationExecutor: 调解策略执行器
    CompromiseExecutor: 妥协策略执行器
    DataDrivenExecutor: 数据驱动策略执行器
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generator, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .divergence_point import DivergencePoint

from .divergence_point import ConflictResolutionStrategy
from .debate_engine import (
    DebatePhase,
    StructuredDebateEngine
)


@dataclass
class ResolutionContext:
    """解决上下文"""
    divergence: 'DivergencePoint'
    divergence_id: str
    participants: List[str]
    previous_attempts: List[Dict[str, Any]] = field(default_factory=list)
    time_budget_minutes: int = 30
    priority: str = "medium"
    additional_context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "divergence_id": self.divergence_id,
            "divergence_content": self.divergence.content if self.divergence else "",
            "participants": self.participants,
            "previous_attempts": self.previous_attempts,
            "time_budget_minutes": self.time_budget_minutes,
            "priority": self.priority,
            "additional_context": self.additional_context
        }


class ResolutionOutcomeType(Enum):
    """解决结果类型"""
    CONSENSUS = "consensus"           # 完全达成共识
    PARTIAL = "partial"               # 部分解决
    FAILED = "failed"                 # 解决失败
    POSTPONED = "postponed"           # 延后处理
    ESCALATED = "escalated"           # 升级处理


@dataclass
class ResolutionResult:
    """解决结果"""
    success: bool
    strategy_used: ConflictResolutionStrategy
    outcome_type: ResolutionOutcomeType
    new_consensus_points: List[Dict[str, Any]] = field(default_factory=list)
    remaining_divergences: List[Dict[str, Any]] = field(default_factory=list)
    participant_satisfaction: Dict[str, float] = field(default_factory=dict)
    execution_summary: str = ""
    execution_details: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: int = 0
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "strategy_used": self.strategy_used.value,
            "outcome_type": self.outcome_type.value,
            "new_consensus_points": self.new_consensus_points,
            "remaining_divergences": self.remaining_divergences,
            "participant_satisfaction": self.participant_satisfaction,
            "execution_summary": self.execution_summary,
            "execution_details": self.execution_details,
            "duration_seconds": self.duration_seconds,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResolutionResult':
        return cls(
            success=data.get("success", False),
            strategy_used=ConflictResolutionStrategy(data.get("strategy_used", "debate")),
            outcome_type=ResolutionOutcomeType(data.get("outcome_type", "failed")),
            new_consensus_points=data.get("new_consensus_points", []),
            remaining_divergences=data.get("remaining_divergences", []),
            participant_satisfaction=data.get("participant_satisfaction", {}),
            execution_summary=data.get("execution_summary", ""),
            execution_details=data.get("execution_details", {}),
            duration_seconds=data.get("duration_seconds", 0),
            created_at=data.get("created_at")
        )


class ResolutionStrategyExecutor(ABC):
    """
    解决策略执行器基类
    
    定义策略执行的统一接口。
    """
    
    def __init__(self):
        self.strategy_name = "base"
        self.execution_history: List[Dict[str, Any]] = []
    
    @abstractmethod
    def execute(self, context: ResolutionContext) -> Generator[Dict[str, Any], None, ResolutionResult]:
        """
        执行解决策略
        
        Args:
            context: 解决上下文
            
        Yields:
            执行过程中的中间状态
            
        Returns:
            解决结果
        """
        pass
    
    @abstractmethod
    def can_handle(self, divergence: 'DivergencePoint') -> bool:
        """
        判断该策略是否适合处理指定分歧
        
        Args:
            divergence: 分歧点
            
        Returns:
            是否可以处理
        """
        pass
    
    @abstractmethod
    def estimate_duration(self, context: ResolutionContext) -> int:
        """
        估算执行时长
        
        Args:
            context: 解决上下文
            
        Returns:
            预估时长（分钟）
        """
        pass
    
    def record_execution(self, context: ResolutionContext, 
                         result: ResolutionResult) -> None:
        """记录执行历史"""
        self.execution_history.append({
            "timestamp": datetime.now().isoformat(),
            "divergence_id": context.divergence_id,
            "success": result.success,
            "outcome_type": result.outcome_type.value,
            "duration_seconds": result.duration_seconds
        })


class DebateExecutor(ResolutionStrategyExecutor):
    """辩论策略执行器"""
    
    def __init__(self):
        super().__init__()
        self.strategy_name = "debate"
        self.active_engines: Dict[str, StructuredDebateEngine] = {}
    
    def can_handle(self, divergence: 'DivergencePoint') -> bool:
        """判断是否适合辩论"""
        # 适合辩论的条件
        has_opposing = len(divergence.opposing_positions) >= 1
        has_participants = len(divergence.proponents) >= 2
        is_intense = divergence.intensity >= 0.5
        return has_opposing and has_participants and is_intense
    
    def estimate_duration(self, context: ResolutionContext) -> int:
        """估算辩论时长"""
        base_duration = 20  # 基础20分钟
        participant_factor = len(context.participants) * 5
        intensity_factor = int(context.divergence.intensity * 10)
        return min(60, base_duration + participant_factor + intensity_factor)
    
    def execute(self, context: ResolutionContext) -> Generator[Dict[str, Any], None, ResolutionResult]:
        """ 执行辩论流程"""
        start_time = datetime.now()
        
        # 创建辩论引擎
        engine = StructuredDebateEngine(context.divergence)
        self.active_engines[context.divergence_id] = engine
        
        try:
            # 开始辩论
            start_info = engine.start_debate()
            yield {
                "step": "debate_started",
                "phase": "opening",
                "data": start_info
            }
            
            # 模拟辩论过程（实际应用中会通过外部输入）
            for phase in StructuredDebateEngine.PHASE_ORDER[1:]:
                engine.advance_phase()
                
                yield {
                    "step": "phase_advanced",
                    "phase": phase.value,
                    "status": engine.get_debate_status()
                }
                
                # 特殊阶段处理
                if phase == DebatePhase.COMMON_GROUND:
                    common_grounds = engine.identify_common_ground()
                    yield {
                        "step": "common_ground_identified",
                        "common_grounds": common_grounds
                    }
                
                if phase == DebatePhase.SYNTHESIS:
                    synthesis = engine.generate_synthesis()
                    yield {
                        "step": "synthesis_generated",
                        "synthesis": synthesis
                    }
            
            # 结束辩论
            end_info = engine.end_debate()
            
            # 构建结果
            duration = int((datetime.now() - start_time).total_seconds())
            synthesis = engine.synthesis_result or {}
            outcome_type = synthesis.get("outcome_type", "partial")
            
            # 根据辩论结果确定是否成功
            success = outcome_type in ["clear_winner", "partial_consensus"]
            
            result = ResolutionResult(
                success=success,
                strategy_used=ConflictResolutionStrategy.DEBATE,
                outcome_type=ResolutionOutcomeType.CONSENSUS if success else ResolutionOutcomeType.PARTIAL,
                new_consensus_points=[
                    {"content": g, "source": "debate"}
                    for g in engine.common_grounds
                ],
                participant_satisfaction={
                    p: min(1.0, s / max(1, len(engine.arguments)))
                    for p, s in engine.evaluation_scores.items()
                },
                execution_summary=f"辩论完成: {outcome_type}",
                execution_details=end_info,
                duration_seconds=duration
            )
            
            self.record_execution(context, result)
            return result
            
        finally:
            # 清理
            if context.divergence_id in self.active_engines:
                del self.active_engines[context.divergence_id]


class VotingExecutor(ResolutionStrategyExecutor):
    """投票策略执行器"""
    
    def __init__(self):
        super().__init__()
        self.strategy_name = "voting"
    
    def can_handle(self, divergence: 'DivergencePoint') -> bool:
        """投票适合多人参与、需要快速决策的情况"""
        has_enough_participants = len(divergence.proponents) >= 3
        multiple_attempts = divergence.resolution_attempts >= 2
        return has_enough_participants or multiple_attempts
    
    def estimate_duration(self, context: ResolutionContext) -> int:
        """投票通常较快"""
        return 10
    
    def execute(self, context: ResolutionContext) -> Generator[Dict[str, Any], None, ResolutionResult]:
        """执行投票流程"""
        start_time = datetime.now()
        
        # 准备投票选项
        options = []
        for i, (proponent, position) in enumerate(context.divergence.proponents.items()):
            options.append({
                "option_id": f"opt_{i}",
                "description": position,
                "proposed_by": proponent
            })
        
        yield {
            "step": "voting_prepared",
            "options": options,
            "voters": context.participants
        }
        
        # 模拟投票结果（实际应用中会收集真实投票）
        votes: Dict[str, List[str]] = {opt["option_id"]: [] for opt in options}
        
        # 模拟：每个人投给自己提出的选项
        for opt in options:
            proposer = opt["proposed_by"]
            votes[opt["option_id"]].append(proposer)
        
        yield {
            "step": "voting_in_progress",
            "message": "投票进行中..."
        }
        
        # 统计结果
        vote_counts = {opt_id: len(voters) for opt_id, voters in votes.items()}
        total_votes = sum(vote_counts.values())
        
        # 找出获胜选项
        winner_id = max(vote_counts, key=vote_counts.get)
        winner_votes = vote_counts[winner_id]
        winner_option = next(opt for opt in options if opt["option_id"] == winner_id)
        
        # 计算获胜比例
        win_ratio = winner_votes / max(1, total_votes)
        
        yield {
            "step": "voting_completed",
            "vote_counts": vote_counts,
            "winner": winner_option,
            "win_ratio": win_ratio
        }
        
        # 构建结果
        duration = int((datetime.now() - start_time).total_seconds())
        success = win_ratio >= 0.5
        
        result = ResolutionResult(
            success=success,
            strategy_used=ConflictResolutionStrategy.VOTING,
            outcome_type=ResolutionOutcomeType.CONSENSUS if win_ratio > 0.6 else ResolutionOutcomeType.PARTIAL,
            new_consensus_points=[
                {"content": winner_option["description"], "source": "voting"}
            ] if success else [],
            participant_satisfaction={
                p: 1.0 if p in votes.get(winner_id, []) else 0.5
                for p in context.participants
            },
            execution_summary=f"投票完成: {winner_option['description'][:50]}... (得票率: {win_ratio:.1%})",
            execution_details={
                "options": options,
                "vote_counts": vote_counts,
                "winner": winner_option,
                "win_ratio": win_ratio
            },
            duration_seconds=duration
        )
        
        self.record_execution(context, result)
        return result


class MediationExecutor(ResolutionStrategyExecutor):
    """调解策略执行器"""
    
    def __init__(self):
        super().__init__()
        self.strategy_name = "mediation"
    
    def can_handle(self, divergence: 'DivergencePoint') -> bool:
        """调解适合两方对峥的情况"""
        has_clear_opposition = len(divergence.opposing_positions) >= 1
        moderate_intensity = 0.4 <= divergence.intensity <= 0.8
        return has_clear_opposition and moderate_intensity
    
    def estimate_duration(self, context: ResolutionContext) -> int:
        """调解需要中等时间"""
        return 25
    
    def execute(self, context: ResolutionContext) -> Generator[Dict[str, Any], None, ResolutionResult]:
        """执行调解流程"""
        start_time = datetime.now()
        
        # 指定调解者（实际应用中可能是 facilitator）
        mediator = "moderator"
        
        yield {
            "step": "mediation_started",
            "mediator": mediator,
            "parties": list(context.divergence.proponents.keys())
        }
        
        # 分别听取各方
        parties_positions = []
        for party, position in context.divergence.proponents.items():
            parties_positions.append({
                "party": party,
                "position": position,
                "concerns": []
            })
            
            yield {
                "step": "hearing_party",
                "party": party,
                "position": position
            }
        
        # 分析分歧点和共同点
        yield {
            "step": "analyzing_positions",
            "message": "调解者正在分析各方立场..."
        }
        
        # 提出折中方案
        compromise_proposal = f"综合各方观点: {context.divergence.content[:100]}..."
        if context.divergence.potential_resolutions:
            compromise_proposal = context.divergence.potential_resolutions[0]
        
        yield {
            "step": "compromise_proposed",
            "proposal": compromise_proposal
        }
        
        # 获取各方反馈（模拟）
        acceptance_rate = 0.7  # 模拟接受率
        
        yield {
            "step": "feedback_collected",
            "acceptance_rate": acceptance_rate
        }
        
        # 构建结果
        duration = int((datetime.now() - start_time).total_seconds())
        success = acceptance_rate >= 0.6
        
        result = ResolutionResult(
            success=success,
            strategy_used=ConflictResolutionStrategy.MEDIATION,
            outcome_type=ResolutionOutcomeType.CONSENSUS if success else ResolutionOutcomeType.PARTIAL,
            new_consensus_points=[
                {"content": compromise_proposal, "source": "mediation"}
            ] if success else [],
            participant_satisfaction={
                p: acceptance_rate for p in context.participants
            },
            execution_summary=f"调解完成: 接受率 {acceptance_rate:.1%}",
            execution_details={
                "mediator": mediator,
                "parties_positions": parties_positions,
                "compromise_proposal": compromise_proposal,
                "acceptance_rate": acceptance_rate
            },
            duration_seconds=duration
        )
        
        self.record_execution(context, result)
        return result


class CompromiseExecutor(ResolutionStrategyExecutor):
    """妥协策略执行器"""
    
    def __init__(self):
        super().__init__()
        self.strategy_name = "compromise"
    
    def can_handle(self, divergence: 'DivergencePoint') -> bool:
        """妥协适合中等强度的分歧"""
        moderate_intensity = 0.3 <= divergence.intensity <= 0.7
        has_multiple_views = len(divergence.proponents) >= 2
        return moderate_intensity and has_multiple_views
    
    def estimate_duration(self, context: ResolutionContext) -> int:
        """妥协通常较快"""
        return 15
    
    def execute(self, context: ResolutionContext) -> Generator[Dict[str, Any], None, ResolutionResult]:
        """执行妥协流程"""
        start_time = datetime.now()
        
        # 识别各方核心诉求
        core_demands = []
        for party, position in context.divergence.proponents.items():
            core_demands.append({
                "party": party,
                "core_demand": position[:100],
                "flexibility": 0.5  # 模拟灵活度
            })
        
        yield {
            "step": "demands_identified",
            "core_demands": core_demands
        }
        
        # 寻找可让步空间
        yield {
            "step": "finding_flexibility",
            "message": "分析各方可让步空间..."
        }
        
        # 构建折中方案
        compromise_elements = [d["core_demand"][:30] for d in core_demands]
        compromise_solution = f"折中方案: 综合 {' + '.join(compromise_elements)}"
        
        yield {
            "step": "compromise_built",
            "solution": compromise_solution
        }
        
        # 确认各方接受度（模拟）
        acceptance = {d["party"]: 0.65 + d["flexibility"] * 0.2 for d in core_demands}
        avg_acceptance = sum(acceptance.values()) / len(acceptance) if acceptance else 0
        
        yield {
            "step": "acceptance_confirmed",
            "acceptance": acceptance,
            "average": avg_acceptance
        }
        
        # 构建结果
        duration = int((datetime.now() - start_time).total_seconds())
        success = avg_acceptance >= 0.6
        
        result = ResolutionResult(
            success=success,
            strategy_used=ConflictResolutionStrategy.COMPROMISE,
            outcome_type=ResolutionOutcomeType.CONSENSUS if avg_acceptance > 0.7 else ResolutionOutcomeType.PARTIAL,
            new_consensus_points=[
                {"content": compromise_solution, "source": "compromise"}
            ] if success else [],
            participant_satisfaction=acceptance,
            execution_summary=f"妥协完成: 平均接受度 {avg_acceptance:.1%}",
            execution_details={
                "core_demands": core_demands,
                "compromise_solution": compromise_solution,
                "acceptance": acceptance
            },
            duration_seconds=duration
        )
        
        self.record_execution(context, result)
        return result


class DataDrivenExecutor(ResolutionStrategyExecutor):
    """数据驱动策略执行器"""
    
    def __init__(self):
        super().__init__()
        self.strategy_name = "data_driven"
    
    def can_handle(self, divergence: 'DivergencePoint') -> bool:
        """数据驱动适合有证据支撑的分歧"""
        has_discussions = len(divergence.discussion_history) >= 2
        return has_discussions
    
    def estimate_duration(self, context: ResolutionContext) -> int:
        """数据分析需要一定时间"""
        return 20
    
    def execute(self, context: ResolutionContext) -> Generator[Dict[str, Any], None, ResolutionResult]:
        """执行数据驱动解决流程"""
        start_time = datetime.now()
        
        # 收集相关数据
        yield {
            "step": "data_collection",
            "message": "收集相关数据和证据..."
        }
        
        # 分析各方观点的数据支撑
        position_evidence = []
        for party, position in context.divergence.proponents.items():
            evidence_score = 0.5  # 模拟证据强度
            position_evidence.append({
                "party": party,
                "position": position,
                "evidence_score": evidence_score
            })
        
        yield {
            "step": "evidence_analyzed",
            "position_evidence": position_evidence
        }
        
        # 基于数据形成结论
        best_supported = max(position_evidence, key=lambda x: x["evidence_score"])
        
        yield {
            "step": "conclusion_formed",
            "best_supported": best_supported
        }
        
        # 构建结果
        duration = int((datetime.now() - start_time).total_seconds())
        max_score = best_supported["evidence_score"]
        success = max_score >= 0.6
        
        result = ResolutionResult(
            success=success,
            strategy_used=ConflictResolutionStrategy.DATA_DRIVEN,
            outcome_type=ResolutionOutcomeType.CONSENSUS if success else ResolutionOutcomeType.PARTIAL,
            new_consensus_points=[
                {"content": best_supported["position"], "source": "data_driven"}
            ] if success else [],
            participant_satisfaction={
                pe["party"]: pe["evidence_score"] for pe in position_evidence
            },
            execution_summary=f"数据分析完成: 最佳支撑观点来自 {best_supported['party']}",
            execution_details={
                "position_evidence": position_evidence,
                "best_supported": best_supported
            },
            duration_seconds=duration
        )
        
        self.record_execution(context, result)
        return result
