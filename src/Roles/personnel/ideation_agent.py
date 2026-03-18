# -*- coding: utf-8 -*-
"""
自主构思智能体 - Ideation Agent

协助「任务分析与角色确定」智能体：通过理解用户任务，调用 Semantic Scholar 与 arXiv 论文查询，
将检索到的最新论文保存到 discussion/{task_id}/files，并基于论文阅读进行自主构思，产生逻辑可推理、
原理不违背世界定理的想法，将想法与论文依据一并提供给学者做任务分析与角色确定。
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional, Callable

from .base_agent import BaseAgent, WorkingStyle

logger = logging.getLogger(__name__)


class IdeationAgent(BaseAgent):
    """自主构思智能体：查论文、读论文、产想法，协助学者做任务分析与角色确定。"""

    def __init__(self, llm_instance=None):
        super().__init__(
            name="自主构思",
            role_definition="基于学术论文检索与阅读的构思专家，为任务分析与角色确定提供有文献支撑、逻辑可推理且不违背科学原理的想法",
            professional_skills=[
                "学术检索（Semantic Scholar、arXiv）",
                "文献理解与摘要",
                "逻辑推理与假设构建",
                "科学原理一致性检查",
            ],
            working_style=WorkingStyle.PROFESSIONAL_OBJECTIVE,
            behavior_guidelines=[
                "仅提出可被现有文献或逻辑支撑的想法",
                "不违背公认科学定律与常识",
                "明确标注每个想法对应的支撑论文",
                "输出结构清晰，便于学者后续分析",
            ],
            output_format="""
**自主构思结果：**
- 检索论文概要
- 核心想法（逻辑可推理、原理一致）
- 每个想法对应的支撑论文
""",
            llm_instance=llm_instance,
        )

    def run_ideation(
        self,
        user_task: str,
        task_id: str,
        yield_progress: Optional[Callable[[str, str, Dict], None]] = None,
        save_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行自主构思：根据任务检索论文（保存到 discussion/{task_id}/files）、阅读并产生产生想法与论文依据，
        供学者做任务分析与角色确定。

        Args:
            user_task: 用户任务描述
            task_id: 任务/讨论 ID，论文 PDF 保存路径将设为 discussion/{task_id}/files（传入 save_path，可由调用方覆盖）
            yield_progress: 可选，用于流式上报进度 (step, message, data)

        Returns:
            {
                "ideas": [{"content": "...", "supporting_paper_ids": [...]}],
                "supporting_papers": [{"title", "authors", "abstract", "year", "source", "pdf_local_path"}],
                "papers_summary": "文本概要",
                "downloaded_to": "discussion/{task_id}/files",
                "query_used": "..."
            }
        """
        def _progress(step: str, message: str, data: Optional[Dict] = None):
            if yield_progress:
                try:
                    yield_progress(step, message, data or {})
                except Exception:
                    pass

        _progress("ideation_agent_start", "🧠 自主构思智能体启动：理解任务并准备检索相关论文…", {})

        # 1) 生成检索关键词（可用 LLM 提炼，或直接用任务摘要）
        query_used = self._derive_search_query(user_task, _progress)
        if not query_used or not query_used.strip():
            query_used = user_task[:200].strip() or "research"
        _progress("ideation_agent_query", f"📎 检索关键词：{query_used[:80]}…", {"query": query_used})

        # 2) 调用多源论文搜索，并下载最新 10 篇到 discussion/task_id/files（或调用方传入的 save_path）
        papers_list: List[Dict[str, Any]] = []
        downloaded_to: Optional[str] = None
        save_dir = save_path if save_path else os.path.join("discussion", task_id, "files")
        tool_mgr = getattr(self, "_tool_manager", None)
        tool = tool_mgr.get_tool("academic_paper_search") if tool_mgr else None
        if tool:
            _progress("ideation_agent_search", "📚 正在检索 arXiv 与 Semantic Scholar 并下载最新 10 篇 PDF…", {})
            try:
                result = tool_mgr.execute_tool(
                    "academic_paper_search",
                    {"query": query_used, "save_path": save_dir, "limit_per_source": 20},
                )
                if result and getattr(result, "success", False) and getattr(result, "data", None):
                    latest = (result.data.get("latest_10_papers") or []) if isinstance(result.data, dict) else []
                    papers_list = latest
                    downloaded_to = result.data.get("downloaded_to") if isinstance(result.data, dict) else None
            except Exception as e:
                logger.warning(f"论文检索/下载失败，继续基于任务描述构思: {e}")
                papers_list = []
                downloaded_to = None
            _progress(
                "ideation_agent_papers",
                f"✅ 已获取 {len(papers_list)} 篇论文" + (f"，PDF 已保存至 {downloaded_to}" if downloaded_to else ""),
                {"count": len(papers_list), "downloaded_to": downloaded_to},
            )
        else:
            _progress("ideation_agent_no_tool", "⚠️ 未配置学术论文搜索工具，将仅基于任务描述进行构思", {})

        # 3) 构建论文摘要文本供 LLM 阅读
        papers_summary = self._build_papers_summary(papers_list)
        supporting_papers = [
            {
                "title": p.get("title", ""),
                "authors": p.get("authors", []),
                "abstract": (p.get("abstract") or "")[:500],
                "year": p.get("year"),
                "source": p.get("source", ""),
                "paper_id": p.get("paper_id", ""),
                "pdf_local_path": p.get("pdf_local_path"),
            }
            for p in papers_list
        ]

        # 4) LLM 自主构思：逻辑可推理、不违背世界定理的想法，并标注支撑论文
        ideas = self._synthesize_ideas(user_task, papers_summary, papers_list, _progress)

        return {
            "ideas": ideas,
            "supporting_papers": supporting_papers,
            "papers_summary": papers_summary,
            "downloaded_to": downloaded_to or save_dir,
            "query_used": query_used,
        }

    def _derive_search_query(self, user_task: str, progress: Callable) -> str:
        """从用户任务提炼 1～2 个英文/中文检索关键词。"""
        if not self.llm:
            return user_task[:200].strip()
        try:
            prompt = f"""根据下面的用户任务，提炼 1～2 个用于在学术库（arXiv、Semantic Scholar）中检索论文的查询词。
要求：简短、与任务核心相关、适合论文检索。若任务偏技术/科研，可保留英文术语。
只输出查询词本身，不要解释。

用户任务：
{user_task[:800]}

查询词："""
            response = self.llm.invoke(prompt)
            text = (response.content if hasattr(response, "content") else str(response)).strip()
            return text.split("\n")[0].strip()[:200] if text else user_task[:200].strip()
        except Exception as e:
            logger.warning(f"自主构思提炼检索词失败: {e}")
            return user_task[:200].strip()

    def _build_papers_summary(self, papers_list: List[Dict[str, Any]]) -> str:
        """将论文列表整理成一段摘要文本。"""
        if not papers_list:
            return "（暂无检索到的论文）"
        lines = []
        for i, p in enumerate(papers_list[:15], 1):
            title = p.get("title", "")
            authors = p.get("authors", [])
            auth = ", ".join(authors[:5]) if isinstance(authors, list) else str(authors)
            abstract = (p.get("abstract") or "")[:400]
            year = p.get("year", "")
            source = p.get("source", "")
            lines.append(f"[{i}] {title} | {auth} | {year} | {source}\n{abstract}")
        return "\n\n".join(lines)

    def _synthesize_ideas(
        self,
        user_task: str,
        papers_summary: str,
        papers_list: List[Dict[str, Any]],
        progress: Callable,
    ) -> List[Dict[str, Any]]:
        """基于任务与论文摘要，生成逻辑可推理、不违背世界定理的想法，并标注支撑论文（按序号）。"""
        progress("ideation_agent_synthesize", "💡 正在基于论文进行自主构思（逻辑可推理、原理一致）…", {})

        ideas: List[Dict[str, Any]] = []
        if not self.llm:
            ideas = [{"content": f"基于任务「{user_task[:100]}」的初步方向，建议结合检索到的文献进一步由学者分析。", "supporting_paper_ids": []}]
            return ideas

        prompt = f"""你是一位严谨的科研构思助手。请根据「用户任务」和「检索到的论文摘要」，产出 2～4 条**逻辑可推理、不违背科学原理与常识**的想法或假设，供后续任务分析与角色确定使用。
每条想法需注明由哪几篇论文（按 [1][2] 序号）支撑；若某条想法主要来自常识/逻辑推理而非某篇论文，可写「逻辑推导」。

## 用户任务
{user_task[:1000]}

## 检索到的论文摘要（序号 [1][2]... 对应下方论文列表）
{papers_summary[:6000]}

## 输出要求
请直接返回一个 JSON 数组，每项格式：
{{"content": "想法或假设的完整表述", "supporting_paper_ids": [1, 2] 或 ["逻辑推导"]}}
不要其他解释，只输出 JSON 数组。"""

        try:
            response = self.llm.invoke(prompt)
            raw = (response.content if hasattr(response, "content") else str(response)).strip()
            if "```" in raw:
                start = raw.find("[")
                end = raw.rfind("]") + 1
                if start != -1 and end > start:
                    raw = raw[start:end]
            if raw.startswith("["):
                arr = json.loads(raw)
                for item in arr[:6]:
                    if isinstance(item, dict) and item.get("content"):
                        ideas.append({
                            "content": item["content"],
                            "supporting_paper_ids": item.get("supporting_paper_ids") or [],
                        })
        except Exception as e:
            logger.warning(f"自主构思 LLM 合成失败: {e}")
            ideas = [{"content": f"基于任务与检索结果，建议由学者进一步分解任务并确定专家角色。", "supporting_paper_ids": []}]
        return ideas
