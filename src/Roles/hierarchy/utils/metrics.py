"""
多层强化学习智能体系统 - 评估指标
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
import statistics


@dataclass
class MetricValue:
    """指标值"""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSummary:
    """指标摘要"""
    name: str
    count: int = 0
    mean: float = 0.0
    std: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    last_value: float = 0.0


class MetricsCollector:
    """
    指标收集器
    收集和汇总系统运行指标
    """
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self._metrics: Dict[str, List[MetricValue]] = {}
    
    def record(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ):
        """记录指标"""
        if name not in self._metrics:
            self._metrics[name] = []
        
        metric = MetricValue(
            name=name,
            value=value,
            tags=tags or {}
        )
        
        self._metrics[name].append(metric)
        
        # 限制大小
        if len(self._metrics[name]) > self.max_history:
            self._metrics[name] = self._metrics[name][-self.max_history:]
    
    def get_summary(self, name: str) -> Optional[MetricSummary]:
        """获取指标摘要"""
        if name not in self._metrics or not self._metrics[name]:
            return None
        
        values = [m.value for m in self._metrics[name]]
        
        return MetricSummary(
            name=name,
            count=len(values),
            mean=statistics.mean(values),
            std=statistics.stdev(values) if len(values) > 1 else 0.0,
            min_val=min(values),
            max_val=max(values),
            last_value=values[-1]
        )
    
    def get_recent(self, name: str, n: int = 100) -> List[MetricValue]:
        """获取最近的指标值"""
        if name not in self._metrics:
            return []
        return self._metrics[name][-n:]
    
    def get_by_tag(
        self,
        name: str,
        tag_key: str,
        tag_value: str
    ) -> List[MetricValue]:
        """按标签过滤指标"""
        if name not in self._metrics:
            return []
        
        return [
            m for m in self._metrics[name]
            if m.tags.get(tag_key) == tag_value
        ]
    
    def get_all_names(self) -> List[str]:
        """获取所有指标名称"""
        return list(self._metrics.keys())
    
    def clear(self, name: Optional[str] = None):
        """清除指标"""
        if name:
            if name in self._metrics:
                self._metrics[name].clear()
        else:
            self._metrics.clear()


class PerformanceTracker:
    """
    性能跟踪器
    跟踪系统各层和智能体的性能
    """
    
    def __init__(self):
        self.collector = MetricsCollector()
        
        # 预定义指标名
        self.EXECUTION_TIME = "execution_time"
        self.REWARD = "reward"
        self.SUCCESS_RATE = "success_rate"
        self.LAYER_THROUGHPUT = "layer_throughput"
        self.AGENT_CONTRIBUTION = "agent_contribution"
    
    # ==================== 执行时间 ====================
    
    def record_execution_time(
        self,
        layer: int,
        duration: float,
        agent_id: Optional[str] = None
    ):
        """记录执行时间"""
        tags = {"layer": str(layer)}
        if agent_id:
            tags["agent_id"] = agent_id
        
        self.collector.record(self.EXECUTION_TIME, duration, tags)
    
    def get_avg_execution_time(self, layer: Optional[int] = None) -> float:
        """获取平均执行时间"""
        if layer:
            values = self.collector.get_by_tag(
                self.EXECUTION_TIME, "layer", str(layer)
            )
            if values:
                return statistics.mean([v.value for v in values])
            return 0.0
        
        summary = self.collector.get_summary(self.EXECUTION_TIME)
        return summary.mean if summary else 0.0
    
    # ==================== 奖励 ====================
    
    def record_reward(
        self,
        layer: int,
        reward: float,
        iteration: int = 0
    ):
        """记录奖励"""
        self.collector.record(
            self.REWARD,
            reward,
            {"layer": str(layer), "iteration": str(iteration)}
        )
    
    def get_reward_trend(self, n: int = 50) -> List[float]:
        """获取奖励趋势"""
        recent = self.collector.get_recent(self.REWARD, n)
        return [m.value for m in recent]
    
    # ==================== 成功率 ====================
    
    def record_success(self, success: bool, session_id: str = ""):
        """记录成功/失败"""
        self.collector.record(
            self.SUCCESS_RATE,
            1.0 if success else 0.0,
            {"session_id": session_id}
        )
    
    def get_success_rate(self, n: int = 100) -> float:
        """获取成功率"""
        recent = self.collector.get_recent(self.SUCCESS_RATE, n)
        if not recent:
            return 0.0
        return sum(m.value for m in recent) / len(recent)
    
    # ==================== 综合报告 ====================
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {}
        }
        
        for name in self.collector.get_all_names():
            summary = self.collector.get_summary(name)
            if summary:
                report["metrics"][name] = {
                    "count": summary.count,
                    "mean": round(summary.mean, 4),
                    "std": round(summary.std, 4),
                    "min": round(summary.min_val, 4),
                    "max": round(summary.max_val, 4),
                    "last": round(summary.last_value, 4)
                }
        
        # 添加派生指标
        report["derived"] = {
            "success_rate": round(self.get_success_rate(), 4),
            "avg_execution_time": round(self.get_avg_execution_time(), 4),
            "reward_trend": self.get_reward_trend(10)
        }
        
        return report
    
    def reset(self):
        """重置跟踪器"""
        self.collector.clear()
