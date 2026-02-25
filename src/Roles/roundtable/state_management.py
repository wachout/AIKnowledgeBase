"""
状态管理模块

包含状态管理相关组件:
- CheckpointStrategy: 检查点策略
- StateHealthMonitor: 状态健康监控器
- StateManager: 统一状态管理器
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime
from pathlib import Path
import json
import threading
import hashlib
import logging

if TYPE_CHECKING:
    from .main import RoundtableDiscussion

logger = logging.getLogger(__name__)


class CheckpointStrategy:
    """
    检查点策略配置
    用于控制何时创建检查点，避免过于频繁的检查点创建
    """
    
    def __init__(self):
        # 时间间隔配置
        self.min_interval_seconds = 60      # 最小间隔 60 秒
        self.max_interval_seconds = 300     # 最大间隔 5 分钟
        
        # 变更计数配置
        self.max_changes_before_checkpoint = 10  # 10 次变更后强制检查点
        
        # 事件触发配置
        self.checkpoint_on_round_complete = True    # 轮次完成时检查点
        self.checkpoint_on_consensus_change = True  # 共识变更时检查点
        self.checkpoint_on_error = True             # 发生错误时检查点
        self.checkpoint_on_agent_join = True        # 智能体加入时检查点
        
        # 状态跟踪
        self.changes_since_checkpoint = 0
        self.last_checkpoint_time = None
        self.checkpoint_history = []  # 记录检查点创建历史
    
    def should_create_checkpoint(self, event_type: str = None) -> bool:
        """
        判断是否应该创建检查点
        
        Args:
            event_type: 事件类型 (round_complete, consensus_change, error, agent_join)
            
        Returns:
            是否应该创建检查点
        """
        now = datetime.now()
        
        # 检查事件触发
        if event_type:
            if event_type == "round_complete" and self.checkpoint_on_round_complete:
                return True
            if event_type == "consensus_change" and self.checkpoint_on_consensus_change:
                return True
            if event_type == "error" and self.checkpoint_on_error:
                return True
            if event_type == "agent_join" and self.checkpoint_on_agent_join:
                return True
        
        # 检查变更计数
        if self.changes_since_checkpoint >= self.max_changes_before_checkpoint:
            return True
        
        # 检查时间间隔
        if self.last_checkpoint_time:
            elapsed = (now - self.last_checkpoint_time).total_seconds()
            
            # 超过最大间隔，强制创建
            if elapsed >= self.max_interval_seconds:
                return True
            
            # 未达到最小间隔，不创建
            if elapsed < self.min_interval_seconds:
                return False
            
            # 在最小和最大间隔之间，根据变更数量决定
            # 变更越多，越容易触发检查点
            threshold = self.max_changes_before_checkpoint * (1 - elapsed / self.max_interval_seconds)
            if self.changes_since_checkpoint >= threshold:
                return True
        
        return False
    
    def record_change(self):
        """记录一次状态变更"""
        self.changes_since_checkpoint += 1
    
    def record_checkpoint(self, checkpoint_name: str):
        """
        记录检查点创建
        
        Args:
            checkpoint_name: 检查点名称
        """
        now = datetime.now()
        self.last_checkpoint_time = now
        self.changes_since_checkpoint = 0
        self.checkpoint_history.append({
            "name": checkpoint_name,
            "timestamp": now.isoformat(),
            "changes_count": self.changes_since_checkpoint
        })
        
        # 限制历史记录数量
        if len(self.checkpoint_history) > 100:
            self.checkpoint_history = self.checkpoint_history[-50:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取检查点统计信息"""
        return {
            "total_checkpoints": len(self.checkpoint_history),
            "changes_since_last": self.changes_since_checkpoint,
            "last_checkpoint_time": self.last_checkpoint_time.isoformat() if self.last_checkpoint_time else None,
            "config": {
                "min_interval_seconds": self.min_interval_seconds,
                "max_interval_seconds": self.max_interval_seconds,
                "max_changes_before_checkpoint": self.max_changes_before_checkpoint
            }
        }


class StateHealthMonitor:
    """
    状态健康监控器
    负责监控各组件状态的一致性和健康度
    """
    
    def __init__(self, discussion: 'RoundtableDiscussion'):
        self.discussion = discussion
        self.health_history = []  # 健康检查历史
        self.anomalies = []  # 异常记录
        self.last_check_time = None
    
    def check_health(self) -> Dict[str, Any]:
        """
        检查状态健康度
        
        Returns:
            健康状态报告
        """
        self.last_check_time = datetime.now()
        
        health_report = {
            "timestamp": self.last_check_time.isoformat(),
            "overall_health": "healthy",
            "health_score": 100,
            "components": {},
            "issues": [],
            "warnings": []
        }
        
        # 检查各组件状态
        health_report["components"]["state_manager"] = self._check_state_manager()
        health_report["components"]["consensus_tracker"] = self._check_consensus_tracker()
        health_report["components"]["discussion_rounds"] = self._check_discussion_rounds()
        health_report["components"]["agents"] = self._check_agents()
        health_report["components"]["exceptions"] = self._check_exceptions()
        
        # 计算总体健康分数
        total_score = 0
        component_count = 0
        
        for component_name, component_status in health_report["components"].items():
            total_score += component_status.get("score", 100)
            component_count += 1
            
            if component_status.get("status") == "critical":
                health_report["issues"].extend(component_status.get("issues", []))
            elif component_status.get("status") == "warning":
                health_report["warnings"].extend(component_status.get("issues", []))
        
        health_report["health_score"] = total_score // component_count if component_count > 0 else 100
        
        # 确定总体健康状态
        if health_report["health_score"] >= 80:
            health_report["overall_health"] = "healthy"
        elif health_report["health_score"] >= 50:
            health_report["overall_health"] = "degraded"
        else:
            health_report["overall_health"] = "critical"
        
        # 记录历史
        self.health_history.append({
            "timestamp": health_report["timestamp"],
            "score": health_report["health_score"],
            "status": health_report["overall_health"]
        })
        
        # 限制历史记录数量
        if len(self.health_history) > 100:
            self.health_history = self.health_history[-50:]
        
        return health_report
    
    def _check_state_manager(self) -> Dict[str, Any]:
        """检查 StateManager 状态"""
        status = {
            "status": "healthy",
            "score": 100,
            "issues": [],
            "details": {}
        }
        
        try:
            state_mgr = self.discussion.state_manager
            
            # 检查状态一致性
            consistency = state_mgr.validate_state_consistency()
            if not consistency.get("is_consistent", True):
                status["status"] = "warning"
                status["score"] -= 20
                status["issues"].extend(consistency.get("issues", []))
            
            # 检查状态漂移
            drift = state_mgr.detect_state_drift()
            if drift.get("drift_detected", False):
                status["status"] = "warning"
                status["score"] -= 30
                status["issues"].append("检测到状态漂移")
            
            # 检查检查点状态
            checkpoint_stats = state_mgr.checkpoint_strategy.get_statistics()
            status["details"]["checkpoints"] = checkpoint_stats
            
            # 检查版本号
            status["details"]["version"] = state_mgr.version
            status["details"]["last_checkpoint_version"] = state_mgr.last_checkpoint_version
            
        except Exception as e:
            status["status"] = "critical"
            status["score"] = 0
            status["issues"].append(f"StateManager 检查失败: {str(e)}")
        
        return status
    
    def _check_consensus_tracker(self) -> Dict[str, Any]:
        """检查 ConsensusTracker 状态"""
        status = {
            "status": "healthy",
            "score": 100,
            "issues": [],
            "details": {}
        }
        
        try:
            tracker = self.discussion.consensus_tracker
            
            # 检查共识和分歧状态
            status["details"]["consensus_count"] = len(tracker.consensus_points)
            status["details"]["divergence_count"] = len(tracker.divergence_points)
            status["details"]["current_round"] = tracker.current_round
            
            # 检查是否有需要辩论的分歧
            debate_required = [dp for dp in tracker.divergence_points if dp.requires_debate]
            if debate_required:
                status["status"] = "warning"
                status["score"] -= 10
                status["issues"].append(f"{len(debate_required)} 个分歧点需要辩论")
            
            # 检查严重分歧
            critical_divergences = [dp for dp in tracker.divergence_points 
                                   if dp.severity.value == "critical"]
            if critical_divergences:
                status["status"] = "warning"
                status["score"] -= 15
                status["issues"].append(f"{len(critical_divergences)} 个严重分歧")
            
        except Exception as e:
            status["status"] = "critical"
            status["score"] = 0
            status["issues"].append(f"ConsensusTracker 检查失败: {str(e)}")
        
        return status
    
    def _check_discussion_rounds(self) -> Dict[str, Any]:
        """检查讨论轮次状态"""
        status = {
            "status": "healthy",
            "score": 100,
            "issues": [],
            "details": {}
        }
        
        try:
            rounds = self.discussion.discussion_rounds
            
            status["details"]["total_rounds"] = len(rounds)
            
            if rounds:
                # 检查轮次连续性
                round_numbers = [r.round_number for r in rounds]
                expected = list(range(1, max(round_numbers) + 1)) if round_numbers else []
                missing = set(expected) - set(round_numbers)
                
                if missing:
                    status["status"] = "warning"
                    status["score"] -= 20
                    status["issues"].append(f"缺失轮次: {sorted(missing)}")
                
                # 检查最后一轮状态
                last_round = rounds[-1]
                status["details"]["last_round_status"] = last_round.get_status()
                status["details"]["last_round_speeches"] = len(last_round.speeches)
            
        except Exception as e:
            status["status"] = "critical"
            status["score"] = 0
            status["issues"].append(f"讨论轮次检查失败: {str(e)}")
        
        return status
    
    def _check_agents(self) -> Dict[str, Any]:
        """检查智能体状态"""
        status = {
            "status": "healthy",
            "score": 100,
            "issues": [],
            "details": {}
        }
        
        try:
            agents = self.discussion.agents
            exception_context = self.discussion.exception_context
            
            status["details"]["total_agents"] = len(agents)
            status["details"]["agent_names"] = list(agents.keys())
            
            # 检查智能体健康状态
            unhealthy_agents = []
            for agent_name, health_record in exception_context.agent_health_records.items():
                health_status = health_record.get("health_status", "healthy")
                if health_status != "healthy":
                    unhealthy_agents.append((agent_name, health_status))
            
            if unhealthy_agents:
                status["status"] = "warning"
                status["score"] -= 10 * len(unhealthy_agents)
                for agent_name, agent_status in unhealthy_agents:
                    status["issues"].append(f"智能体 {agent_name} 状态异常: {agent_status}")
            
            status["details"]["health_records"] = exception_context.agent_health_records
            
        except Exception as e:
            status["status"] = "critical"
            status["score"] = 0
            status["issues"].append(f"智能体检查失败: {str(e)}")
        
        return status
    
    def _check_exceptions(self) -> Dict[str, Any]:
        """检查异常状态"""
        status = {
            "status": "healthy",
            "score": 100,
            "issues": [],
            "details": {}
        }
        
        try:
            exception_context = self.discussion.exception_context
            
            # 获取异常汇总
            summary = exception_context.get_exception_summary(self.discussion.discussion_id)
            status["details"]["exception_summary"] = summary
            
            # 检查未解决的异常
            unresolved = summary.get("unresolved_exceptions", 0)
            if unresolved > 5:
                status["status"] = "warning"
                status["score"] -= 20
                status["issues"].append(f"{unresolved} 个未解决的异常")
            
            # 检查需要人工干预的异常
            intervention_required = summary.get("human_intervention_required", 0)
            if intervention_required > 0:
                status["status"] = "critical"
                status["score"] -= 30
                status["issues"].append(f"{intervention_required} 个异常需要人工干预")
            
            # 检查失败发言
            failed_speeches = exception_context.get_failed_speeches_summary(self.discussion.discussion_id)
            pending_retry = failed_speeches.get("pending_retry", 0)
            if pending_retry > 0:
                status["issues"].append(f"{pending_retry} 个失败发言待重试")
            
            status["details"]["failed_speeches"] = failed_speeches
            
        except Exception as e:
            status["status"] = "critical"
            status["score"] = 0
            status["issues"].append(f"异常检查失败: {str(e)}")
        
        return status
    
    def detect_anomalies(self) -> List[str]:
        """
        检测异常
        
        Returns:
            异常列表
        """
        anomalies = []
        
        # 检查状态漂移
        drift = self.discussion.state_manager.detect_state_drift()
        if drift.get("drift_detected", False):
            anomalies.append("检测到状态漂移")
        
        # 检查健康分数下降趋势
        if len(self.health_history) >= 3:
            recent_scores = [h["score"] for h in self.health_history[-3:]]
            if all(recent_scores[i] > recent_scores[i+1] for i in range(len(recent_scores)-1)):
                anomalies.append("健康分数持续下降")
        
        # 记录异常
        if anomalies:
            self.anomalies.extend([{
                "timestamp": datetime.now().isoformat(),
                "anomaly": a
            } for a in anomalies])
        
        return anomalies
    
    def get_recovery_suggestions(self) -> List[str]:
        """
        获取恢复建议
        
        Returns:
            建议列表
        """
        suggestions = []
        
        # 根据最近的健康检查结果生成建议
        if self.health_history:
            last_health = self.health_history[-1]
            
            if last_health["status"] == "critical":
                suggestions.append("建议立即从最近的检查点恢复")
                suggestions.append("检查并解决所有需要人工干预的异常")
            
            elif last_health["status"] == "degraded":
                suggestions.append("建议重试失败的发言")
                suggestions.append("检查智能体健康状态")
        
        # 根据异常记录生成建议
        exception_context = self.discussion.exception_context
        retry_candidates = exception_context.get_retry_candidates(self.discussion.discussion_id)
        
        if retry_candidates:
            suggestions.append(f"有 {len(retry_candidates)} 个失败发言可以重试")
        
        return suggestions


class StateManager:
    """
    统一状态管理器
    负责整合所有组件状态，提供持久化、检查点和恢复功能
    """

    def __init__(self, discussion_id: str, storage_path: str = "./discussion"):
        # 验证 discussion_id 防止路径遍历攻击
        self.discussion_id = self._sanitize_discussion_id(discussion_id)
        # 状态保存到会议专属文件夹: storage_path/discussion_id/
        self.storage_path = Path(storage_path) / self.discussion_id
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 状态存储
        self.states = {
            "discussion": {},  # 讨论基本信息
            "rounds": {},      # 轮次状态
            "agents": {},      # 智能体状态
            "consensus": {},   # 共识状态
            "moderator": {},   # 主持人状态
            "exceptions": {},  # 异常状态
            "checkpoints": {}  # 检查点
        }

        # 状态锁
        self.state_lock = threading.RLock()

        # 版本控制
        self.version = 0
        self.last_checkpoint_version = 0

        # 状态变更监听器
        self.change_listeners = []
        
        # 智能检查点策略
        self.checkpoint_strategy = CheckpointStrategy()
        
        # 状态哈希历史（用于检测状态漂移）
        self.state_hash_history = []

    def _sanitize_discussion_id(self, discussion_id: str) -> str:
        """
        清理和验证 discussion_id，防止路径遍历攻击
        
        Args:
            discussion_id: 原始的讨论ID
            
        Returns:
            清理后的安全ID
        """
        import re
        
        if not discussion_id:
            discussion_id = f"discussion_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 移除危险字符：路径分隔符、父目录引用等
        # 只允许字母数字、下划线、连字符
        sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '_', discussion_id)
        
        # 移除连续的下划线
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # 限制长度
        sanitized = sanitized[:100]
        
        # 确保不为空
        if not sanitized:
            sanitized = f"discussion_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return sanitized

    def update_discussion_state(self, **kwargs):
        """更新讨论状态"""
        with self.state_lock:
            self.states["discussion"].update(kwargs)
            self.states["discussion"]["last_updated"] = datetime.now().isoformat()
            self._notify_listeners("discussion", kwargs)
            self.version += 1

    def update_round_state(self, round_number: int, **kwargs):
        """更新轮次状态"""
        with self.state_lock:
            round_key = f"round_{round_number}"
            if round_key not in self.states["rounds"]:
                self.states["rounds"][round_key] = {}
            self.states["rounds"][round_key].update(kwargs)
            self.states["rounds"][round_key]["last_updated"] = datetime.now().isoformat()
            self._notify_listeners("rounds", {round_key: kwargs})
            self.version += 1

    def update_agent_state(self, agent_name: str, **kwargs):
        """更新智能体状态"""
        with self.state_lock:
            if agent_name not in self.states["agents"]:
                self.states["agents"][agent_name] = {}
            self.states["agents"][agent_name].update(kwargs)
            self.states["agents"][agent_name]["last_updated"] = datetime.now().isoformat()
            self._notify_listeners("agents", {agent_name: kwargs})
            self.version += 1

    def update_consensus_state(self, **kwargs):
        """更新共识状态"""
        with self.state_lock:
            self.states["consensus"].update(kwargs)
            self.states["consensus"]["last_updated"] = datetime.now().isoformat()
            self._notify_listeners("consensus", kwargs)
            self.version += 1

    def update_moderator_state(self, **kwargs):
        """更新主持人状态"""
        with self.state_lock:
            self.states["moderator"].update(kwargs)
            self.states["moderator"]["last_updated"] = datetime.now().isoformat()
            self._notify_listeners("moderator", kwargs)
            self.version += 1

    def update_exception_state(self, **kwargs):
        """更新异常状态"""
        with self.state_lock:
            self.states["exceptions"].update(kwargs)
            self.states["exceptions"]["last_updated"] = datetime.now().isoformat()
            self._notify_listeners("exceptions", kwargs)
            self.version += 1

    def update_rounds_state(self, rounds: List[Dict[str, Any]], 
                           last_round_action: Dict[str, Any] = None):
        """批量更新轮次状态"""
        with self.state_lock:
            for round_data in rounds:
                round_number = round_data.get("round_number")
                if round_number is not None:
                    round_key = f"round_{round_number}"
                    if round_key not in self.states["rounds"]:
                        self.states["rounds"][round_key] = {}
                    self.states["rounds"][round_key].update(round_data)
                    self.states["rounds"][round_key]["last_updated"] = datetime.now().isoformat()
            
            if last_round_action:
                self.states["rounds"]["last_action"] = last_round_action
            
            self._notify_listeners("rounds", {"rounds_count": len(rounds), "last_action": last_round_action})
            self.version += 1

    def update_agents_state(self, agents: List[str] = None,
                           last_agent_action: Dict[str, Any] = None):
        """更新智能体列表状态"""
        with self.state_lock:
            if agents is not None:
                self.states["agents"]["agent_list"] = agents
                self.states["agents"]["last_updated"] = datetime.now().isoformat()
            
            if last_agent_action:
                self.states["agents"]["last_action"] = last_agent_action
            
            self._notify_listeners("agents", {"agent_list": agents, "last_action": last_agent_action})
            self.version += 1

    def create_checkpoint(self, checkpoint_name: str = None, event_type: str = None) -> str:
        """
        创建检查点
        
        Args:
            checkpoint_name: 检查点名称，如果为 None 则自动生成
            event_type: 事件类型，用于检查点策略判断
            
        Returns:
            检查点名称
        """
        with self.state_lock:
            if checkpoint_name is None:
                checkpoint_name = f"checkpoint_{self.version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            checkpoint_data = {
                "checkpoint_id": checkpoint_name,
                "version": self.version,
                "timestamp": datetime.now().isoformat(),
                "states": self._deep_copy_states(),
                "hash": self._calculate_state_hash(),
                "event_type": event_type
            }

            self.states["checkpoints"][checkpoint_name] = checkpoint_data
            self.last_checkpoint_version = self.version

            # 持久化检查点
            self._persist_checkpoint(checkpoint_data)
            
            # 记录检查点创建
            self.checkpoint_strategy.record_checkpoint(checkpoint_name)
            
            # 记录状态哈希历史
            self._record_state_hash(checkpoint_data["hash"])

            self._notify_listeners("checkpoints", {checkpoint_name: checkpoint_data})
            logger.debug(f"创建检查点: {checkpoint_name}")
            return checkpoint_name

    def smart_checkpoint(self, event_type: str = None) -> Optional[str]:
        """
        智能检查点 - 根据策略判断是否需要创建检查点
        
        Args:
            event_type: 事件类型 (round_complete, consensus_change, error, agent_join)
            
        Returns:
            检查点名称或 None（如果不需要创建）
        """
        if self.checkpoint_strategy.should_create_checkpoint(event_type):
            checkpoint_name = f"auto_{event_type or 'periodic'}_{datetime.now().strftime('%H%M%S')}"
            return self.create_checkpoint(checkpoint_name, event_type)
        return None

    def _deep_copy_states(self) -> Dict[str, Any]:
        """深度复制状态，避免引用问题"""
        import copy
        # 排除 checkpoints 以避免循环引用
        states_copy = {}
        for key, value in self.states.items():
            if key != "checkpoints":
                states_copy[key] = copy.deepcopy(value)
            else:
                # 只保存检查点的元数据，不保存完整状态
                states_copy[key] = {
                    k: {"checkpoint_id": v.get("checkpoint_id"), 
                        "version": v.get("version"),
                        "timestamp": v.get("timestamp")}
                    for k, v in value.items()
                }
        return states_copy

    def _record_state_hash(self, state_hash: str):
        """记录状态哈希历史"""
        self.state_hash_history.append({
            "hash": state_hash,
            "version": self.version,
            "timestamp": datetime.now().isoformat()
        })
        # 限制历史记录数量
        if len(self.state_hash_history) > 100:
            self.state_hash_history = self.state_hash_history[-50:]

    def detect_state_drift(self) -> Dict[str, Any]:
        """
        检测状态漂移
        
        Returns:
            漂移检测结果
        """
        current_hash = self._calculate_state_hash()
        
        result = {
            "current_hash": current_hash,
            "drift_detected": False,
            "drift_details": []
        }
        
        if self.state_hash_history:
            last_hash = self.state_hash_history[-1]["hash"]
            last_version = self.state_hash_history[-1]["version"]
            
            # 如果版本相同但哈希不同，说明发生了漂移
            if self.version == last_version and current_hash != last_hash:
                result["drift_detected"] = True
                result["drift_details"].append({
                    "type": "hash_mismatch",
                    "expected_hash": last_hash,
                    "actual_hash": current_hash,
                    "version": self.version
                })
        
        return result

    def restore_from_checkpoint(self, checkpoint_name: str) -> bool:
        """从检查点恢复状态"""
        with self.state_lock:
            if checkpoint_name not in self.states["checkpoints"]:
                return False

            checkpoint_data = self.states["checkpoints"][checkpoint_name]
            self.states = checkpoint_data["states"].copy()
            self.version = checkpoint_data["version"]

            self._notify_listeners("restore", {"checkpoint": checkpoint_name, "version": self.version})
            return True

    def persist_state(self):
        """持久化当前状态"""
        state_file = self.storage_path / "roundtable_state.json"  # 使用不同文件名避免和业务层 discussion_state.json 冲突
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump({
                "discussion_id": self.discussion_id,
                "version": self.version,
                "last_checkpoint_version": self.last_checkpoint_version,
                "timestamp": datetime.now().isoformat(),
                "states": self.states
            }, f, ensure_ascii=False, indent=2)

    def load_state(self) -> bool:
        """
        加载持久化状态
        
        处理多种边界情况：
        - 文件不存在
        - 文件为空（刚创建还未写入）
        - 文件正在写入中（JSON不完整）
        - 文件格式不兼容（由其他系统创建）
        """
        state_file = self.storage_path / "roundtable_state.json"  # 使用不同文件名避免和业务层 discussion_state.json 冲突
        if not state_file.exists():
            return False

        try:
            # 检查文件是否为空（可能刚创建还未写入）
            file_size = state_file.stat().st_size
            if file_size == 0:
                logger.info(f"状态文件为空（可能正在初始化），跳过加载")
                return False
            
            # 读取文件内容
            with open(state_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查内容是否为空白
            if not content or not content.strip():
                logger.info(f"状态文件内容为空，跳过加载")
                return False
            
            # 尝试解析 JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError as je:
                # JSON 解析失败，可能文件正在写入中或损坏
                logger.warning(f"状态文件 JSON 解析失败（可能文件正在写入中）: {je}")
                return False
            
            # 检查解析结果是否为字典
            if not isinstance(data, dict):
                logger.warning(f"状态文件格式错误：期望字典，实际为 {type(data).__name__}")
                return False

            # 兼容性检查：检查是否是 StateManager 创建的格式
            # 如果没有 'states' 键，可能是 control_discussion.py 创建的业务状态文件
            if "states" not in data:
                logger.info(f"状态文件格式不兼容（缺少 'states' 键），可能是业务层状态文件，跳过加载")
                return False
            
            if "version" not in data:
                logger.info(f"状态文件格式不兼容（缺少 'version' 键），跳过加载")
                return False

            self.states = data["states"]
            self.version = data["version"]
            self.last_checkpoint_version = data.get("last_checkpoint_version", 0)

            self._notify_listeners("loaded", {"version": self.version})
            logger.info(f"成功加载状态，版本: {self.version}")
            return True
            
        except FileNotFoundError:
            # 文件在检查后被删除
            logger.info(f"状态文件不存在或已被删除")
            return False
        except PermissionError:
            # 文件被占用（可能正在写入）
            logger.warning(f"状态文件被占用（可能正在写入），跳过加载")
            return False
        except Exception as e:
            logger.error(f"加载状态失败: {type(e).__name__}: {e}")
            return False

    def _persist_checkpoint(self, checkpoint_data: Dict[str, Any]):
        """持久化检查点"""
        checkpoint_file = self.storage_path / f"checkpoint_{checkpoint_data['checkpoint_id']}.json"
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)

    def _calculate_state_hash(self) -> str:
        """计算状态哈希"""
        state_str = json.dumps(self.states, sort_keys=True, default=str)
        return hashlib.sha256(state_str.encode()).hexdigest()

    def add_change_listener(self, listener: callable):
        """添加状态变更监听器"""
        self.change_listeners.append(listener)

    def remove_change_listener(self, listener: callable):
        """移除状态变更监听器"""
        if listener in self.change_listeners:
            self.change_listeners.remove(listener)

    def _notify_listeners(self, state_type: str, changes: Dict[str, Any]):
        """通知监听器"""
        for listener in self.change_listeners:
            try:
                listener(state_type, changes)
            except Exception as e:
                logger.error(f"状态变更监听器执行失败: {e}")

    def get_state_summary(self) -> Dict[str, Any]:
        """获取状态摘要"""
        with self.state_lock:
            return {
                "discussion_id": self.discussion_id,
                "version": self.version,
                "last_checkpoint_version": self.last_checkpoint_version,
                "total_checkpoints": len(self.states["checkpoints"]),
                "total_rounds": len(self.states["rounds"]),
                "total_agents": len(self.states["agents"]),
                "consensus_points": len(self.states["consensus"].get("consensus_points", [])),
                "divergence_points": len(self.states["consensus"].get("divergence_points", [])),
                "last_updated": max(
                    self.states["discussion"].get("last_updated", ""),
                    *[round_data.get("last_updated", "") for round_data in self.states["rounds"].values()],
                    *[agent_data.get("last_updated", "") for agent_data in self.states["agents"].values()],
                    self.states["consensus"].get("last_updated", ""),
                    self.states["moderator"].get("last_updated", ""),
                    self.states["exceptions"].get("last_updated", "")
                )
            }

    def validate_state_consistency(self) -> Dict[str, Any]:
        """验证状态一致性"""
        issues = []

        # 检查轮次连续性
        round_numbers = []
        for round_key in self.states["rounds"].keys():
            try:
                round_num = int(round_key.split("_")[1])
                round_numbers.append(round_num)
            except (IndexError, ValueError):
                issues.append(f"无效的轮次键: {round_key}")

        if round_numbers:
            round_numbers.sort()
            expected_rounds = list(range(1, max(round_numbers) + 1))
            missing_rounds = set(expected_rounds) - set(round_numbers)
            if missing_rounds:
                issues.append(f"缺少轮次: {sorted(missing_rounds)}")

        # 检查智能体状态完整性
        for agent_name, agent_state in self.states["agents"].items():
            if not agent_state.get("role"):
                issues.append(f"智能体 {agent_name} 缺少角色信息")
            if not agent_state.get("health_status"):
                issues.append(f"智能体 {agent_name} 缺少健康状态")

        # 检查共识状态
        consensus_state = self.states["consensus"]
        if "consensus_points" in consensus_state and "divergence_points" in consensus_state:
            total_points = len(consensus_state["consensus_points"]) + len(consensus_state["divergence_points"])
            if total_points == 0 and len(self.states["rounds"]) > 1:
                issues.append("多轮讨论后仍无共识或分歧点")

        return {
            "is_consistent": len(issues) == 0,
            "issues": issues,
            "checked_at": datetime.now().isoformat()
        }
