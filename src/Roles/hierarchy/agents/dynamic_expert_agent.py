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
        
        # 保存当前任务上下文，供 JSON 解析失败时从 discuss 的 markdown 回退读取
        self._current_task_context = task_context
        
        # 构建专业化提示词
        prompt = self._build_proposal_prompt(task_context)
        
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        full_response = "".join(response_parts)
        
        # 解析结构化方案
        self.last_proposal = self._parse_proposal(full_response)
        
        yield f"\n{'─' * 40}\n"
    
    def get_proposal(self) -> Optional[ExpertProposal]:
        """获取最近的方案提议"""
        return self.last_proposal
    
    def _parse_json_with_fallback(self, json_str: str) -> dict:
        """
        解析 JSON，失败时尝试修复（去除尾逗号、截断后补全括号）后重试。
        若仍失败则抛出异常，由调用方触发 discuss 回退。
        """
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # 尝试修复常见问题：尾逗号 ,] ,}
            repaired = re.sub(r',\s*([}\]])', r'\1', json_str)
            if repaired != json_str:
                try:
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    pass
            # 尝试截断：在错误位置之前找到最后一个 }，补全括号后重试
            pos = getattr(e, 'pos', len(json_str))
            if pos and pos > 10:
                prefix = json_str[:pos]
                last_brace = prefix.rfind('}')
                last_bracket = prefix.rfind(']')
                cut = max(last_brace, last_bracket)
                if cut > 0:
                    open_braces = prefix[: cut + 1].count('{') - prefix[: cut + 1].count('}')
                    open_brackets = prefix[: cut + 1].count('[') - prefix[: cut + 1].count(']')
                    repaired = json_str[: cut + 1] + ']' * max(0, open_brackets) + '}' * max(0, open_braces)
                    try:
                        return json.loads(repaired)
                    except json.JSONDecodeError:
                        pass
            raise

    def _parse_proposal(self, response: str) -> ExpertProposal:
        """解析LLM返回的结构化方案"""
        proposal = ExpertProposal(
            expert_role=self.role,
            expert_name=self.name,
            domain=self.domain,
            proposal_content=response
        )
        
        try:
            # 尝试提取JSON块
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接匹配JSON对象
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    logger.warning(f"[{self.name}] 未找到JSON结构，使用原始文本")
                    return proposal
            
            # 去除控制字符，降低 Invalid control character 等解析错误
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
            data = self._parse_json_with_fallback(json_str)
            
            # 填充结构化字段
            proposal.professional_analysis = data.get('professional_analysis', '')
            
            # 解析实施步骤（含细化字段：acceptance_criteria）
            raw_steps = data.get('implementation_steps', [])
            proposal.implementation_steps = []
            for i, step in enumerate(raw_steps):
                if isinstance(step, dict):
                    proposal.implementation_steps.append({
                        "step": step.get('step', i + 1),
                        "name": step.get('name', f'步骤{i+1}'),
                        "description": step.get('description', ''),
                        "duration": step.get('duration', '待定'),
                        "deliverable": step.get('deliverable', ''),
                        "acceptance_criteria": step.get('acceptance_criteria', ''),
                    })
                elif isinstance(step, str):
                    proposal.implementation_steps.append({
                        "step": i + 1,
                        "name": step,
                        "description": step,
                        "duration": "待定",
                        "deliverable": "",
                        "acceptance_criteria": "",
                    })
            
            proposal.estimated_duration = data.get('estimated_duration', '')
            proposal.required_resources = data.get('required_resources', [])
            
            # 解析潜在风险
            raw_risks = data.get('potential_risks', [])
            proposal.potential_risks = []
            for risk in raw_risks:
                if isinstance(risk, dict):
                    proposal.potential_risks.append({
                        "risk": risk.get('risk', ''),
                        "severity": risk.get('severity', '中'),
                        "mitigation": risk.get('mitigation', '')
                    })
                elif isinstance(risk, str):
                    proposal.potential_risks.append({
                        "risk": risk,
                        "severity": "中",
                        "mitigation": ""
                    })
            
            proposal.dependencies = data.get('dependencies', [])
            proposal.confidence_level = float(data.get('confidence_level', 0.8))
            proposal.verification_notes = data.get('verification_notes', '')
            
            logger.info(f"[{self.name}] 成功解析结构化方案: {len(proposal.implementation_steps)}个步骤, {len(proposal.potential_risks)}个风险")
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"[{self.name}] 解析结构化方案失败: {e}，尝试从 discuss 发言 markdown 回退")
            fallback_content = self._try_load_proposal_from_discuss_md()
            if fallback_content:
                proposal.proposal_content = fallback_content
                # 用第一层发言内容填充至少一个实施步骤，便于下游使用
                proposal.implementation_steps = [{
                    "step": 1,
                    "name": "来自第一层发言",
                    "description": fallback_content[:1000] + ("..." if len(fallback_content) > 1000 else ""),
                    "duration": "待定",
                    "deliverable": "",
                    "acceptance_criteria": "",
                }]
                proposal.professional_analysis = fallback_content[:500] + ("..." if len(fallback_content) > 500 else "")
                logger.info(f"[{self.name}] 已从 discuss 发言 markdown 回退填充方案")
            else:
                logger.warning(f"[{self.name}] 未找到可用的 discuss markdown，保留原始文本")
        
        return proposal
    
    def _try_load_proposal_from_discuss_md(self) -> Optional[str]:
        """
        当 JSON 解析失败时，从第一层讨论保存的 markdown 发言文件中读取内容。
        查找 discuss_dir 下 expert_<名称或领域>_round*.md，取最新一份，提取「发言内容」或全文。
        """
        ctx = getattr(self, "_current_task_context", None) or {}
        discuss_dir = ctx.get("discuss_dir") or ""
        if not discuss_dir or not os.path.isdir(discuss_dir):
            return None
        # 文件名中领域可能带斜杠，保存时会被替换为下划线，如 expert_工业设计_生物形态学_round1_xxx.md
        name_part = (self.name or self.domain or "").replace("/", "_").strip()
        if not name_part:
            return None
        candidates = []
        try:
            for f in os.listdir(discuss_dir):
                if not f.endswith(".md") or "round" not in f.lower():
                    continue
                # 优先 expert_*，其次 skeptic_expert_*（质疑者对本领域的意见也可作为参考）
                if (f.startswith("expert_") or f.startswith("skeptic_expert_")) and name_part in f:
                    path = os.path.join(discuss_dir, f)
                    try:
                        mtime = os.path.getmtime(path)
                        # 专家发言优先于质疑者（expert_ 排在 skeptic_ 前面）
                        priority = 0 if f.startswith("expert_") else 1
                        candidates.append((priority, mtime, path))
                    except OSError:
                        continue
            if not candidates:
                # 未找到 .md 时，尝试从 .json 读取 speech
                return self._try_load_speech_from_discuss_json(discuss_dir)
            # 先按 priority（expert 优先），再按 mtime 取最新
            candidates.sort(key=lambda x: (x[0], -x[1]))
            latest_path = candidates[0][2]
            with open(latest_path, "r", encoding="utf-8") as fp:
                raw = fp.read()
        except (OSError, IOError) as e:
            logger.debug(f"[{self.name}] 读取 discuss markdown 失败: {e}")
            return self._try_load_speech_from_discuss_json(discuss_dir) if discuss_dir else None
        # 提取 ## 发言内容 到文末或下一级 ##
        match = re.search(r"##\s*发言内容\s*\n([\s\S]*?)(?=\n##\s|\Z)", raw)
        if match:
            return match.group(1).strip()
        # 若无「发言内容」节，则取「思考过程」之后到下一 ##
        match = re.search(r"##\s*思考过程\s*\n([\s\S]*?)(?=\n##\s|\Z)", raw)
        if match:
            return match.group(1).strip()
        # 若仍无，尝试从 discuss 下的 .json 文件读取 speech 字段
        fallback_json = self._try_load_speech_from_discuss_json(discuss_dir)
        if fallback_json:
            return fallback_json
        return raw.strip() or None

    def _try_load_speech_from_discuss_json(self, discuss_dir: str) -> Optional[str]:
        """当 markdown 未找到或内容为空时，从 discuss 下的 expert_*.json 或 skeptic_expert_*.json 读取 speech 字段。"""
        name_part = (self.name or self.domain or "").replace("/", "_").strip()
        if not name_part:
            return None
        candidates = []
        try:
            for f in os.listdir(discuss_dir):
                if not f.endswith(".json") or "round" not in f.lower():
                    continue
                if not (f.startswith("expert_") or f.startswith("skeptic_expert_")):
                    continue
                if name_part not in f:
                    continue
                path = os.path.join(discuss_dir, f)
                try:
                    mtime = os.path.getmtime(path)
                    candidates.append((mtime, path))
                except OSError:
                    continue
            if not candidates:
                return None
            # 优先 expert_*，再 skeptic_expert_*；同类型取最新
            def sort_key(item):
                mtime, path = item
                fname = os.path.basename(path)
                priority = 0 if fname.startswith("expert_") else 1
                return (priority, -mtime)
            candidates.sort(key=sort_key)
            with open(candidates[0][1], "r", encoding="utf-8") as fp:
                obj = json.load(fp)
            speech = obj.get("speech") or obj.get("thinking") or ""
            return speech.strip() or None
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def _build_proposal_prompt(self, task_context: Dict[str, Any]) -> str:
        """构建专业化提示词（紧扣用户目标、第一层讨论与质疑者意见、可实施措施并反复验证）"""
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
    
    async def review_proposal(
        self,
        proposal: Dict[str, Any],
        task_context: Dict[str, Any] = None
    ) -> AsyncGenerator[str, None]:
        """
        审阅其他专家的方案，给出专业意见
        
        Args:
            proposal: 待审阅的专家方案 {expert_name, domain, content, ...}
            task_context: 任务上下文
        
        Yields:
            审阅过程的输出
        """
        target_name = proposal.get('expert_name', '未知专家')
        target_domain = proposal.get('domain', '未知领域')
        yield f"\n[{self.name}] 审阅 {target_name} 的方案...\n"
        
        prompt = self._build_review_prompt(proposal, task_context)
        
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        full_response = "".join(response_parts)
        
        # 解析审阅结果
        self.last_review = self._parse_review(full_response, target_name, target_domain)
        yield "\n"

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
"""
        parts = []
        async for chunk in self.call_llm(prompt):
            parts.append(chunk)
        revised = "".join(parts).strip()
        return revised if revised else current_proposal_content
    
    def _build_review_prompt(
        self,
        proposal: Dict[str, Any],
        task_context: Dict[str, Any] = None
    ) -> str:
        """构建专业审阅提示词"""
        target_name = proposal.get('expert_name', '未知专家')
        target_domain = proposal.get('domain', '未知领域')
        content = proposal.get('content', '')[:2000]
        
        expertise_text = "、".join(self.expertise) if self.expertise else self.domain
        
        return f"""你是{self.name}，专精于{self.domain}（{expertise_text}）。

请从你的专业角度审阅以下专家的方案，给出客观的专业评价。

## 待审阅方案
**专家**: {target_name} ({target_domain})
**方案内容**:
{content}

## 审阅要求

请从以下角度进行审阅：
1. 方案的可行性和专业性
2. 与你的专业领域的协同/冲突
3. 潜在的改进建议

**请严格按以下JSON格式输出**（用```json```代码块包裹）：

```json
{{{{{{
  "stance": "agree/neutral/disagree",
  "strengths": ["方案优点1", "方案优点2"],
  "concerns": ["担忧点1", "担忧点2"],
  "suggestions": ["改进建议1", "改进建议2"],
  "synergy_with_my_domain": "与我的领域({self.domain})的协同说明",
  "confidence": 0.8
}}}}}}
```

请直接输出JSON审阅意见：
"""
    
    def _parse_review(self, response: str, target_name: str, target_domain: str) -> Dict[str, Any]:
        """解析审阅结果"""
        review = {
            "reviewer": self.name,
            "reviewer_domain": self.domain,
            "target_expert": target_name,
            "target_domain": target_domain,
            "stance": "neutral",
            "strengths": [],
            "concerns": [],
            "suggestions": [],
            "synergy_with_my_domain": "",
            "confidence": 0.8
        }
        
        try:
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    logger.warning(f"[{self.name}] 审阅结果无JSON，使用默认")
                    return review
            
            data = json.loads(json_str)
            review["stance"] = data.get("stance", "neutral")
            review["strengths"] = data.get("strengths", [])
            review["concerns"] = data.get("concerns", [])
            review["suggestions"] = data.get("suggestions", [])
            review["synergy_with_my_domain"] = data.get("synergy_with_my_domain", "")
            review["confidence"] = float(data.get("confidence", 0.8))
            
            logger.info(f"[{self.name}] 审阅 {target_name}: stance={review['stance']}, concerns={len(review['concerns'])}")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"[{self.name}] 解析审阅结果失败: {e}")
        
        return review

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
