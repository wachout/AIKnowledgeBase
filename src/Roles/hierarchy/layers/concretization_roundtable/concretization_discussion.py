# -*- coding: utf-8 -*-
"""
第三层具像化层 - 讨论/编排

- 阅读 discussion/discussion_id/implement 中的实施步骤
- 针对每个实施步骤按领域自动创建「领域具像化智能体」，执行数字化+具像化
- 三个固定智能体：数字工程师、具像化工程师、抽象化工程师（可参与审核或汇总）
- 结果保存到 discussion/discussion_id/concretization
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, AsyncGenerator
from dataclasses import dataclass, field

from .concretization_agents import (
    DigitalEngineerAgent,
    ConcretizationEngineerAgent,
    AbstractionEngineerAgent,
    DomainConcretizationAgent,
    ConcretizationOutput,
)

logger = logging.getLogger(__name__)


@dataclass
class ConcretizationResult:
    """具像化层运行结果"""
    discussion_id: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    steps_processed: int = 0
    outputs: List[Dict[str, Any]] = field(default_factory=list)
    success: bool = False


def _collect_implementation_steps(implement_dir: str) -> List[Dict[str, Any]]:
    """
    从 implement/ 目录收集实施步骤。
    读取 impl_discussion_*.json、impl_synthesized_plan_*.json、impl_expert_*_proposal_*.json，
    提取 implementation_phases[].steps、refined_task_assignment、expert proposal steps 等。
    返回列表项: { "domain": str, "step_name": str, "step_description": str, "source": str }
    """
    steps = []
    if not os.path.isdir(implement_dir):
        return steps

    # 1) impl_discussion_*.json -> refined_task_assignment (sub_steps), implementation_plan
    for fname in os.listdir(implement_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(implement_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"读取 {path} 失败: {e}")
            continue

        # refined_task_assignment: [{ parent_task, domain, subtask_name, subtask_description, sub_steps[], assigned_role }]
        refined = data.get("refined_task_assignment") or []
        for item in refined:
            if isinstance(item, dict):
                domain = item.get("domain", "通用")
                sub_name = item.get("subtask_name", "")
                sub_desc = item.get("subtask_description", "")
                if sub_name or sub_desc:
                    steps.append({
                        "domain": domain,
                        "step_name": sub_name or "未命名子任务",
                        "step_description": sub_desc,
                        "source": fname,
                    })
                sub_steps = item.get("sub_steps") or []
                for ss in sub_steps:
                    if isinstance(ss, dict):
                        steps.append({
                            "domain": domain,
                            "step_name": ss.get("step_name", "子步骤"),
                            "step_description": ss.get("description", ss.get("deliverable", "")),
                            "source": fname,
                        })
                    elif isinstance(ss, str):
                        steps.append({
                            "domain": domain,
                            "step_name": "子步骤",
                            "step_description": ss,
                            "source": fname,
                        })

        # implementation_phases (from synthesized or impl_data)
        phases = data.get("implementation_phases") or data.get("synthesized_plan", {}).get("implementation_phases") or []
        for ph in phases:
            if not isinstance(ph, dict):
                continue
            domain = ph.get("domain", "通用")
            phase_name = ph.get("name", "阶段")
            for s in ph.get("steps", []):
                if isinstance(s, dict):
                    steps.append({
                        "domain": domain,
                        "step_name": s.get("name", phase_name),
                        "step_description": s.get("description", s.get("deliverable", "")),
                        "source": fname,
                    })
                elif isinstance(s, str):
                    steps.append({
                        "domain": domain,
                        "step_name": phase_name,
                        "step_description": s,
                        "source": fname,
                    })

    # 2) impl_expert_*_proposal_*.json -> structured.implementation_steps
    for fname in os.listdir(implement_dir):
        if "impl_expert_" not in fname or "_proposal_" not in fname or not fname.endswith(".json"):
            continue
        path = os.path.join(implement_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            continue
        structured = data.get("structured") or {}
        domain = data.get("domain", "通用")
        for s in structured.get("implementation_steps", []):
            if isinstance(s, dict):
                steps.append({
                    "domain": domain,
                    "step_name": s.get("name", "步骤"),
                    "step_description": s.get("description", s.get("deliverable", "")),
                    "source": fname,
                })
            elif isinstance(s, str):
                steps.append({
                    "domain": domain,
                    "step_name": "步骤",
                    "step_description": s,
                    "source": fname,
                })

    # 去重：同一 domain+step_name 只保留一条（可选：合并 description）
    seen = set()
    unique = []
    for s in steps:
        key = (s.get("domain", ""), s.get("step_name", ""), (s.get("step_description", ""))[:100])
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
    return unique


class ConcretizationDiscussion:
    """
    第三层具像化层讨论/编排
    
    - 数字工程师、具像化工程师、抽象化工程师：三个固定智能体
    - 每阅读一份实施步骤，自动创建对应领域的领域具像化智能体，执行数字化+具像化
    - 输出符合第一性原理、物理守恒、材料约束、制造边界、环境适应、安全与冗余
    """

    def __init__(self, llm_adapter=None):
        self.llm_adapter = llm_adapter
        self.digital_engineer = DigitalEngineerAgent(llm_adapter=llm_adapter)
        self.concretization_engineer = ConcretizationEngineerAgent(llm_adapter=llm_adapter)
        self.abstraction_engineer = AbstractionEngineerAgent(llm_adapter=llm_adapter)
        self.domain_agents: List[DomainConcretizationAgent] = []
        self._result: Optional[ConcretizationResult] = None

    async def run_concretization(
        self,
        discussion_base_path: str,
        discussion_id: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        从 implement/ 读取实施步骤，按领域创建具像化智能体并执行，结果写入 concretization/。
        """
        implement_dir = os.path.join(discussion_base_path, "implement")
        concretization_dir = os.path.join(discussion_base_path, "concretization")
        os.makedirs(concretization_dir, exist_ok=True)

        self._result = ConcretizationResult(discussion_id=discussion_id or os.path.basename(discussion_base_path))

        yield "\n" + "=" * 60 + "\n"
        yield "          第三层 · 具像化层\n"
        yield "=" * 60 + "\n\n"

        steps = _collect_implementation_steps(implement_dir)
        if not steps:
            yield "[具像化层] 未在 implement/ 中发现实施步骤，跳过。\n"
            self._result.completed_at = datetime.now()
            self._result.success = True
            return

        yield f"[具像化层] 共发现 {len(steps)} 条实施步骤，将按领域创建具像化智能体并执行。\n\n"

        for i, step in enumerate(steps, 1):
            domain = step.get("domain", "通用")
            step_name = step.get("step_name", "步骤")
            step_desc = step.get("step_description", "")
            yield f"[{i}/{len(steps)}] 领域: {domain} | 步骤: {step_name}\n"

            agent = DomainConcretizationAgent(
                domain=domain,
                step_name=step_name,
                step_description=step_desc,
                llm_adapter=self.llm_adapter,
            )
            self.domain_agents.append(agent)
            try:
                async for chunk in agent.run_concretization():
                    yield chunk
                if agent.last_output:
                    self._result.outputs.append(agent.last_output.to_dict())
            except Exception as e:
                logger.exception(f"领域具像化执行失败: {e}")
                yield f"  [错误] {e}\n"

        self._result.steps_processed = len(steps)
        self._result.completed_at = datetime.now()
        self._result.success = True

        # 保存到 concretization/
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_json = os.path.join(concretization_dir, f"concretization_result_{ts}.json")
        out_md = os.path.join(concretization_dir, f"concretization_result_{ts}.md")
        try:
            save_data = {
                "discussion_id": self._result.discussion_id,
                "started_at": self._result.started_at.isoformat(),
                "completed_at": self._result.completed_at.isoformat() if self._result.completed_at else None,
                "steps_processed": self._result.steps_processed,
                "outputs": self._result.outputs,
            }
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            yield f"\n[具像化层] 结果已保存: {out_json}\n"

            md_lines = [
                "# 第三层具像化结果\n\n",
                f"**讨论ID**: {self._result.discussion_id}\n",
                f"**处理步骤数**: {self._result.steps_processed}\n\n",
                "---\n\n",
            ]
            for j, o in enumerate(self._result.outputs, 1):
                md_lines.append(f"## {j}. {o.get('step_name', '')} ({o.get('domain', '')})\n\n")
                md_lines.append(f"**步骤描述**: {o.get('step_description', '')}\n\n")
                md_lines.append(f"**数字化描述**: {o.get('digital_description', '')}\n\n")
                md_lines.append(f"**文字描述**: {o.get('textual_description', '')}\n\n")
                md_lines.append(f"**模拟描述**: {o.get('simulation_description', '')}\n\n")
                if o.get("constraints_check"):
                    md_lines.append("**已考虑约束**: " + ", ".join(o["constraints_check"]) + "\n\n")
                md_lines.append("---\n\n")
            with open(out_md, "w", encoding="utf-8") as f:
                f.write("".join(md_lines))
            yield f"[具像化层] Markdown 报告已保存: {out_md}\n"
        except Exception as e:
            logger.warning(f"保存具像化结果失败: {e}")
            yield f"[警告] 保存结果失败: {e}\n"

        yield "=" * 60 + "\n"

    def get_last_result(self) -> Optional[ConcretizationResult]:
        return self._result
