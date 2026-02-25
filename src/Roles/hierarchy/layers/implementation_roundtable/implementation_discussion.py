"""
实施与专业领域知识划分层 - 圆桌讨论主类（第二层）

核心为「实施」与「按领域细化」：对第一层讨论共识进行专业领域划分，产出各领域细化实施步骤。
实现完整的实施讨论系统，采用动态专家生成模式：
1. 科学家分析任务需求，确定所需专家及领域划分
2. 动态生成各领域专家智能体
3. 任务细化分配：按领域分解为可执行子任务及详细步骤
4. 各领域专家给出详细实施方案（步骤细化与扩展）
5. 综合者汇总各领域方案，保留领域细化步骤，找出质疑点

约定：第二层每个智能体的结果由控制层统一保存到 discussion/discussion_id/pro 目录。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator, TYPE_CHECKING
import asyncio
import logging
import os
import uuid

# 复用第一层圆桌讨论的通信组件
from ....roundtable import MessageBus, CommunicationProtocol, AgentMessage, MessageType

# 领域步骤模板（用于任务细化时的领域步骤扩展）
from .domain_step_templates import get_phase_hints_for_domain

# 本模块组件
from .implementation_consensus import (
    ImplementationConsensus,
    ConsensusCategory,
    OpinionStance,
    ConsensusResult
)
from .implementation_coordinator import (
    ImplementationCoordinator,
    DiscussionPhase,
    PhaseResult
)

# 新增：动态智能体相关
from ...agents import (
    BaseHierarchicalAgent,
    ScholarAgent,
    DynamicExpertAgent,
    DynamicAgentFactory,
    SynthesizerAgent
)

# 类型
from ...types import Task, ImplementationRole

if TYPE_CHECKING:
    from ..implementation_layer import ImplementationGroup


logger = logging.getLogger(__name__)


def _get_layer1_domain_experts_from_participants(participants: List[Any]) -> List[Dict[str, Any]]:
    """
    从第一层参与者列表解析出「领域专家」名单，用于第二层与第一层一一对应创建实施步骤智能体。
    第一层命名约定：expert_<领域名> 为领域专家，skeptic_expert_<领域名> 为对应质疑者。
    """
    if not participants:
        return []
    experts = []
    seen_domains = set()
    for p in participants:
        name = (p.get("name") if isinstance(p, dict) else str(p)).strip()
        if not name.startswith("expert_") or name.startswith("skeptic_expert_"):
            continue
        domain = name.replace("expert_", "", 1).strip()
        if not domain or domain in seen_domains:
            continue
        seen_domains.add(domain)
        experts.append({
            "role": f"impl_{domain}",
            "name": domain,
            "domain": domain,
            "reason": "对应第一层该领域专家，根据其讨论结果与质疑者意见给出可实施步骤",
            "expertise": [f"{domain}实施", "步骤细化", "可执行方案"],
            "priority": 1,
        })
    return experts


def _get_layer1_speeches_by_domain(rounds: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    从第一层各轮发言中按领域汇总：每个领域专家的发言、以及针对该领域专家的质疑者发言。
    第二层使用第一层智能体的「最终修订稿」：每个领域每轮只保留该专家在该轮的最后一条发言
    （即两轮质疑→修订后的最终稿），便于实施层基于稳定结论做步骤细化。
    返回 { "领域名": { "expert_speeches": [...], "skeptic_speeches": [...] } }
    """
    by_domain = {}
    for round_data in rounds or []:
        rn = round_data.get("round_number", 0)
        for speech_data in round_data.get("speeches", []):
            speaker = speech_data.get("speaker", "")
            is_skeptic = speech_data.get("is_skeptic", False)
            target_expert = speech_data.get("target_expert", "")
            content = {
                "round": rn,
                "thinking": speech_data.get("thinking", ""),
                "speech": speech_data.get("speech", ""),
                "target_expert": target_expert,
            }
            if is_skeptic and target_expert:
                domain = target_expert.replace("expert_", "", 1).strip() if "expert_" in target_expert else target_expert
                if domain not in by_domain:
                    by_domain[domain] = {"expert_speeches": [], "skeptic_speeches": [], "_final_by_round": {}}
                by_domain[domain]["skeptic_speeches"].append(content)
            elif speaker.startswith("expert_") and not speaker.startswith("skeptic_expert_"):
                domain = speaker.replace("expert_", "", 1).strip()
                if domain not in by_domain:
                    by_domain[domain] = {"expert_speeches": [], "skeptic_speeches": [], "_final_by_round": {}}
                # 每轮只保留该领域专家的最后一条发言（最终修订稿）
                by_domain[domain]["_final_by_round"][rn] = content
    # 将每轮最终稿转为 expert_speeches 列表（按轮次排序）
    for domain in by_domain:
        final_by_round = by_domain[domain].pop("_final_by_round", {})
        by_domain[domain]["expert_speeches"] = [final_by_round[r] for r in sorted(final_by_round.keys())]
    return by_domain


@dataclass
class DiscussionConfig:
    """讨论配置"""
    max_experts: int = 6                 # 最大专家数量
    min_experts: int = 3                 # 最小专家数量
    timeout_seconds: float = 600.0       # 讨论超时时间
    enable_debate: bool = True           # 是否启用辩论
    enable_consensus_tracking: bool = True  # 是否启用共识追踪
    min_consensus_level: float = 0.6     # 最低共识度要求


@dataclass
class DiscussionResult:
    """讨论结果"""
    discussion_id: str = field(default_factory=lambda: f"impl_disc_{uuid.uuid4().hex[:8]}")
    task_id: str = ""
    task_name: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    # 科学家分析结果
    scholar_analysis: Dict[str, Any] = field(default_factory=dict)
    # 动态生成的专家列表
    experts_created: List[Dict[str, Any]] = field(default_factory=list)
    # 专家方案
    expert_proposals: List[Dict[str, Any]] = field(default_factory=list)
    # 综合方案
    synthesized_plan: Dict[str, Any] = field(default_factory=dict)
    # 质疑点
    challenges: List[Dict[str, Any]] = field(default_factory=list)
    # 最终状态
    final_consensus_level: float = 0.0
    success: bool = False
    # 补全字段: control_discussion.py 中 _save_implementation_result 需要
    total_rounds: int = 0
    key_decisions: List[str] = field(default_factory=list)
    implementation_plan: str = ""
    # 交叉审阅结果
    cross_reviews: List[Dict[str, Any]] = field(default_factory=list)
    # 细化任务分配（第二层规划时对任务的更细分解与角色分配）
    refined_task_assignment: List[Dict[str, Any]] = field(default_factory=list)


class ImplementationDiscussion:
    """
    实施层圆桌讨论主类（重构版）
    
    新的四阶段讨论流程：
    1. 科学家分析 - 分析任务，确定所需专家
    2. 专家生成 - 动态创建各领域专家智能体
    3. 专家讨论 - 各专家给出实施方案
    4. 综合汇总 - 综合者汇总方案，找出质疑点
    """
    
    def __init__(
        self,
        llm_adapter=None,
        config: Optional[DiscussionConfig] = None
    ):
        self.llm_adapter = llm_adapter
        self.config = config or DiscussionConfig()
        
        # 复用第一层圆桌讨论的通信系统
        self.message_bus = MessageBus()
        self.communication_protocol = CommunicationProtocol(self.message_bus)
        
        # 实施共识追踪器
        self.consensus_tracker = ImplementationConsensus()
        
        # 核心智能体
        self.scholar: Optional[ScholarAgent] = None
        self.synthesizer: Optional[SynthesizerAgent] = None
        
        # 动态生成的专家
        self.expert_factory: Optional[DynamicAgentFactory] = None
        self.dynamic_experts: List[DynamicExpertAgent] = []
        
        # 讨论历史
        self._discussion_results: List[DiscussionResult] = []
        self._current_result: Optional[DiscussionResult] = None
    
    async def run_implementation_discussion(
        self,
        task_list,
        first_layer_output: Dict[str, Any] = None,
        group: 'ImplementationGroup' = None
    ) -> AsyncGenerator[str, None]:
        """
        运行完整的实施讨论（新流程）
        
        兼容两种调用方式：
        1. 新方式: run_implementation_discussion(task_list, first_layer_output, group)
        2. 旧方式: run_implementation_discussion(task_or_object, group)  (来自 control_discussion)
        
        Args:
            task_list: 任务列表 List[Dict] 或单个 Task 对象
            first_layer_output: 第一层完整输出（新方式必传）
            group: 实施小组（可选）
            
        Yields:
            讨论过程的输出
        """
        # ============ 参数兼容处理 ============
        if first_layer_output is None:
            # 旧方式调用: run_implementation_discussion(task, group)
            # task_list 实际上是单个 Task 对象, first_layer_output 是 group
            raw_task = task_list
            if group is None and first_layer_output is None:
                # 检查第二个参数是否是 group（被赋给了 first_layer_output）
                pass
            first_layer_output = {}
            # 将 Task 对象转为任务列表
            if isinstance(raw_task, list):
                task_list = raw_task
            elif hasattr(raw_task, 'name'):
                task_list = [{
                    "name": raw_task.name,
                    "description": raw_task.description if hasattr(raw_task, 'description') else str(raw_task),
                    "task_id": raw_task.task_id if hasattr(raw_task, 'task_id') else str(uuid.uuid4().hex[:8]),
                    "priority": raw_task.priority if hasattr(raw_task, 'priority') else 3
                }]
                first_layer_output = {
                    "discussion_summary": raw_task.description if hasattr(raw_task, 'description') else str(raw_task)
                }
            else:
                task_list = [{"name": str(raw_task), "description": str(raw_task)}]
        elif not isinstance(task_list, list):
            # task_list 不是列表，包装一下
            raw_task = task_list
            if hasattr(raw_task, 'name'):
                task_list = [{
                    "name": raw_task.name,
                    "description": raw_task.description if hasattr(raw_task, 'description') else str(raw_task),
                    "task_id": raw_task.task_id if hasattr(raw_task, 'task_id') else str(uuid.uuid4().hex[:8])
                }]
            else:
                task_list = [{"name": str(raw_task), "description": str(raw_task)}]
        
        # 初始化讨论结果
        self._current_result = DiscussionResult(
            task_id=first_layer_output.get('discussion_id', str(uuid.uuid4().hex[:8])),
            task_name="实施讨论"
        )
        
        # 第一层领域专家与发言汇总（第二层与第一层一一对应）
        participants = first_layer_output.get("participants", [])
        rounds = first_layer_output.get("rounds", [])
        layer1_domain_experts = _get_layer1_domain_experts_from_participants(participants)
        layer1_speeches_by_domain = _get_layer1_speeches_by_domain(rounds)
        user_goal = first_layer_output.get("user_goal", "") or first_layer_output.get("discussion_summary", "")
        
        yield "\n" + "=" * 60 + "\n"
        yield "          实施步骤细化层 (与第一层领域专家一一对应)\n"
        yield "=" * 60 + "\n"
        
        try:
            # ============ 阶段1: 科学家分析（若有第一层领域专家则与之对齐） ============
            yield "\n[阶段1/5] 任务与第一层讨论对齐\n"
            yield "-" * 40 + "\n"
            
            self.scholar = ScholarAgent(llm_adapter=self.llm_adapter)
            async for chunk in self.scholar.analyze_required_experts(
                task_list, first_layer_output
            ):
                yield chunk
            
            expert_specs = self.scholar.get_required_experts_specs()
            # 第二层与第一层一一对应：若有第一层领域专家，则以其为准创建第二层实施步骤智能体
            if layer1_domain_experts:
                expert_specs = layer1_domain_experts[: self.config.max_experts]
                yield f"\n[对齐第一层] 已按第一层 {len(expert_specs)} 个领域专家创建对应实施步骤智能体\n"
            
            self._current_result.scholar_analysis = {
                "task_analysis": self.scholar.last_analysis.task_analysis if self.scholar.last_analysis else "",
                "project_type": self.scholar.last_analysis.project_type if self.scholar.last_analysis else "",
                "required_experts": expert_specs,
                "layer1_aligned": bool(layer1_domain_experts),
            }
            
            # ============ 阶段2: 动态生成专家（与第一层领域一一对应） ============
            yield "\n\n[阶段2/5] 动态生成专家团队\n"
            yield "-" * 40 + "\n"
            
            self.expert_factory = DynamicAgentFactory(llm_adapter=self.llm_adapter)
            
            specs_to_create = expert_specs[:self.config.max_experts]
            if len(specs_to_create) < self.config.min_experts:
                default_specs = [
                    {"role": "project_planner", "name": "项目规划师", "domain": "项目规划", "reason": "统筹项目"},
                    {"role": "technical_expert", "name": "技术专家", "domain": "技术实施", "reason": "技术支持"},
                    {"role": "quality_manager", "name": "质量管理师", "domain": "质量控制", "reason": "质量保障"}
                ]
                for spec in default_specs:
                    if len(specs_to_create) >= self.config.min_experts:
                        break
                    if spec['role'] not in [s['role'] for s in specs_to_create]:
                        specs_to_create.append(spec)
            
            self.dynamic_experts = self.expert_factory.create_experts_batch(specs_to_create)
            
            yield f"\n已创建 {len(self.dynamic_experts)} 位专家:\n"
            for i, expert in enumerate(self.dynamic_experts, 1):
                yield f"  {i}. {expert.name} ({expert.domain})\n"
                self._current_result.experts_created.append(expert.to_dict())
            
            # ============ 阶段2.5: 任务细化分配 ============
            yield "\n\n[阶段2.5/5] 任务细化分配\n"
            yield "-" * 40 + "\n"
            refined_tasks = []
            async for chunk in self._refine_task_assignment(task_list, expert_specs):
                yield chunk
            if hasattr(self, '_last_refined_tasks') and self._last_refined_tasks:
                refined_tasks = self._last_refined_tasks
                self._current_result.refined_task_assignment = refined_tasks
                yield f"  已细化 {len(refined_tasks)} 项子任务并分配责任角色\n"
            else:
                self._current_result.refined_task_assignment = [{"task": t, "assigned_roles": []} for t in task_list]
            
            # ============ 阶段3a: 专家独立提案 ============
            yield "\n\n[阶段3a/5] 专家独立提案\n"
            yield "-" * 40 + "\n"
            
            # 第一层发言保存目录，供第二层专家在 JSON 解析失败时从 md 回退读取（优先使用 control 传入的绝对路径）
            discuss_dir = first_layer_output.get("discuss_dir") or os.path.join(
                "discussion", str(first_layer_output.get("discussion_id", "")), "discuss"
            )
            # 构建任务上下文（含第一层本领域发言与质疑者意见，供专家给出可实施步骤并反复验证）
            task_context_base = {
                "task_list": task_list,
                "refined_task_assignment": getattr(self._current_result, 'refined_task_assignment', []) or [],
                "first_layer_output": first_layer_output,
                "user_goal": user_goal,
                "layer1_speeches_by_domain": layer1_speeches_by_domain,
                "discuss_dir": discuss_dir,
                "task": {
                    "name": "实施方案讨论",
                    "description": first_layer_output.get('discussion_summary', '')
                }
            }
            layer1_summary = first_layer_output.get('layer1_summary', {})
            if layer1_summary:
                task_context_base['layer1_summary_index'] = layer1_summary
                yield f"[信息] 已加载第一层讨论汇总文档索引\n"
            
            expert_proposals = []
            for expert in self.dynamic_experts:
                # 为该领域注入第一层本领域专家发言与质疑者意见，便于给出可实施步骤并验证
                task_context = dict(task_context_base)
                domain_speeches = layer1_speeches_by_domain.get(expert.domain, {})
                task_context["first_layer_expert_speeches"] = domain_speeches.get("expert_speeches", [])
                task_context["first_layer_skeptic_critiques"] = domain_speeches.get("skeptic_speeches", [])
                proposal_content = []
                async for chunk in expert.propose_solution(task_context):
                    yield chunk
                    proposal_content.append(chunk)
                proposal_content = "".join(proposal_content)

                # 第二层：每个专家对应质疑者，质疑→专家修订，循环两次，得到最终修订稿（第三层将使用此稿）
                revision_cycles = 2
                for cycle in range(1, revision_cycles + 1):
                    challenge = await self._generate_layer2_skeptic_challenge(
                        expert.name, expert.domain, proposal_content
                    )
                    if not (challenge and challenge.strip()):
                        break
                    yield f"\n[质疑者-{expert.domain}] 第{cycle}轮质疑\n"
                    yield f"{challenge[:500]}{'...' if len(challenge) > 500 else ''}\n"
                    try:
                        revised = await expert.revise_proposal_after_skeptic(
                            proposal_content, challenge, task_context, revision_round=cycle
                        )
                        if revised and revised.strip():
                            proposal_content = revised
                    except Exception as e:
                        logger.warning(f"[{expert.name}] 第{cycle}轮修订失败: {e}")

                # 使用结构化的 ExpertProposal 数据（若修订后未重新解析则沿用 last_proposal）
                structured_proposal = None
                if expert.last_proposal:
                    structured_proposal = expert.last_proposal.to_dict()
                # 记录最终修订稿（供第三层与保存使用）
                proposal = {
                    "expert_name": expert.name,
                    "domain": expert.domain,
                    "content": proposal_content,
                    "structured": structured_proposal
                }
                expert_proposals.append(proposal)
                self._current_result.expert_proposals.append(proposal)

                # 记录到共识追踪器: 专家对自己方案持 AGREE 立场
                if self.config.enable_consensus_tracking:
                    self.consensus_tracker.record_opinion(
                        agent_id=expert.agent_id,
                        agent_role=expert.role,
                        category=ConsensusCategory.TECHNICAL,
                        topic=f"方案:{expert.name}",
                        stance=OpinionStance.STRONGLY_AGREE,
                        content=f"{expert.name} 提出了{expert.domain}领域的实施方案",
                        supporting_evidence=[expert.domain]
                    )
                
                # 更新上下文（供后续专家参考已产生的方案）
                task_context_base["other_proposals"] = expert_proposals.copy()
            
            # ============ 阶段3b: 专家交叉审阅 ============
            cross_reviews = []  # 所有审阅结果
            if self.config.enable_debate and len(self.dynamic_experts) >= 2:
                yield "\n\n[阶段3b/5] 专家交叉审阅\n"
                yield "-" * 40 + "\n"
                yield f"[信息] {len(self.dynamic_experts)} 位专家互相审阅方案\n\n"
                review_ctx = dict(task_context_base)
                review_ctx["other_proposals"] = expert_proposals.copy()
                for reviewer_expert in self.dynamic_experts:
                    for proposal in expert_proposals:
                        # 不审阅自己的方案
                        if proposal['expert_name'] == reviewer_expert.name:
                            continue
                        
                        review_content = []
                        async for chunk in reviewer_expert.review_proposal(proposal, review_ctx):
                            yield chunk
                            review_content.append(chunk)
                        
                        # 获取解析后的审阅结果
                        review_result = getattr(reviewer_expert, 'last_review', None) or {}
                        review_result['raw_content'] = "".join(review_content)
                        cross_reviews.append(review_result)
                        
                        # 记录到共识追踪器
                        if self.config.enable_consensus_tracking and review_result:
                            stance = review_result.get('stance', 'neutral')
                            stance_map = {
                                'agree': OpinionStance.AGREE,
                                'strongly_agree': OpinionStance.STRONGLY_AGREE,
                                'neutral': OpinionStance.NEUTRAL,
                                'disagree': OpinionStance.DISAGREE,
                                'strongly_disagree': OpinionStance.STRONGLY_DISAGREE
                            }
                            consensus_stance = stance_map.get(stance, OpinionStance.NEUTRAL)
                            
                            self.consensus_tracker.record_opinion(
                                agent_id=reviewer_expert.agent_id,
                                agent_role=reviewer_expert.role,
                                category=ConsensusCategory.TECHNICAL,
                                topic=f"方案:{proposal['expert_name']}",
                                stance=consensus_stance,
                                content=review_result.get('synergy_with_my_domain', ''),
                                supporting_evidence=review_result.get('strengths', []),
                                concerns=review_result.get('concerns', [])
                            )
                
                yield f"\n[交叉审阅完成] 共产生 {len(cross_reviews)} 条审阅意见\n"
            
            # 将交叉审阅结果写入上下文，供综合者使用
            task_context_base['cross_reviews'] = cross_reviews
            
            # ============ 阶段4: 综合者汇总 ============
            yield "\n\n[阶段4/5] 综合者汇总\n"
            yield "-" * 40 + "\n"
            
            self.synthesizer = SynthesizerAgent(llm_adapter=self.llm_adapter)
            
            async for chunk in self.synthesizer.synthesize_and_challenge(
                expert_proposals, task_context_base
            ):
                yield chunk
            
            # 获取综合结果
            validation_output = self.synthesizer.get_output_for_validation()
            self._current_result.synthesized_plan = validation_output
            self._current_result.challenges = validation_output.get("challenges", [])
            
            # ============ 阶段5: 共识评估 ============
            yield "\n\n[阶段5/5] 共识评估\n"
            yield "-" * 40 + "\n"
            
            # 从共识追踪器获取整体共识度
            overall_consensus = self.consensus_tracker.get_overall_consensus()
            
            # 获取未解决冲突
            unresolved = self.consensus_tracker.get_unresolved_conflicts()
            
            # 将未解决冲突追加到质疑点
            for conflict in unresolved:
                conflict_challenge = {
                    "point": f"共识分歧: {conflict.topic}",
                    "category": conflict.category.value if hasattr(conflict.category, 'value') else str(conflict.category),
                    "severity": "high" if conflict.consensus_level < 0.3 else "medium",
                    "related_experts": conflict.dissenters[:3],
                    "suggestion": "; ".join(conflict.key_disagreements[:2]) if conflict.key_disagreements else "需进一步讨论"
                }
                self._current_result.challenges.append(conflict_challenge)
            
            yield f"  - 整体共识度: {overall_consensus:.2f}\n"
            yield f"  - 未解决分歧: {len(unresolved)} 项\n"
            yield f"  - 交叉审阅意见: {len(cross_reviews)} 条\n"
            
            # ============ 填充结构化字段 ============
            self._current_result.total_rounds = 5  # 五个阶段
            self._current_result.final_consensus_level = overall_consensus
            
            # 存储交叉审阅结果
            self._current_result.cross_reviews = cross_reviews
            
            # 从综合方案中提取关键决策
            self._current_result.key_decisions = self._extract_key_decisions(validation_output)
            
            # 生成完整的实施计划文本
            self._current_result.implementation_plan = self._generate_implementation_plan_text(
                validation_output, expert_proposals
            )
            
            # ============ 完成讨论 ============
            self._current_result.completed_at = datetime.now()
            self._current_result.success = validation_output.get("ready_for_validation", False)
            
            yield "\n" + "=" * 60 + "\n"
            yield "[实施讨论完成]\n"
            yield f"  - 参与专家: {len(self.dynamic_experts)} 位\n"
            yield f"  - 方案数量: {len(expert_proposals)} 个\n"
            yield f"  - 交叉审阅: {len(cross_reviews)} 条\n"
            yield f"  - 共识度: {overall_consensus:.2f}\n"
            yield f"  - 质疑点: {len(self._current_result.challenges)} 个\n"
            yield f"  - 准备检验: {'是' if self._current_result.success else '否'}\n"
            yield "=" * 60 + "\n"
            
            # 保存结果
            self._discussion_results.append(self._current_result)
            
        except Exception as e:
            logger.error(f"实施讨论失败: {e}", exc_info=True)
            yield f"\n[错误] 讨论过程出错: {str(e)}\n"
            if self._current_result:
                self._current_result.success = False
    
    async def _refine_task_assignment(
        self,
        task_list: List[Dict[str, Any]],
        expert_specs: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """第二层规划时细化任务分配：按知识领域将任务分解为可执行子任务及详细步骤，并分配责任角色。"""
        import json as _json
        import re as _re
        self._last_refined_tasks = []
        if not self.llm_adapter or not task_list or not expert_specs:
            yield "  无 LLM 或任务/专家列表，跳过细化分配\n"
            return
        expert_items = [(s.get("name", s.get("role", "")), s.get("domain", "")) for s in expert_specs[:10]]
        expert_lines = "\n".join(f"  - {n}（{d}）" for n, d in expert_items if n)
        tasks_text = "\n".join(
            f"  - {t.get('name', '')}: {t.get('description', '')[:150]}"
            for t in task_list[:15]
        )
        # 构建领域步骤扩展提示（供 LLM 参考）
        domains = [d for _, d in expert_items if d]
        domain_hints = []
        for d in domains[:5]:
            hints = get_phase_hints_for_domain(d)
            if hints:
                domain_hints.append(f"  - {d}: {', '.join(hints[:4])}...")
        domain_hints_text = "\n".join(domain_hints) if domain_hints else "  - 通用: 需求理解、方案设计、执行实施、检查验证、交付总结"

        prompt = f"""你是一位项目规划专家，负责「实施与专业领域知识划分」：将任务按知识领域拆成可执行的子任务，并为每个子任务列出详细实施步骤。

## 任务列表
{tasks_text}

## 可用专家角色（含专业领域）
{expert_lines}

## 各领域的典型步骤参考（用于细化子任务）
{domain_hints_text}

## 输出要求

请输出 JSON 数组，每个元素形如：
{{
  "parent_task": "原任务名",
  "domain": "该子任务所属领域（对应上面专家领域）",
  "subtask_name": "子任务名称",
  "subtask_description": "子任务描述",
  "sub_steps": [
    {{"step_name": "步骤名", "description": "具体做什么", "deliverable": "产出物"}},
    ...
  ],
  "assigned_role": "负责的专家名",
  "sequence": 1
}}

要求：
1. 子任务要按领域划分，每个子任务只分配一位主要负责专家
2. sub_steps 至少 3 项，要细化到可执行级别
3. 每个步骤需包含 step_name、description、deliverable
4. 充分利用各领域的典型步骤参考进行扩展"""
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(lambda: self.llm_adapter.invoke(prompt).content),
                timeout=60.0
            )
            m = _re.search(r'\[\s*\{[\s\S]*\}\s*\]', response)
            if m:
                raw = m.group()
                # 移除 JSON 中未转义的控制字符，避免 json.loads 报 Invalid control character
                raw_clean = _re.sub(r'[\x00-\x1f]', ' ', raw)
                arr = _json.loads(raw_clean)
                if isinstance(arr, list):
                    self._last_refined_tasks = arr[:50]
                    yield f"  已分解并分配 {len(self._last_refined_tasks)} 项子任务（含领域细化步骤）\n"
            else:
                yield "  未解析到有效子任务列表，将使用原任务列表\n"
        except Exception as e:
            logger.warning(f"任务细化分配异常: {e}")
            yield f"  任务细化分配异常，将使用原任务列表: {str(e)[:80]}\n"
    
    def get_output_for_validation(self) -> Dict[str, Any]:
        """
        获取传递给第三层检验系统的输出
        
        Returns:
            结构化的检验输入
        """
        if not self._current_result:
            return {"error": "无讨论结果"}
        
        return {
            "discussion_id": self._current_result.discussion_id,
            "scholar_analysis": self._current_result.scholar_analysis,
            "experts": self._current_result.experts_created,
            "refined_task_assignment": getattr(self._current_result, "refined_task_assignment", []) or [],
            "proposals": self._current_result.expert_proposals,
            "cross_reviews": self._current_result.cross_reviews,
            "synthesized_plan": self._current_result.synthesized_plan,
            "challenges": self._current_result.challenges,
            "key_decisions": self._current_result.key_decisions,
            "implementation_plan": self._current_result.implementation_plan,
            "total_rounds": self._current_result.total_rounds,
            "consensus_level": self._current_result.final_consensus_level,
            "consensus_summary": self.consensus_tracker.get_discussion_summary() if self.consensus_tracker else {},
            "ready_for_validation": self._current_result.success
        }
    
    async def _generate_layer2_skeptic_challenge(
        self, expert_name: str, domain: str, proposal_content: str
    ) -> str:
        """第二层：针对某专家方案生成质疑者的一轮质疑内容（偏向具像化与可实施，避免虚理论）。"""
        prompt = f"""你是实施阶段的质疑者，专门对「{domain}」领域专家 {expert_name} 的实施方案进行批判性审阅。

**重要原则：质疑必须偏向「具像化的计划与实施」，不要停留在虚理论。** 多问具体步骤、责任、验收与时间线，少问抽象概念。

## 该专家的方案内容
{proposal_content[:6000]}

## 任务（优先具像化与可执行）
请从以下维度提出建设性质疑（抓住可落地、可验收的要点）：
1. **可执行步骤**：是否拆成具体动作？缺哪些步骤、责任人或交付物？时间与里程碑是否清晰？
2. **验收与指标**：如何判断某一步完成？有无可量化的验收标准？
3. **实施约束**：资源、依赖、技术约束是否写清？实施难度与成本是否现实？
4. **风险与替代**：落地过程中有哪些具体风险？有无更易实施的替代做法？

**请避免**：只谈「应加强」「需重视」等空泛表述；**务必**把质疑落在具体计划、步骤与验收上。

请直接输出你的质疑与建议（一段完整文字），不要用 JSON，不要加「质疑：」等前缀。"""
        try:
            if getattr(self, "llm_adapter", None) is None:
                return ""
            if hasattr(self.llm_adapter, "invoke"):
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        lambda: self.llm_adapter.invoke(prompt)
                    ),
                    timeout=60.0,
                )
                text = getattr(response, "content", None) or (response if isinstance(response, str) else "")
                return (text or "").strip()
            # 回退：用任意一位专家的 call_llm
            if self.dynamic_experts:
                parts = []
                async for chunk in self.dynamic_experts[0].call_llm(prompt):
                    parts.append(chunk)
                return "".join(parts).strip()
        except Exception as e:
            logger.warning(f"第二层质疑生成失败 ({expert_name}): {e}")
        return ""

    def _extract_key_decisions(self, validation_output: Dict[str, Any]) -> List[str]:
        """从综合方案中提取关键决策"""
        decisions = []
        
        # 从实施阶段中提取
        phases = validation_output.get('implementation_phases', [])
        for phase in phases:
            if isinstance(phase, dict):
                name = phase.get('name', '')
                desc = phase.get('description', '')
                if name:
                    decisions.append(f"实施阶段: {name} - {desc[:80]}" if desc else f"实施阶段: {name}")
        
        # 从成功标准中提取
        criteria = validation_output.get('success_criteria', [])
        for criterion in criteria:
            if isinstance(criterion, str) and criterion:
                decisions.append(f"成功标准: {criterion}")
        
        # 从质疑点中提取需要关注的决策
        challenges = validation_output.get('challenges', [])
        for ch in challenges:
            if isinstance(ch, dict) and ch.get('severity') == 'high':
                decisions.append(f"高优先级质疑: {ch.get('point', '')}")
        
        return decisions[:10]  # 最多10个
    
    def _generate_implementation_plan_text(
        self,
        validation_output: Dict[str, Any],
        expert_proposals: List[Dict[str, Any]]
    ) -> str:
        """生成完整的实施计划文本"""
        parts = []
        
        # 标题和概述
        title = validation_output.get('title', '实施方案')
        summary = validation_output.get('summary', '')
        parts.append(f"# {title}\n")
        if summary:
            parts.append(f"## 概述\n{summary}\n")
        
        # 时间线
        timeline = validation_output.get('timeline', '')
        total_duration = validation_output.get('total_duration', '')
        if timeline or total_duration:
            parts.append(f"## 时间规划\n")
            if total_duration:
                parts.append(f"总预估时间: {total_duration}\n")
            if timeline:
                parts.append(f"时间线: {timeline}\n")
        
        # 实施阶段
        phases = validation_output.get('implementation_phases', [])
        if phases:
            parts.append(f"## 实施阶段 ({len(phases)}个)\n")
            for phase in phases:
                if isinstance(phase, dict):
                    phase_num = phase.get('phase', '')
                    name = phase.get('name', '未命名阶段')
                    desc = phase.get('description', '')
                    duration = phase.get('duration', '待定')
                    steps = phase.get('steps', [])
                    responsible = phase.get('responsible_experts', [])
                    deliverables = phase.get('deliverables', [])
                    
                    parts.append(f"\n### 阶段{phase_num}: {name}\n")
                    if desc:
                        parts.append(f"{desc}\n")
                    parts.append(f"- 预估时间: {duration}\n")
                    if responsible:
                        parts.append(f"- 负责专家: {', '.join(responsible)}\n")
                    if steps:
                        parts.append(f"- 具体步骤:\n")
                        for j, step in enumerate(steps, 1):
                            if isinstance(step, str):
                                parts.append(f"  {j}. {step}\n")
                            elif isinstance(step, dict):
                                name = step.get('name', step.get('description', str(step)))
                                desc = step.get('description', '')
                                deliverable = step.get('deliverable', '')
                                parts.append(f"  {j}. {name}\n")
                                if desc and desc != name:
                                    parts.append(f"     {desc}\n")
                                if deliverable:
                                    parts.append(f"     交付物: {deliverable}\n")
                    if deliverables:
                        parts.append(f"- 交付物: {', '.join(deliverables)}\n")
        
        # 按领域划分的步骤汇总
        domain_breakdown = validation_output.get('domain_breakdown', [])
        if domain_breakdown:
            parts.append(f"\n## 各领域实施步骤汇总\n")
            for db in domain_breakdown:
                if isinstance(db, dict):
                    domain = db.get('domain', '')
                    expert = db.get('expert', '')
                    key_steps = db.get('key_steps', [])
                    duration = db.get('duration', '')
                    parts.append(f"\n### {domain}（负责: {expert}）\n")
                    if duration:
                        parts.append(f"- 预估时间: {duration}\n")
                    for i, s in enumerate(key_steps[:10], 1):
                        parts.append(f"  {i}. {s}\n")
        
        # 资源需求
        resources = validation_output.get('required_resources', [])
        if resources:
            parts.append(f"\n## 资源需求\n")
            for res in resources:
                parts.append(f"- {res}\n")
        
        # 成功标准
        criteria = validation_output.get('success_criteria', [])
        if criteria:
            parts.append(f"\n## 成功标准\n")
            for c in criteria:
                parts.append(f"- {c}\n")
        
        # 风险评估
        risk = validation_output.get('risk_assessment', '')
        if risk:
            parts.append(f"\n## 风险评估\n{risk}\n")
        
        # 质疑点
        challenges = validation_output.get('challenges', [])
        if challenges:
            parts.append(f"\n## 质疑点 ({len(challenges)}个)\n")
            for i, ch in enumerate(challenges, 1):
                if isinstance(ch, dict):
                    point = ch.get('point', '')
                    severity = ch.get('severity', 'medium')
                    suggestion = ch.get('suggestion', '')
                    parts.append(f"{i}. [{severity.upper()}] {point}\n")
                    if suggestion:
                        parts.append(f"   建议: {suggestion}\n")
        
        return "".join(parts)
    
    def get_last_result(self) -> Optional[DiscussionResult]:
        """获取最近一次讨论结果"""
        return self._current_result
    
    def get_all_results(self) -> List[DiscussionResult]:
        """获取所有讨论结果"""
        return self._discussion_results.copy()
    
    def reset(self):
        """重置讨论系统"""
        self.scholar = None
        self.synthesizer = None
        self.dynamic_experts.clear()
        if self.expert_factory:
            self.expert_factory.clear_experts()
        self.consensus_tracker.clear()
        self._current_result = None

