"""
异常上下文模块

包含智能体异常上下文记录:
- AgentExceptionContext: 智能体异常上下文记录
"""

from typing import Dict, Any, List
from datetime import datetime
import logging
import traceback

logger = logging.getLogger(__name__)


class AgentExceptionContext:
    """
    智能体异常上下文记录
    负责记录和管理讨论过程中的所有异常信息
    """

    def __init__(self):
        self.exception_history = []
        self.agent_health_records = {}
        self.failed_speeches = {}  # 记录失败的发言，用于二次请求
        self.retry_queue = []  # 重试队列

    def record_exception(self, discussion_id: str, round_number: int, speaker_name: str,
                        exception_type: str, error_message: str, stage: str,
                        attempt_count: int, context_info: Dict[str, Any],
                        requires_human_intervention: bool = False,
                        intervention_suggestions: List[str] = None,
                        llm_request_info: Dict[str, Any] = None,
                        llm_response_info: Dict[str, Any] = None,
                        stack_trace: str = None,
                        recovery_action: str = None):
        """
        记录异常信息

        Args:
            discussion_id: 讨论ID
            round_number: 讨论轮次
            speaker_name: 智能体名称
            exception_type: 异常类型 (timeout, network, content_filter, etc.)
            error_message: 错误信息
            stage: 异常发生的阶段 (thinking, speaking, coordination)
            attempt_count: 尝试次数
            context_info: 上下文信息
            requires_human_intervention: 是否需要人工干预
            intervention_suggestions: 人工干预建议
            llm_request_info: LLM 请求信息（用于调试）
            llm_response_info: LLM 响应信息（用于调试）
            stack_trace: 完整调用栈
            recovery_action: 已采取的恢复措施
        """
        # 如果没有提供调用栈，自动获取
        if stack_trace is None:
            stack_trace = traceback.format_exc()
        
        exception_record = {
            "exception_id": f"exc_{discussion_id}_{round_number}_{speaker_name}_{datetime.now().strftime('%H%M%S%f')}",
            "discussion_id": discussion_id,
            "round_number": round_number,
            "speaker_name": speaker_name,
            "exception_type": exception_type,
            "error_message": error_message,
            "stage": stage,
            "attempt_count": attempt_count,
            "timestamp": datetime.now().isoformat(),
            "context_info": context_info,
            "requires_human_intervention": requires_human_intervention,
            "intervention_suggestions": intervention_suggestions or [],
            "llm_request_info": llm_request_info or {},
            "llm_response_info": llm_response_info or {},
            "stack_trace": stack_trace,
            "recovery_action": recovery_action or "pending",
            "resolved": False,
            "resolution_time": None,
            "resolution_notes": "",
            "can_retry": self._can_retry(exception_type, attempt_count)
        }

        self.exception_history.append(exception_record)

        # 更新智能体健康记录
        if speaker_name not in self.agent_health_records:
            self.agent_health_records[speaker_name] = {
                "total_exceptions": 0,
                "exception_types": {},
                "last_exception_time": None,
                "health_status": "healthy"
            }

        agent_record = self.agent_health_records[speaker_name]
        agent_record["total_exceptions"] += 1
        agent_record["last_exception_time"] = exception_record["timestamp"]

        if exception_type not in agent_record["exception_types"]:
            agent_record["exception_types"][exception_type] = 0
        agent_record["exception_types"][exception_type] += 1

        # 更新健康状态
        self._update_agent_health_status(speaker_name)

        # 记录到日志
        self._log_exception_record(exception_record)

    def _update_agent_health_status(self, speaker_name: str):
        """更新智能体健康状态"""
        agent_record = self.agent_health_records[speaker_name]
        total_exceptions = agent_record["total_exceptions"]
        exception_types = agent_record["exception_types"]

        # 计算健康分数 (0-100, 100为最健康)
        health_score = max(0, 100 - (total_exceptions * 10))

        # 如果最近有严重错误，降低分数
        serious_errors = ["content_filter", "rate_limit", "network", "unexpected"]
        serious_count = sum(exception_types.get(et, 0) for et in serious_errors)
        health_score = max(0, health_score - (serious_count * 5))

        # 根据分数设置状态
        if health_score >= 80:
            agent_record["health_status"] = "healthy"
        elif health_score >= 50:
            agent_record["health_status"] = "degraded"
        else:
            agent_record["health_status"] = "critical"

    def _log_exception_record(self, record: Dict[str, Any]):
        """记录异常到日志"""
        log_level = "ERROR"
        if record["requires_human_intervention"]:
            log_level = "CRITICAL"

        intervention_note = ""
        if record["requires_human_intervention"] and record["intervention_suggestions"]:
            intervention_note = f" | 人工干预建议: {', '.join(record['intervention_suggestions'])}"

        logger.log(getattr(logging, log_level),
                  f"异常记录 - 讨论:{record['discussion_id']} 轮次:{record['round_number']} "
                  f"智能体:{record['speaker_name']} 阶段:{record['stage']} "
                  f"异常类型:{record['exception_type']} 尝试次数:{record['attempt_count']} "
                  f"错误:{record['error_message']}{intervention_note}")

    def get_exception_summary(self, discussion_id: str = None) -> Dict[str, Any]:
        """获取异常汇总信息"""
        if discussion_id:
            relevant_exceptions = [e for e in self.exception_history if e["discussion_id"] == discussion_id]
        else:
            relevant_exceptions = self.exception_history

        summary = {
            "total_exceptions": len(relevant_exceptions),
            "exceptions_by_type": {},
            "exceptions_by_stage": {},
            "exceptions_by_agent": {},
            "unresolved_exceptions": len([e for e in relevant_exceptions if not e["resolved"]]),
            "human_intervention_required": len([e for e in relevant_exceptions if e["requires_human_intervention"]]),
            "agent_health_status": self.agent_health_records.copy()
        }

        for exception in relevant_exceptions:
            # 按类型统计
            ex_type = exception["exception_type"]
            summary["exceptions_by_type"][ex_type] = summary["exceptions_by_type"].get(ex_type, 0) + 1

            # 按阶段统计
            stage = exception["stage"]
            summary["exceptions_by_stage"][stage] = summary["exceptions_by_stage"].get(stage, 0) + 1

            # 按智能体统计
            agent = exception["speaker_name"]
            summary["exceptions_by_agent"][agent] = summary["exceptions_by_agent"].get(agent, 0) + 1

        return summary

    def get_recent_exceptions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的异常记录"""
        return sorted(self.exception_history, key=lambda x: x["timestamp"], reverse=True)[:limit]

    def mark_exception_resolved(self, exception_index: int, resolution_notes: str = ""):
        """标记异常为已解决"""
        if 0 <= exception_index < len(self.exception_history):
            self.exception_history[exception_index]["resolved"] = True
            self.exception_history[exception_index]["resolution_time"] = datetime.now().isoformat()
            self.exception_history[exception_index]["resolution_notes"] = resolution_notes
    
    def _can_retry(self, exception_type: str, attempt_count: int) -> bool:
        """判断异常是否可以重试"""
        # 不可重试的异常类型
        non_retryable = ["content_filter", "invalid_request", "authentication"]
        if exception_type in non_retryable:
            return False
            
        # 超过最大重试次数
        max_retries = 3
        if attempt_count >= max_retries:
            return False
            
        return True
    
    def record_failed_speech(self, discussion_id: str, round_number: int,
                            speaker_name: str, stage: str,
                            context: Dict[str, Any], topic: str,
                            previous_speeches: List[str],
                            exception_id: str) -> str:
        """
        记录失败的发言，以便后续重试
            
        Returns:
            failed_speech_id: 失败发言的唯一ID
        """
        failed_speech_id = f"fs_{discussion_id}_{round_number}_{speaker_name}_{datetime.now().strftime('%H%M%S%f')}"
            
        self.failed_speeches[failed_speech_id] = {
            "failed_speech_id": failed_speech_id,
            "discussion_id": discussion_id,
            "round_number": round_number,
            "speaker_name": speaker_name,
            "stage": stage,
            "context": context,
            "topic": topic,
            "previous_speeches": previous_speeches,
            "exception_id": exception_id,
            "created_at": datetime.now().isoformat(),
            "retry_count": 0,
            "max_retries": 3,
            "status": "pending",  # pending, retrying, success, abandoned
            "last_retry_at": None,
            "retry_results": []
        }
            
        logger.info(f"记录失败发言: {failed_speech_id} - {speaker_name} 在 {stage} 阶段")
        return failed_speech_id
    
    def add_to_retry_queue(self, failed_speech_id: str, priority: int = 0):
        """添加到重试队列"""
        if failed_speech_id in self.failed_speeches:
            self.retry_queue.append({
                "failed_speech_id": failed_speech_id,
                "priority": priority,
                "added_at": datetime.now().isoformat()
            })
            # 按优先级排序
            self.retry_queue.sort(key=lambda x: x["priority"], reverse=True)
            logger.info(f"添加到重试队列: {failed_speech_id}")
    
    def get_retry_candidates(self, discussion_id: str = None) -> List[Dict[str, Any]]:
        """获取可重试的失败发言列表"""
        candidates = []
        for fs_id, fs_info in self.failed_speeches.items():
            if discussion_id and fs_info["discussion_id"] != discussion_id:
                continue
            if fs_info["status"] == "pending" and fs_info["retry_count"] < fs_info["max_retries"]:
                candidates.append(fs_info)
        return candidates
    
    def get_failed_speech(self, failed_speech_id: str) -> Dict[str, Any]:
        """获取失败发言记录"""
        return self.failed_speeches.get(failed_speech_id)
    
    def update_failed_speech_status(self, failed_speech_id: str, status: str, 
                                     result: Dict[str, Any] = None):
        """更新失败发言的状态"""
        if failed_speech_id in self.failed_speeches:
            fs = self.failed_speeches[failed_speech_id]
            fs["status"] = status
            fs["last_retry_at"] = datetime.now().isoformat()
            if result:
                fs["retry_results"].append({
                    "attempt": fs["retry_count"],
                    "timestamp": datetime.now().isoformat(),
                    "result": result
                })
            logger.info(f"更新失败发言状态: {failed_speech_id} -> {status}")
    
    def increment_retry_count(self, failed_speech_id: str):
        """增加重试计数"""
        if failed_speech_id in self.failed_speeches:
            self.failed_speeches[failed_speech_id]["retry_count"] += 1
    
    def get_exception_by_id(self, exception_id: str) -> Dict[str, Any]:
        """根据 ID 获取异常记录"""
        for exc in self.exception_history:
            if exc.get("exception_id") == exception_id:
                return exc
        return None
    
    def get_failed_speeches_summary(self, discussion_id: str = None) -> Dict[str, Any]:
        """获取失败发言汇总"""
        if discussion_id:
            relevant = {k: v for k, v in self.failed_speeches.items() 
                       if v["discussion_id"] == discussion_id}
        else:
            relevant = self.failed_speeches
            
        summary = {
            "total_failed": len(relevant),
            "pending_retry": len([v for v in relevant.values() if v["status"] == "pending"]),
            "retrying": len([v for v in relevant.values() if v["status"] == "retrying"]),
            "success_after_retry": len([v for v in relevant.values() if v["status"] == "success"]),
            "abandoned": len([v for v in relevant.values() if v["status"] == "abandoned"]),
            "by_speaker": {},
            "by_stage": {}
        }
            
        for fs in relevant.values():
            speaker = fs["speaker_name"]
            stage = fs["stage"]
            summary["by_speaker"][speaker] = summary["by_speaker"].get(speaker, 0) + 1
            summary["by_stage"][stage] = summary["by_stage"].get(stage, 0) + 1
            
        return summary
