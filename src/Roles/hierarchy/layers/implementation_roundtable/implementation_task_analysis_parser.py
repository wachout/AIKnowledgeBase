# -*- coding: utf-8 -*-
"""
从「实施任务分析」智能体输出的 Markdown 中解析出角色列表及各角色对应的任务。
用于第二层根据任务分析结果动态创建智能体并分配任务。
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def parse_implementation_task_analysis_md(md_path: str) -> List[Dict[str, Any]]:
    """
    解析实施任务分析 Markdown，提取人力资源配置表中的角色及其参与任务列表。

    支持常见格式：
    - Markdown 表：| 岗位名称 | 职责描述 | 所属层级 | 参与任务列表 |
    - 列表/小节：### 岗位名 / **岗位名称** xxx / - 岗位：xxx，参与任务：T1, T2

    Returns:
        [{"role_name": str, "role_description": str, "layer": str, "professional_domain": str, "tasks": [str], "skills": [str]}, ...]
    """
    if not md_path or not os.path.isfile(md_path):
        return []
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logger.warning("读取实施任务分析文件失败 %s: %s", md_path, e)
        return []

    roles_with_tasks: List[Dict[str, Any]] = []

    # 优先在「人力资源配置表」小节内解析，确保取到角色与任务表
    hr_section_match = re.search(
        r'(?:##\s*[3三四3.]?\s*人力资源配置表|###\s*人力资源配置表)[\s\S]*?(?=##\s|###\s|\Z)',
        content,
        re.IGNORECASE
    )
    search_content = hr_section_match.group(0) if hr_section_match else content

    # 1) 尝试解析 Markdown 表：表头含 岗位/角色 与 任务（表头取匹配内容的第一行，否则会误取上一行标题）
    table_pattern = r'\|[^\n]*岗位[^\n]*\|\s*\n\|[-:\s|]+\|\s*\n((?:\|[^\n]+\|\s*\n?)+)'
    table_match = re.search(table_pattern, search_content, re.IGNORECASE)
    if table_match:
        table_lines = table_match.group(0).split("\n")
        header_line = table_lines[0].strip() if table_lines else ""
        body = table_match.group(1)
        headers = [h.strip() for h in re.split(r'\|', header_line) if h.strip()]
        name_col = _find_column_index(headers, ["岗位名称", "岗位", "角色", "角色名称"])
        desc_col = _find_column_index(headers, ["职责描述", "职责", "描述"])
        layer_col = _find_column_index(headers, ["所属层级", "层级"])
        domain_col = _find_column_index(headers, ["专业领域", "领域", "学科领域"])
        task_col = _find_column_index(headers, ["参与任务", "参与任务列表", "任务列表", "任务"])
        skills_col = _find_column_index(headers, ["关键技能要求", "技能要求", "技能"])
        if name_col is not None:
            for line in body.strip().split("\n"):
                if not line.strip() or line.strip().startswith("|---"):
                    continue
                cells = [c.strip() for c in re.split(r'\|', line) if c is not None]
                if len(cells) <= name_col:
                    continue
                role_name = (cells[name_col] or "").strip().strip("*")
                if not role_name or role_name in ["岗位名称", "岗位", "角色"]:
                    continue
                role_desc = (cells[desc_col] if desc_col is not None and desc_col < len(cells) else "").strip().strip("*")
                layer = (cells[layer_col] if layer_col is not None and layer_col < len(cells) else "").strip().strip("*")
                professional_domain = (cells[domain_col] if domain_col is not None and domain_col < len(cells) else "").strip().strip("*")
                tasks_str = cells[task_col] if task_col is not None and task_col < len(cells) else ""
                tasks = _split_tasks_text(tasks_str)
                skills_str = cells[skills_col] if skills_col is not None and skills_col < len(cells) else ""
                skills = _split_skills_text(skills_str)
                if not professional_domain and role_name:
                    professional_domain = role_name
                roles_with_tasks.append({
                    "role_name": role_name,
                    "role_description": role_desc or role_name,
                    "layer": layer,
                    "professional_domain": professional_domain,
                    "tasks": tasks,
                    "skills": skills,
                })
            if roles_with_tasks:
                return roles_with_tasks

    # 2) 尝试从「人力资源配置表」小节中按标题/列表解析
    hr_section = re.search(
        r'(?:##\s*人力资源配置表|###\s*人力资源配置表)[\s\S]*?(?=##\s|###\s[^人]|\Z)',
        content,
        re.IGNORECASE
    )
    if hr_section:
        section = hr_section.group(0)
        # 按 ### 或 **岗位** 拆成块
        blocks = re.split(r'(?=###\s|\*\*岗位|岗位名称\s*[：:])', section)
        for block in blocks:
            role_name = ""
            role_desc = ""
            layer = ""
            tasks = []
            m_title = re.search(r'(?:###\s+|\*\*岗位[名称]*[：:]*\s*)([^\n*]+)', block)
            if m_title:
                role_name = m_title.group(1).strip()
            if not role_name:
                continue
            m_desc = re.search(r'职责[描述]*[：:]\s*([^\n]+)', block)
            if m_desc:
                role_desc = m_desc.group(1).strip()
            m_layer = re.search(r'所属层级[：:]\s*([^\n]+)', block)
            if m_layer:
                layer = m_layer.group(1).strip()
            m_tasks = re.search(r'参与任务[列表]*[：:]\s*([^\n]+)', block)
            if m_tasks:
                tasks = _split_tasks_text(m_tasks.group(1))
            m_domain = re.search(r'专业领域[：:]\s*([^\n]+)', block)
            professional_domain = m_domain.group(1).strip() if m_domain else role_name
            m_skills = re.search(r'关键技能[^：:]*[：:]\s*([^\n]+)', block)
            skills = _split_skills_text(m_skills.group(1)) if m_skills else []
            roles_with_tasks.append({
                "role_name": role_name,
                "role_description": role_desc or role_name,
                "layer": layer,
                "professional_domain": professional_domain,
                "tasks": tasks,
                "skills": skills,
            })
        if roles_with_tasks:
            return roles_with_tasks

    # 3) 从 RACI 或任务分解清单中提取角色名，再在全文匹配任务
    role_names = set()
    raci_section = re.search(r'(?:##\s*RACI[^\n]*|###\s*RACI[^\n]*)[\s\S]*?(?=##\s|\Z)', content, re.IGNORECASE)
    if raci_section:
        for m in re.finditer(r'负责人[：:]\s*([^\n|]+)|执行[者]*[：:]\s*([^\n|]+)|[|\s]([^\s|]+)(?=\s*\|\s*R\s|\s*\|\s*A\s)', raci_section.group(0)):
            g = m.lastgroup
            if g:
                name = (m.group(1) or m.group(2) or m.group(3) or "").strip()
                if name and len(name) < 50 and name not in ("R", "A", "C", "I"):
                    role_names.add(name)
    if not role_names:
        for line in content.split("\n"):
            if "岗位" in line or "角色" in line:
                for part in re.split(r'[：:|\t]', line):
                    part = part.strip()
                    if part and 2 <= len(part) <= 30 and part not in ("岗位名称", "职责描述", "所属层级", "参与任务列表"):
                        role_names.add(part)
                        break

    for rn in role_names:
        roles_with_tasks.append({
            "role_name": rn,
            "role_description": rn,
            "layer": "",
            "professional_domain": rn,
            "tasks": [],
            "skills": [],
        })

    return roles_with_tasks


def _find_column_index(headers: List[str], keywords: List[str]) -> Optional[int]:
    for i, h in enumerate(headers):
        if any(k in (h or "") for k in keywords):
            return i
    return None


def _split_tasks_text(text: str) -> List[str]:
    """将参与任务列表字符串拆成任务编号/名称列表"""
    if not text or not text.strip():
        return []
    text = text.strip()
    tasks = []
    for part in re.split(r'[,，、;；\n]', text):
        part = part.strip()
        if part:
            tasks.append(part)
    return tasks[:100]


def _split_skills_text(text: str) -> List[str]:
    """将关键技能要求字符串拆成技能列表"""
    if not text or not text.strip():
        return []
    text = text.strip()
    skills = []
    for part in re.split(r'[,，、;；/／\n]', text):
        part = part.strip().strip("*")
        if part and part not in ("关键技能要求", "技能"):
            skills.append(part)
    return skills[:20]
