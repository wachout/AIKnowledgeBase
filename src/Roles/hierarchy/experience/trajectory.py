"""
多层强化学习智能体系统 - 轨迹记录
记录完整的执行轨迹用于策略学习
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
import uuid

from ..types import (
    Experience, LayerType, DecisionOutput, ImplementationOutput, ValidationOutput
)


@dataclass
class TrajectoryStep:
    """轨迹步骤"""
    step_id: str = field(default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}")
    layer: LayerType = LayerType.DECISION
    agent_id: str = ""
    state: Dict[str, Any] = field(default_factory=dict)
    action: str = ""
    reward: float = 0.0
    next_state: Dict[str, Any] = field(default_factory=dict)
    done: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Trajectory:
    """
    完整执行轨迹
    记录从决策到验证的完整流程
    """
    trajectory_id: str = field(default_factory=lambda: f"traj_{uuid.uuid4().hex[:8]}")
    session_id: str = ""
    query: str = ""
    
    # 各层输出
    decision_output: Optional[DecisionOutput] = None
    implementation_outputs: List[ImplementationOutput] = field(default_factory=list)
    validation_output: Optional[ValidationOutput] = None
    
    # 轨迹步骤
    steps: List[TrajectoryStep] = field(default_factory=list)
    
    # 统计
    total_reward: float = 0.0
    iteration: int = 0
    success: bool = False
    
    # 时间
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def add_step(self, step: TrajectoryStep):
        """添加步骤"""
        self.steps.append(step)
        self.total_reward += step.reward
    
    def get_experiences(self) -> List[Experience]:
        """转换为经验列表"""
        experiences = []
        
        for step in self.steps:
            exp = Experience(
                layer=step.layer.value,
                agent_id=step.agent_id,
                state=step.state,
                action=None,  # 需要转换
                reward=step.reward,
                next_state=step.next_state,
                done=step.done,
                timestamp=step.timestamp,
                metadata=step.metadata
            )
            experiences.append(exp)
        
        return experiences
    
    def get_layer_steps(self, layer: LayerType) -> List[TrajectoryStep]:
        """获取指定层的步骤"""
        return [s for s in self.steps if s.layer == layer]
    
    def get_duration(self) -> float:
        """获取执行时长（秒）"""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return (datetime.now() - self.started_at).total_seconds()
    
    def complete(self, success: bool = True):
        """标记轨迹完成"""
        self.completed_at = datetime.now()
        self.success = success
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trajectory_id": self.trajectory_id,
            "session_id": self.session_id,
            "query": self.query,
            "total_reward": self.total_reward,
            "iteration": self.iteration,
            "success": self.success,
            "step_count": len(self.steps),
            "duration": self.get_duration(),
            "layer_distribution": {
                layer.name: len(self.get_layer_steps(layer))
                for layer in LayerType
            }
        }


class TrajectoryRecorder:
    """
    轨迹记录器
    负责记录和管理执行轨迹
    """
    
    def __init__(self, max_trajectories: int = 1000):
        self.max_trajectories = max_trajectories
        self._trajectories: List[Trajectory] = []
        self._current_trajectory: Optional[Trajectory] = None
    
    def start_trajectory(self, session_id: str, query: str) -> Trajectory:
        """开始新轨迹"""
        trajectory = Trajectory(
            session_id=session_id,
            query=query
        )
        self._current_trajectory = trajectory
        return trajectory
    
    def record_step(
        self,
        layer: LayerType,
        agent_id: str,
        state: Dict[str, Any],
        action: str,
        reward: float,
        next_state: Dict[str, Any],
        done: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[TrajectoryStep]:
        """记录步骤"""
        if self._current_trajectory is None:
            return None
        
        step = TrajectoryStep(
            layer=layer,
            agent_id=agent_id,
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=done,
            metadata=metadata or {}
        )
        
        self._current_trajectory.add_step(step)
        return step
    
    def record_decision(self, output: DecisionOutput):
        """记录决策层输出"""
        if self._current_trajectory:
            self._current_trajectory.decision_output = output
    
    def record_implementation(self, output: ImplementationOutput):
        """记录实施层输出"""
        if self._current_trajectory:
            self._current_trajectory.implementation_outputs.append(output)
    
    def record_validation(self, output: ValidationOutput):
        """记录检验层输出"""
        if self._current_trajectory:
            self._current_trajectory.validation_output = output
    
    def end_trajectory(self, success: bool = True) -> Optional[Trajectory]:
        """结束当前轨迹"""
        if self._current_trajectory is None:
            return None
        
        trajectory = self._current_trajectory
        trajectory.complete(success)
        
        # 保存到历史
        self._trajectories.append(trajectory)
        
        # 限制大小
        if len(self._trajectories) > self.max_trajectories:
            self._trajectories = self._trajectories[-self.max_trajectories:]
        
        self._current_trajectory = None
        return trajectory
    
    @property
    def current(self) -> Optional[Trajectory]:
        """获取当前轨迹"""
        return self._current_trajectory
    
    def get_trajectory(self, trajectory_id: str) -> Optional[Trajectory]:
        """获取指定轨迹"""
        for traj in self._trajectories:
            if traj.trajectory_id == trajectory_id:
                return traj
        return None
    
    def get_recent(self, n: int) -> List[Trajectory]:
        """获取最近的轨迹"""
        return self._trajectories[-n:]
    
    def get_successful(self) -> List[Trajectory]:
        """获取成功的轨迹"""
        return [t for t in self._trajectories if t.success]
    
    def get_all_experiences(self) -> List[Experience]:
        """获取所有经验"""
        experiences = []
        for traj in self._trajectories:
            experiences.extend(traj.get_experiences())
        return experiences
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._trajectories:
            return {"total": 0}
        
        successful = [t for t in self._trajectories if t.success]
        
        return {
            "total": len(self._trajectories),
            "successful": len(successful),
            "success_rate": len(successful) / len(self._trajectories),
            "avg_reward": sum(t.total_reward for t in self._trajectories) / len(self._trajectories),
            "avg_steps": sum(len(t.steps) for t in self._trajectories) / len(self._trajectories),
            "avg_duration": sum(t.get_duration() for t in self._trajectories) / len(self._trajectories)
        }
    
    def clear(self):
        """清空所有轨迹"""
        self._trajectories.clear()
        self._current_trajectory = None
