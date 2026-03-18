"""
动态专家智能体

可配置任意领域的专家智能体，根据科学家分析结果动态创建。
第二层要求各领域专家产出细化、可扩展的实施步骤。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator
import asyncio
import json
import logging
import os
import re
import uuid

from .base_hierarchical_agent import (
    BaseHierarchicalAgent, HierarchicalAgentConfig, AgentCapability
)
from ..types import LayerType, AgentAction
from ..layers.implementation_roundtable.domain_step_templates import (
    get_min_steps_for_domain,
    get_phase_hints_for_domain,
    get_step_expansion_hint,
)


logger = logging.getLogger(__name__)


@dataclass
class ExpertProposal:
    """专家方案提议"""
    expert_role: str
    expert_name: str
    domain: str
    proposal_content: str
    professional_analysis: str = ""
    implementation_steps: List[Dict[str, Any]] = field(default_factory=list)
    estimated_duration: str = ""
    required_resources: List[str] = field(default_factory=list)
    potential_risks: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    confidence_level: float = 0.8
    verification_notes: str = ""  # 实施准确性自检与验证要点
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "expert_role": self.expert_role,
            "expert_name": self.expert_name,
            "domain": self.domain,
            "professional_analysis": self.professional_analysis,
            "implementation_steps": self.implementation_steps,
            "estimated_duration": self.estimated_duration,
            "required_resources": self.required_resources,
            "potential_risks": self.potential_risks,
            "dependencies": self.dependencies,
            "confidence_level": self.confidence_level,
            "verification_notes": self.verification_notes,
            "timestamp": self.timestamp.isoformat()
        }


class DynamicExpertAgent(BaseHierarchicalAgent):
    """
    动态专家智能体
    
    可根据配置扮演任意领域的专家角色，
    根据专业领域知识给出实施方案。
    """
    
    def __init__(
        self,
        role: str,
        name: str,
        domain: str,
        expertise: List[str] = None,
        reason: str = "",
        llm_adapter=None,
        agent_id: str = None
    ):
        """
        初始化动态专家
        
        Args:
            role: 角色标识 (如 software_architect)
            name: 显示名称 (如 软件架构师)
            domain: 专业领域 (如 软件架构设计)
            expertise: 具体专长列表
            reason: 被选中的原因
            llm_adapter: LLM适配器
            agent_id: 智能体ID
        """
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"{role}_{uuid.uuid4().hex[:6]}",
            name=name,
            layer=LayerType.IMPLEMENTATION,
            role=role,
            capabilities={
                AgentCapability.REASONING,
                AgentCapability.PLANNING,
                AgentCapability.IMPLEMENTATION,
                AgentCapability.COMMUNICATION
            }
        )
        super().__init__(config, llm_adapter)
        
        self.domain = domain
        self.expertise = expertise or []
        self.reason = reason
        self.last_proposal: Optional[ExpertProposal] = None
        self.last_review: Optional[Dict[str, Any]] = None
    
    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """执行专家动作"""
        yield f"[{self.name}] 正在分析任务...\n"
        
        prompt = self.get_prompt(context)
        response_parts = []
        
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        full_response = "".join(response_parts)
        self.last_result = {"action": "propose", "response": full_response}
    
    async def propose_solution(
        self,
        task_context: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        根据专业领域给出实施方案
        
        Args:
            task_context: 任务上下文，包含任务详情、其他专家方案等
        
        Yields:
            方案提议过程的输出
        """
        yield f"\n[{self.name}] ({self.domain})\n"
        yield f"{'─' * 40}\n"
        
        prompt = self._build_proposal_prompt(task_context)
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        full_response = "".join(response_parts)
        
        # 第二层已取消解析结构化，仅保留原文方案
        self.last_proposal = ExpertProposal(
            expert_role=self.role,
            expert_name=self.name,
            domain=self.domain,
            proposal_content=full_response,
        )
        yield f"\n{'─' * 40}\n"
    
    async def propose_solution_full(
        self,
        task_context: Dict[str, Any]
    ) -> str:
        """
        并行模式：一次性返回完整发言内容（非流式）
        
        Args:
            task_context: 任务上下文
        
        Returns:
            完整的发言内容字符串
        """
        prompt = self._build_proposal_prompt(task_context)
        response_parts = []
        async for chunk in self.call_llm(prompt):
            response_parts.append(chunk)
        full_response = "".join(response_parts)
        
        # 保存到 last_proposal
        self.last_proposal = ExpertProposal(
            expert_role=self.role,
            expert_name=self.name,
            domain=self.domain,
            proposal_content=full_response,
        )
        return full_response
    
    def get_proposal(self) -> Optional[ExpertProposal]:
        """获取最近的方案提议"""
        return self.last_proposal
    
    def _build_proposal_prompt(self, task_context: Dict[str, Any]) -> str:
        """构建专业化提示词（紧扣用户目标、第一层讨论与质疑者意见、可实施措施并反复验证）"""
        my_tasks = task_context.get("my_tasks")  # 实施任务分析分配的本角色任务列表
        if my_tasks and isinstance(my_tasks, list):
            return self._build_proposal_prompt_by_tasks(task_context, my_tasks)
        task = task_context.get('task', {})
        task_name = task.get('name', '未知任务') if isinstance(task, dict) else str(task)
        task_desc = task.get('description', '') if isinstance(task, dict) else ''
        user_goal = task_context.get('user_goal', '') or task_desc
        first_layer_expert_speeches = task_context.get('first_layer_expert_speeches', [])
        first_layer_skeptic_critiques = task_context.get('first_layer_skeptic_critiques', [])

        other_proposals = task_context.get('other_proposals', [])
        other_proposals_text = ""
        if other_proposals:
            other_proposals_text = "\n## 其他专家的方案\n"
            for prop in other_proposals[:3]:
                other_proposals_text += f"\n### {prop.get('expert_name', '专家')}\n"
                content = prop.get('content', '')[:300]
                other_proposals_text += f"{content}...\n"

        layer1_expert_block = ""
        if first_layer_expert_speeches:
            layer1_expert_block = "\n## 第一层本领域专家讨论（请据此给出可实施步骤）\n"
            for i, s in enumerate(first_layer_expert_speeches[:5], 1):
                layer1_expert_block += f"\n### 第{s.get('round', i)}轮发言\n"
                if s.get('thinking'):
                    layer1_expert_block += f"思考：{s.get('thinking', '')[:400]}...\n"
                layer1_expert_block += f"发言：{s.get('speech', '')}\n"
        layer1_skeptic_block = ""
        if first_layer_skeptic_critiques:
            layer1_skeptic_block = "\n## 质疑者对本领域观点的意见（请吸纳并验证实施准确性）\n"
            for i, s in enumerate(first_layer_skeptic_critiques[:5], 1):
                layer1_skeptic_block += f"\n- 第{s.get('round', i)}轮质疑：{s.get('speech', '')}\n"

        expertise_text = "、".join(self.expertise) if self.expertise else self.domain
        min_steps = get_min_steps_for_domain(self.domain)
        phase_hints = get_phase_hints_for_domain(self.domain)
        expansion_hint = get_step_expansion_hint(self.domain)
        phase_hints_text = "、".join(phase_hints[:6]) if phase_hints else "需求理解、方案设计、执行实施、检查验证、交付总结"

        return f"""【重要】第二层「实施步骤细化」：你对应第一层本领域专家，需根据第一层讨论结果与质疑者意见，给出**可落地、可验证**的实施步骤。请明确用户目标，不要提出过虚发言，输出必须是可实施措施。

你是一位{self.name}，专精于{self.domain}。
你的具体专长包括：{expertise_text}
你被选中参与此项目的原因：{self.reason}

## 用户目标（必须紧扣）
{user_goal}

## 当前任务
任务名称：{task_name}
任务描述：{task_desc}
{layer1_expert_block}
{layer1_skeptic_block}
{other_proposals_text}

## 领域步骤细化要求（{self.domain}）

本领域建议的实施阶段参考：{phase_hints_text}
步骤扩展要求：{expansion_hint}
**至少需要 {min_steps} 个详细实施步骤**，每个步骤需细化到可执行级别。

## 输出要求

请紧扣用户目标，根据第一层本领域专家的讨论与质疑者意见，从{self.domain}角度给出**可实施、可验证**的详细步骤。不要空泛表述，每条步骤需具体可执行，并在方案中简要说明如何验证实施准确性。

**请严格按以下JSON格式输出你的方案**（用```json```代码块包裹）：

```json
{{{{
  "professional_analysis": "从{self.domain}角度对任务关键点的专业分析",
  "implementation_steps": [
    {{{{
      "step": 1,
      "name": "步骤名称",
      "description": "详细描述这一步要做什么（含输入条件、具体动作、产出物、验收标准）",
      "duration": "预估时间（如：2天、1周）",
      "deliverable": "这一步的交付物",
      "acceptance_criteria": "可选：验收标准"
    }}}}
  ],
  "estimated_duration": "总时间估算",
  "required_resources": ["所需资源1", "所需资源2"],
  "potential_risks": [
    {{{{
      "risk": "风险描述",
      "severity": "高/中/低",
      "mitigation": "规避方式"
    }}}}
  ],
  "dependencies": ["依赖项1"],
  "confidence_level": 0.8,
  "verification_notes": "针对上述步骤的准确性自检与验证要点（如何反复验证实施准确性）"
}}}}
```

请确保：
1. **明确用户目标**：方案围绕用户目标展开，不要过虚、空泛。
2. implementation_steps 至少包含 {min_steps} 个**可实施**步骤，每步具体可执行（做什么、怎么做、产出是什么）。
3. 每个步骤都有明确的 deliverable，且与第一层讨论及质疑者关切相呼应。
4. potential_risks 至少列出2个风险；verification_notes 中说明如何反复验证实施准确性。
5. confidence_level 在0.0-1.0之间。

请直接输出你的JSON方案：
"""

    def _build_proposal_prompt_by_tasks(self, task_context: Dict[str, Any], my_tasks: List[str]) -> str:
        """按实施任务分析分配的任务列表构建提示；若提供第一层本领域汇总文档，要求先阅读再细化实施步骤。"""
        user_goal = task_context.get("user_goal", "") or task_context.get("discussion_summary", "")
        role_prompt = task_context.get("role_prompt", "")
        tasks_text = "\n".join(f"- {t}" for t in (my_tasks or [])[:50])
        layer1_domain_md = (task_context.get("layer1_domain_summary_md") or "").strip()
        layer1_block = ""
        intro = "请针对每项任务给出可执行方案（步骤、交付物、预估时长），直接以 Markdown 输出，无需 JSON。"
        if layer1_domain_md:
            layer1_block = f"""
## 第一层本领域讨论汇总（请先阅读上述角色分工与本段汇总，再据此细化实施步骤）
以下为第一层讨论中与你本领域相关的专家与质疑者汇总，请结合你负责的任务逐项给出可执行方案。

{layer1_domain_md[:12000]}

---
"""
            intro = "请**先阅读下方第一层本领域汇总文档**，再针对每项任务给出可执行方案（步骤、交付物、预估时长），直接以 Markdown 输出，无需 JSON。"
        return f"""你是一位实施角色「{self.name}」，负责执行以下分配给你的任务。{intro}

{role_prompt}

## 用户/项目目标
{user_goal[:2000] if user_goal else "（见第一层讨论汇总）"}
{layer1_block}
## 你负责的任务（请逐项给出可执行方案）
{tasks_text}

## 输出要求
- 先结合第一层本领域讨论要点，再按上述任务逐项写出：任务名称、实施步骤（具体可执行）、交付物、预估时长。
- 使用清晰 Markdown（标题、列表），无需 JSON。
- 确保步骤可落地、可验收。
请直接输出你的方案：
"""
    
    async def revise_proposal_after_skeptic(
        self,
        current_proposal_content: str,
        skeptic_challenge: str,
        task_context: Dict[str, Any],
        revision_round: int = 1,
    ) -> str:
        """
        根据质疑者的意见完善修改自己的方案（第二层质疑→修订循环）。
        
        Args:
            current_proposal_content: 当前方案全文
            skeptic_challenge: 质疑者本轮质疑/建议
            task_context: 任务上下文
            revision_round: 第几轮修订（1 或 2）
            
        Returns:
            修订后的方案全文
        """
        prompt = f"""你是{self.name}，专精于{self.domain}。你刚提交了实施方案，质疑者提出了以下意见，请据此完善你的方案。

## 你当前的方案内容
{current_proposal_content[:8000]}

## 质疑者的质疑/建议（请认真吸纳）
{skeptic_challenge}

## 要求
1. 保留你仍坚持的合理内容，对质疑中合理的部分进行补充、修正或澄清。
2. 若方案含 JSON 或结构化内容，修订后请保持合法 JSON 与原有字段结构。
3. 直接输出修订后的**完整方案**（可含 markdown 与代码块），不要只写修改片段，不要加「修订版」等前缀。
4. **思维与边界**：可在**本领域内**突破思维、创新完成任务；但在**角色领域内**不要随意突破边界，勿越界到其他专业。
"""
        parts = []
        async for chunk in self.call_llm(prompt):
            parts.append(chunk)
        revised = "".join(parts).strip()
        return revised if revised else current_proposal_content

    async def review_proposal(
        self,
        proposal: Dict[str, Any],
        task_context: Dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        """
        审阅其他专家的方案（专家交叉审阅）
        
        Args:
            proposal: 待审阅的方案，包含 expert_name, content 等
            task_context: 任务上下文
        
        Yields:
            审阅过程输出
        """
        expert_name = proposal.get('expert_name', '未知专家')
        proposal_content = proposal.get('content', '')
        
        yield f"\n[{self.name}] 审阅 {expert_name} 的方案\n"
        separator = '\u2500' * 30
        yield f"{separator}\n"
        
        prompt = f"""你是{self.name}，专精于{self.domain}。
请从你的专业角度审阅以下方案，给出客观的评价。

## 待审阅方案（来自 {expert_name}）
{proposal_content[:6000]}

## 请输出你的审阅意见，包括：
1. **总体评价**：方案的优点与不足
2. **专业视角**：从{self.domain}角度的建议
3. **立场**：你对该方案的态度（strongly_agree/agree/neutral/disagree/strongly_disagree）
4. **改进建议**：具体可行的改进方向

请简洁输出你的审阅意见：
"""
        
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        full_response = "".join(response_parts)
        
        # 解析立场
        stance = 'neutral'
        response_lower = full_response.lower()
        if 'strongly_agree' in response_lower or '非常赞同' in full_response:
            stance = 'strongly_agree'
        elif 'strongly_disagree' in response_lower or '强烈反对' in full_response:
            stance = 'strongly_disagree'
        elif 'agree' in response_lower or '赞同' in full_response:
            stance = 'agree'
        elif 'disagree' in response_lower or '反对' in full_response:
            stance = 'disagree'
        
        # 保存审阅结果
        self.last_review = {
            'reviewer': self.name,
            'reviewer_domain': self.domain,
            'reviewed_expert': expert_name,
            'stance': stance,
            'review_content': full_response,
        }
        
        yield f"\n{separator}\n"
    
    def get_prompt(self, context: Dict[str, Any]) -> str:
        """获取通用提示词"""
        return self._build_proposal_prompt(context)
    
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        """选择动作"""
        return AgentAction.IMPLEMENT
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示"""
        result = {
            "agent_id": self.agent_id,
            "role": self.role,
            "name": self.name,
            "domain": self.domain,
            "expertise": self.expertise,
            "reason": self.reason
        }
        # 包含结构化的 proposal 数据
        if self.last_proposal:
            result["proposal"] = self.last_proposal.to_dict()
        return result
    
    @classmethod
    def from_spec(cls, spec: Dict[str, Any], llm_adapter=None) -> 'DynamicExpertAgent':
        """
        从规格字典创建专家实例
        
        Args:
            spec: 专家规格，包含 role, name, domain, expertise, reason
            llm_adapter: LLM适配器
        
        Returns:
            DynamicExpertAgent 实例
        """
        return cls(
            role=spec.get('role', 'custom'),
            name=spec.get('name', '领域专家'),
            domain=spec.get('domain', '通用'),
            expertise=spec.get('expertise', []),
            reason=spec.get('reason', ''),
            llm_adapter=llm_adapter
        )
