"""
实施层讨论协调器

负责协调实施讨论的流程：
- 协调发言顺序（架构师 -> 开发者 -> 测试员 -> 协调员）
- 触发质疑和辩论
- 汇总讨论结果
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator, TYPE_CHECKING
from enum import Enum
import asyncio
import uuid
import logging

if TYPE_CHECKING:
    from ...agents.base_hierarchical_agent import BaseHierarchicalAgent
    from ....types import Task

from .implementation_consensus import (
    ImplementationConsensus,
    ConsensusCategory,
    OpinionStance,
    ConsensusResult
)


logger = logging.getLogger(__name__)


class DiscussionPhase(Enum):
    """讨论阶段（新四阶段流程）"""
    # 新流程阶段
    SCHOLAR_ANALYSIS = "scholar_analysis"       # 科学家分析
    EXPERT_GENERATION = "expert_generation"     # 专家生成
    EXPERT_DISCUSSION = "expert_discussion"     # 专家讨论
    SYNTHESIS = "synthesis"                     # 综合汇总
    # 保留旧阶段用于兼容
    DESIGN_PROPOSAL = "design_proposal"         # 设计方案提出
    FEASIBILITY_REVIEW = "feasibility_review"   # 可行性评审
    RISK_ASSESSMENT = "risk_assessment"         # 风险评估
    CONSENSUS_BUILDING = "consensus_building"   # 共识构建


@dataclass
class PhaseConfig:
    """阶段配置"""
    phase: DiscussionPhase
    name: str
    description: str
    lead_role: str                    # 主导角色
    participating_roles: List[str]    # 参与角色
    consensus_categories: List[ConsensusCategory]  # 关注的共识类别
    min_rounds: int = 1               # 最少讨论轮次
    max_rounds: int = 3               # 最多讨论轮次
    consensus_threshold: float = 0.6  # 共识阈值


@dataclass
class SpeechRecord:
    """发言记录"""
    record_id: str = field(default_factory=lambda: f"speech_{uuid.uuid4().hex[:8]}")
    phase: DiscussionPhase = DiscussionPhase.DESIGN_PROPOSAL
    round_num: int = 1
    agent_id: str = ""
    agent_role: str = ""
    speech_type: str = "statement"  # statement, question, response, challenge, summary
    content: str = ""
    target_agent_id: Optional[str] = None  # 针对的智能体（用于质疑/回应）
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PhaseResult:
    """阶段结果"""
    phase: DiscussionPhase
    rounds_completed: int = 0
    speeches: List[SpeechRecord] = field(default_factory=list)
    consensus_results: Dict[str, ConsensusResult] = field(default_factory=dict)
    key_decisions: List[str] = field(default_factory=list)
    unresolved_issues: List[str] = field(default_factory=list)
    success: bool = False
    summary: str = ""


class ImplementationCoordinator:
    """
    实施讨论协调器
    
    负责协调四阶段讨论流程：
    1. 设计方案提出 - 架构师主导
    2. 可行性评审 - 开发者主导
    3. 风险评估 - 测试员主导
    4. 共识构建 - 协调员主导
    """
    
    # 阶段配置
    PHASE_CONFIGS = {
        DiscussionPhase.DESIGN_PROPOSAL: PhaseConfig(
            phase=DiscussionPhase.DESIGN_PROPOSAL,
            name="设计方案提出",
            description="架构师提出技术方案，其他成员提出问题和建议",
            lead_role="architect",
            participating_roles=["developer", "tester", "coordinator"],
            consensus_categories=[ConsensusCategory.TECHNICAL, ConsensusCategory.PATH],
            min_rounds=1,
            max_rounds=2
        ),
        DiscussionPhase.FEASIBILITY_REVIEW: PhaseConfig(
            phase=DiscussionPhase.FEASIBILITY_REVIEW,
            name="可行性评审",
            description="开发者评估实现可行性，识别技术难点",
            lead_role="developer",
            participating_roles=["architect", "tester", "coordinator"],
            consensus_categories=[ConsensusCategory.PATH, ConsensusCategory.RESOURCE],
            min_rounds=1,
            max_rounds=2
        ),
        DiscussionPhase.RISK_ASSESSMENT: PhaseConfig(
            phase=DiscussionPhase.RISK_ASSESSMENT,
            name="风险评估",
            description="测试员评估潜在风险，提出测试策略",
            lead_role="tester",
            participating_roles=["architect", "developer", "coordinator"],
            consensus_categories=[ConsensusCategory.RISK, ConsensusCategory.QUALITY],
            min_rounds=1,
            max_rounds=2
        ),
        DiscussionPhase.CONSENSUS_BUILDING: PhaseConfig(
            phase=DiscussionPhase.CONSENSUS_BUILDING,
            name="共识构建",
            description="协调员汇总讨论，推动形成最终共识",
            lead_role="coordinator",
            participating_roles=["architect", "developer", "tester"],
            consensus_categories=[ConsensusCategory.TECHNICAL, ConsensusCategory.PATH, 
                                  ConsensusCategory.RISK, ConsensusCategory.RESOURCE],
            min_rounds=1,
            max_rounds=3,
            consensus_threshold=0.7
        ),
    }
    
    # 角色发言顺序
    ROLE_ORDER = ["architect", "developer", "tester", "documenter", "coordinator"]
    
    def __init__(
        self,
        consensus_tracker: Optional[ImplementationConsensus] = None,
        llm_adapter=None
    ):
        self.consensus_tracker = consensus_tracker or ImplementationConsensus()
        self.llm_adapter = llm_adapter
        
        # 讨论记录
        self._phase_results: Dict[DiscussionPhase, PhaseResult] = {}
        self._all_speeches: List[SpeechRecord] = []
        self._current_phase: Optional[DiscussionPhase] = None
    
    async def coordinate_discussion(
        self,
        agents: Dict[str, 'BaseHierarchicalAgent'],
        task: 'Task',
        task_context: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        协调完整的讨论流程
        
        Args:
            agents: 智能体字典 {agent_id: agent}
            task: 当前任务
            task_context: 任务上下文
            
        Yields:
            讨论过程的输出
        """
        yield f"\n{'='*60}\n"
        yield f"[实施圆桌] 开始讨论任务: {task.name if hasattr(task, 'name') else str(task)}\n"
        yield f"[实施圆桌] 参与成员: {len(agents)} 人\n"
        yield f"{'='*60}\n"
        
        # 按顺序执行四个阶段
        phases = [
            DiscussionPhase.DESIGN_PROPOSAL,
            DiscussionPhase.FEASIBILITY_REVIEW,
            DiscussionPhase.RISK_ASSESSMENT,
            DiscussionPhase.CONSENSUS_BUILDING
        ]
        
        for phase in phases:
            self._current_phase = phase
            config = self.PHASE_CONFIGS[phase]
            
            yield f"\n{'─'*50}\n"
            yield f"[阶段 {phases.index(phase)+1}/4] {config.name}\n"
            yield f"[说明] {config.description}\n"
            yield f"[主导] {config.lead_role}\n"
            yield f"{'─'*50}\n"
            
            # 执行该阶段
            async for chunk in self._run_phase(phase, agents, task, task_context):
                yield chunk
            
            # 检查共识是否达成
            phase_consensus = self._check_phase_consensus(phase)
            if phase_consensus < config.consensus_threshold:
                yield f"\n[警告] 当前阶段共识度 ({phase_consensus:.2f}) 未达阈值 ({config.consensus_threshold})\n"
        
        # 生成最终总结
        yield f"\n{'='*60}\n"
        yield "[实施圆桌] 讨论完成\n"
        yield f"{'='*60}\n"
        async for chunk in self._generate_final_summary():
            yield chunk
    
    async def _run_phase(
        self,
        phase: DiscussionPhase,
        agents: Dict[str, 'BaseHierarchicalAgent'],
        task: 'Task',
        task_context: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """执行单个讨论阶段"""
        config = self.PHASE_CONFIGS[phase]
        phase_result = PhaseResult(phase=phase)
        
        round_num = 0
        consensus_reached = False
        
        while round_num < config.max_rounds and not consensus_reached:
            round_num += 1
            yield f"\n[轮次 {round_num}/{config.max_rounds}]\n"
            
            # 1. 主导角色发言
            lead_agent = self._find_agent_by_role(agents, config.lead_role)
            if lead_agent:
                yield f"\n[{config.lead_role.upper()}] 主导发言\n"
                async for chunk in self._agent_speak(
                    lead_agent, phase, round_num, "statement", task, task_context
                ):
                    yield chunk
            
            # 2. 其他角色按顺序发言/质疑
            for role in config.participating_roles:
                agent = self._find_agent_by_role(agents, role)
                if agent:
                    # 第一轮发表意见，后续轮次可质疑或补充
                    speech_type = "statement" if round_num == 1 else "challenge"
                    yield f"\n[{role.upper()}] "
                    yield "发表意见\n" if round_num == 1 else "提出质疑/补充\n"
                    async for chunk in self._agent_speak(
                        agent, phase, round_num, speech_type, task, task_context
                    ):
                        yield chunk
            
            # 3. 检查共识
            if round_num >= config.min_rounds:
                current_consensus = self._check_phase_consensus(phase)
                yield f"\n[共识度] {current_consensus:.2f}\n"
                if current_consensus >= config.consensus_threshold:
                    consensus_reached = True
                    yield "[状态] 已达成共识\n"
        
        phase_result.rounds_completed = round_num
        phase_result.success = consensus_reached
        self._phase_results[phase] = phase_result
    
    async def _agent_speak(
        self,
        agent: 'BaseHierarchicalAgent',
        phase: DiscussionPhase,
        round_num: int,
        speech_type: str,
        task: 'Task',
        task_context: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """智能体发言"""
        config = self.PHASE_CONFIGS[phase]
        
        # 将 Task 对象转换为字典，避免 'Task' object has no attribute 'get' 错误
        task_dict = {
            "task_id": getattr(task, 'task_id', ''),
            "name": getattr(task, 'name', '未知任务'),
            "description": getattr(task, 'description', ''),
            "priority": getattr(task, 'priority', 'medium'),
            "status": getattr(task, 'status', 'pending')
        }
        
        # 构建发言上下文
        context = {
            **task_context,
            "task": task_dict,  # 使用字典而非 Task 对象
            "phase": phase.value,
            "phase_name": config.name,
            "round_num": round_num,
            "speech_type": speech_type,
            "previous_speeches": self._get_phase_speeches(phase),
            "consensus_summary": self.consensus_tracker.get_discussion_summary()
        }
        
        # 调用智能体
        speech_content = []
        try:
            async for chunk in agent.act(context):
                yield chunk
                speech_content.append(chunk)
        except Exception as e:
            logger.error(f"智能体发言失败: {e}")
            yield f"[错误] 发言失败: {str(e)}\n"
            return
        
        full_content = "".join(speech_content)
        
        # 记录发言
        record = SpeechRecord(
            phase=phase,
            round_num=round_num,
            agent_id=agent.config.agent_id if hasattr(agent, 'config') else str(id(agent)),
            agent_role=agent.config.role if hasattr(agent, 'config') else "unknown",
            speech_type=speech_type,
            content=full_content
        )
        self._all_speeches.append(record)
        
        # 解析并记录意见到共识追踪器
        self._record_opinion_from_speech(record, config.consensus_categories)
    
    def _record_opinion_from_speech(
        self,
        record: SpeechRecord,
        categories: List[ConsensusCategory]
    ):
        """从发言中提取并记录意见"""
        # 简化处理：根据发言类型确定立场
        if record.speech_type == "statement":
            stance = OpinionStance.AGREE
        elif record.speech_type == "challenge":
            stance = OpinionStance.DISAGREE
        elif record.speech_type == "response":
            stance = OpinionStance.NEUTRAL
        else:
            stance = OpinionStance.NEUTRAL
        
        # 为每个相关类别记录意见
        for category in categories[:2]:  # 最多记录2个类别
            self.consensus_tracker.record_opinion(
                agent_id=record.agent_id,
                agent_role=record.agent_role,
                category=category,
                topic=record.phase.value,
                stance=stance,
                content=record.content[:500]  # 截取前500字符
            )
    
    def _find_agent_by_role(
        self,
        agents: Dict[str, 'BaseHierarchicalAgent'],
        role: str
    ) -> Optional['BaseHierarchicalAgent']:
        """根据角色查找智能体"""
        for agent_id, agent in agents.items():
            if hasattr(agent, 'config') and hasattr(agent.config, 'role'):
                if agent.config.role.lower() == role.lower():
                    return agent
            elif role.lower() in agent_id.lower():
                return agent
        return None
    
    def _get_phase_speeches(self, phase: DiscussionPhase) -> List[Dict[str, Any]]:
        """获取当前阶段的发言记录"""
        speeches = [
            {
                "agent_role": s.agent_role,
                "speech_type": s.speech_type,
                "content": s.content[:200]  # 摘要
            }
            for s in self._all_speeches
            if s.phase == phase
        ]
        return speeches[-10:]  # 最近10条
    
    def _check_phase_consensus(self, phase: DiscussionPhase) -> float:
        """检查当前阶段的共识度"""
        config = self.PHASE_CONFIGS[phase]
        consensus_levels = []
        
        for category in config.consensus_categories:
            result = self.consensus_tracker.calculate_consensus_level(category, phase.value)
            consensus_levels.append(result.consensus_level)
        
        if not consensus_levels:
            return 0.5  # 默认值
        
        return sum(consensus_levels) / len(consensus_levels)
    
    async def _generate_final_summary(self) -> AsyncGenerator[str, None]:
        """生成最终讨论总结"""
        summary = self.consensus_tracker.get_discussion_summary()
        
        yield "\n[讨论摘要]\n"
        yield f"- 总意见数: {summary['total_opinions']}\n"
        yield f"- 整体共识度: {summary['overall_consensus']:.2f}\n"
        yield f"- 未解决冲突: {summary['unresolved_conflicts']} 项\n"
        
        yield "\n[各阶段结果]\n"
        for phase, result in self._phase_results.items():
            status = "✓ 达成共识" if result.success else "○ 需继续讨论"
            yield f"- {self.PHASE_CONFIGS[phase].name}: {status} ({result.rounds_completed}轮)\n"
        
        # 汇总关键决策
        conflicts = self.consensus_tracker.get_unresolved_conflicts()
        if conflicts:
            yield "\n[待解决事项]\n"
            for conflict in conflicts[:5]:
                yield f"- {conflict.category.value}: {conflict.topic}\n"
    
    def get_discussion_result(self) -> Dict[str, Any]:
        """获取讨论结果"""
        return {
            "phase_results": {
                phase.value: {
                    "rounds": result.rounds_completed,
                    "success": result.success,
                    "speeches": len(result.speeches)
                }
                for phase, result in self._phase_results.items()
            },
            "total_speeches": len(self._all_speeches),
            "consensus_summary": self.consensus_tracker.get_discussion_summary()
        }
    
    def reset(self):
        """重置协调器状态"""
        self._phase_results.clear()
        self._all_speeches.clear()
        self._current_phase = None
        self.consensus_tracker.clear()
