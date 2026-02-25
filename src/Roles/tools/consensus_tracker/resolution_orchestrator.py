"""
解决会话与编排器模块

管理分歧解决的会话和流程编排。

Classes:
    SessionState: 会话状态枚举
    ResolutionSession: 解决会话数据类
    ResolutionOrchestrator: 解决流程编排器
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generator, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .divergence_point import DivergencePoint

from .divergence_point import ConflictResolutionStrategy
from .conflict_detection import ConflictAlert
from .strategy_executor import (
    ResolutionContext,
    ResolutionOutcomeType,
    ResolutionResult,
    ResolutionStrategyExecutor,
    DebateExecutor,
    VotingExecutor,
    MediationExecutor,
    CompromiseExecutor,
    DataDrivenExecutor
)


class SessionState(Enum):
    """会话状态"""
    PENDING = "pending"           # 等待开始
    ACTIVE = "active"             # 执行中
    PAUSED = "paused"             # 暂停
    EVALUATING = "evaluating"     # 评估中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    ESCALATED = "escalated"       # 已升级


@dataclass
class ResolutionSession:
    """解决会话"""
    session_id: str
    divergence_id: str
    strategy: ConflictResolutionStrategy
    state: SessionState = SessionState.PENDING
    participants: List[str] = field(default_factory=list)
    started_at: str = None
    ended_at: str = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    intermediate_results: List[Dict[str, Any]] = field(default_factory=list)
    final_result: Optional[ResolutionResult] = None
    escalation_count: int = 0
    
    def __post_init__(self):
        if not self.session_id:
            self.session_id = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(self) % 10000}"
    
    def start(self) -> None:
        """开始会话"""
        self.state = SessionState.ACTIVE
        self.started_at = datetime.now().isoformat()
        self.add_event("session_started", {})
    
    def pause(self) -> None:
        """暂停会话"""
        if self.state == SessionState.ACTIVE:
            self.state = SessionState.PAUSED
            self.add_event("session_paused", {})
    
    def resume(self) -> None:
        """恢复会话"""
        if self.state == SessionState.PAUSED:
            self.state = SessionState.ACTIVE
            self.add_event("session_resumed", {})
    
    def complete(self, result: ResolutionResult) -> None:
        """完成会话"""
        self.state = SessionState.COMPLETED
        self.ended_at = datetime.now().isoformat()
        self.final_result = result
        self.add_event("session_completed", {"success": result.success})
    
    def fail(self, reason: str) -> None:
        """标记会话失败"""
        self.state = SessionState.FAILED
        self.ended_at = datetime.now().isoformat()
        self.add_event("session_failed", {"reason": reason})
    
    def escalate(self, new_strategy: ConflictResolutionStrategy) -> None:
        """升级策略"""
        self.state = SessionState.ESCALATED
        self.escalation_count += 1
        self.add_event("session_escalated", {
            "from_strategy": self.strategy.value,
            "to_strategy": new_strategy.value
        })
        self.strategy = new_strategy
        self.state = SessionState.ACTIVE
    
    def add_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """添加事件到历史"""
        self.history.append({
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        })
    
    def add_intermediate_result(self, step: str, data: Dict[str, Any]) -> None:
        """添加中间结果"""
        self.intermediate_results.append({
            "step": step,
            "timestamp": datetime.now().isoformat(),
            "data": data
        })
    
    def get_progress(self) -> float:
        """获取进度"""
        if self.state == SessionState.COMPLETED:
            return 1.0
        if self.state == SessionState.PENDING:
            return 0.0
        if self.state in [SessionState.FAILED, SessionState.ESCALATED]:
            return 0.5
        
        # 基于中间结果数量估算
        return min(0.9, len(self.intermediate_results) * 0.15)
    
    def get_result(self) -> Optional[Dict[str, Any]]:
        """获取结果"""
        if self.final_result:
            return self.final_result.to_dict()
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "divergence_id": self.divergence_id,
            "strategy": self.strategy.value,
            "state": self.state.value,
            "participants": self.participants,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "history": self.history,
            "intermediate_results": self.intermediate_results,
            "final_result": self.final_result.to_dict() if self.final_result else None,
            "escalation_count": self.escalation_count,
            "progress": self.get_progress()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResolutionSession':
        session = cls(
            session_id=data.get("session_id", ""),
            divergence_id=data.get("divergence_id", ""),
            strategy=ConflictResolutionStrategy(data.get("strategy", "debate")),
            state=SessionState(data.get("state", "pending")),
            participants=data.get("participants", []),
            started_at=data.get("started_at"),
            ended_at=data.get("ended_at"),
            history=data.get("history", []),
            intermediate_results=data.get("intermediate_results", []),
            escalation_count=data.get("escalation_count", 0)
        )
        if data.get("final_result"):
            session.final_result = ResolutionResult.from_dict(data["final_result"])
        return session


class ResolutionOrchestrator:
    """
    解决流程编排器
    
    管理各种策略执行器，协调完整的冲突解决流程。
    """
    
    # 策略升级顺序
    STRATEGY_ESCALATION = [
        ConflictResolutionStrategy.COMPROMISE,
        ConflictResolutionStrategy.MEDIATION,
        ConflictResolutionStrategy.DATA_DRIVEN,
        ConflictResolutionStrategy.DEBATE,
        ConflictResolutionStrategy.VOTING,
        ConflictResolutionStrategy.EXPERT_REVIEW
    ]
    
    def __init__(self):
        self.executors: Dict[ConflictResolutionStrategy, ResolutionStrategyExecutor] = {
            ConflictResolutionStrategy.DEBATE: DebateExecutor(),
            ConflictResolutionStrategy.VOTING: VotingExecutor(),
            ConflictResolutionStrategy.MEDIATION: MediationExecutor(),
            ConflictResolutionStrategy.COMPROMISE: CompromiseExecutor(),
            ConflictResolutionStrategy.DATA_DRIVEN: DataDrivenExecutor(),
        }
        self.active_sessions: Dict[str, ResolutionSession] = {}
        self.completed_sessions: List[ResolutionSession] = []
    
    def start_resolution(self, alert: ConflictAlert,
                         divergence: 'DivergencePoint') -> ResolutionSession:
        """
        启动解决流程
        
        Args:
            alert: 冲突警报
            divergence: 分歧点
            
        Returns:
            创建的解决会话
        """
        # 创建会话
        session = ResolutionSession(
            session_id="",
            divergence_id=alert.divergence_id,
            strategy=alert.recommended_strategy,
            participants=alert.participants
        )
        session.start()
        
        self.active_sessions[session.session_id] = session
        
        return session
    
    def select_best_strategy(self, divergence: 'DivergencePoint') -> ConflictResolutionStrategy:
        """
        选择最佳策略
        
        Args:
            divergence: 分歧点
            
        Returns:
            推荐的解决策略
        """
        # 找出所有可以处理该分歧的执行器
        capable_executors = [
            (strategy, executor)
            for strategy, executor in self.executors.items()
            if executor.can_handle(divergence)
        ]
        
        if not capable_executors:
            # 默认使用辩论
            return ConflictResolutionStrategy.DEBATE
        
        # 根据分歧特征选择最佳策略
        # 高强度分歧优先辩论
        if divergence.intensity >= 0.8:
            if ConflictResolutionStrategy.DEBATE in [s for s, _ in capable_executors]:
                return ConflictResolutionStrategy.DEBATE
        
        # 多人参与优先投票
        if len(divergence.proponents) >= 4:
            if ConflictResolutionStrategy.VOTING in [s for s, _ in capable_executors]:
                return ConflictResolutionStrategy.VOTING
        
        # 中等强度优先调解或妥协
        if 0.4 <= divergence.intensity <= 0.7:
            for strategy in [ConflictResolutionStrategy.MEDIATION, 
                           ConflictResolutionStrategy.COMPROMISE]:
                if strategy in [s for s, _ in capable_executors]:
                    return strategy
        
        # 返回第一个可用的
        return capable_executors[0][0]
    
    def execute_session(self, session: ResolutionSession,
                        divergence: 'DivergencePoint'
                       ) -> Generator[Dict[str, Any], None, ResolutionResult]:
        """
        执行解决会话
        
        Args:
            session: 解决会话
            divergence: 分歧点
            
        Yields:
            执行过程中的状态更新
            
        Returns:
            解决结果
        """
        executor = self.executors.get(session.strategy)
        if not executor:
            yield {
                "step": "error",
                "message": f"未找到策略执行器: {session.strategy.value}"
            }
            session.fail(f"未找到策略执行器: {session.strategy.value}")
            return ResolutionResult(
                success=False,
                strategy_used=session.strategy,
                outcome_type=ResolutionOutcomeType.FAILED,
                execution_summary="未找到执行器"
            )
        
        # 创建上下文
        context = ResolutionContext(
            divergence=divergence,
            divergence_id=session.divergence_id,
            participants=session.participants,
            previous_attempts=[h for h in session.history if h.get("event_type") == "execution_attempt"]
        )
        
        yield {
            "step": "execution_started",
            "strategy": session.strategy.value,
            "session_id": session.session_id
        }
        
        # 执行策略
        result = None
        for step_result in executor.execute(context):
            session.add_intermediate_result(step_result.get("step", "unknown"), step_result)
            yield step_result
            
            # 检查是否返回了最终结果
            if isinstance(step_result, ResolutionResult):
                result = step_result
        
        # 处理结果
        if result:
            session.complete(result)
            yield {
                "step": "execution_completed",
                "success": result.success,
                "outcome_type": result.outcome_type.value
            }
        else:
            # 如果生成器没有返回结果，创建一个默认的
            result = ResolutionResult(
                success=False,
                strategy_used=session.strategy,
                outcome_type=ResolutionOutcomeType.PARTIAL,
                execution_summary="执行完成但未返回明确结果"
            )
            session.complete(result)
        
        # 移动到已完成列表
        if session.session_id in self.active_sessions:
            del self.active_sessions[session.session_id]
        self.completed_sessions.append(session)
        
        return result
    
    def escalate_strategy(self, session_id: str,
                          divergence: 'DivergencePoint') -> Optional[ConflictResolutionStrategy]:
        """
        升级策略
        
        Args:
            session_id: 会话ID
            divergence: 分歧点
            
        Returns:
            新策略，如果无法升级则返回 None
        """
        session = self.active_sessions.get(session_id)
        if not session:
            return None
        
        current_index = -1
        if session.strategy in self.STRATEGY_ESCALATION:
            current_index = self.STRATEGY_ESCALATION.index(session.strategy)
        
        # 寻找下一个可用策略
        for i in range(current_index + 1, len(self.STRATEGY_ESCALATION)):
            next_strategy = self.STRATEGY_ESCALATION[i]
            executor = self.executors.get(next_strategy)
            if executor and executor.can_handle(divergence):
                session.escalate(next_strategy)
                return next_strategy
        
        return None
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话状态"""
        session = self.active_sessions.get(session_id)
        if session:
            return session.to_dict()
        
        # 查找已完成的
        for s in self.completed_sessions:
            if s.session_id == session_id:
                return s.to_dict()
        
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        completed_success = sum(1 for s in self.completed_sessions 
                               if s.final_result and s.final_result.success)
        return {
            "active_sessions": len(self.active_sessions),
            "completed_sessions": len(self.completed_sessions),
            "success_rate": completed_success / max(1, len(self.completed_sessions)),
            "total_escalations": sum(s.escalation_count for s in self.completed_sessions),
            "strategy_usage": self._get_strategy_usage()
        }
    
    def _get_strategy_usage(self) -> Dict[str, int]:
        """获取策略使用统计"""
        usage = {}
        for session in self.completed_sessions:
            strategy_name = session.strategy.value
            usage[strategy_name] = usage.get(strategy_name, 0) + 1
        return usage
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_sessions": {
                sid: s.to_dict() for sid, s in self.active_sessions.items()
            },
            "completed_sessions": [s.to_dict() for s in self.completed_sessions],
            "statistics": self.get_statistics()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResolutionOrchestrator':
        orchestrator = cls()
        orchestrator.active_sessions = {
            sid: ResolutionSession.from_dict(s)
            for sid, s in data.get("active_sessions", {}).items()
        }
        orchestrator.completed_sessions = [
            ResolutionSession.from_dict(s)
            for s in data.get("completed_sessions", [])
        ]
        return orchestrator
