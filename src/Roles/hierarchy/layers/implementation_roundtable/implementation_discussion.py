"""
实施层圆桌讨论主类

实现完整的实施讨论系统，采用动态专家生成模式：
1. 科学家分析任务需求，确定所需专家
2. 动态生成各领域专家智能体
3. 专家讨论，各自给出实施方案
4. 综合者汇总方案，找出质疑点
5. 输出传递给第三层检验系统
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator, TYPE_CHECKING
import asyncio
import logging
import uuid
import os
import re
import json

# 复用第一层圆桌讨论的通信组件
from ....roundtable import MessageBus, CommunicationProtocol, AgentMessage, MessageType

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


@dataclass
class DiscussionConfig:
    """讨论配置"""
    max_experts: int = 50                # 最大专家数量（不限制，按角色安排文件创建）
    min_experts: int = 2                 # 最小专家数量
    timeout_seconds: float = 600.0       # 讨论超时时间
    enable_debate: bool = False          # 是否启用交叉审阅辩论（默认关闭以提高效率）
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
    # 专家发言文件记录（用于任务恢复）
    expert_speech_files: List[Dict[str, Any]] = field(default_factory=list)  # [{expert_name, domain, relative_file_path, timestamp}]


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
        
        yield "\n" + "=" * 60 + "\n"
        yield "          实施圆桌讨论系统 (动态专家模式)\n"
        yield "=" * 60 + "\n"
        
        try:
            # ============ 优先使用角色安排文件 ============
            role_arrangement_file = first_layer_output.get('implementation_role_arrangement_file', '')
            pre_defined_roles = []
            if role_arrangement_file and os.path.exists(role_arrangement_file):
                try:
                    with open(role_arrangement_file, 'r', encoding='utf-8') as f:
                        pre_defined_roles = json.load(f)
                    yield f"\n[信息] 已加载角色安排文件，共 {len(pre_defined_roles)} 个角色\n"
                except Exception as e:
                    logger.warning(f"加载角色安排文件失败: {e}")
            
            # ============ 阶段1: 确定专家团队 ============
            if pre_defined_roles:
                # 使用预定义角色，跳过科学家分析
                yield "\n[阶段1/5] 使用预定义角色安排\n"
                yield "-" * 40 + "\n"
                yield f"[信息] 从角色安排文件加载 {len(pre_defined_roles)} 个角色\n"
                
                # 转换为专家规格
                expert_specs = []
                for role in pre_defined_roles:
                    expert_specs.append({
                        "role": role.get('role_name', '').replace(' ', '_').lower(),
                        "name": role.get('role_name', '领域专家'),
                        "domain": role.get('professional_domain', role.get('layer', '通用')),
                        "expertise": role.get('skills', []),
                        "reason": role.get('role_description', '项目需要'),
                        "tasks": role.get('tasks', []),
                        "layer": role.get('layer', '')
                    })
                
                self._current_result.scholar_analysis = {
                    "task_analysis": "使用预定义角色安排",
                    "project_type": "综合项目",
                    "required_experts": expert_specs
                }
            else:
                # 无预定义角色，使用科学家分析
                yield "\n[阶段1/5] 科学家分析任务需求\n"
                yield "-" * 40 + "\n"
                
                self.scholar = ScholarAgent(llm_adapter=self.llm_adapter)
                
                async for chunk in self.scholar.analyze_required_experts(
                    task_list, first_layer_output
                ):
                    yield chunk
                
                # 获取分析结果
                expert_specs = self.scholar.get_required_experts_specs()
                self._current_result.scholar_analysis = {
                    "task_analysis": self.scholar.last_analysis.task_analysis if self.scholar.last_analysis else "",
                    "project_type": self.scholar.last_analysis.project_type if self.scholar.last_analysis else "",
                    "required_experts": expert_specs
                }
            
            # ============ 阶段2: 动态生成专家 ============
            yield "\n\n[阶段2/5] 动态生成专家团队\n"
            yield "-" * 40 + "\n"
            
            self.expert_factory = DynamicAgentFactory(llm_adapter=self.llm_adapter)
            
            # 使用全部专家规格（不再限制数量）
            specs_to_create = expert_specs
            if len(specs_to_create) < self.config.min_experts:
                default_specs = [
                    {"role": "project_planner", "name": "项目规划师", "domain": "项目规划", "reason": "统筹项目"},
                    {"role": "technical_expert", "name": "技术专家", "domain": "技术实施", "reason": "技术支持"}
                ]
                for spec in default_specs:
                    if len(specs_to_create) >= self.config.min_experts:
                        break
                    if spec['role'] not in [s.get('role', '') for s in specs_to_create]:
                        specs_to_create.append(spec)
            
            self.dynamic_experts = self.expert_factory.create_experts_batch(specs_to_create)
            
            yield f"\n已创建 {len(self.dynamic_experts)} 位专家:\n"
            for i, expert in enumerate(self.dynamic_experts, 1):
                yield f"  {i}. {expert.name} ({expert.domain})\n"
                self._current_result.experts_created.append(expert.to_dict())
            
            # ============ 保存专家角色Prompt到roles目录 ============
            discussion_base_path = first_layer_output.get('discussion_base_path', '')
            if discussion_base_path:
                roles_dir = os.path.join(discussion_base_path, "roles")
                os.makedirs(roles_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                for expert in self.dynamic_experts:
                    role_file = self._save_expert_role_prompt(
                        expert, roles_dir, timestamp, first_layer_output
                    )
                    if role_file:
                        yield f"  [角色文件] {os.path.basename(role_file)}\n"
            
            # ============ 阶段3a: 专家独立提案 ============
            yield "\n\n[阶段3a/5] 专家独立提案\n"
            yield "-" * 40 + "\n"
            
            # 构建任务上下文
            task_context = {
                "task_list": task_list,
                "first_layer_output": first_layer_output,
                "task": {
                    "name": "实施方案讨论",
                    "description": first_layer_output.get('discussion_summary', '')
                }
            }
            
            # 加载第一层汇总文档索引
            layer1_summary_index = first_layer_output.get('layer1_summary', {})
            layer1_role_summaries = {}  # role -> summary_content
            
            # 如果有第一层汇总文档索引，加载各角色汇总
            if layer1_summary_index:
                task_context['layer1_summary_index'] = layer1_summary_index
                yield f"[信息] 已加载第一层讨论汇总文档索引\n"
                
                # 从索引中获取各角色汇总文档
                role_summary_records = layer1_summary_index.get('role_summary_records', [])
                discussion_base = first_layer_output.get('discussion_base_path', '')
                
                for record in role_summary_records:
                    role_name = record.get('role', '')
                    relative_file = record.get('relative_file', '')
                    if relative_file and discussion_base:
                        full_path = os.path.join(discussion_base, relative_file)
                        if os.path.exists(full_path):
                            try:
                                with open(full_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                layer1_role_summaries[role_name] = content
                                # 也用领域名存一份（去掉 expert_ 前缀）
                                if role_name.startswith('expert_'):
                                    domain_name = role_name.replace('expert_', '').split('（')[0]
                                    layer1_role_summaries[domain_name] = content
                            except Exception as e:
                                logger.warning(f"读取角色汇总文档失败 {full_path}: {e}")
                
                if layer1_role_summaries:
                    yield f"[信息] 已加载 {len(layer1_role_summaries)} 个领域汇总文档\n"
            
            # ============ 并行执行专家发言 ============
            yield f"\n[信息] {len(self.dynamic_experts)} 位专家并行生成发言中...\n"
            
            # 为每个专家准备上下文
            expert_contexts = []
            for expert in self.dynamic_experts:
                # 为当前专家查找匹配的第一层领域汇总文档
                expert_domain_summary = ""
                if layer1_role_summaries:
                    domain = expert.domain
                    possible_keys = [
                        domain,
                        f"expert_{domain}",
                        f"expert_{domain}（与对应质疑者）",
                    ]
                    for key in possible_keys:
                        if key in layer1_role_summaries:
                            expert_domain_summary = layer1_role_summaries[key]
                            break
                    # 模糊匹配
                    if not expert_domain_summary:
                        for key, content in layer1_role_summaries.items():
                            if domain in key or key in domain:
                                expert_domain_summary = content
                                break
                
                # 构建专家上下文
                expert_task_context = task_context.copy()
                if expert_domain_summary:
                    expert_task_context['layer1_domain_summary_md'] = expert_domain_summary
                expert_contexts.append((expert, expert_task_context, bool(expert_domain_summary)))
            
            # 并行执行所有专家的发言任务
            async def expert_propose_task(expert, ctx):
                """单个专家的发言任务"""
                return await expert.propose_solution_full(ctx)
            
            tasks = [expert_propose_task(exp, ctx) for exp, ctx, _ in expert_contexts]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理并行执行结果
            expert_proposals = []
            for i, (expert, ctx, has_summary) in enumerate(expert_contexts):
                result = results[i]
                
                if isinstance(result, Exception):
                    logger.warning(f"专家 {expert.name} 发言失败: {result}")
                    yield f"\n[{expert.name}] 发言失败: {result}\n"
                    continue
                
                # 输出发言内容
                yield f"\n[{expert.name}] ({expert.domain})"
                if has_summary:
                    yield " [已加载第一层汇总]"
                yield f"\n{'─' * 40}\n"
                yield result
                yield f"\n{'─' * 40}\n"
                
                # 获取结构化数据
                structured_proposal = None
                if expert.last_proposal:
                    structured_proposal = expert.last_proposal.to_dict()
                
                # 记录方案
                proposal = {
                    "expert_name": expert.name,
                    "domain": expert.domain,
                    "content": result,
                    "structured": structured_proposal
                }
                expert_proposals.append(proposal)
                self._current_result.expert_proposals.append(proposal)
                
                # 保存专家发言到implement目录
                if discussion_base_path:
                    speech_file = self._save_expert_speech(
                        expert, proposal, discussion_base_path, timestamp
                    )
                    if speech_file:
                        yield f"  [发言已保存] {os.path.basename(speech_file)}\n"
                
                # 记录到共识追踪器
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
            
            yield f"\n[信息] {len(expert_proposals)} 位专家并行发言完成\n"
            
            # ============ 阶段3b: 专家交叉审阅 ============
            cross_reviews = []  # 所有审阅结果
            if self.config.enable_debate and len(self.dynamic_experts) >= 2:
                yield "\n\n[阶段3b/5] 专家交叉审阅\n"
                yield "-" * 40 + "\n"
                yield f"[信息] {len(self.dynamic_experts)} 位专家互相审阅方案\n\n"
                
                for reviewer_expert in self.dynamic_experts:
                    for proposal in expert_proposals:
                        # 不审阅自己的方案
                        if proposal['expert_name'] == reviewer_expert.name:
                            continue
                        
                        review_content = []
                        async for chunk in reviewer_expert.review_proposal(proposal, task_context):
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
            task_context['cross_reviews'] = cross_reviews
            
            # ============ 阶段4: 综合者汇总 ============
            yield "\n\n[阶段4/5] 综合者汇总\n"
            yield "-" * 40 + "\n"
            
            self.synthesizer = SynthesizerAgent(llm_adapter=self.llm_adapter)
            
            async for chunk in self.synthesizer.synthesize_and_challenge(
                expert_proposals, task_context
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
            self._current_result.total_rounds = 5  # 五个阶段（取消了团体汇总）
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
            "proposals": self._current_result.expert_proposals,
            "cross_reviews": self._current_result.cross_reviews,
            "synthesized_plan": self._current_result.synthesized_plan,
            "challenges": self._current_result.challenges,
            "key_decisions": self._current_result.key_decisions,
            "implementation_plan": self._current_result.implementation_plan,
            "total_rounds": self._current_result.total_rounds,
            "consensus_level": self._current_result.final_consensus_level,
            "consensus_summary": self.consensus_tracker.get_discussion_summary() if self.consensus_tracker else {},
            "ready_for_validation": self._current_result.success,
        }
    
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
                                parts.append(f"  {j}. {step.get('name', step.get('description', str(step)))}\n")
                    if deliverables:
                        parts.append(f"- 交付物: {', '.join(deliverables)}\n")
        
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

    def _save_expert_role_prompt(
        self,
        expert: DynamicExpertAgent,
        roles_dir: str,
        timestamp: str,
        first_layer_output: Dict[str, Any]
    ) -> Optional[str]:
        """
        保存动态专家的角色Prompt到roles目录
        
        Args:
            expert: 动态专家智能体实例
            roles_dir: 角色文件保存目录
            timestamp: 时间戳
            first_layer_output: 第一层输出（用于构建上下文）
        
        Returns:
            保存的文件路径，失败返回None
        """
        try:
            # 构建角色文件名（第二层_领域名_时间戳）
            safe_domain = expert.domain.replace("/", "_").replace("\\", "_")
            role_filename = f"layer2_expert_{safe_domain}_{timestamp}.json"
            role_path = os.path.join(roles_dir, role_filename)
            
            # 构建示例任务上下文以生成完整prompt
            sample_task_context = {
                "task_list": [],
                "first_layer_output": first_layer_output,
                "task": {
                    "name": "实施方案讨论",
                    "description": first_layer_output.get('discussion_summary', '')
                },
                "user_goal": first_layer_output.get('user_goal', ''),
            }
            
            # 获取专家的提案prompt
            proposal_prompt = expert._build_proposal_prompt(sample_task_context)
            
            # 构建角色定义
            expertise_text = "、".join(expert.expertise) if expert.expertise else expert.domain
            role_definition = f"{expert.domain}领域实施专家，专注于将第一层讨论成果转化为可执行的实施步骤"
            
            # 构建完整的角色JSON
            role_data = {
                "agent_id": expert.agent_id,
                "agent_name": expert.name,
                "layer": "实施层（第二层）",
                "role": expert.role,
                "domain": expert.domain,
                "expertise": expert.expertise,
                "reason": expert.reason,
                "role_definition": role_definition,
                "professional_skills": [
                    f"{expert.domain}专业知识",
                    "实施步骤细化",
                    "方案设计与规划",
                    "风险评估与规避",
                    "资源预估与依赖分析"
                ] + list(expert.expertise[:3]),
                "working_style": "专业严谨、注重可执行性",
                "behavior_guidelines": [
                    "紧扣用户目标，不做空泛表述",
                    "每个步骤具体可执行，含输入条件、具体动作、产出物",
                    "基于第一层讨论成果细化实施方案",
                    "考虑实际可行性和约束条件",
                    "提供风险评估和规避措施",
                    "在本领域内创新突破，但不越界到其他专业"
                ],
                "output_format": """
## 专业分析
[从本领域角度对任务关键点的专业分析]

## 实施步骤
### 步骤1: [步骤名称]
- **描述**: [详细描述这一步要做什么]
- **预估时间**: [如：2天、1周]
- **交付物**: [这一步的产出]
- **验收标准**: [如何验证完成]

### 步骤2: ...

## 所需资源
- [资源1]
- [资源2]

## 风险与规避
| 风险 | 严重程度 | 规避措施 |
|------|----------|----------|
| ... | 高/中/低 | ... |

## 验证要点
[如何反复验证实施准确性]
""",
                "system_prompt": proposal_prompt,
                "health_status": "healthy",
                "created_at": datetime.now().isoformat(),
            }
            
            # 保存角色文件
            with open(role_path, "w", encoding="utf-8") as f:
                json.dump(role_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"保存第二层专家角色Prompt: {role_filename}")
            return role_path
            
        except Exception as e:
            logger.warning(f"保存专家角色Prompt失败 ({expert.name}): {e}")
            return None

    def _save_expert_speech(
        self,
        expert: DynamicExpertAgent,
        proposal: Dict[str, Any],
        discussion_base_path: str,
        timestamp: str
    ) -> Optional[str]:
        """
        保存专家发言到implement目录
        
        Args:
            expert: 专家智能体实例
            proposal: 专家提案内容
            discussion_base_path: 讨论基础目录
            timestamp: 时间戳
        
        Returns:
            保存的文件路径，失败返回None
        """
        try:
            # 确保implement目录存在
            implement_dir = os.path.join(discussion_base_path, "implement")
            os.makedirs(implement_dir, exist_ok=True)
            
            # 构建文件名（专家名_领域_时间戳）
            safe_name = expert.name.replace("/", "_").replace("\\", "_").replace(" ", "_")
            safe_domain = expert.domain.replace("/", "_").replace("\\", "_").replace(" ", "_")
            speech_filename = f"expert_speech_{safe_name}_{safe_domain}_{timestamp}.md"
            speech_path = os.path.join(implement_dir, speech_filename)
            
            # 构建发言内容
            content = proposal.get('content', '')
            structured = proposal.get('structured', {})
            
            # 写入Markdown文件
            with open(speech_path, "w", encoding="utf-8") as f:
                f.write(f"# 第二层专家发言 - {expert.name}\n\n")
                f.write(f"**领域**: {expert.domain}\n")
                f.write(f"**专长**: {', '.join(expert.expertise) if expert.expertise else '通用'}\n")
                f.write(f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("---\n\n")
                f.write("## 发言内容\n\n")
                f.write(content)
                
                # 如果有结构化数据，也保存
                if structured:
                    f.write("\n\n---\n\n## 结构化数据\n\n")
                    f.write("```json\n")
                    f.write(json.dumps(structured, ensure_ascii=False, indent=2))
                    f.write("\n```\n")
            
            logger.info(f"保存第二层专家发言: {speech_filename}")
            
            # 记录到 expert_speech_files 用于任务恢复
            if self._current_result:
                relative_path = f"implement/{speech_filename}"
                self._current_result.expert_speech_files.append({
                    "expert_name": expert.name,
                    "domain": expert.domain,
                    "relative_file_path": relative_path,
                    "timestamp": timestamp,
                })
            
            return speech_path
            
        except Exception as e:
            logger.warning(f"保存专家发言失败 ({expert.name}): {e}")
            return None
