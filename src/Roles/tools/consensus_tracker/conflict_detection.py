"""
共识追踪系统 - 冲突检测与触发
包含冲突自动检测器和冲突触发管理器。
"""

from typing import Dict, Any, List, Tuple, Optional, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from .types import ConflictSeverity
from .divergence_point import ConflictResolutionStrategy

if TYPE_CHECKING:
    from .divergence_point import DivergencePoint
    from .tracker import EnhancedConsensusTracker


class ConflictTriggerCondition(Enum):
    """冲突触发条件"""
    INTENSITY_THRESHOLD = "intensity"       # 强度超过阈值
    OPPOSING_POSITIONS = "opposing"         # 对立立场数量
    STAGNATION = "stagnation"               # 分歧停滞
    ESCALATION = "escalation"               # 分歧升级
    EXPERT_REQUEST = "expert_request"       # 专家主动请求
    POLARIZATION = "polarization"           # 极化（两极分化）
    DEADLOCK = "deadlock"                   # 僵局


@dataclass
class ConflictAlert:
    """冲突警报"""
    alert_id: str
    divergence_id: str
    trigger_condition: ConflictTriggerCondition
    severity: ConflictSeverity
    recommended_strategy: ConflictResolutionStrategy
    urgency_score: float  # 0-1 紧急程度
    participants: List[str] = field(default_factory=list)
    created_at: str = None
    acknowledged: bool = False
    acknowledged_at: str = None
    trigger_details: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if not self.alert_id:
            self.alert_id = f"alert_{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(self) % 10000}"
    
    def acknowledge(self) -> None:
        """确认警报"""
        self.acknowledged = True
        self.acknowledged_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "divergence_id": self.divergence_id,
            "trigger_condition": self.trigger_condition.value,
            "severity": self.severity.value,
            "recommended_strategy": self.recommended_strategy.value,
            "urgency_score": self.urgency_score,
            "participants": self.participants,
            "created_at": self.created_at,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at,
            "trigger_details": self.trigger_details
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConflictAlert':
        return cls(
            alert_id=data.get("alert_id", ""),
            divergence_id=data.get("divergence_id", ""),
            trigger_condition=ConflictTriggerCondition(data.get("trigger_condition", "intensity")),
            severity=ConflictSeverity(data.get("severity", "medium")),
            recommended_strategy=ConflictResolutionStrategy(data.get("recommended_strategy", "debate")),
            urgency_score=data.get("urgency_score", 0.5),
            participants=data.get("participants", []),
            created_at=data.get("created_at"),
            acknowledged=data.get("acknowledged", False),
            acknowledged_at=data.get("acknowledged_at"),
            trigger_details=data.get("trigger_details", {})
        )


class ConflictDetector:
    """
    冲突自动检测器
    
    实时监控分歧状态，根据多种触发条件识别需要干预的冲突。
    """
    
    # 阈值配置
    INTENSITY_THRESHOLD = 0.7              # 强度触发阈值
    OPPOSING_THRESHOLD = 2                 # 对立立场数量阈值
    STAGNATION_ROUNDS = 3                  # 停滞轮次阈值
    ESCALATION_RATE_THRESHOLD = 0.15       # 升级速率阈值
    POLARIZATION_THRESHOLD = 0.8           # 极化阈值
    AUTO_TRIGGER_URGENCY = 0.75            # 自动触发的紧急程度阈值
    
    # 严重程度权重
    SEVERITY_WEIGHTS = {
        ConflictSeverity.CRITICAL: 1.0,
        ConflictSeverity.HIGH: 0.8,
        ConflictSeverity.MEDIUM: 0.5,
        ConflictSeverity.LOW: 0.3
    }
    
    # 策略推荐映射
    CONDITION_STRATEGY_MAP = {
        ConflictTriggerCondition.INTENSITY_THRESHOLD: ConflictResolutionStrategy.DEBATE,
        ConflictTriggerCondition.OPPOSING_POSITIONS: ConflictResolutionStrategy.MEDIATION,
        ConflictTriggerCondition.STAGNATION: ConflictResolutionStrategy.DATA_DRIVEN,
        ConflictTriggerCondition.ESCALATION: ConflictResolutionStrategy.DEBATE,
        ConflictTriggerCondition.EXPERT_REQUEST: ConflictResolutionStrategy.EXPERT_REVIEW,
        ConflictTriggerCondition.POLARIZATION: ConflictResolutionStrategy.COMPROMISE,
        ConflictTriggerCondition.DEADLOCK: ConflictResolutionStrategy.VOTING
    }
    
    def __init__(self):
        self.detection_history: List[Dict[str, Any]] = []
        self.intensity_history: Dict[str, List[float]] = {}  # divergence_id -> [intensities]
    
    def monitor_divergences(self, divergences: List['DivergencePoint'],
                            current_round: int) -> List[ConflictAlert]:
        """
        监控所有分歧点，返回需要触发的冲突警报
        
        Args:
            divergences: 分歧点列表
            current_round: 当前轮次
            
        Returns:
            触发的冲突警报列表
        """
        alerts = []
        
        for idx, divergence in enumerate(divergences):
            divergence_id = f"div_{idx}"
            
            # 更新强度历史
            if divergence_id not in self.intensity_history:
                self.intensity_history[divergence_id] = []
            self.intensity_history[divergence_id].append(divergence.intensity)
            
            # 检测各种触发条件
            triggered_conditions = []
            
            # 1. 检测强度超过阈值
            if divergence.intensity >= self.INTENSITY_THRESHOLD:
                triggered_conditions.append((
                    ConflictTriggerCondition.INTENSITY_THRESHOLD,
                    {"intensity": divergence.intensity, "threshold": self.INTENSITY_THRESHOLD}
                ))
            
            # 2. 检测对立立场数量
            if len(divergence.opposing_positions) >= self.OPPOSING_THRESHOLD:
                triggered_conditions.append((
                    ConflictTriggerCondition.OPPOSING_POSITIONS,
                    {"opposing_count": len(divergence.opposing_positions),
                     "threshold": self.OPPOSING_THRESHOLD}
                ))
            
            # 3. 检测分歧停滞
            if self._detect_stagnation(divergence_id, current_round, divergence):
                triggered_conditions.append((
                    ConflictTriggerCondition.STAGNATION,
                    {"stagnation_rounds": self._get_stagnation_rounds(divergence_id),
                     "threshold": self.STAGNATION_ROUNDS}
                ))
            
            # 4. 检测分歧升级
            escalation_rate = self._detect_escalation(divergence_id)
            if escalation_rate >= self.ESCALATION_RATE_THRESHOLD:
                triggered_conditions.append((
                    ConflictTriggerCondition.ESCALATION,
                    {"escalation_rate": escalation_rate,
                     "threshold": self.ESCALATION_RATE_THRESHOLD}
                ))
            
            # 5. 检测专家主动请求
            if divergence.requires_debate and divergence.debate_suggested_by:
                triggered_conditions.append((
                    ConflictTriggerCondition.EXPERT_REQUEST,
                    {"suggested_by": divergence.debate_suggested_by}
                ))
            
            # 6. 检测极化
            polarization_score = self._detect_polarization(divergence)
            if polarization_score >= self.POLARIZATION_THRESHOLD:
                triggered_conditions.append((
                    ConflictTriggerCondition.POLARIZATION,
                    {"polarization_score": polarization_score,
                     "threshold": self.POLARIZATION_THRESHOLD}
                ))
            
            # 7. 检测僵局
            if self._detect_deadlock(divergence, current_round):
                triggered_conditions.append((
                    ConflictTriggerCondition.DEADLOCK,
                    {"resolution_attempts": divergence.resolution_attempts,
                     "rounds_since_created": current_round - divergence.round_created}
                ))
            
            # 如果有触发条件，创建警报
            if triggered_conditions:
                # 选择最严重的触发条件
                primary_condition, details = self._select_primary_condition(triggered_conditions)
                
                alert = self._create_alert(
                    divergence_id=divergence_id,
                    divergence=divergence,
                    trigger_condition=primary_condition,
                    trigger_details=details,
                    all_conditions=triggered_conditions
                )
                
                alerts.append(alert)
                
                # 记录检测历史
                self.detection_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "divergence_id": divergence_id,
                    "round": current_round,
                    "triggered_conditions": [c[0].value for c in triggered_conditions],
                    "alert_id": alert.alert_id
                })
        
        return alerts
    
    def _detect_stagnation(self, divergence_id: str, current_round: int,
                          divergence: 'DivergencePoint') -> bool:
        """检测分歧是否停滞"""
        history = self.intensity_history.get(divergence_id, [])
        if len(history) < self.STAGNATION_ROUNDS:
            return False
        
        # 检查最近几轮的强度变化
        recent = history[-self.STAGNATION_ROUNDS:]
        variance = sum((x - sum(recent)/len(recent))**2 for x in recent) / len(recent)
        
        # 方差很小且强度持续较高表示停滞
        return variance < 0.01 and sum(recent)/len(recent) > 0.5
    
    def _get_stagnation_rounds(self, divergence_id: str) -> int:
        """获取停滞的轮次数"""
        history = self.intensity_history.get(divergence_id, [])
        if len(history) < 2:
            return 0
        
        count = 0
        avg = sum(history[-3:]) / min(3, len(history))
        for intensity in reversed(history):
            if abs(intensity - avg) < 0.05:
                count += 1
            else:
                break
        return count
    
    def _detect_escalation(self, divergence_id: str) -> float:
        """检测分歧升级速率"""
        history = self.intensity_history.get(divergence_id, [])
        if len(history) < 2:
            return 0.0
        
        # 计算平均增长率
        deltas = [history[i] - history[i-1] for i in range(1, len(history))]
        return sum(max(0, d) for d in deltas[-3:]) / min(3, len(deltas)) if deltas else 0.0
    
    def _detect_polarization(self, divergence: 'DivergencePoint') -> float:
        """检测立场极化程度"""
        if len(divergence.proponents) < 2:
            return 0.0
        
        # 极化程度基于对立立场的数量和参与者分布
        opposing_ratio = len(divergence.opposing_positions) / max(1, len(divergence.proponents))
        participant_count = len(divergence.proponents)
        
        # 参与者多且对立比例高表示极化
        polarization = min(1.0, opposing_ratio * 0.6 + (participant_count / 5) * 0.4)
        return polarization
    
    def _detect_deadlock(self, divergence: 'DivergencePoint', current_round: int) -> bool:
        """检测是否进入僵局"""
        # 多次尝试解决但仍未解决
        has_multiple_attempts = divergence.resolution_attempts >= 2
        # 持续时间较长
        long_duration = (current_round - divergence.round_created) >= 4
        # 强度仍然较高
        still_intense = divergence.intensity >= 0.6
        
        return has_multiple_attempts and long_duration and still_intense
    
    def _select_primary_condition(self, conditions: List[Tuple[ConflictTriggerCondition, Dict]]
                                  ) -> Tuple[ConflictTriggerCondition, Dict]:
        """选择最主要的触发条件"""
        # 优先级排序
        priority_order = [
            ConflictTriggerCondition.DEADLOCK,
            ConflictTriggerCondition.ESCALATION,
            ConflictTriggerCondition.POLARIZATION,
            ConflictTriggerCondition.EXPERT_REQUEST,
            ConflictTriggerCondition.INTENSITY_THRESHOLD,
            ConflictTriggerCondition.OPPOSING_POSITIONS,
            ConflictTriggerCondition.STAGNATION
        ]
        
        for priority_condition in priority_order:
            for condition, details in conditions:
                if condition == priority_condition:
                    return condition, details
        
        return conditions[0]
    
    def _create_alert(self, divergence_id: str, divergence: 'DivergencePoint',
                     trigger_condition: ConflictTriggerCondition,
                     trigger_details: Dict[str, Any],
                     all_conditions: List[Tuple[ConflictTriggerCondition, Dict]]) -> ConflictAlert:
        """创建冲突警报"""
        # 计算紧急程度
        urgency = self.calculate_urgency_score(divergence, all_conditions)
        
        # 确定严重程度
        severity = self._determine_severity(divergence, all_conditions)
        
        # 推荐策略
        strategy = self._recommend_strategy(trigger_condition, divergence, all_conditions)
        
        return ConflictAlert(
            alert_id="",  # 自动生成
            divergence_id=divergence_id,
            trigger_condition=trigger_condition,
            severity=severity,
            recommended_strategy=strategy,
            urgency_score=urgency,
            participants=list(divergence.proponents.keys()),
            trigger_details={
                "primary": trigger_details,
                "all_conditions": [
                    {"condition": c.value, "details": d}
                    for c, d in all_conditions
                ]
            }
        )
    
    def calculate_urgency_score(self, divergence: 'DivergencePoint',
                                conditions: List[Tuple[ConflictTriggerCondition, Dict]]) -> float:
        """
        计算冲突的紧急程度
        
        综合考虑：
        1. 分歧强度
        2. 触发条件数量
        3. 严重程度
        4. 参与者数量
        5. 对立立场数量
        """
        # 基础分数：分歧强度
        base_score = divergence.intensity
        
        # 条件加成：触发条件越多越紧急
        condition_bonus = min(0.3, len(conditions) * 0.1)
        
        # 严重程度加成
        severity_bonus = self.SEVERITY_WEIGHTS.get(divergence.severity, 0.5) * 0.2
        
        # 参与者加成：涉及人数越多越紧急
        participant_bonus = min(0.15, len(divergence.proponents) * 0.03)
        
        # 对立立场加成
        opposing_bonus = min(0.15, len(divergence.opposing_positions) * 0.05)
        
        urgency = base_score * 0.4 + condition_bonus + severity_bonus + participant_bonus + opposing_bonus
        return min(1.0, urgency)
    
    def _determine_severity(self, divergence: 'DivergencePoint',
                           conditions: List[Tuple[ConflictTriggerCondition, Dict]]) -> ConflictSeverity:
        """确定冲突严重程度"""
        # 已有严重程度为 CRITICAL 或 HIGH 的直接采用
        if divergence.severity in [ConflictSeverity.CRITICAL, ConflictSeverity.HIGH]:
            return divergence.severity
        
        # 根据条件数量和类型判断
        critical_conditions = [
            ConflictTriggerCondition.DEADLOCK,
            ConflictTriggerCondition.ESCALATION
        ]
        high_conditions = [
            ConflictTriggerCondition.POLARIZATION,
            ConflictTriggerCondition.INTENSITY_THRESHOLD
        ]
        
        condition_types = [c for c, _ in conditions]
        
        if any(c in critical_conditions for c in condition_types):
            return ConflictSeverity.CRITICAL
        if any(c in high_conditions for c in condition_types) or len(conditions) >= 3:
            return ConflictSeverity.HIGH
        if len(conditions) >= 2:
            return ConflictSeverity.MEDIUM
        return ConflictSeverity.LOW
    
    def _recommend_strategy(self, primary_condition: ConflictTriggerCondition,
                           divergence: 'DivergencePoint',
                           all_conditions: List[Tuple[ConflictTriggerCondition, Dict]]
                           ) -> ConflictResolutionStrategy:
        """推荐解决策略"""
        # 获取默认策略
        default_strategy = self.CONDITION_STRATEGY_MAP.get(
            primary_condition, ConflictResolutionStrategy.DEBATE
        )
        
        # 根据特殊情况调整
        # 如果有很多对立立场，优先调解
        if len(divergence.opposing_positions) >= 4:
            return ConflictResolutionStrategy.MEDIATION
        
        # 如果多次尝试失败，考虑投票
        if divergence.resolution_attempts >= 3:
            return ConflictResolutionStrategy.VOTING
        
        # 如果强度极高，直接辩论
        if divergence.intensity >= 0.9:
            return ConflictResolutionStrategy.DEBATE
        
        return default_strategy
    
    def should_auto_trigger(self, alert: ConflictAlert) -> bool:
        """判断是否应该自动触发解决流程"""
        return (
            alert.urgency_score >= self.AUTO_TRIGGER_URGENCY or
            alert.severity in [ConflictSeverity.CRITICAL, ConflictSeverity.HIGH] or
            alert.trigger_condition in [
                ConflictTriggerCondition.DEADLOCK,
                ConflictTriggerCondition.ESCALATION
            ]
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "detection_history": self.detection_history,
            "intensity_history": self.intensity_history
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConflictDetector':
        detector = cls()
        detector.detection_history = data.get("detection_history", [])
        detector.intensity_history = data.get("intensity_history", {})
        return detector


class ConflictTriggerManager:
    """
    冲突触发管理器
    
    管理冲突警报的生命周期，协调检测、触发和解决流程。
    """
    
    def __init__(self, consensus_tracker: 'EnhancedConsensusTracker' = None):
        self.consensus_tracker = consensus_tracker
        self.detector = ConflictDetector()
        self.pending_alerts: List[ConflictAlert] = []
        self.triggered_alerts: List[ConflictAlert] = []
        self.resolved_alerts: List[ConflictAlert] = []
        self.auto_trigger_enabled: bool = True
        self.last_check_round: int = 0
    
    def set_consensus_tracker(self, tracker: 'EnhancedConsensusTracker') -> None:
        """设置关联的共识追踪器"""
        self.consensus_tracker = tracker
    
    def check_and_trigger(self, current_round: int) -> List[ConflictAlert]:
        """
        检查并返回需要触发的冲突
        
        Args:
            current_round: 当前轮次
            
        Returns:
            需要触发的冲突警报列表
        """
        if not self.consensus_tracker:
            return []
        
        # 避免同一轮重复检查
        if current_round == self.last_check_round:
            return self.get_pending_auto_triggers()
        
        self.last_check_round = current_round
        
        # 监控所有分歧
        divergences = self.consensus_tracker.divergence_points
        new_alerts = self.detector.monitor_divergences(divergences, current_round)
        
        # 过滤已存在的警报（避免重复）
        existing_ids = {a.divergence_id for a in self.pending_alerts + self.triggered_alerts}
        new_alerts = [a for a in new_alerts if a.divergence_id not in existing_ids]
        
        # 添加到待处理列表
        self.pending_alerts.extend(new_alerts)
        
        # 返回需要自动触发的警报
        auto_triggers = []
        if self.auto_trigger_enabled:
            auto_triggers = self.get_pending_auto_triggers()
        
        return auto_triggers
    
    def get_pending_auto_triggers(self) -> List[ConflictAlert]:
        """获取待处理的自动触发警报"""
        return [
            alert for alert in self.pending_alerts
            if self.detector.should_auto_trigger(alert) and not alert.acknowledged
        ]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        确认警报，准备启动解决流程
        
        Args:
            alert_id: 警报ID
            
        Returns:
            是否成功确认
        """
        for alert in self.pending_alerts:
            if alert.alert_id == alert_id:
                alert.acknowledge()
                return True
        return False
    
    def start_resolution(self, alert_id: str) -> Optional[ConflictAlert]:
        """
        将警报移至触发状态
        
        Args:
            alert_id: 警报ID
            
        Returns:
            被触发的警报
        """
        for i, alert in enumerate(self.pending_alerts):
            if alert.alert_id == alert_id:
                triggered = self.pending_alerts.pop(i)
                self.triggered_alerts.append(triggered)
                return triggered
        return None
    
    def complete_resolution(self, alert_id: str, success: bool = True) -> bool:
        """
        完成解决流程
        
        Args:
            alert_id: 警报ID
            success: 是否成功解决
            
        Returns:
            是否成功完成
        """
        for i, alert in enumerate(self.triggered_alerts):
            if alert.alert_id == alert_id:
                resolved = self.triggered_alerts.pop(i)
                self.resolved_alerts.append(resolved)
                return True
        return False
    
    def get_priority_conflicts(self, max_count: int = 3) -> List[ConflictAlert]:
        """
        获取优先处理的冲突
        
        Args:
            max_count: 最大返回数量
            
        Returns:
            按优先级排序的冲突警报
        """
        # 按紧急程度和严重程度排序
        sorted_alerts = sorted(
            self.pending_alerts,
            key=lambda a: (
                -a.urgency_score,
                -{
                    ConflictSeverity.CRITICAL: 4,
                    ConflictSeverity.HIGH: 3,
                    ConflictSeverity.MEDIUM: 2,
                    ConflictSeverity.LOW: 1
                }.get(a.severity, 0)
            )
        )
        return sorted_alerts[:max_count]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取管理器统计信息"""
        return {
            "pending_count": len(self.pending_alerts),
            "triggered_count": len(self.triggered_alerts),
            "resolved_count": len(self.resolved_alerts),
            "auto_trigger_enabled": self.auto_trigger_enabled,
            "last_check_round": self.last_check_round,
            "detection_history_count": len(self.detector.detection_history)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pending_alerts": [a.to_dict() for a in self.pending_alerts],
            "triggered_alerts": [a.to_dict() for a in self.triggered_alerts],
            "resolved_alerts": [a.to_dict() for a in self.resolved_alerts],
            "auto_trigger_enabled": self.auto_trigger_enabled,
            "last_check_round": self.last_check_round,
            "detector": self.detector.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], 
                  consensus_tracker: 'EnhancedConsensusTracker' = None) -> 'ConflictTriggerManager':
        manager = cls(consensus_tracker)
        manager.pending_alerts = [
            ConflictAlert.from_dict(a) for a in data.get("pending_alerts", [])
        ]
        manager.triggered_alerts = [
            ConflictAlert.from_dict(a) for a in data.get("triggered_alerts", [])
        ]
        manager.resolved_alerts = [
            ConflictAlert.from_dict(a) for a in data.get("resolved_alerts", [])
        ]
        manager.auto_trigger_enabled = data.get("auto_trigger_enabled", True)
        manager.last_check_round = data.get("last_check_round", 0)
        if "detector" in data:
            manager.detector = ConflictDetector.from_dict(data["detector"])
        return manager
