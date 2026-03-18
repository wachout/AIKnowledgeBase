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
    ToolIntegratedConcretizationAgent,
)
from .concretization_summary_prompt_template import (
    CONCRETIZATION_SUMMARY_AGENT_PROMPT,
    CONCRETIZATION_SINGLE_SUMMARY_PROMPT,
)

try:
    from Config.llm_config import get_chat_long
except Exception:
    get_chat_long = None

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
    # 对第二层多份汇总文件具像化后生成的文件路径（相对 discussion_base_path 或绝对路径）
    summary_output_files: List[str] = field(default_factory=list)
    # 已处理的专家发言记录（用于任务恢复时跳过）
    # 格式: [{base_name, category_name, output_file, timestamp}, ...]
    processed_experts: List[Dict[str, Any]] = field(default_factory=list)


async def _run_concretization_summary_agent(
    outputs: List[Dict[str, Any]],
    concretization_dir: str,
    discussion_id: str,
) -> Optional[str]:
    """
    具像化结果汇总智能体：阅读全部具像化结果，使用长文本大模型输出总结文件（Markdown）。
    返回总结文件路径，失败或未配置长文本模型时返回 None。
    """
    if not outputs:
        return None
    if get_chat_long is None:
        logger.warning("get_chat_long 不可用，跳过具像化结果汇总")
        return None
    parts = []
    for i, o in enumerate(outputs, 1):
        parts.append(f"### 任务 {i}（领域: {o.get('domain', '')}）\n")
        parts.append(f"- **步骤名称**: {o.get('step_name', '')}\n")
        parts.append(f"- **步骤描述**: {o.get('step_description', '')}\n")
        parts.append(f"- **数字化描述**: {o.get('digital_description', '')}\n")
        parts.append(f"- **文字描述**: {o.get('textual_description', '')}\n")
        parts.append(f"- **模拟描述**: {o.get('simulation_description', '')}\n")
        if o.get("constraints_check"):
            parts.append(f"- **已考虑约束**: {', '.join(o['constraints_check'])}\n")
        parts.append("\n")
    body = "".join(parts)
    prompt = f"""{CONCRETIZATION_SUMMARY_AGENT_PROMPT}

---
## 当前待汇总的具像化结果

以下为各领域具像化输出的完整内容，请按 Workflow 与 OutputFormat 进行汇总、去重并生成统一格式的任务文档（Markdown，含任务名称、负责人、截止时间、资源投入、交付物、预期成果等）。

**讨论ID**: {discussion_id}
**任务条数**: {len(outputs)}

{body}
"""
    try:
        llm = get_chat_long(temperature=0.2, streaming=False)
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            asyncio.to_thread(llm.invoke, prompt),
            timeout=300.0,
        )
        text = getattr(response, "content", None) or str(response)
        if not text or not text.strip():
            return None
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_path = os.path.join(concretization_dir, f"concretization_summary_{ts}.md")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write("# 具像化结果汇总（项目任务优化分析师）\n\n")
            f.write(f"**讨论ID**: {discussion_id}\n\n**生成时间**: {ts}\n\n---\n\n")
            f.write(text.strip())
        return summary_path
    except asyncio.TimeoutError:
        logger.warning("具像化结果汇总智能体调用超时")
        return None
    except Exception as e:
        logger.warning(f"具像化结果汇总智能体执行失败: {e}", exc_info=True)
        return None


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


def _collect_second_layer_summary_files(implement_dir: str) -> List[Dict[str, Any]]:
    """
    从 implement/ 目录收集第二层专家发言文件（Markdown）。
    只收集 expert_speech_*.md（专家直接发言）
    返回列表项: { "path": str, "base_name": str, "content": str, "category_name": str, "type": str }
    """
    collected = []
    if not os.path.isdir(implement_dir):
        return collected
    
    import re
    # 专家发言文件模式：expert_speech_{专家名}_{领域}_{时间戳}.md
    expert_speech_pattern = re.compile(r'^expert_speech_(.+?)_(.+?)_\d{8}_\d{6}\.md$')
    
    for fname in sorted(os.listdir(implement_dir)):
        if not fname.endswith(".md"):
            continue
        # 排除 prompt 文件
        if "_prompt.md" in fname:
            continue
        
        path = os.path.join(implement_dir, fname)
        
        # 匹配专家发言文件 expert_speech_*.md
        match_expert = expert_speech_pattern.match(fname)
        if match_expert:
            expert_name = match_expert.group(1)  # 专家名
            domain = match_expert.group(2)  # 领域
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                logger.warning(f"读取专家发言文件 {path} 失败: {e}")
                continue
            base_name = os.path.splitext(fname)[0]
            collected.append({
                "path": path,
                "base_name": base_name,
                "content": content,
                "category_name": f"{expert_name}（{domain}）",
                "type": "expert_speech",
            })
    
    if collected:
        logger.info(f"发现 {len(collected)} 份专家发言文件，用于第三层具象化")
    
    return collected


async def _run_single_summary_concretization(
    content: str,
    source_base_name: str,
    category_name: str,
    concretization_dir: str,
    discussion_id: str,
    is_expert_speech: bool = True,
) -> Optional[str]:
    """
    对第二层专家发言进行具象化：阅读专家发言，给出实施具象化内容。
    使用长文本大模型生成一份具象化 Markdown，保存到 concretization/。
    返回保存后的文件路径，失败返回 None。
    
    Args:
        content: 专家发言内容
        source_base_name: 来源文件基本名
        category_name: 专家名
        concretization_dir: 具象化输出目录
        discussion_id: 讨论ID
        is_expert_speech: 是否为专家发言（默认True，保留参数兼容性）
    """
    if not content or not content.strip():
        return None
    if get_chat_long is None:
        logger.warning("get_chat_long 不可用，跳过具象化")
        return None
    
    # 构建专家发言的具象化提示词
    header = f"专家发言（专家: {category_name}，来源: {source_base_name}）"
    prompt = f"""{CONCRETIZATION_SINGLE_SUMMARY_PROMPT}

---
## {header}

你正在阅读第二层动态专家的直接发言内容。请仔细分析专家的实施方案，
将其中的抽象描述转化为可执行的具体实施细节。

**讨论ID**: {discussion_id}
**专家名称**: {category_name}

```markdown
{content.strip()[:120000]}
```

请基于以上专家发言：
1. 提取关键实施步骤
2. 将每个步骤具象化为可执行的任务
3. 补充必要的技术细节、参数规格、资源需求
4. 给出时间节点和交付物定义
"""
    try:
        llm = get_chat_long(temperature=0.2, streaming=False)
        response = await asyncio.wait_for(
            asyncio.to_thread(llm.invoke, prompt),
            timeout=300.0,
        )
        text = getattr(response, "content", None) or str(response)
        if not text or not text.strip():
            return None
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_category = "".join(c if c.isalnum() or c in "._-" else "_" for c in category_name)[:30]
        
        out_path = os.path.join(concretization_dir, f"concretization_expert_{safe_category}_{ts}.md")
        title = f"具象化结果（专家: {category_name}）"
        
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n")
            f.write(f"**讨论ID**: {discussion_id}\n\n**来源类型**: 专家发言\n\n**生成时间**: {ts}\n\n---\n\n")
            f.write(text.strip())
        return out_path
    except asyncio.TimeoutError:
        logger.warning(f"专家发言具象化调用超时: {category_name}")
        return None
    except Exception as e:
        logger.warning(f"专家发言具象化执行失败 {category_name}: {e}", exc_info=True)
        return None


class ConcretizationDiscussion:
    """
    第三层具像化层讨论/编排
    
    - 数字工程师、具像化工程师、抽象化工程师：三个固定智能体
    - 每阅读一份实施步骤，自动创建对应领域的领域具像化智能体，执行数字化+具像化
    - 输出符合第一性原理、物理守恒、材料约束、制造边界、环境适应、安全与冗余
    - 领域具像化智能体可使用 web_search_fn 查询细节步骤、定义或原理以补全描述
    - 工具智能体集成：写代码工具、3D打印工具，实现任务中的软硬件功能
    """

    def __init__(self, llm_adapter=None, web_search_fn=None, enable_tools: bool = True):
        self.llm_adapter = llm_adapter
        self.web_search_fn = web_search_fn  # (query: str) -> str，供领域具像化智能体网络检索
        self.enable_tools = enable_tools  # 是否启用工具智能体
        self.digital_engineer = DigitalEngineerAgent(llm_adapter=llm_adapter)
        self.concretization_engineer = ConcretizationEngineerAgent(llm_adapter=llm_adapter)
        self.abstraction_engineer = AbstractionEngineerAgent(llm_adapter=llm_adapter)
        self.domain_agents: List[DomainConcretizationAgent] = []
        self._result: Optional[ConcretizationResult] = None
        
        # 初始化工具集成智能体
        self.tool_integrated_agent: Optional[ToolIntegratedConcretizationAgent] = None
        if enable_tools:
            self.tool_integrated_agent = ToolIntegratedConcretizationAgent(
                domain="通用",
                llm_adapter=llm_adapter,
            )
            if self.tool_integrated_agent.has_tools():
                logger.info(f"工具集成智能体已初始化，可用工具: {self.tool_integrated_agent.get_available_tools()}")

    async def run_concretization(
        self,
        discussion_base_path: str,
        discussion_id: str = "",
        processed_experts: List[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        从 implement/ 读取第二层的专家发言文件（expert_speech_*.md），
        并行处理所有专家发言，让具象化智能体阅读并给出实施具象化内容。
        结果写入 concretization/。
        
        Args:
            discussion_base_path: 讨论基础目录
            discussion_id: 讨论ID
            processed_experts: 已处理的专家发言文件名列表（用于任务恢复时跳过）
        """
        implement_dir = os.path.join(discussion_base_path, "implement")
        concretization_dir = os.path.join(discussion_base_path, "concretization")
        os.makedirs(concretization_dir, exist_ok=True)
        
        processed_experts = processed_experts or []

        self._result = ConcretizationResult(discussion_id=discussion_id or os.path.basename(discussion_base_path))

        yield "\n" + "=" * 60 + "\n"
        yield "          第三层 · 具象化层\n"
        yield "=" * 60 + "\n\n"

        # 收集第二层的专家发言文件
        summary_files = _collect_second_layer_summary_files(implement_dir)

        if not summary_files:
            yield "[具象化层] 未在 implement/ 中发现专家发言文件（expert_speech_*.md），跳过。\n"
            self._result.completed_at = datetime.now()
            self._result.success = True
            return

        # 过滤已处理的专家发言
        pending_files = []
        skipped_count = 0
        for doc in summary_files:
            base_name = doc["base_name"]
            if base_name in processed_experts:
                skipped_count += 1
                # 记录已跳过的专家到结果中
                self._result.processed_experts.append({
                    "base_name": base_name,
                    "category_name": doc.get("category_name", "未命名"),
                    "status": "skipped",
                    "reason": "已处理",
                })
            else:
                pending_files.append(doc)
        
        if skipped_count > 0:
            yield f"[具象化层] 跳过 {skipped_count} 份已处理的专家发言\n"
        
        if not pending_files:
            yield f"[具象化层] 所有 {len(summary_files)} 份专家发言已处理完成，无需重复处理。\n"
            self._result.completed_at = datetime.now()
            self._result.success = True
            return

        yield f"[具象化层] 共发现 {len(summary_files)} 份专家发言文件，待处理 {len(pending_files)} 份，将并行进行具象化处理。\n\n"

        # ============ 并行处理所有专家发言的具象化 ============
        async def process_single_expert(doc: Dict[str, Any], idx: int) -> Dict[str, Any]:
            """处理单个专家发言的具象化（用于并行执行）"""
            base_name = doc["base_name"]
            content = doc["content"]
            category_name = doc.get("category_name", "未命名")
            
            result_info = {
                "idx": idx,
                "category_name": category_name,
                "base_name": base_name,
                "content_length": len(content),
                "out_path": None,
                "success": False,
                "tool_outputs": [],
            }
            
            try:
                out_path = await _run_single_summary_concretization(
                    content=content,
                    source_base_name=base_name,
                    category_name=category_name,
                    concretization_dir=concretization_dir,
                    discussion_id=self._result.discussion_id,
                    is_expert_speech=True,
                )
                if out_path:
                    result_info["out_path"] = out_path
                    result_info["success"] = True
                    
                    # 调用工具智能体生成软硬件实现
                    if self.tool_integrated_agent is not None and self.tool_integrated_agent.has_tools():
                        tool_chunks = []
                        async for tool_chunk in self.tool_integrated_agent.analyze_and_execute_tools(
                            concretization_content=content,
                            category_name=category_name,
                            output_base_dir=discussion_base_path,
                        ):
                            tool_chunks.append(tool_chunk)
                        result_info["tool_outputs"] = tool_chunks
            except Exception as e:
                logger.warning(f"专家 {category_name} 具象化失败: {e}")
                result_info["error"] = str(e)
            
            return result_info

        # 创建所有并行任务（只处理待处理的文件）
        tasks = [
            process_single_expert(doc, idx)
            for idx, doc in enumerate(pending_files, 1)
        ]
        
        yield f"[并行执行] 启动 {len(tasks)} 个具象化任务...\n"
        
        # 并行执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # ============ 统一输出结果 ============
        success_count = 0
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        for result in results:
            if isinstance(result, Exception):
                yield f"\n[错误] 具象化任务异常: {result}\n"
                continue
            
            idx = result["idx"]
            category_name = result["category_name"]
            base_name = result["base_name"]
            content_length = result["content_length"]
            
            yield f"\n[专家具象化 {idx}/{len(pending_files)}] 专家: {category_name}\n"
            yield f"  来源文件: {base_name}\n"
            yield f"  文档长度: {content_length} 字符\n"
            
            if result["success"]:
                out_path = result["out_path"]
                self._result.summary_output_files.append(out_path)
                yield f"  ✓ 具象化完成，已保存: {os.path.basename(out_path)}\n"
                success_count += 1
                
                # 记录已处理的专家（用于任务恢复）
                self._result.processed_experts.append({
                    "base_name": base_name,
                    "category_name": category_name,
                    "output_file": os.path.basename(out_path) if out_path else None,
                    "timestamp": ts,
                    "status": "completed",
                })
                
                # 输出工具智能体结果
                if result["tool_outputs"]:
                    yield "  工具智能体执行结果:\n"
                    for chunk in result["tool_outputs"]:
                        yield f"    {chunk}"
            else:
                error_msg = result.get("error", "未知错误")
                yield f"  × 具象化失败: {error_msg}\n"

        self._result.steps_processed = len(summary_files)
        self._result.completed_at = datetime.now()
        self._result.success = success_count > 0

        yield "\n" + "=" * 60 + "\n"
        yield f"[具象化层完成] 共处理 {len(summary_files)} 份专家发言（并行执行）\n"
        yield f"  成功生成: {len(self._result.summary_output_files)} 份具象化文档\n"
        yield "=" * 60 + "\n"

    def get_last_result(self) -> Optional[ConcretizationResult]:
        return self._result
