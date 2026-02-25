"""
综合者智能体

汇总各专家方案，整理实施计划，找出质疑点。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator
import asyncio
import uuid
import json
import re
import logging

from .base_hierarchical_agent import (
    BaseHierarchicalAgent, HierarchicalAgentConfig, AgentCapability
)
from ..types import LayerType, AgentAction


logger = logging.getLogger(__name__)


@dataclass
class Challenge:
    """质疑点"""
    challenge_id: str = field(default_factory=lambda: f"ch_{uuid.uuid4().hex[:6]}")
    point: str = ""
    raised_by: str = ""
    related_experts: List[str] = field(default_factory=list)
    severity: str = "medium"
    status: str = "pending"
    resolution: str = ""


@dataclass
class SynthesizedPlan:
    """综合方案（含各领域细化步骤）"""
    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    title: str = ""
    summary: str = ""
    implementation_phases: List[Dict[str, Any]] = field(default_factory=list)
    domain_breakdown: List[Dict[str, Any]] = field(default_factory=list)  # 各领域实施步骤汇总
    timeline: str = ""
    total_duration: str = ""
    required_resources: List[str] = field(default_factory=list)
    expert_contributions: Dict[str, str] = field(default_factory=dict)
    challenges: List[Challenge] = field(default_factory=list)
    risk_assessment: str = ""
    success_criteria: List[str] = field(default_factory=list)
    ready_for_validation: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


class SynthesizerAgent(BaseHierarchicalAgent):
    """
    综合者智能体
    
    职责：
    1. 汇总各专家的方案提议
    2. 整理形成完整的实施计划
    3. 找出方案中的质疑点和潜在问题
    4. 生成最终输出，传递给第三层检验系统
    """
    
    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"synthesizer_{uuid.uuid4().hex[:6]}",
            name="综合者",
            layer=LayerType.IMPLEMENTATION,
            role="synthesizer",
            capabilities={
                AgentCapability.REASONING,
                AgentCapability.PLANNING,
                AgentCapability.CONSENSUS_BUILDING,
                AgentCapability.COMMUNICATION
            }
        )
        super().__init__(config, llm_adapter)
        self.last_synthesized_plan: Optional[SynthesizedPlan] = None
    
    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """执行综合动作"""
        yield f"[{self.name}] 正在综合各专家方案...\n"
        prompt = self.get_prompt(context)
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        full_response = "".join(response_parts)
        self.last_result = {"action": "synthesize", "response": full_response}
    
    async def synthesize_and_challenge(
        self,
        expert_proposals: List[Dict[str, Any]],
        task_context: Dict[str, Any] = None
    ) -> AsyncGenerator[str, None]:
        """综合专家方案并提出质疑"""
        yield "\n[综合者汇总阶段]\n"
        yield "=" * 40 + "\n\n"
        yield f"[综合者] 收到 {len(expert_proposals)} 位专家的方案\n\n"
        
        # 阶段1: 汇总方案
        yield "[阶段1] 汇总各专家方案\n"
        yield "-" * 40 + "\n"
        
        synthesis_prompt = self._build_synthesis_prompt(expert_proposals, task_context)
        response_parts = []
        async for chunk in self.call_llm(synthesis_prompt):
            yield chunk
            response_parts.append(chunk)
        synthesis_response = "".join(response_parts)
        
        # 阶段2: 识别质疑点
        yield "\n\n[阶段2] 识别质疑点\n"
        yield "-" * 40 + "\n"
        
        challenge_prompt = self._build_challenge_prompt(expert_proposals, synthesis_response)
        challenge_parts = []
        async for chunk in self.call_llm(challenge_prompt):
            yield chunk
            challenge_parts.append(chunk)
        challenge_response = "".join(challenge_parts)
        
        # 解析并存储结果
        yield "\n\n[综合者] 正在整理最终方案...\n"
        self.last_synthesized_plan = self._parse_synthesized_plan(
            synthesis_response, challenge_response, expert_proposals
        )
        
        yield f"\n[综合者] 综合完成\n"
        yield f"  - 实施阶段: {len(self.last_synthesized_plan.implementation_phases)} 个\n"
        yield f"  - 质疑点: {len(self.last_synthesized_plan.challenges)} 个\n"
    
    def get_synthesized_plan(self) -> Optional[SynthesizedPlan]:
        """获取综合方案"""
        return self.last_synthesized_plan
    
    def get_output_for_validation(self) -> Dict[str, Any]:
        """获取传递给第三层检验系统的输出"""
        if not self.last_synthesized_plan:
            return {"error": "无综合方案"}
        plan = self.last_synthesized_plan
        return {
            "plan_id": plan.plan_id,
            "title": plan.title,
            "summary": plan.summary,
            "implementation_phases": plan.implementation_phases,
            "domain_breakdown": getattr(plan, "domain_breakdown", []) or [],
            "timeline": plan.timeline,
            "total_duration": plan.total_duration,
            "required_resources": plan.required_resources,
            "expert_contributions": plan.expert_contributions,
            "challenges": [
                {
                    "point": c.point,
                    "category": getattr(c, 'category', ''),
                    "severity": c.severity,
                    "status": c.status,
                    "related_experts": c.related_experts,
                    "suggestion": c.resolution
                } for c in plan.challenges
            ],
            "success_criteria": plan.success_criteria,
            "risk_assessment": plan.risk_assessment,
            "ready_for_validation": plan.ready_for_validation,
            "timestamp": plan.timestamp.isoformat()
        }
    
    def _build_synthesis_prompt(self, expert_proposals: List[Dict[str, Any]], task_context: Dict[str, Any] = None) -> str:
        """构建综合提示词"""
        proposals_text = ""
        for i, prop in enumerate(expert_proposals, 1):
            expert_name = prop.get('expert_name', f'专家{i}')
            domain = prop.get('domain', '未知领域')
            content = prop.get('content', prop.get('proposal_content', ''))
            proposals_text += f"\n### {i}. {expert_name} ({domain})\n{content}\n"
        
        task_info = ""
        if task_context:
            task = task_context.get('task', {})
            if isinstance(task, dict):
                task_info = f"任务: {task.get('name', '未知')}\n描述: {task.get('description', '')}"
        
        expert_names = [prop.get('expert_name', f'专家{i}') for i, prop in enumerate(expert_proposals, 1)]
        
        return f"""你是综合者，负责整合各领域专家的方案，形成一个完整的结构化实施计划。
第二层要求**保留并合并各知识领域的细化步骤**，形成按领域划分的详细实施计划。

## 背景信息
{task_info}

## 参与专家
{", ".join(expert_names)}

## 各领域专家方案
{proposals_text}

## 你的任务

请综合以上各领域专家的方案，形成完整的实施计划。**务必保留各专家的细化实施步骤**，按领域或阶段组织。

**请严格按以下JSON格式输出**（用```json```代码块包裹）：

```json
{{{{
  "title": "方案标题",
  "summary": "用2-3句话概括整个方案",
  "implementation_phases": [
    {{{{
      "phase": 1,
      "name": "阶段名称（可带领域，如：软件架构设计阶段）",
      "description": "阶段描述",
      "domain": "该阶段所属领域",
      "steps": [
        {{{{
          "name": "步骤名",
          "description": "详细描述（保留专家给出的细化内容）",
          "deliverable": "交付物"
        }}}}
      ],
      "responsible_experts": ["负责的专家"],
      "duration": "预估时间",
      "deliverables": ["交付物1"],
      "dependencies": []
    }}}}
  ],
  "domain_breakdown": [
    {{{{
      "domain": "领域名",
      "expert": "专家名",
      "key_steps": ["该领域关键步骤1", "关键步骤2"],
      "duration": "该领域预估时间"
    }}}}
  ],
  "timeline": "整体时间线描述",
  "total_duration": "总预估时间",
  "required_resources": ["资源1", "资源2"],
  "success_criteria": ["成功标准1", "成功标准2"],
  "risk_assessment": "整体风险评估"
}}}}
```

请确保：
1. implementation_phases 至少包含2个阶段，每个阶段 steps 为对象数组（含 name、description、deliverable）
2. 保留并整合各专家方案中的**细化步骤**，勿合并为笼统描述
3. domain_breakdown 汇总各领域的核心步骤
4. 时间线要具体可行，成功标准要可衡量

请直接输出你的JSON综合方案：
"""
    
    def _build_challenge_prompt(self, expert_proposals: List[Dict[str, Any]], synthesis: str) -> str:
        """构建质疑点识别提示词"""
        expert_names = [prop.get('expert_name', f'专家{i}') for i, prop in enumerate(expert_proposals, 1)]
        return f"""作为综合者，请审视之前的综合方案，找出潜在的问题和质疑点。

## 已综合的方案
{synthesis[:2000]}

## 参与专家
{", ".join(expert_names)}

## 质疑点识别

请从以下角度找出方案中的问题：
1. 方案冲突：不同专家的方案是否有矛盾？
2. 遗漏环节：是否有遗漏的重要环节？
3. 风险隐患：有哪些潜在风险？
4. 资源约束：资源估算是否合理？
5. 时间可行性：时间规划是否可行？

**请严格按以下JSON格式输出**（用```json```代码块包裹）：

```json
{{{{
  "challenges": [
    {{{{
      "point": "质疑点描述",
      "category": "方案冲突/遗漏环节/风险隐患/资源约束/时间可行性",
      "severity": "high/medium/low",
      "related_experts": ["相关专家名称"],
      "suggestion": "建议解决方式"
    }}}}
  ]
}}}}
```

请直接输出JSON：
"""
    
    def _parse_synthesized_plan(self, synthesis_response: str, challenge_response: str, expert_proposals: List[Dict[str, Any]]) -> SynthesizedPlan:
        """解析综合结果"""
        # 解析专家贡献
        expert_contributions = {}
        for prop in expert_proposals:
            name = prop.get('expert_name', '专家')
            content = prop.get('content', prop.get('proposal_content', ''))
            expert_contributions[name] = content[:200] + "..." if len(content) > 200 else content
        
        # 解析综合方案 JSON
        title = "实施方案"
        summary = ""
        phases = []
        domain_breakdown = []
        timeline = ""
        total_duration = ""
        required_resources = []
        success_criteria = []
        risk_assessment = ""
        
        try:
            synthesis_data = self._extract_json(synthesis_response)
            if synthesis_data:
                title = synthesis_data.get('title', '实施方案')
                summary = synthesis_data.get('summary', '')
                timeline = synthesis_data.get('timeline', '')
                total_duration = synthesis_data.get('total_duration', '')
                required_resources = synthesis_data.get('required_resources', [])
                success_criteria = synthesis_data.get('success_criteria', [])
                risk_assessment = synthesis_data.get('risk_assessment', '')
                
                # 解析实施阶段
                raw_phases = synthesis_data.get('implementation_phases', [])
                for p in raw_phases:
                    if isinstance(p, dict):
                        phases.append({
                            "phase": p.get('phase', len(phases) + 1),
                            "name": p.get('name', f'阶段{len(phases)+1}'),
                            "description": p.get('description', ''),
                            "domain": p.get('domain', ''),
                            "steps": p.get('steps', []),
                            "responsible_experts": p.get('responsible_experts', []),
                            "duration": p.get('duration', '待定'),
                            "deliverables": p.get('deliverables', []),
                            "dependencies": p.get('dependencies', [])
                        })
                
                # 解析各领域步骤汇总（保留各知识领域的细化步骤）
                domain_breakdown_raw = synthesis_data.get('domain_breakdown', [])
                domain_breakdown = [d for d in domain_breakdown_raw if isinstance(d, dict)]
                
                logger.info(f"[综合者] 成功解析结构化综合方案: {len(phases)}个阶段, {len(domain_breakdown)}个领域")
            else:
                # fallback: 从文本中提取
                summary = synthesis_response[:500] if synthesis_response else "综合方案"
                phases = self._extract_phases_from_text(synthesis_response)
                logger.warning("[综合者] JSON解析失败，使用文本提取")
        except Exception as e:
            logger.warning(f"[综合者] 解析综合方案失败: {e}")
            summary = synthesis_response[:500] if synthesis_response else "综合方案"
            phases = self._extract_phases_from_text(synthesis_response)
        
        # 解析质疑点
        challenges = self._extract_challenges_from_json(challenge_response)
        
        return SynthesizedPlan(
            title=title,
            summary=summary,
            implementation_phases=phases,
            domain_breakdown=domain_breakdown,
            timeline=timeline,
            total_duration=total_duration,
            required_resources=required_resources,
            expert_contributions=expert_contributions,
            challenges=challenges,
            risk_assessment=risk_assessment,
            success_criteria=success_criteria if success_criteria else ["完成所有实施阶段", "通过第三层检验"],
            ready_for_validation=len(challenges) == 0 or all(c.severity != "high" for c in challenges)
        )
    
    def _extract_json(self, response: str) -> Optional[Dict[str, Any]]:
        """从响应文本中提取JSON"""
        try:
            # 尝试提取```json```代码块
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                return json.loads(json_match.group(1))
            
            # 尝试直接匹配JSON对象
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group(0))
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"JSON解析失败: {e}")
        return None
    
    def _extract_phases_from_text(self, synthesis: str) -> List[Dict[str, Any]]:
        """从fallback文本中提取阶段信息"""
        phases = []
        lines = synthesis.split('\n')
        current_phase = None
        for line in lines:
            line = line.strip()
            if line.startswith('##') or '阶段' in line:
                if current_phase:
                    phases.append(current_phase)
                current_phase = {
                    "phase": len(phases) + 1,
                    "name": line.replace('#', '').strip(),
                    "description": "",
                    "steps": [],
                    "responsible_experts": [],
                    "duration": "待定",
                    "deliverables": [],
                    "dependencies": []
                }
            elif current_phase and line:
                current_phase["description"] += line + "\n"
        if current_phase:
            phases.append(current_phase)
        if not phases:
            phases = [{
                "phase": 1,
                "name": "实施阶段",
                "description": synthesis[:300],
                "steps": [],
                "responsible_experts": [],
                "duration": "待定",
                "deliverables": [],
                "dependencies": []
            }]
        return phases
    
    def _extract_challenges_from_json(self, challenge_response: str) -> List[Challenge]:
        """从质疑响应中提取质疑点（优先JSON解析）"""
        challenges = []
        
        try:
            data = self._extract_json(challenge_response)
            if data and 'challenges' in data:
                for ch in data['challenges']:
                    if isinstance(ch, dict):
                        challenges.append(Challenge(
                            point=ch.get('point', ''),
                            raised_by="综合者",
                            related_experts=ch.get('related_experts', []),
                            severity=ch.get('severity', 'medium'),
                            status="pending",
                            resolution=ch.get('suggestion', '')
                        ))
                logger.info(f"[综合者] 成功解析 {len(challenges)} 个结构化质疑点")
                return challenges[:8]  # 最多8个
        except Exception as e:
            logger.warning(f"[综合者] JSON解析质疑点失败: {e}，使用文本提取")
        
        # fallback: 文本提取
        return self._extract_challenges_from_text(challenge_response)
    
    def _extract_challenges_from_text(self, challenge_response: str) -> List[Challenge]:
        """从fallback文本中提取质疑点"""
        challenges = []
        lines = challenge_response.split('\n')
        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-') or line.startswith('*')):
                content = line.lstrip('0123456789.-*) ').strip()
                if len(content) > 10:
                    severity = "high" if "风险" in content or "问题" in content or "严重" in content else "medium"
                    challenges.append(Challenge(point=content, raised_by="综合者", severity=severity))
        return challenges[:8]
    
    def get_prompt(self, context: Dict[str, Any]) -> str:
        """获取通用提示词"""
        expert_proposals = context.get('expert_proposals', [])
        return self._build_synthesis_prompt(expert_proposals, context)
    
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        """选择动作"""
        return AgentAction.COORDINATE
