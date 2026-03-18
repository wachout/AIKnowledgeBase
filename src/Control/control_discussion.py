# -*- coding:utf-8 -*-
"""
圆桌讨论系统控制模块
- 第一层讨论层：每个智能体发言保存到 discussion/discussion_id/discuss
- 第二层实施步骤层：每个实施方案保存到 discussion/discussion_id/implement
- 第三层具像化层：阅读实施步骤，按领域具像化（数字化+具像化），结果保存到 discussion/discussion_id/concretization
"""

import os
import re
import json
import time
import logging
import uuid
import asyncio
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Dict, Any, List, Optional
from datetime import datetime

from Db.sqlite_db import cSingleSqlite
from Config.llm_config import get_chat_tongyi
try:
    from Config.llm_config import get_chat_long
except Exception:
    get_chat_long = None
from Roles import RoundtableDiscussion

# 导入三层系统组件
from Roles.hierarchy import (
    # 类型定义
    Task, Objective, Constraint, DecisionOutput, ImplementationOutput,
    ExecutionStatus, ImplementationRole,
    LayerContext,
    # 实施层
    ImplementationLayer,
)
from Roles.hierarchy.layers.implementation_layer import ImplementGroupScheduler, ImplementationGroup
from Roles.hierarchy.layers.implementation_roundtable import ImplementationDiscussion
from Roles.hierarchy.layers.concretization_roundtable import ConcretizationDiscussion

logger = logging.getLogger(__name__)

# 第一层讨论汇总：按「发言智能体 + 该智能体对应的质疑者」一起汇总为一个结果，不分开汇总专家与质疑者
# 每个汇总单元 = 某专家的全部发言 + 针对该专家的质疑者发言，合并为一份汇总
LAYER1_PER_ROLE_SUMMARY_PROMPT = """# Role：圆桌讨论汇总专家

## Background：
第一层圆桌讨论结束后，按「发言的智能体与其对应质疑者」**一起**汇总为一份结果。**每份汇总**包含：（1）**该专家/智能体的全部发言**（多轮、思考、内容），（2）**针对该专家的质疑者发言**。将二者合并审视后输出**一条**结构清晰、**侧重有价值和可实施信息**的 Markdown 汇总段落，供第二层实施专家按领域查阅。不将专家与质疑者分开汇总。

## Attention：
请结合该角色发言与对应角色发言，识别**讨论与矛盾**之处；在汇总时**选择有价值和可实施的信息**，对争议点可做简要归纳或采纳更可实施的立场，不编造原文没有的信息，输出需可独立理解、便于落地。

## Profile：
- Author: prompt-optimizer
- Version: 1.0
- Language: 中文
- Description: 圆桌讨论汇总专家将「该专家全部发言」与「针对该专家的质疑者发言」合并为一条汇总（专家与对应质疑者一起汇总，不分开），提炼核心观点与可执行建议，识别讨论与矛盾并筛选有价值、可实施的内容，输出便于第二层任务分解的汇总。

### Skills:
- 从该角色多轮发言与对应方发言中提炼核心观点与主要立场，识别讨论与矛盾
- 识别并保留关键论据、数据、指标（参数、规格、时间节点等），优先保留可验证、可落地的信息
- 在存在分歧或矛盾时，选择更有价值、更可实施的结论或建议，可简要说明不同观点及采纳理由
- 将结论与可执行建议归纳为要点或列表，便于下游任务分解与实施

## Goals:
- 提炼该角色的核心观点与主要立场
- 结合对应角色发言，识别**讨论与矛盾**
- **选择有价值和可实施的信息**写入汇总：保留关键论据与数据，对争议点做取舍或归纳
- 明确归纳结论与可执行建议（要点或列表），便于第二层实施

## Constrains:
- 仅基于下方提供的「该角色全部发言」与「对应角色发言」进行提炼，不得编造
- 输出为纯 Markdown，可使用二级/三级标题、有序/无序列表、加粗等
- 不得输出任何与汇总无关的前缀或后缀，直接输出 Markdown 汇总正文

## Workflow:
1. 通读该角色的全部发言与对应角色发言，标记讨论与矛盾
2. 从中选择有价值、可实施的信息，对矛盾点做取舍或简要归纳
3. 按「核心观点 → 关键论据与数据 → 结论与建议 → 讨论/矛盾与采纳说明（若有）」组织内容
4. 输出结构清晰的 Markdown 段落，保证可独立理解、便于第二层按角色查阅与落地

## OutputFormat:
- 核心观点（可选小标题，段落或列表）
- 关键论据与数据（保留参数、规格、时间等，侧重可实施信息）
- 结论与建议（要点或有序列表，可执行优先）
- 讨论/矛盾与采纳说明（若有：争议点、不同观点、采纳或取舍理由）

## Initialization
作为圆桌讨论汇总专家，你必须遵守上述约束条件，使用中文输出，且直接输出 Markdown 汇总正文，不要输出与汇总无关的前缀或后缀。

---
请基于下方「该角色的全部发言」与「对应角色发言」内容，完成该角色的汇总，**选择有价值和可实施的信息**，直接输出符合 OutputFormat 的 Markdown 正文。"""

# 第二层实施任务分析智能体（方案实施架构师）：阅读第一层汇总文档与索引，输出任务分解、RACI、人力资源配置
IMPLEMENTATION_TASK_ANALYSIS_AGENT_PROMPT = """# Role：方案实施架构师

## Background：
用户希望基于会议讨论的最终方案，构建一个结构清晰、责任明确且可执行性强的人员安排与任务分配体系。该任务需要对方案进行深度解析，并根据以下三个职能层级（基础执行层、协调管理层、战略指导层）进行人员配置与职责划分：
- **基础执行层**：负责具体操作性任务，具有明确输入输出和标准化流程，通常由一线员工或技术专员承担；
- **协调管理层**：负责跨部门沟通、资源调配及进度控制，需具备一定的统筹能力和项目管理经验；
- **战略指导层**：负责制定方向、评估风险与关键决策，通常由高层管理者或专家顾问担任。
同时确保任务分解具备中等颗粒度并采用RACI模型进行角色分配。

## Attention：
请以高度专业性和系统性完成此任务，确保每个层级的人员配置逻辑合理、任务分配清晰、时间节点明确，最终输出结果需具有可操作性和落地价值。

## Profile：
- Author: prompt-optimizer
- Version: 1.0
- Language: 中文
- Description: 方案实施架构师是一种专注于将抽象方案转化为具体执行路径的专业角色，擅长任务分解、资源规划和组织设计，能够结合项目管理方法论与实际业务场景制定高效可行的实施方案。

### Skills:
- 精通项目管理流程，熟悉WBS（工作分解结构）与RACI矩阵的应用
- 具备跨部门协作与沟通能力，能识别关键利益相关方并合理分配角色
- 擅长任务粒度控制，能根据复杂程度将任务拆解为2人日以内的子任务
- 能够根据任务类型匹配合适的专业人才，并评估其所需技能与资源
- 熟悉时间估算技术（如三点估算法），能为每项任务设定精确时长，并在必要时提供估算依据

## Goals:
- 解析会议最终方案的核心内容与实施逻辑，识别关键里程碑与依赖关系
- 将方案分解为三个层级的任务模块：基础执行层（负责具体操作性任务）、协调管理层（负责跨部门沟通和资源调配）、战略指导层（负责制定方向和关键决策）
- 为每个任务定义输入/输出内容、所需资源、预估时长及交付标准
- 使用RACI模型为每个任务分配角色，确保R与A角色明确，C与I角色合理
- **识别每个岗位所需的专业领域**（如：软件架构、机械设计、项目管理、仿生学、控制理论、材料工程等），确保人员配置与任务需求匹配
- 输出完整的人力资源配置表，包含岗位名称、职责描述、所属层级、**专业领域**、参与任务列表、关键技能要求

## Constrains:
- 所有任务必须被拆解为中等颗粒度（建议单个子任务时长控制在2人日之间，确保可独立交付）
- 每个任务必须至少包含1个R（执行者）和1个A（负责人）
- 时间估算需精确到小时，不得使用模糊表述
- 不得遗漏任何影响任务执行的关键资源或外部依赖
- RACI角色配置需依据任务影响范围进行动态调整，避免过度或不足配置

## Workflow:
1. 阅读并理解会议最终方案，提取关键任务与目标，绘制初步任务框架
2. 根据任务属性与复杂度，将其归类至基础执行层、协调管理层或战略指导层
3. 对每个任务进行细化分解，确保符合中等颗粒度要求，并为每个子任务设定输入/输出、资源需求及时长
4. 应用RACI模型为每个子任务分配角色，确保职责清晰、权责对等
5. **为每个岗位明确所需专业领域**（与职责、任务相匹配的学科或行业领域），并列出关键技能要求
6. 整合所有信息，形成完整的任务清单、人力资源配置表（含专业领域与关键技能要求）及时间进度计划

## OutputFormat:
- 任务分解清单（含任务编号、名称、层级、输入/输出、资源需求、预估时长）
- RACI角色分配表（按任务编号列出R/A/C/I角色及其对应人员）
- 人力资源配置表（**必须为 Markdown 表格**，表头包含：岗位名称、职责描述、所属层级、**专业领域**、参与任务列表、关键技能要求；专业领域填写该岗位所需的学科/行业领域，如「软件架构」「机械设计」「项目管理」「仿生学」等，便于系统据此自动创建对应角色智能体）

## Suggestions:
- 定期回顾任务分解的合理性，确保任务之间无重复或遗漏
- 在RACI角色分配过程中，优先考虑角色的实际能力和过往经验
- 建立任务之间的依赖关系图，有助于识别关键路径与潜在瓶颈
- 结合敏捷方法，为复杂任务预留缓冲时间和应急资源
- 利用可视化工具（如甘特图、泳道图）辅助任务展示与沟通

## Initialization
作为方案实施架构师，你必须遵守上述约束条件，使用默认中文与用户交流。

---
请基于下方提供的「第一层圆桌讨论汇总文档」与「第一层汇总文档索引」内容，完成方案实施架构分析，直接输出符合 OutputFormat 的 Markdown 文档（任务分解清单、RACI角色分配表、人力资源配置表），不要输出与文档无关的前缀或后缀。"""

# 第二层角色安排智能体：根据「任务分析与人员要求」文档抽取需要的人员角色，输出结构化 JSON，供系统自动创建对应智能体
IMPLEMENTATION_ROLE_ARRANGEMENT_AGENT_PROMPT = """# Role：角色安排抽取专家

## 任务
下方是一份由「任务分析与人员要求智能体」（方案实施架构师）产出的人力资源配置文档，可能包含任务分解清单、RACI 角色分配表、人力资源配置表等。请你**从中抽取所有需要的人员/岗位角色**，输出为**唯一**的 JSON 数组，便于系统据此自动创建对应的实施角色智能体。

## 输出要求
1. **仅输出一个 JSON 数组**，不要输出任何 Markdown、说明或前后缀。
2. 数组中每个元素表示一个角色，**必须**包含字段：
   - **role_name** (string)：岗位/角色名称
   - **role_description** (string)：职责描述（简要）
   - **layer** (string)：所属层级（如：基础执行层、协调管理层、战略指导层，可空字符串）
   - **professional_domain** (string)：专业领域（如：软件架构、机械设计、项目管理，无则用角色名）
   - **tasks** (array of string)：该角色参与的任务编号或任务名称列表（如 ["T001","T002"] 或 ["任务名称1","任务名称2"]）
   - **skills** (array of string)：关键技能要求列表（如 ["项目管理","沟通协调"]，可空数组）
3. 不遗漏文档中出现的任何岗位/角色；同一岗位只出现一次。
4. 若文档中无表格或表格解析困难，请根据段落、列表中的岗位与任务描述自行归纳为上述结构。

## 示例（仅作格式参考，勿照抄）
[
  {"role_name": "项目总监", "role_description": "负责项目总体方向与关键决策", "layer": "战略指导层", "professional_domain": "项目管理", "tasks": ["T012","T017"], "skills": ["高层管理","决策力"]},
  {"role_name": "系统工程师", "role_description": "需求与接口管理", "layer": "协调管理层", "professional_domain": "系统工程", "tasks": ["T005","T013"], "skills": ["MBSE","需求工程"]}
]

请直接输出 JSON 数组，不要用 markdown 代码块包裹。"""

# 第二层实施文档汇总智能体：阅读各角色执行结果，使用长文本大模型生成一份完整实施文档
LAYER2_IMPLEMENTATION_SUMMARY_AGENT_PROMPT = """你是一名实施文档汇总专家。你的任务是一次性阅读下方「各角色实施执行结果」的全部内容，生成一份结构清晰、便于落地执行的**实施文档**（Markdown）。

## 要求
1. 输出为纯 Markdown，包含（可自拟小节标题）：
   - **文档概述**：项目/方案目标、总体思路
   - **角色与责任**：各实施角色及其职责
   - **任务与步骤**：按角色或按阶段整理的任务清单、实施步骤、交付物、预估时长
   - **资源与依赖**：所需资源、关键依赖与风险提示
   - **执行建议**：优先级、里程碑、验收要点
2. 内容需基于下方各角色原文提炼与整合，不编造；可合并重复、补全逻辑顺序
3. 直接输出 Markdown 正文，不要输出「好的，以下是」等前缀或后缀。"""


class DiscussionControl:
    """圆桌讨论系统控制类
    支持三层系统：
    1. 第一层讨论层：发言保存到 discuss/
    2. 第二层实施步骤层：实施方案保存到 implement/
    3. 第三层具像化层：数字/具像化/抽象化工程师 + 按领域具像化智能体，结果保存到 concretization/
    """
    
    def __init__(self):
        # 实施组调度器
        self.impl_scheduler = ImplementGroupScheduler()
        # LLM实例（延迟初始化）
        self._llm_instance = None
    
    def _get_llm_instance(self):
        """获取LLM实例（延迟初始化）"""
        if self._llm_instance is None:
            self._llm_instance = get_chat_tongyi()
        return self._llm_instance
    
    def _convert_to_decision_output(self, discussion_state: dict, final_report: dict, query: str) -> DecisionOutput:
        """
        将圆桌讨论结果转换为 DecisionOutput
        
        Args:
            discussion_state: 讨论状态
            final_report: 最终报告
            query: 原始查询
        
        Returns:
            DecisionOutput
        """
        # 提取共识点作为目标
        consensus_data = discussion_state.get('consensus_data', {})
        key_points = consensus_data.get('key_points', [])
        
        objectives = []
        for i, point in enumerate(key_points[:5]):  # 最多5个目标
            obj = Objective(
                name=f"共识目标_{i+1}",
                description=point if isinstance(point, str) else str(point),
                priority=5 - i
            )
            objectives.append(obj)
        
        # 提取行动建议作为任务
        final_report_data = discussion_state.get('final_report', {}) if not final_report else final_report
        action_recommendations = final_report_data.get('action_recommendations', [])
        key_insights = final_report_data.get('key_insights', [])
        
        tasks = []
        for i, action in enumerate(action_recommendations[:5]):  # 最多5个任务
            task = Task(
                name=f"实施任务_{i+1}",
                description=action if isinstance(action, str) else str(action),
                priority=5 - i,
                status=ExecutionStatus.PENDING
            )
            tasks.append(task)
        
        # 如果没有任务，从关键洞察创建
        if not tasks and key_insights:
            for i, insight in enumerate(key_insights[:3]):
                task = Task(
                    name=f"洞察实施_{i+1}",
                    description=insight if isinstance(insight, str) else str(insight),
                    priority=3 - i,
                    status=ExecutionStatus.PENDING
                )
                tasks.append(task)
        
        # 提取分歧点作为约束
        divergences = consensus_data.get('divergences', [])
        constraints = []
        for i, div in enumerate(divergences[:3]):
            constraint = Constraint(
                name=f"分歧约束_{i+1}",
                description=div if isinstance(div, str) else str(div),
                constraint_type="soft"
            )
            constraints.append(constraint)
        
        # 构建讨论摘要
        total_rounds = discussion_state.get('current_round', 0)
        consensus_level = consensus_data.get('overall_level', 0.0)
        discussion_summary = f"""
圆桌讨论完成，共进行 {total_rounds} 轮讨论。
最终共识水平: {consensus_level:.2f}
共识点: {len(key_points)} 个
分歧点: {len(divergences)} 个
行动建议: {len(action_recommendations)} 条
        """.strip()
        
        return DecisionOutput(
            query=query,
            objectives=objectives,
            tasks=tasks,
            constraints=constraints,
            success_criteria=[f"完成共识水平: {consensus_level:.2f}"],
            discussion_summary=discussion_summary
        )
    
    def _run_implementation_layer(
        self,
        decision_output: DecisionOutput,
        discussion_state: dict,
        discussion_base_path: str
    ):
        """
        运行第二层：实施讨论组
        
        Args:
            decision_output: 第一层决策输出
            discussion_state: 讨论状态
            discussion_base_path: 讨论文件夹路径
        
        Returns:
            (impl_outputs: List[ImplementationOutput], impl_result: 第二层讨论结果，供第三层使用)
        """
        logger.info("\n" + "=" * 60)
        logger.info("🛠️ 【第二层】启动实施讨论组...")
        logger.info("=" * 60)
        
        impl_outputs = []
        impl_result = None
        llm_instance = self._get_llm_instance()
        
        # 创建实施讨论系统
        impl_discussion = ImplementationDiscussion(llm_adapter=llm_instance)
        
        # 构建第一层完整输出（供第二层使用；第二层将按第一层领域专家一一对应创建实施步骤智能体）
        first_layer_output = {
            'discussion_id': discussion_state.get('discussion_id', ''),
            'discussion_summary': discussion_state.get('final_report', {}).get('discussion_summary', ''),
            'consensus_data': discussion_state.get('consensus_data', {}),
            'key_insights': discussion_state.get('final_report', {}).get('key_insights', []),
            'action_recommendations': discussion_state.get('final_report', {}).get('action_recommendations', []),
            'participants': discussion_state.get('participants', []),
            'total_rounds': discussion_state.get('current_round', 0),
            'rounds': discussion_state.get('rounds', []),  # 各轮发言，供第二层按领域提取专家发言与质疑者意见
            'user_goal': discussion_state.get('topic', ''),  # 用户目标，第二层须紧扣此目标给出可实施措施
            'discuss_dir': os.path.abspath(os.path.join(discussion_base_path, "discuss")),  # 第一层 discuss 目录，供 JSON 解析失败时回退读取
        }
        
        # 如果有第一层汇总文档索引，传入
        if 'layer1_summary' in discussion_state:
            first_layer_output['layer1_summary'] = discussion_state['layer1_summary']
        # 若第二层任务分析/角色安排已发言过，恢复文件路径供本次直接使用
        base_for_impl = os.path.abspath(discussion_base_path)
        if discussion_state.get('implementation_task_analysis_file'):
            rel = discussion_state['implementation_task_analysis_file']
            abs_path = os.path.join(base_for_impl, rel) if not os.path.isabs(rel) else rel
            if os.path.isfile(abs_path):
                first_layer_output['implementation_task_analysis_file'] = abs_path
        if discussion_state.get('implementation_role_arrangement_file'):
            rel = discussion_state['implementation_role_arrangement_file']
            abs_path = os.path.join(base_for_impl, rel) if not os.path.isabs(rel) else rel
            if os.path.isfile(abs_path):
                first_layer_output['implementation_role_arrangement_file'] = abs_path
        # 第二层智能体是否已发言：供再次启动时跳过已发言的智能体，直接使用已保存方案
        layer2 = discussion_state.get('layer2') or {}
        first_layer_output['layer2_speeches'] = layer2.get('speeches', [])
        first_layer_output['layer2_expert_has_spoken'] = layer2.get('expert_has_spoken', [])
        first_layer_output['discussion_base_path'] = discussion_base_path
        # 第二层流程进度：动态角色发言进度；再次启动时检查并从未执行步骤继续
        first_layer_output['layer2_process'] = discussion_state.get('layer2_process') or {}

        # 构建任务列表
        task_list = []
        for task in decision_output.tasks:
            task_list.append({
                'name': task.name,
                'description': task.description,
                'task_id': task.task_id,
                'priority': task.priority if hasattr(task, 'priority') else 3
            })
        
        logger.info(f"第二层接收 {len(task_list)} 个任务")
        if first_layer_output.get('layer1_summary'):
            logger.info("已加载第一层汇总文档索引")
            # 任务分析智能体：若已发言过则使用已有文档，否则调用 LLM 并做发言记录
            task_analysis_path = first_layer_output.get("implementation_task_analysis_file")
            if task_analysis_path and os.path.isfile(task_analysis_path):
                logger.info("任务分析与人员要求智能体已发言，使用文档中的内容: %s", task_analysis_path)
            else:
                logger.info("开始执行第二层任务分析智能体（将读取第一层汇总并调用长文本模型，可能需数分钟，请稍候）...")
                try:
                    task_analysis_path = self._run_implementation_task_analysis_agent(
                        discussion_base_path, first_layer_output
                    )
                    if task_analysis_path:
                        logger.info("📋 第二层实施任务分析已生成: %s", task_analysis_path)
                        # 发言记录：写入 discussion_state.layer2_speeches，并持久化任务分析文件路径
                        try:
                            rel_path = os.path.relpath(task_analysis_path, discussion_base_path)
                            discussion_state["implementation_task_analysis_file"] = rel_path
                            if "layer2_speeches" not in discussion_state:
                                discussion_state["layer2_speeches"] = []
                            discussion_state["layer2_speeches"].append({
                                "speaker": "方案实施架构师",
                                "role_type": "task_analysis",
                                "content_type": "task_analysis",
                                "relative_md_file": rel_path,
                                "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                                "datetime": datetime.now().isoformat(),
                            })
                            discussion_state["updated_at"] = datetime.now().isoformat()
                            self._save_discussion_state(discussion_base_path, discussion_state)
                        except Exception as save_err:
                            logger.warning("保存任务分析发言记录失败: %s", save_err)
                        # 角色安排智能体：从任务分析文档抽取人员角色列表（表格解析失败时供第二层创建智能体）
                        try:
                            role_arr_path = self._run_implementation_role_arrangement_agent(
                                discussion_base_path, first_layer_output
                            )
                            if role_arr_path:
                                logger.info("📋 第二层角色安排（抽取角色）已生成: %s", role_arr_path)
                                try:
                                    rel_role = os.path.relpath(role_arr_path, discussion_base_path)
                                    discussion_state["implementation_role_arrangement_file"] = rel_role
                                    if "layer2_speeches" not in discussion_state:
                                        discussion_state["layer2_speeches"] = []
                                    discussion_state["layer2_speeches"].append({
                                        "speaker": "角色抽取智能体",
                                        "role_type": "role_arrangement",
                                        "content_type": "role_arrangement",
                                        "relative_json_file": rel_role,
                                        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                                        "datetime": datetime.now().isoformat(),
                                    })
                                    discussion_state["updated_at"] = datetime.now().isoformat()
                                    self._save_discussion_state(discussion_base_path, discussion_state)
                                except Exception as e:
                                    logger.warning("保存角色抽取智能体发言记录失败: %s", e)
                        except Exception as ra_err:
                            logger.warning("角色安排智能体异常: %s", ra_err)
                    else:
                        logger.debug("未执行或跳过实施任务分析智能体")
                except Exception as ta_err:
                    logger.warning("实施任务分析智能体异常（继续执行第二层讨论）: %s", ta_err)
            # 若已有任务分析文档但尚无角色安排 JSON，可补跑角色安排智能体
            if first_layer_output.get("implementation_task_analysis_file") and not first_layer_output.get("implementation_role_arrangement_file"):
                try:
                    role_arr_path = self._run_implementation_role_arrangement_agent(
                        discussion_base_path, first_layer_output
                    )
                    if role_arr_path:
                        logger.info("📋 第二层角色安排（抽取角色）已生成: %s", role_arr_path)
                        try:
                            rel_role = os.path.relpath(role_arr_path, discussion_base_path)
                            discussion_state["implementation_role_arrangement_file"] = rel_role
                            if "layer2_speeches" not in discussion_state:
                                discussion_state["layer2_speeches"] = []
                            discussion_state["layer2_speeches"].append({
                                "speaker": "角色抽取智能体",
                                "role_type": "role_arrangement",
                                "content_type": "role_arrangement",
                                "relative_json_file": rel_role,
                                "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                                "datetime": datetime.now().isoformat(),
                            })
                            discussion_state["updated_at"] = datetime.now().isoformat()
                            self._save_discussion_state(discussion_base_path, discussion_state)
                        except Exception as e:
                            logger.warning("保存角色抽取智能体发言记录失败: %s", e)
                except Exception as ra_err:
                    logger.warning("角色安排智能体异常: %s", ra_err)
        
        try:
            logger.info("第二层实施讨论即将启动（异步 run_implementation_discussion）...")
            # 运行异步讨论
            async def run_discussion():
                outputs = []
                async for chunk in impl_discussion.run_implementation_discussion(
                    task_list=task_list,
                    first_layer_output=first_layer_output
                ):
                    # logger.info(chunk.strip())
                    outputs.append(chunk)
                return outputs
            
            # 在同步上下文中运行异步代码
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    future = asyncio.run_coroutine_threadsafe(run_discussion(), loop)
                    future.result(timeout=600)
                else:
                    asyncio.run(run_discussion())
            except RuntimeError:
                asyncio.run(run_discussion())
            
            # 收集讨论结果
            result = impl_discussion._current_result
            impl_result = result
            if result:
                impl_output = ImplementationOutput(
                    task_id=result.task_id,
                    status=ExecutionStatus.COMPLETED if result.success else ExecutionStatus.FAILED,
                    started_at=result.started_at,
                    completed_at=result.completed_at
                )
                impl_output.metrics['consensus_level'] = result.final_consensus_level
                impl_outputs.append(impl_output)
                
                logger.info(f"✅ 实施讨论完成，共识度: {result.final_consensus_level:.2f}")
                
                # 第二层实施方案已保存到 discussion/discussion_id/implement
                self._save_implementation_result(
                    discussion_base_path,
                    decision_output.tasks[0] if decision_output.tasks else None,
                    result
                )
                # 科学家分析结果 -> implement/
                if result.scholar_analysis:
                    self._save_layer2_scholar_result(discussion_base_path, result)
                # 综合者产出（综合方案）-> implement/
                if result.synthesized_plan:
                    self._save_layer2_synthesized_plan(discussion_base_path, result)
                # 第二层创建的角色智能体保存到 discussion/xxx/roles/（layer_2_ 前缀），便于恢复与查看
                self._save_layer2_roles_and_state(
                    discussion_base_path, result, discussion_state
                )
                logger.info("第二层角色智能体已保存到 roles 目录: %s", os.path.join(discussion_base_path, "roles"))
                # 任务分析驱动时：角色执行结果保存到 concretization/，并调用汇总智能体生成实施文档
                if first_layer_output.get("implementation_task_analysis_file") and (result.expert_proposals or []):
                    try:
                        self._save_layer2_results_to_concretization(discussion_base_path, result)
                        summary_path = self._run_implementation_summary_agent(
                            discussion_base_path, result.expert_proposals
                        )
                        if summary_path:
                            logger.info("📄 实施文档（汇总）已生成: %s", summary_path)
                    except Exception as conc_ex:
                        logger.warning("保存到 concretization 或实施文档汇总失败: %s", conc_ex)

        except Exception as e:
            logger.error(f"❌ 实施讨论失败: {e}", exc_info=True)
            impl_output = ImplementationOutput(
                task_id=task_list[0].get('task_id', '') if task_list else '',
                status=ExecutionStatus.FAILED
            )
            impl_outputs.append(impl_output)
            # 即使讨论中途失败，也保存已创建的第二层角色到 roles，便于恢复或查看
            result = getattr(impl_discussion, '_current_result', None)
            if result and (result.experts_created or []):
                try:
                    self._save_layer2_roles_and_state(
                        discussion_base_path, result, discussion_state
                    )
                    logger.info("已保存第二层已创建角色到 roles（讨论中途失败后的部分结果）")
                except Exception as save_ex:
                    logger.warning(f"保存第二层部分结果失败: {save_ex}")
            # 第二层流程进度：部分完成也记录
            if result is not None:
                discussion_state['layer2_process'] = {
                    'speeches_done': bool(getattr(result, 'expert_proposals', None) and len(result.expert_proposals) > 0),
                }
                self._save_discussion_state(discussion_base_path, discussion_state)
        
        # 第二层流程进度记录：动态角色发言
        _result = impl_result or getattr(impl_discussion, '_current_result', None)
        if _result is not None:
            discussion_state['layer2_process'] = {
                'speeches_done': bool(getattr(_result, 'expert_proposals', None) and len(_result.expert_proposals) > 0),
            }
        # 更新讨论状态
        discussion_state['implementation_layer'] = {
            'status': 'completed',
            'task_count': len(decision_output.tasks),
            'completed_count': sum(1 for o in impl_outputs if o.status == ExecutionStatus.COMPLETED),
            'timestamp': datetime.now().isoformat()
        }
        self._save_discussion_state(discussion_base_path, discussion_state)
        
        logger.info(f"\n🛠️ 实施讨论组完成，共处理 {len(impl_outputs)} 个任务")
        return impl_outputs, impl_result

    def _run_concretization_layer(
        self,
        discussion_base_path: str,
        discussion_id: str,
        processed_experts: List[str] = None,
    ):
        """
        运行第三层具像化层：阅读 implement/ 中的专家发言，按领域创建具像化智能体，
        执行数字化+具像化（符合第一性原理、物理守恒、材料约束等），结果保存到 concretization/。
        支持任务恢复：传入已处理的专家列表，跳过已完成的专家。
        
        Args:
            discussion_base_path: 讨论基础目录
            discussion_id: 讨论ID
            processed_experts: 已处理的专家发言文件名列表（base_name）
        
        Returns:
            dict: {
                "output_files": 具象化输出文件路径列表,
                "processed_experts": 已处理的专家列表（包含本次新处理的）
            }
        """
        processed_experts = processed_experts or []
        try:
            llm_instance = self._get_llm_instance()
            # 为具像化层提供网络检索能力：查询细节步骤、定义与原理
            web_search_fn = None
            try:
                from Roles.tools.tool_manager import ToolManager
                from Roles.tools.web_search_tool import WebSearchTool
                _tm = ToolManager()
                _tm.register_tool(WebSearchTool())

                def _web_search_for_concretization(query: str) -> str:
                    res = _tm.execute_tool("web_search", {"query": query, "limit": 5})
                    if not res.success or not getattr(res, "data", None):
                        return ""
                    data = res.data
                    results = data.get("results", []) if isinstance(data, dict) else []
                    return "\n".join(
                        f"- {r.get('title', '')}: {r.get('snippet', '')}"
                        for r in results[:5]
                        if r.get("snippet") or r.get("title")
                    )

                web_search_fn = _web_search_for_concretization
            except Exception as e:
                logger.debug(f"具像化层未启用网络检索: {e}")

            conc_discussion = ConcretizationDiscussion(
                llm_adapter=llm_instance,
                web_search_fn=web_search_fn,
            )

            async def run_conc():
                outputs = []
                async for chunk in conc_discussion.run_concretization(
                    discussion_base_path=discussion_base_path,
                    discussion_id=discussion_id,
                    processed_experts=processed_experts,
                ):
                    # logger.info(chunk.strip())
                    outputs.append(chunk)
                return outputs

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    future = asyncio.run_coroutine_threadsafe(run_conc(), loop)
                    future.result(timeout=600)
                else:
                    asyncio.run(run_conc())
            except RuntimeError:
                asyncio.run(run_conc())
            logger.info("✅ 第三层具像化层完成")
            result = conc_discussion.get_last_result()
            
            # 构建返回结果
            ret = {
                "output_files": [],
                "processed_experts": [],
            }
            
            if result:
                # 收集输出文件路径（转为相对路径）
                if getattr(result, "summary_output_files", None):
                    for p in result.summary_output_files:
                        if os.path.isabs(p) and p.startswith(os.path.abspath(discussion_base_path)):
                            ret["output_files"].append(os.path.relpath(p, discussion_base_path))
                        else:
                            ret["output_files"].append(p)
                
                # 收集已处理的专家列表
                if getattr(result, "processed_experts", None):
                    ret["processed_experts"] = result.processed_experts
            
            return ret
        except Exception as e:
            logger.error(f"❌ 第三层具像化层执行失败: {e}", exc_info=True)
            return {"output_files": [], "processed_experts": []}

    def _save_implementation_result(self, discussion_base_path: str, task, result):
        """保存实施讨论结果到 discussion/discussion_id/implement/"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            task_name = task.name if task and hasattr(task, 'name') else result.task_name
            safe_task_name = re.sub(r'[^\w\u4e00-\u9fa5]', '_', task_name)
            
            impl_dir = os.path.join(discussion_base_path, "implement")
            os.makedirs(impl_dir, exist_ok=True)
            
            json_filename = f"impl_discussion_{safe_task_name}_{timestamp}.json"
            json_filepath = os.path.join(impl_dir, json_filename)
            
            impl_data = {
                "task_name": task_name,
                "task_id": task.task_id if task and hasattr(task, 'task_id') else result.task_id,
                "discussion_id": result.discussion_id,
                "started_at": result.started_at.isoformat() if result.started_at else None,
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                "total_rounds": result.total_rounds,
                "final_consensus_level": result.final_consensus_level,
                "key_decisions": result.key_decisions,
                "implementation_plan": result.implementation_plan,
                "success": result.success,
                # 结构化数据
                "scholar_analysis": result.scholar_analysis,
                "experts_created": result.experts_created,
                "expert_proposals_count": len(result.expert_proposals),
                "cross_reviews_count": len(result.cross_reviews) if hasattr(result, 'cross_reviews') else 0,
                "synthesized_plan": result.synthesized_plan,
                "challenges": result.challenges
            }
            
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(impl_data, f, ensure_ascii=False, indent=2)
            logger.info(f"保存实施讨论结果: {json_filepath}")
            
            md_filename = f"impl_report_{safe_task_name}_{timestamp}.md"
            md_filepath = os.path.join(impl_dir, md_filename)
            
            md_content = self._generate_implementation_report_md(task, result)
            
            with open(md_filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)
            logger.info(f"保存实施讨论报告: {md_filepath}")
            
        except Exception as e:
            logger.error(f"保存实施讨论结果失败: {e}")
    
    def _save_layer2_roles_and_state(
        self,
        discussion_base_path: str,
        result,
        discussion_state: dict,
    ):
        """将第二层已创建智能体保存到 roles/（含每个角色配置 JSON 与对应 prompt 的 .md 文件），并写入 discussion_state['layer2']。讨论中途失败时也可调用以保存部分结果。"""
        layer2_participants = []
        layer2_agents = []
        for expert in (result.experts_created or []):
            name = expert.get('name') or expert.get('role') or expert.get('domain') or 'expert'
            try:
                # 保存到 roles：配置 JSON + 该角色 prompt 的 _prompt.md（由 _save_agent_config 一并写入）
                self._save_agent_config(discussion_base_path, f"layer_2_{name}", expert)
            except Exception as ex:
                logger.warning(f"保存第二层角色配置失败 {name}: {ex}")
            layer2_participants.append(name)
            layer2_agents.append({
                "name": name,
                "domain": expert.get("domain", ""),
                "role": expert.get("role", ""),
            })
        layer2_speeches = []
        impl_dir = os.path.join(discussion_base_path, "implement")
        os.makedirs(impl_dir, exist_ok=True)
        info_entries = discussion_state.setdefault("info", [])
        
        # 从 result.expert_speech_files 读取已保存的发言文件（由 implementation_discussion 保存）
        for speech_record in getattr(result, 'expert_speech_files', []) or []:
            expert_name = speech_record.get("expert_name", "未知专家")
            relative_path = speech_record.get("relative_file_path", "")
            ts = speech_record.get("timestamp", datetime.now().strftime("%Y%m%d_%H%M%S"))
            
            layer2_speeches.append({
                "speaker": expert_name,
                "relative_file_path": relative_path,
                "timestamp": ts,
            })
            logger.info(
                "第二层专家「%s」发言已记录至 discussion_state.layer2.speeches: %s",
                expert_name, relative_path,
            )
            info_entries.append({
                "timestamp": datetime.now().isoformat(),
                "message": f"第二层专家「{expert_name}」发言已保存至 {relative_path}",
                "layer": "implementation",
                "speaker": expert_name,
                "relative_md": relative_path,
            })
        # 方案汇总智能体、角色分类智能体：写入 layer2_speeches 与 discussion_state，再次启动时可复用
        if getattr(result, 'plan_summary_role_classification_file', None):
            discussion_state["plan_summary_role_classification_file"] = result.plan_summary_role_classification_file
            logger.info("角色分类智能体结果已记录至 discussion_state: %s", result.plan_summary_role_classification_file)
            info_entries.append({
                "timestamp": datetime.now().isoformat(),
                "message": f"角色分类智能体已运行，分类结果已保存至 {result.plan_summary_role_classification_file}",
                "layer": "implementation",
                "speaker": "角色分类智能体",
                "relative_md": result.plan_summary_role_classification_file,
                "relative_json": "",
            })
        if getattr(result, 'plan_summary_file', None):
            ts_plan = datetime.now().strftime("%Y%m%d_%H%M%S")
            layer2_speeches.append({
                "speaker": "方案汇总智能体",
                "relative_file_path": result.plan_summary_file,
                "relative_json_path": "",
                "timestamp": ts_plan,
            })
            discussion_state["plan_summary_agent_file"] = result.plan_summary_file
            logger.info("方案汇总智能体发言已记录至 discussion_state: %s", result.plan_summary_file)
            info_entries.append({
                "timestamp": datetime.now().isoformat(),
                "message": f"方案汇总智能体已发言，汇总已保存至 {result.plan_summary_file}，已记录供再次启动时复用",
                "layer": "implementation",
                "speaker": "方案汇总智能体",
                "relative_md": result.plan_summary_file,
                "relative_json": "",
            })
        # 记录已完成的类别汇总，供任务恢复时跳过已完成的类别
        if getattr(result, 'plan_summary_categories_done', None):
            discussion_state["plan_summary_categories_done"] = result.plan_summary_categories_done
            logger.info("已完成的类别汇总已记录至 discussion_state: %s", result.plan_summary_categories_done)
        # 智能体是否发言：保存到 discussion_state，再次启动时已发言的智能体不再调用 LLM
        expert_has_spoken = [s.get("speaker") for s in layer2_speeches if s.get("speaker")]
        discussion_state['layer2'] = {
            'participants': layer2_participants,
            'agents': layer2_agents,
            'speeches': layer2_speeches,
            'expert_has_spoken': expert_has_spoken,
            'completed_at': datetime.now().isoformat(),
        }
        discussion_state["updated_at"] = datetime.now().isoformat()
        self._save_discussion_state(discussion_base_path, discussion_state)

    def _proposal_content_to_markdown_no_json(
        self,
        content: str,
        structured: Any,
        expert_name: str,
        domain: str,
    ) -> str:
        """将第二层智能体发言内容转为纯 Markdown（去掉 ```json ... ``` 代码块，不包含 JSON 格式内容）。"""
        if not content and not structured:
            return f"# {expert_name}\n\n**领域**: {domain}\n\n（无正文）\n"
        parts = [f"# {expert_name}\n\n**领域**: {domain}\n\n---\n\n"]
        # 去掉 content 中的 ```json ... ``` 块，保留其余正文
        if content:
            no_json = re.sub(r'```json\s*[\s\S]*?```', '\n\n（结构化数据见同名 .json 文件）\n\n', content, flags=re.IGNORECASE)
            no_json = re.sub(r'```\s*[\s\S]*?```', '\n\n（代码块已省略，见同名 .json 文件）\n\n', no_json)
            no_json = no_json.strip()
            if no_json:
                parts.append(no_json)
                parts.append("\n\n")
        # 若有 structured，转为可读的 Markdown 列表（不直接贴 JSON）
        if structured and isinstance(structured, dict):
            parts.append("## 结构化要点\n\n")
            raw_steps = structured.get("implementation_steps")
            impl_steps = raw_steps if isinstance(raw_steps, list) else []
            if impl_steps:
                for idx, step in enumerate(impl_steps, 1):
                    if isinstance(step, dict):
                        name = step.get("name") or step.get("step_name") or f"步骤{idx}"
                        desc = step.get("description") or step.get("desc") or ""
                        duration = step.get("duration") or step.get("duration_estimate") or ""
                        deliverable = step.get("deliverable") or step.get("deliverables") or ""
                        parts.append(f"### {idx}. {name}\n\n")
                        if desc:
                            parts.append(f"{desc}\n\n")
                        if duration:
                            parts.append(f"- **时长**: {duration}\n")
                        if deliverable:
                            parts.append(f"- **交付**: {deliverable}\n")
                        parts.append("\n")
                    else:
                        parts.append(f"- {step}\n")
            prof = structured.get("professional_analysis") or structured.get("summary") or ""
            if prof and not (impl_steps and prof in str(impl_steps)):
                parts.append("### 专业分析\n\n")
                parts.append(f"{prof}\n\n")
        return "".join(parts).strip() or f"# {expert_name}\n\n**领域**: {domain}\n\n（无正文）\n"

    def _save_layer2_scholar_result(self, discussion_base_path: str, result):
        """实施层：科学家智能体结果保存到 discussion/discussion_id/implement"""
        try:
            impl_dir = os.path.join(discussion_base_path, "implement")
            os.makedirs(impl_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_path = os.path.join(impl_dir, f"impl_scholar_analysis_{ts}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result.scholar_analysis, f, ensure_ascii=False, indent=2)
            logger.info(f"保存实施层科学家分析到 implement: {json_path}")
        except Exception as e:
            logger.warning(f"保存实施层科学家结果失败: {e}")
    
    def _save_layer2_synthesized_plan(self, discussion_base_path: str, result):
        """实施层：综合者智能体结果（综合方案）保存到 discussion/discussion_id/implement"""
        try:
            impl_dir = os.path.join(discussion_base_path, "implement")
            os.makedirs(impl_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_path = os.path.join(impl_dir, f"impl_synthesized_plan_{ts}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result.synthesized_plan, f, ensure_ascii=False, indent=2)
            md_path = os.path.join(impl_dir, f"impl_synthesized_plan_{ts}.md")
            plan = result.synthesized_plan or {}
            summary = plan.get("summary", "")
            phases = plan.get("implementation_phases", [])
            md_lines = ["# 实施综合方案\n\n", f"**摘要**: {summary}\n\n", "## 实施阶段\n\n"]
            for i, ph in enumerate(phases, 1):
                if isinstance(ph, dict):
                    md_lines.append(f"### {i}. {ph.get('name', f'阶段{i}')}\n\n")
                    for j, step in enumerate(ph.get("steps", []), 1):
                        s = step if isinstance(step, dict) else {"name": str(step)}
                        md_lines.append(f"- {s.get('name', str(step))}\n")
                    md_lines.append("\n")
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write("".join(md_lines))
            logger.info(f"保存实施层综合方案到 implement: {json_path}, {md_path}")
        except Exception as e:
            logger.warning(f"保存实施层综合方案失败: {e}")
    
    def _generate_implementation_report_md(self, task, result) -> str:
        """生成实施讨论的 Markdown 报告"""
        task_name = task.name if task and hasattr(task, 'name') else result.task_name
        parts = []
        parts.append(f"""# 实施讨论报告

**任务**: {task_name}
**讨论 ID**: {result.discussion_id}
**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**状态**: {'成功' if result.success else '未完成'}
**共识度**: {result.final_consensus_level:.2f}

---
""")
        
        # 科学家分析摘要
        scholar = result.scholar_analysis
        if scholar:
            parts.append(f"""## 科学家分析

- **项目类型**: {scholar.get('project_type', '未分析')}
- **任务分析**: {scholar.get('task_analysis', '无')[:200]}
- **所需专家**: {len(scholar.get('required_experts', []))} 位

""")
        
        # 专家团队
        experts = result.experts_created
        if experts:
            parts.append(f"## 专家团队 ({len(experts)} 位)\n\n")
            parts.append("| 序号 | 专家 | 领域 | 角色 |\n")
            parts.append("|------|------|------|------|\n")
            for i, expert in enumerate(experts, 1):
                name = expert.get('name', '未知')
                domain = expert.get('domain', '未知')
                role = expert.get('role', '未知')
                parts.append(f"| {i} | {name} | {domain} | {role} |\n")
            parts.append("\n")
        
        # 各专家方案摘要
        proposals = result.expert_proposals
        if proposals:
            parts.append(f"## 专家方案摘要 ({len(proposals)} 个)\n\n")
            for i, prop in enumerate(proposals, 1):
                expert_name = prop.get('expert_name', f'专家{i}')
                domain = prop.get('domain', '未知领域')
                content = prop.get('content', '')[:500]
                parts.append(f"### {i}. {expert_name} ({domain})\n\n{content}\n\n")
        
        # 交叉审阅结果
        cross_reviews = result.cross_reviews if hasattr(result, 'cross_reviews') else []
        if cross_reviews:
            parts.append(f"## 交叉审阅结果 ({len(cross_reviews)} 条)\n\n")
            parts.append("| 审阅者 | 审阅对象 | 立场 | 优点 | 担忧 |\n")
            parts.append("|--------|----------|------|------|------|\n")
            for review in cross_reviews:
                reviewer = review.get('reviewer', '未知')
                target = review.get('target_expert', '未知')
                stance = review.get('stance', 'neutral')
                strengths = ', '.join(review.get('strengths', [])[:2])
                concerns = ', '.join(review.get('concerns', [])[:2])
                parts.append(f"| {reviewer} | {target} | {stance} | {strengths[:50]} | {concerns[:50]} |\n")
            parts.append("\n")
        
        # 综合实施计划
        if result.implementation_plan:
            parts.append(f"## 综合实施计划\n\n{result.implementation_plan}\n\n")
        
        # 关键决策
        if result.key_decisions:
            parts.append(f"## 关键决策 ({len(result.key_decisions)} 项)\n\n")
            for i, decision in enumerate(result.key_decisions, 1):
                parts.append(f"{i}. {decision}\n")
            parts.append("\n")
        
        # 质疑点
        challenges = result.challenges
        if challenges:
            parts.append(f"## 质疑点 ({len(challenges)} 个)\n\n")
            for i, ch in enumerate(challenges, 1):
                if isinstance(ch, dict):
                    point = ch.get('point', '')
                    severity = ch.get('severity', 'medium')
                    suggestion = ch.get('suggestion', '')
                    parts.append(f"{i}. **[{severity.upper()}]** {point}\n")
                    if suggestion:
                        parts.append(f"   - 建议: {suggestion}\n")
                else:
                    parts.append(f"{i}. {ch}\n")
            parts.append("\n")
        
        return "".join(parts)
    
    def _generate_layer1_summary_document(
        self,
        discussion_base_path: str,
        discussion_state: dict,
        final_report: dict,
        query: str
    ) -> Optional[str]:
        """
        生成第一层圆桌讨论的汇总文档（发言智能体与对应质疑者一起汇总，不分开）
        
        按「发言的智能体 + 该智能体对应的质疑者」一起汇总为一个结果：每个专家与其对应质疑者的发言
        合并为一条汇总，不再为专家和质疑者分别产出两条汇总。最后追加共识与分歧、最终报告与行动建议，供第二层实施层专家按领域查阅。
        
        生成两个文件:
        1. Markdown 可读文档（各角色汇总段 + 共识与最终报告）
        2. JSON 结构化索引（供程序化查询）
        
        Args:
            discussion_base_path: 讨论文件夹路径
            discussion_state: 完整讨论状态（汇总显示的讨论主题优先从 discussion_state['topic'] 读取）
            final_report: 最终报告
            query: 用户原始查询（当 discussion_state 中无 topic 时作回退）
            
        Returns:
            汇总文档路径，失败返回 None
        """
        try:
            # 主题优先从 discussion_state.json 的 topic 读取，避免显示为当前聊天内容（如「xxx 任务启动」）
            topic = (discussion_state.get('topic') or '').strip() or (query or '')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            discuss_dir = os.path.join(discussion_base_path, "discuss")
            os.makedirs(discuss_dir, exist_ok=True)
            
            # ---- 收集所有发言数据 ----
            rounds_data = discussion_state.get('rounds', [])
            all_speeches_by_speaker = {}  # {speaker: [speech, ...]}
            all_speeches_by_round = {}    # {round_num: [speech, ...]}
            skeptic_speeches = []
            
            for round_data in rounds_data:
                round_num = round_data.get('round_number', 0)
                speeches = round_data.get('speeches', [])
                all_speeches_by_round[round_num] = []
                
                for speech_data in speeches:
                    speaker = speech_data.get('speaker', '未知')
                    is_skeptic = speech_data.get('is_skeptic', False)
                    speech_entry = {
                        'round': round_num,
                        'thinking': speech_data.get('thinking', ''),
                        'speech': speech_data.get('speech', ''),
                        'is_skeptic': is_skeptic,
                        'target_expert': speech_data.get('target_expert', ''),
                    }
                    
                    if speaker not in all_speeches_by_speaker:
                        all_speeches_by_speaker[speaker] = []
                    all_speeches_by_speaker[speaker].append(speech_entry)
                    all_speeches_by_round[round_num].append({**speech_entry, 'speaker': speaker})
                    
                    if is_skeptic:
                        skeptic_speeches.append({**speech_entry, 'speaker': speaker})
            
            total_rounds = len(rounds_data)
            total_speeches = sum(len(r.get('speeches', [])) for r in rounds_data)
            participants = discussion_state.get('participants', [])
            consensus_data = discussion_state.get('consensus_data', {})
            consensus_level = consensus_data.get('overall_level', 0.0)
            
            # ---- 按「发言智能体 + 对应质疑者」一起汇总为一个结果，不分开汇总 ----
            md = []
            doc_header = f"""# 圆桌讨论汇总文档

**讨论主题**: {topic}
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**总轮次**: {total_rounds} | **总发言**: {total_speeches} | **参与者**: {len(participants)} | **共识**: {consensus_level:.2f}

---

"""
            md.append(doc_header)

            # 确定角色顺序：优先与 participants 一致，否则按 all_speeches_by_speaker 键顺序
            ordered_speakers = []
            for p in participants:
                if p in all_speeches_by_speaker:
                    ordered_speakers.append(p)
            for name in all_speeches_by_speaker:
                if name not in ordered_speakers:
                    ordered_speakers.append(name)

            # 针对某专家的质疑者发言：{ 专家名: [ {speaker, round, thinking, speech, target_expert}, ... ] }
            skeptic_speeches_by_target = {}
            for sk in skeptic_speeches:
                target = (sk.get('target_expert') or '').strip()
                if target:
                    if target not in skeptic_speeches_by_target:
                        skeptic_speeches_by_target[target] = []
                    skeptic_speeches_by_target[target].append(sk)

            def format_speech_list(speech_list, title_prefix=""):
                parts = []
                for idx, sp in enumerate(speech_list, 1):
                    speaker = sp.get('speaker', '未知')
                    parts.append(f"### {title_prefix}发言#{idx}（第{sp.get('round', 0)}轮）\n\n")
                    if sp.get('target_expert'):
                        parts.append(f"**针对**: {sp['target_expert']}\n\n")
                    if sp.get('thinking'):
                        parts.append(f"**思考**: {sp['thinking']}\n\n")
                    parts.append(f"**{speaker} 内容**: {sp.get('speech', '无')}\n\n")
                return "".join(parts)

            per_role_sections = []
            llm_used = False
            role_summary_records = []  # 每个汇总单元的 info 记录
            for speaker_name in ordered_speakers:
                speeches = all_speeches_by_speaker[speaker_name]
                any_skeptic = any(s['is_skeptic'] for s in speeches)
                # 质疑者不单独汇总：其内容已并入对应专家的汇总中，跳过
                if any_skeptic:
                    continue
                # 专家（或非质疑者角色）：有对应质疑者时与该质疑者一起汇总为一个结果
                skeptics_aimed = skeptic_speeches_by_target.get(speaker_name, [])
                role_label = f"{speaker_name}（与对应质疑者）" if skeptics_aimed else speaker_name
                # 该角色原始发言文档
                raw_parts = [f"**发言智能体**: {speaker_name}\n\n"]
                for idx, sp in enumerate(speeches, 1):
                    raw_parts.append(f"### 第{sp['round']}轮 发言#{idx}\n\n")
                    if sp.get('thinking'):
                        raw_parts.append(f"**思考**: {sp['thinking']}\n\n")
                    raw_parts.append(f"**内容**: {sp.get('speech', '无')}\n\n")
                role_raw_content = "".join(raw_parts)
                # 追加「针对本专家的质疑者」的发言，一起汇总（上面已取 skeptics_aimed）
                if skeptics_aimed:
                    corresponding_text = "## 针对本专家的质疑者发言（与上方专家发言一起汇总）\n\n" + format_speech_list(skeptics_aimed)
                else:
                    corresponding_text = "## 针对本专家的质疑者发言\n\n（本场无针对本专家的质疑者发言）"
                raw_content = f"{role_raw_content}\n\n{corresponding_text}"

                section_body = None
                summary_method = "原文拼接"
                if get_chat_long is not None:
                    try:
                        prompt = f"{LAYER1_PER_ROLE_SUMMARY_PROMPT}\n\n---\n\n## 该发言智能体与对应质疑者的全部发言（一起汇总）\n\n{raw_content}"
                        llm = get_chat_long(temperature=0.2, streaming=False)
                        response = llm.invoke(prompt)
                        body = getattr(response, "content", None) or str(response)
                        if body and body.strip():
                            section_body = body.strip()
                            llm_used = True
                            summary_method = "LLM汇总"
                    except Exception as e:
                        logger.warning("第一层按角色汇总时 LLM 调用失败 [%s]: %s，该单元使用原文拼接", role_label, e)
                if section_body is None:
                    section_body = role_raw_content + "\n\n" + corresponding_text
                # 将该单元（专家+对应质疑者）汇总单独保存到 discuss 目录
                safe_role_name = re.sub(r'[^\w\u4e00-\u9fa5\-]', '_', speaker_name)
                role_md_filename = f"layer1_summary_{safe_role_name}_{timestamp}.md"
                role_md_filepath = os.path.join(discuss_dir, role_md_filename)
                combined_speech_count = len(speeches) + len(skeptics_aimed)
                role_doc_content = f"""# {role_label} 汇总

**讨论主题**: {topic}
**发言数**: {len(speeches)}（智能体）+ {len(skeptics_aimed)}（质疑者）= {combined_speech_count} | **汇总方式**: {summary_method}
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

{section_body}
"""
                try:
                    with open(role_md_filepath, 'w', encoding='utf-8') as f:
                        f.write(role_doc_content)
                    logger.info("第一层汇总 - 已保存汇总到 discuss: %s（发言智能体+对应质疑者一起）", role_md_filename)
                except Exception as e:
                    logger.warning("第一层汇总 - 保存汇总文件失败 [%s]: %s", role_label, e)
                role_record = {
                    "role": role_label,
                    "speech_count": combined_speech_count,
                    "summary_method": summary_method,
                    "file": role_md_filepath,
                    "relative_file": os.path.relpath(role_md_filepath, discussion_base_path),
                }
                role_summary_records.append(role_record)
                logger.info(
                    "第一层汇总 - [%s] 汇总完成 | 发言数: %d | 方式: %s",
                    role_label, combined_speech_count, summary_method
                )
                per_role_sections.append(f"## {role_label}\n\n{section_body}\n\n")

            md.append("\n".join(per_role_sections))

            # ---- 共识与分歧、最终报告（统一拼接在文档末尾） ----
            md.append("## 共识与分歧\n\n")
            key_points = consensus_data.get('key_points', [])
            if key_points:
                md.append("### 共识点\n\n")
                for i, p in enumerate(key_points, 1):
                    md.append(f"{i}. {p}\n")
                md.append("\n")
            divergences = consensus_data.get('divergences', [])
            if divergences:
                md.append("### 分歧点\n\n")
                for i, d in enumerate(divergences, 1):
                    md.append(f"{i}. {d}\n")
                md.append("\n")
            md.append(f"**整体共识水平**: {consensus_level:.2f}\n\n---\n\n")
            md.append("## 最终报告与行动建议\n\n")
            if final_report:
                for i, ins in enumerate(final_report.get('key_insights', []), 1):
                    md.append(f"{i}. {ins}\n")
                md.append("\n")
                for i, rec in enumerate(final_report.get('action_recommendations', []), 1):
                    md.append(f"{i}. {rec}\n")
                md.append("\n")
            if llm_used:
                md.append("---\n*此文档由圆桌讨论系统第一层按「发言智能体与对应质疑者一起」汇总后拼接生成，供第二层实施专家查阅。*\n")
            else:
                md.append("---\n*此文档由圆桌讨论系统自动按发言智能体与对应质疑者一起拼接生成，供第二层实施专家查阅。*\n")
            
            # ---- 写入 Markdown（第一层汇总保存到 discuss/） ----
            md_filename = f"layer1_discussion_summary_{timestamp}.md"
            md_filepath = os.path.join(discuss_dir, md_filename)
            with open(md_filepath, 'w', encoding='utf-8') as f:
                f.write("".join(md))
            logger.info(f"生成第一层汇总文档: {md_filepath}")
            
            # ---- JSON 结构化索引（含每个角色汇总的 info 记录） ----
            json_index = {
                "document_type": "layer1_discussion_summary",
                "discussion_id": discussion_state.get('discussion_id', ''),
                "topic": topic,
                "generated_at": datetime.now().isoformat(),
                "summary_md_file": md_filepath,
                "statistics": {
                    "total_rounds": total_rounds,
                    "total_speeches": total_speeches,
                    "participants_count": len(participants),
                    "consensus_level": consensus_level
                },
                "role_summary_records": role_summary_records,
                "table_of_contents": {
                    "by_role": {
                        sp_name: {
                            "speech_count": len(sp_list),
                            "rounds": sorted(set(s['round'] for s in sp_list)),
                            "is_skeptic": any(s['is_skeptic'] for s in sp_list)
                        }
                        for sp_name, sp_list in all_speeches_by_speaker.items()
                    },
                    "by_round": {
                        str(rn): {
                            "speech_count": len(sp_list),
                            "speakers": [s['speaker'] for s in sp_list]
                        }
                        for rn, sp_list in all_speeches_by_round.items()
                    }
                },
                "consensus_data": {
                    "overall_level": consensus_level,
                    "key_points": consensus_data.get("key_points", []),
                    "divergences": consensus_data.get("divergences", [])
                },
                "final_report": {
                    "key_insights": final_report.get('key_insights', []) if final_report else [],
                    "action_recommendations": final_report.get('action_recommendations', []) if final_report else []
                }
            }
            
            json_filename = f"layer1_discussion_index_{timestamp}.json"
            json_filepath = os.path.join(discuss_dir, json_filename)
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(json_index, f, ensure_ascii=False, indent=2)
            logger.info(f"生成第一层结构化索引: {json_filepath}")
            
            # 更新 discussion_state（统一用相对 discussion_base_path 的路径，便于后续与 base 拼接时不会重复 discussion_id）
            relative_md = os.path.relpath(md_filepath, discussion_base_path)
            relative_json = os.path.relpath(json_filepath, discussion_base_path)
            discussion_state['layer1_summary'] = {
                'md_file': relative_md,
                'json_index_file': relative_json,
                'relative_md_file': relative_md,
                'relative_json_file': relative_json,
                'timestamp': timestamp,
                'statistics': json_index['statistics'],
                'table_of_contents': json_index['table_of_contents']
            }
            
            return md_filepath
            
        except Exception as e:
            logger.error(f"生成第一层汇总文档失败: {e}", exc_info=True)
            return None

    def _run_implementation_task_analysis_agent(
        self,
        discussion_base_path: str,
        first_layer_output: dict,
    ) -> Optional[str]:
        """
        第二层实施任务分析智能体（方案实施架构师）：阅读第一层汇总文档与索引，
        使用长文本大模型输出任务分解清单、RACI 角色分配表、人力资源配置表，保存到 implement/。
        
        Returns:
            生成的 Markdown 文件路径，未执行或失败时返回 None。
        """
        layer1_summary = first_layer_output.get("layer1_summary") or {}
        rel_md = layer1_summary.get("relative_md_file")
        rel_json = layer1_summary.get("relative_json_file")
        md_file = layer1_summary.get("md_file") or rel_md
        json_file = layer1_summary.get("json_index_file") or rel_json
        if not md_file or not json_file:
            logger.info("第一层汇总文档或索引缺失，跳过实施任务分析智能体")
            return None
        base = os.path.abspath(discussion_base_path)
        # 优先用 relative_* 与 base 拼接，避免 md_file 含 "discussion/xxx/..." 时拼接出重复路径
        if rel_md and not os.path.isabs(rel_md):
            md_path = os.path.join(base, rel_md)
        elif md_file and os.path.isabs(md_file):
            md_path = md_file
        elif md_file and 'discuss' in md_file:
            md_path = os.path.join(base, md_file[md_file.find('discuss'):])
        else:
            md_path = os.path.join(base, md_file)
        if rel_json and not os.path.isabs(rel_json):
            json_path = os.path.join(base, rel_json)
        elif json_file and os.path.isabs(json_file):
            json_path = json_file
        elif json_file and 'discuss' in json_file:
            json_path = os.path.join(base, json_file[json_file.find('discuss'):])
        else:
            json_path = os.path.join(base, json_file)
        if not os.path.isfile(md_path):
            logger.warning("第一层汇总文档不存在: %s", md_path)
            return None
        if not os.path.isfile(json_path):
            logger.warning("第一层汇总索引不存在: %s", json_path)
            return None
        if get_chat_long is None:
            logger.warning("get_chat_long 不可用，跳过实施任务分析智能体")
            return None
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()
            with open(json_path, "r", encoding="utf-8") as f:
                index_data = json.load(f)
            index_str = json.dumps(index_data, ensure_ascii=False, indent=2)
            prompt = f"""{IMPLEMENTATION_TASK_ANALYSIS_AGENT_PROMPT}

## 第一层圆桌讨论汇总文档

{md_content}

## 第一层汇总文档索引（JSON）

```json
{index_str}
```
"""
            prompt_len = len(prompt)
            logger.info("任务分析智能体：正在调用长文本模型（输入约 %d 字符），请稍候...", prompt_len)
            llm = get_chat_long(temperature=0.2, streaming=False)
            # 长文本调用可能较久，放入线程并设超时（10 分钟），避免主流程无限阻塞
            _task_analysis_timeout = 600
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(llm.invoke, prompt)
                    response = future.result(timeout=_task_analysis_timeout)
            except FuturesTimeoutError:
                logger.warning("任务分析智能体调用长文本模型超时（%d 秒），请检查网络或模型服务", _task_analysis_timeout)
                return None
            body = getattr(response, "content", None) or str(response)
            if not body or not body.strip():
                logger.warning("实施任务分析智能体返回为空")
                return None
            impl_dir = os.path.join(base, "implement")
            os.makedirs(impl_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_filename = f"implementation_task_analysis_{timestamp}.md"
            out_filepath = os.path.join(impl_dir, out_filename)
            with open(out_filepath, "w", encoding="utf-8") as f:
                f.write("# 实施任务分析（方案实施架构师）\n\n")
                f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")
                f.write(body.strip())
            logger.info("实施任务分析智能体已生成: %s", out_filepath)
            first_layer_output["implementation_task_analysis_file"] = out_filepath
            return out_filepath
        except Exception as e:
            logger.warning("实施任务分析智能体执行失败: %s", e, exc_info=True)
            return None

    def _run_implementation_role_arrangement_agent(
        self,
        discussion_base_path: str,
        first_layer_output: dict,
    ) -> Optional[str]:
        """
        第二层角色安排智能体：根据「任务分析与人员要求」文档抽取需要的人员角色，输出 JSON，
        供表格解析失败时由第二层据此创建对应智能体。
        Returns:
            生成的 JSON 文件路径，未执行或失败时返回 None。
        """
        task_analysis_file = first_layer_output.get("implementation_task_analysis_file") or ""
        if not task_analysis_file or not os.path.isfile(task_analysis_file):
            return None
        if get_chat_long is None:
            logger.warning("get_chat_long 不可用，跳过角色安排智能体")
            return None
        base = os.path.abspath(discussion_base_path)
        if not os.path.isabs(task_analysis_file):
            task_analysis_file = os.path.join(base, task_analysis_file)
        if not os.path.isfile(task_analysis_file):
            return None
        try:
            with open(task_analysis_file, "r", encoding="utf-8") as f:
                doc_content = f.read()
            prompt = f"""{IMPLEMENTATION_ROLE_ARRANGEMENT_AGENT_PROMPT}

## 任务分析与人员要求文档（全文）

{doc_content}
"""
            llm = get_chat_long(temperature=0.2, streaming=False)
            response = llm.invoke(prompt)
            body = (getattr(response, "content", None) or str(response) or "").strip()
            if not body:
                logger.warning("角色安排智能体返回为空")
                return None
            # 抽取 JSON 数组：允许被 ```json ... ``` 包裹
            import re as _re
            m = _re.search(r'\[\s*\{[\s\S]*\}\s*\]', body)
            if not m:
                logger.warning("角色安排智能体未返回有效 JSON 数组")
                return None
            raw = m.group()
            raw_clean = _re.sub(r'[\x00-\x1f]', ' ', raw)
            arr = json.loads(raw_clean)
            if not isinstance(arr, list) or len(arr) == 0:
                logger.warning("角色安排智能体返回非列表或空列表")
                return None
            # 标准化为 roles_with_tasks 格式
            out_roles = []
            for item in arr:
                if not isinstance(item, dict):
                    continue
                role_name = (item.get("role_name") or item.get("name") or "").strip() or "实施角色"
                out_roles.append({
                    "role_name": role_name,
                    "role_description": (item.get("role_description") or item.get("description") or role_name).strip(),
                    "layer": (item.get("layer") or "").strip(),
                    "professional_domain": (item.get("professional_domain") or item.get("domain") or role_name).strip(),
                    "tasks": list(item.get("tasks") or []),
                    "skills": list(item.get("skills") or item.get("expertise") or []),
                })
            if not out_roles:
                return None
            impl_dir = os.path.join(base, "implement")
            os.makedirs(impl_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_filename = f"implementation_role_arrangement_{timestamp}.json"
            out_filepath = os.path.join(impl_dir, out_filename)
            with open(out_filepath, "w", encoding="utf-8") as f:
                json.dump(out_roles, f, ensure_ascii=False, indent=2)
            logger.info("角色安排智能体已生成: %s，共 %d 个角色", out_filepath, len(out_roles))
            first_layer_output["implementation_role_arrangement_file"] = out_filepath
            return out_filepath
        except Exception as e:
            logger.warning("角色安排智能体执行失败: %s", e, exc_info=True)
            return None

    def _save_layer2_results_to_concretization(
        self,
        discussion_base_path: str,
        result,
    ) -> List[str]:
        """
        将第二层各角色执行结果保存到 concretization/（仅用于任务分析驱动流程）。
        Returns:
            已保存的 .md 文件路径列表
        """
        saved_paths = []
        conc_dir = os.path.join(os.path.abspath(discussion_base_path), "concretization")
        os.makedirs(conc_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        for i, prop in enumerate(result.expert_proposals or []):
            name = prop.get("expert_name") or prop.get("domain") or f"role_{i}"
            safe = re.sub(r'[^\w\u4e00-\u9fa5]', '_', str(name)[:50])
            fn = f"impl_role_{safe}_{ts}.md"
            filepath = os.path.join(conc_dir, fn)
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(f"# 实施角色：{name}\n\n")
                    f.write(f"**领域/角色**: {prop.get('domain', '')}\n\n---\n\n")
                    f.write(prop.get("content", ""))
                saved_paths.append(filepath)
            except Exception as ex:
                logger.warning("保存角色执行结果到 concretization 失败 %s: %s", name, ex)
        if saved_paths:
            logger.info("第二层角色执行结果已保存到 concretization/: %d 个文件", len(saved_paths))
        return saved_paths

    def _run_implementation_summary_agent(
        self,
        discussion_base_path: str,
        expert_proposals: List[Dict[str, Any]],
    ) -> Optional[str]:
        """
        实施文档汇总智能体：阅读各角色执行结果，使用长文本大模型生成实施文档，保存到 concretization/。
        Returns:
            生成的实施文档 .md 路径，失败或未配置长文本模型时返回 None。
        """
        if not expert_proposals:
            return None
        if get_chat_long is None:
            logger.warning("get_chat_long 不可用，跳过实施文档汇总智能体")
            return None
        try:
            parts = []
            for i, prop in enumerate(expert_proposals, 1):
                name = prop.get("expert_name") or prop.get("domain") or f"角色{i}"
                parts.append(f"## 角色 {i}：{name}\n\n")
                parts.append(prop.get("content", "") or "(无内容)\n")
                parts.append("\n\n---\n\n")
            body = "".join(parts)
            prompt = f"""{LAYER2_IMPLEMENTATION_SUMMARY_AGENT_PROMPT}

## 各角色实施执行结果

{body}
"""
            llm = get_chat_long(temperature=0.2, streaming=False)
            response = llm.invoke(prompt)
            text = getattr(response, "content", None) or str(response)
            if not text or not text.strip():
                logger.warning("实施文档汇总智能体返回为空")
                return None
            conc_dir = os.path.join(os.path.abspath(discussion_base_path), "concretization")
            os.makedirs(conc_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(conc_dir, f"implementation_summary_{ts}.md")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("# 实施文档（汇总）\n\n")
                f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")
                f.write(text.strip())
            logger.info("实施文档汇总智能体已生成: %s", out_path)
            return out_path
        except Exception as e:
            logger.warning("实施文档汇总智能体执行失败: %s", e, exc_info=True)
            return None

    def _save_plan_summary_to_concretization(
        self,
        discussion_base_path: str,
        result,
        discussion_state: Optional[dict] = None,
    ) -> Optional[str]:
        """
        将第二层「根据分类的角色发言汇总」（方案汇总智能体/按类汇总结果）保存到 concretization/。
        当发言数>5 时为先角色分类再按类汇总的 consolidated 内容；否则为累计汇总内容。
        优先使用 result.plan_summary_consolidated / result.plan_summary_file，若无则从 discussion_state.plan_summary_agent_file 读取。
        Returns:
            保存后的 .md 文件路径，未保存时返回 None。
        """
        content = getattr(result, "plan_summary_consolidated", None) or ""
        plan_file = getattr(result, "plan_summary_file", None) or (discussion_state or {}).get("plan_summary_agent_file")
        if not content and plan_file:
            base = os.path.abspath(discussion_base_path)
            abs_path = os.path.join(base, plan_file) if plan_file and not os.path.isabs(plan_file) else plan_file
            if abs_path and os.path.isfile(abs_path):
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception as e:
                    logger.warning("读取方案汇总文件失败: %s", e)
        if not content or not content.strip():
            return None
        try:
            conc_dir = os.path.join(os.path.abspath(discussion_base_path), "concretization")
            os.makedirs(conc_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(conc_dir, f"plan_summary_by_category_{ts}.md")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("# 方案汇总（按分类角色发言汇总）\n\n")
                f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")
                f.write(content.strip())
            return out_path
        except Exception as e:
            logger.warning("保存分类汇总到 concretization 失败: %s", e)
            return None

    def _save_discussion_state(self, discussion_base_path: str, state_data: dict):
        """保存会议状态到JSON文件"""
        try:
            state_file = os.path.join(discussion_base_path, "discussion_state.json")
            state_data['updated_at'] = datetime.now().isoformat()
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
            logger.info(f"保存会议状态: {state_file}")
        except Exception as e:
            logger.error(f"保存会议状态失败: {e}")

    def _load_discussion_state(self, discussion_base_path: str) -> Optional[dict]:
        """从文件加载会议状态；若文件不存在或读取失败则返回 None。"""
        try:
            state_file = os.path.join(discussion_base_path, "discussion_state.json")
            if not os.path.exists(state_file):
                return None
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            logger.info(f"已从文件加载讨论状态: {state_file}, topic={state.get('topic', '')[:80]}...")
            return state
        except Exception as e:
            logger.warning(f"加载讨论状态失败: {e}")
            return None

    def _build_speech_search_index(self, discussion_base_path: str) -> None:
        """
        对发言完成的任务建立上下文搜索目录（speech_index.json），
        便于按内容查询哪个智能体在哪次发言中说了什么。
        """
        try:
            index_entries: List[Dict[str, Any]] = []
            discuss_dir = os.path.join(discussion_base_path, "discuss")
            impl_dir = os.path.join(discussion_base_path, "implement")
            conc_dir = os.path.join(discussion_base_path, "concretization")
            state = self._load_discussion_state(discussion_base_path)
            # 第一层：从 state.rounds[].speeches[] 或 discuss/*.md
            if state:
                for r in state.get("rounds", []):
                    rn = r.get("round_number", 0)
                    for sp in r.get("speeches", []):
                        speaker = sp.get("speaker", "未知")
                        rel = sp.get("relative_file_path") or sp.get("file_path", "")
                        if rel and not os.path.isabs(rel):
                            path = os.path.join(discussion_base_path, rel)
                        else:
                            path = sp.get("file_path", "")
                        if path and os.path.exists(path):
                            try:
                                with open(path, "r", encoding="utf-8") as f:
                                    text = f.read()
                                preview = (text[:200] + "…") if len(text) > 200 else text
                            except Exception:
                                preview = ""
                            index_entries.append({
                                "layer": 1,
                                "speaker": speaker,
                                "round": rn,
                                "path": os.path.relpath(path, discussion_base_path),
                                "preview": preview,
                            })
            for d, layer in [(discuss_dir, 1), (impl_dir, 2), (conc_dir, 3)]:
                if not os.path.isdir(d):
                    continue
                for fn in os.listdir(d):
                    if not fn.endswith(".md"):
                        continue
                    path = os.path.join(d, fn)
                    rel = os.path.relpath(path, discussion_base_path)
                    speaker = fn.replace(".md", "").replace("impl_expert_", "").replace("_proposal_", " ")
                    if layer == 1 and state:
                        for r in state.get("rounds", []):
                            for sp in r.get("speeches", []):
                                if rel in (sp.get("relative_file_path") or "", sp.get("file_path") or ""):
                                    speaker = sp.get("speaker", speaker)
                                    break
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            text = f.read()
                        preview = (text[:200] + "…") if len(text) > 200 else text
                    except Exception:
                        preview = ""
                    if not any(e.get("path") == rel for e in index_entries):
                        index_entries.append({
                            "layer": layer,
                            "speaker": speaker,
                            "round": None,
                            "path": rel,
                            "preview": preview,
                        })
            out_path = os.path.join(discussion_base_path, "speech_index.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"updated_at": datetime.now().isoformat(), "entries": index_entries}, f, ensure_ascii=False, indent=2)
            logger.info(f"已生成发言检索索引: {out_path}, 共 {len(index_entries)} 条")
        except Exception as e:
            logger.warning(f"构建发言检索索引失败: {e}", exc_info=True)

    def modify_agent_speech(
        self,
        discussion_id: str,
        speaker_name: Optional[str] = None,
        layer: Optional[int] = None,
        user_content: str = "",
    ) -> None:
        """
        修改指定任务中某智能体的发言内容；若修改第一层则级联重跑第二、三层，若修改第二层则级联重跑第三层。
        """
        discussion_base_path = os.path.join("discussion", discussion_id)
        discussion_state = self._load_discussion_state(discussion_base_path)
        if not discussion_state:
            logger.warning(f"未找到任务: {discussion_id}")
            return

        def _speaker_match(name: str, target: Optional[str]) -> bool:
            if not (name and target):
                return False
            n, t = (name or "").strip(), (target or "").strip()
            if not t:
                return False
            return t in n or n in t or n.replace("专家_", "") == t.replace("专家_", "")

        modified_layer: Optional[int] = None
        query = discussion_state.get("topic", "")

        # 第一层：在 rounds[].speeches[] 中按 speaker 匹配并写回文件与 state
        if layer in (None, 1):
            for round_data in discussion_state.get("rounds", []):
                for speech in round_data.get("speeches", []):
                    if not _speaker_match(speech.get("speaker", ""), speaker_name):
                        continue
                    fp = speech.get("file_path") or os.path.join(discussion_base_path, speech.get("relative_file_path", ""))
                    if not os.path.isabs(fp):
                        fp = os.path.join(discussion_base_path, fp)
                    if not fp:
                        continue
                    try:
                        with open(fp, "w", encoding="utf-8") as f:
                            f.write(user_content)
                        speech["speech"] = user_content
                        jpath = speech.get("json_file_path") or (fp.replace(".md", ".json") if fp.endswith(".md") else "")
                        if jpath and not os.path.isabs(jpath):
                            jpath = os.path.join(discussion_base_path, jpath)
                        if jpath and os.path.exists(jpath):
                            with open(jpath, "r", encoding="utf-8") as f:
                                j = json.load(f)
                            j["speech"] = user_content
                            with open(jpath, "w", encoding="utf-8") as f:
                                json.dump(j, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        logger.warning(f"写回第一层发言文件失败: {e}")
                    modified_layer = 1
                    break
                if modified_layer == 1:
                    break

        # 第二层：在 layer2.speeches[] 中按 speaker 匹配并写回 implement 下文件
        if modified_layer is None and layer in (None, 2):
            for s in discussion_state.get("layer2", {}).get("speeches", []):
                if not _speaker_match(s.get("speaker", ""), speaker_name):
                    continue
                rel = s.get("relative_file_path", "")
                if not rel:
                    continue
                full = os.path.join(discussion_base_path, rel)
                try:
                    with open(full, "w", encoding="utf-8") as f:
                        f.write(user_content)
                except Exception as e:
                    logger.warning(f"写回第二层发言文件失败: {e}")
                modified_layer = 2
                break

        if modified_layer is None:
            logger.warning(f"未找到匹配的发言: discussion_id={discussion_id}, speaker={speaker_name}, layer={layer}")
            return

        self._save_discussion_state(discussion_base_path, discussion_state)

        if modified_layer == 1:
            discussion_state.pop("implementation_layer", None)
            discussion_state.pop("concretization_layer", None)
            discussion_state.pop("layer2", None)
            self._save_discussion_state(discussion_base_path, discussion_state)
            final_report = discussion_state.get("final_report", {})
            decision_output = self._convert_to_decision_output(discussion_state, final_report, query)
            self._run_implementation_layer(decision_output, discussion_state, discussion_base_path)
            conc_result = self._run_concretization_layer(discussion_base_path, discussion_state.get("discussion_id", ""))
            discussion_state["concretization_layer"] = {
                "status": "completed",
                "timestamp": datetime.now().isoformat(),
                "processed_experts": conc_result.get("processed_experts", []),
            }
            if conc_result.get("output_files"):
                discussion_state["concretization_summary_output_files"] = conc_result["output_files"]
            self._save_discussion_state(discussion_base_path, discussion_state)
        elif modified_layer == 2:
            discussion_state.pop("concretization_layer", None)
            self._save_discussion_state(discussion_base_path, discussion_state)
            conc_result = self._run_concretization_layer(discussion_base_path, discussion_state.get("discussion_id", ""))
            discussion_state["concretization_layer"] = {
                "status": "completed",
                "timestamp": datetime.now().isoformat(),
                "processed_experts": conc_result.get("processed_experts", []),
            }
            if conc_result.get("output_files"):
                discussion_state["concretization_summary_output_files"] = conc_result["output_files"]
            self._save_discussion_state(discussion_base_path, discussion_state)

        self._build_speech_search_index(discussion_base_path)
    
    def _make_config_json_serializable(self, obj: Any) -> Any:
        """将可能含非 JSON 类型的配置转为可序列化结构（如 DomainExpert 等对象）。"""
        if obj is None or isinstance(obj, (bool, int, float)):
            return obj
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            return {k: self._make_config_json_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._make_config_json_serializable(x) for x in obj]
        # 非基本类型：优先取 name/role 等描述，否则用字符串表示
        if hasattr(obj, 'name') and hasattr(obj, 'role'):
            return {"name": getattr(obj, 'name', None), "role": getattr(obj, 'role', None), "domain": getattr(obj, 'domain', None)}
        if hasattr(obj, '__dict__'):
            return self._make_config_json_serializable({k: v for k, v in obj.__dict__.items() if not k.startswith('_')})
        return str(obj)

    def _save_agent_config(self, discussion_base_path: str, agent_name: str, agent_config: dict):
        """
        保存智能体配置到 roles 目录，并单独保存该角色的 prompt 到同目录的 .md 文件。
        
        Args:
            discussion_base_path: 讨论文件夹路径
            agent_name: 智能体名称
            agent_config: 智能体配置字典（可能含 role_prompt、DomainExpert 等，会先转为可序列化）
        """
        try:
            config_serializable = self._make_config_json_serializable(agent_config)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_agent_name = re.sub(r'[^\w\u4e00-\u9fa5]', '_', agent_name)
            roles_dir = os.path.join(discussion_base_path, "roles")
            os.makedirs(roles_dir, exist_ok=True)
            json_filename = f"{safe_agent_name}_{timestamp}.json"
            json_filepath = os.path.join(roles_dir, json_filename)
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(config_serializable, f, ensure_ascii=False, indent=2)
            logger.info(f"保存智能体配置到 roles: {json_filepath}")
            # 第二层创建的角色对应的 prompt 保存到 roles 目录：JSON 中已含 role_prompt，再单独写一份 .md 便于查看与复用
            role_prompt = agent_config.get("role_prompt") if isinstance(agent_config, dict) else None
            if role_prompt and isinstance(role_prompt, str) and role_prompt.strip():
                prompt_filename = f"{safe_agent_name}_{timestamp}_prompt.md"
                prompt_filepath = os.path.join(roles_dir, prompt_filename)
                with open(prompt_filepath, 'w', encoding='utf-8') as f:
                    f.write(f"# {agent_name} - 角色 Prompt\n\n")
                    f.write(f"**保存时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")
                    f.write(role_prompt.strip())
                logger.info(f"保存角色 prompt 到: {prompt_filepath}")
            return json_filepath
        except Exception as e:
            logger.error(f"保存智能体配置失败: {e}")
            return None

    def chat_with_discussion(self, user_id, session_id, query, file_path, discussion_id):
        """
        圆桌讨论头脑风暴会议系统 - 启动新任务
        支持多智能体协作的深度讨论和决策
        
        注意：意图识别已移至 control_chat.py，此方法只负责启动新任务

        Args:
            user_id: 用户ID
            session_id: 会话ID  
            query: 用户查询/讨论主题
            file_path: 文件路径
            discussion_id: 会议ID
        """
        try:
            # 生成唯一ID
            _id = f"roundtable-{int(time.time())}"

            # 添加初始日志
            logger.info(f"开始圆桌会议处理: user_id={user_id}, session_id={session_id}, query={query[:100] if query else 'None'}")
            logger.info("🚀 正在启动圆桌讨论系统...")
            
            discussion_base_path = os.path.join("discussion", discussion_id)
            
            # 创建文件夹结构：discuss/ 第一层；implement/ 第二层；inspect/ 检验层输出；concretization/ 第三层具像化
            os.makedirs(os.path.join(discussion_base_path, "discuss"), exist_ok=True)
            os.makedirs(os.path.join(discussion_base_path, "implement"), exist_ok=True)
            os.makedirs(os.path.join(discussion_base_path, "inspect"), exist_ok=True)
            os.makedirs(os.path.join(discussion_base_path, "concretization"), exist_ok=True)
            os.makedirs(os.path.join(discussion_base_path, "code"), exist_ok=True)
            os.makedirs(os.path.join(discussion_base_path, "images"), exist_ok=True)
            os.makedirs(os.path.join(discussion_base_path, "pro"), exist_ok=True)
            os.makedirs(os.path.join(discussion_base_path, "files"), exist_ok=True)
            os.makedirs(os.path.join(discussion_base_path, "roles"), exist_ok=True)
            
            logger.info(f"创建圆桌会议文件夹: {discussion_base_path}")
            
            # 重启时从文件读取状态与主题，避免用当前用户输入覆盖已有主题
            discussion_state = self._load_discussion_state(discussion_base_path)
            if discussion_state is not None:
                topic_for_session = discussion_state.get("topic") or query
                logger.info(f"恢复已有任务，使用文件中主题: {topic_for_session[:80] if topic_for_session else 'None'}...")
            else:
                topic_for_session = query
                discussion_state = {
                    "discussion_id": discussion_id,
                    "topic": query,
                    "status": "initializing",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "current_round": 0,
                    "max_rounds": 5,
                    "participants": [],
                    "rounds": [],
                    "consensus_data": {
                        "overall_level": 0.0,
                        "key_points": [],
                        "divergences": []
                    },
                    "file_path": file_path
                }
                self._save_discussion_state(discussion_base_path, discussion_state)
            
            # 仅新建任务时写入数据库记录
            if session_id and discussion_state.get("status") == "initializing":
                try:
                    cSingleSqlite.insert_discussion_task_record(
                        session_id=session_id,
                        discussion_id=discussion_id,
                        user_id=user_id,
                        task_status='active'
                    )
                    logger.info(f"保存任务记录成功: session_id={session_id}, discussion_id={discussion_id}")
                except Exception as e:
                    logger.warning(f"保存任务记录失败: {e}")

            # 初始化LLM实例
            llm_instance = get_chat_tongyi()
            print("LLM实例初始化完成")
            print(discussion_id)
            # 创建圆桌讨论系统实例
            discussion_system = RoundtableDiscussion(llm_instance=llm_instance, discussion_id=discussion_id)

            # 启动讨论系统
            initialization_complete = False
            initialization_error = False
            
            try:
                is_resuming = discussion_state is not None and discussion_state.get("status") != "initializing"
                for init_step in discussion_system.start_discussion(topic_for_session, is_resuming=is_resuming):
                    step_type = init_step.get("step")
                    
                    # 处理错误步骤（优先处理）
                    if step_type == "error":
                        logger.error(f"❌ {init_step['message']}，错误详情: {init_step.get('error_details', '未知错误')}")
                        initialization_error = True
                        return False
                    
                    # 处理各个初始化步骤
                    if step_type == "init_start":
                        logger.info(f"初始化开始: {init_step['message']}")
                    
                    elif step_type == "scholar_analysis":
                        logger.info(f"学者分析: {init_step['message']}")
                    
                    elif step_type == "scholar_result":
                        # 保存学者分析结果到文件
                        task_analysis = init_step.get("task_analysis")
                        if task_analysis:
                            core_analysis = task_analysis.get('core_analysis', {})
                            domain_analysis = task_analysis.get('domain_analysis', {})
                            participant_analysis = task_analysis.get('participant_analysis', {})
                            risk_analysis = task_analysis.get('risk_analysis', {})
                            
                            # 第一层讨论结果保存到 discuss/
                            discuss_dir = os.path.join(discussion_base_path, "discuss")
                            os.makedirs(discuss_dir, exist_ok=True)
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            json_filename = f"scholar_analysis_{timestamp}.json"
                            json_filepath = os.path.join(discuss_dir, json_filename)
                            
                            try:
                                scholar_analysis_data = {
                                    "analysis_time": datetime.now().isoformat(),
                                    "topic": query,
                                    "core_analysis": core_analysis,
                                    "domain_analysis": domain_analysis,
                                    "participant_analysis": participant_analysis,
                                    "risk_analysis": risk_analysis,
                                    "full_task_analysis": task_analysis
                                }
                                
                                with open(json_filepath, 'w', encoding='utf-8') as f:
                                    json.dump(scholar_analysis_data, f, ensure_ascii=False, indent=2)
                                logger.info(f"保存学者分析结果到JSON文件: {json_filepath}")
                            except Exception as e:
                                logger.error(f"保存学者分析JSON文件失败: {e}", exc_info=True)
                            
                            # 保存到Markdown文件（可读格式）
                            md_filename = f"scholar_analysis_{timestamp}.md"
                            md_filepath = os.path.join(discuss_dir, md_filename)
                            
                            try:
                                md_content = f"""# 📚 学者分析结果

**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 🎯 核心问题

{core_analysis.get('core_problem', '未分析')}

## 📝 问题分解

""" + "\n".join(f"{i+1}. {problem}" for i, problem in enumerate(core_analysis.get('sub_problems', []))) + f"""

## ⏱️ 项目评估

| 维度 | 值 |
|------|-----|
| 预估时间 | {core_analysis.get('time_estimate', '未预估')} |
| 复杂度 | {core_analysis.get('complexity_level', '未评估')} |

## 🏢 领域分析

- **主要领域**: {domain_analysis.get('primary_domain', '未确定')}
- **相关领域**: {', '.join(domain_analysis.get('secondary_domains', []))}

## 👥 推荐专家角色 ({len(participant_analysis.get('recommended_roles', []))}个)

""" + "\n".join(f"{i+1}. **{role.get('role', '未知角色')}** - {role.get('reason', '需要专业知识')}" 
                 for i, role in enumerate(participant_analysis.get('recommended_roles', []))) + f"""

## ⚠️ 风险分析

### 风险因素 ({len(risk_analysis.get('risk_factors', []))} 个)

""" + "\n".join(f"- {risk}" for risk in risk_analysis.get('risk_factors', [])) + f"""

### 缓解策略 ({len(risk_analysis.get('mitigation_strategies', []))} 条)

""" + "\n".join(f"- {strategy}" for strategy in risk_analysis.get('mitigation_strategies', [])) + "\n"
                                
                                with open(md_filepath, 'w', encoding='utf-8') as f:
                                    f.write(md_content)
                                logger.info(f"保存学者分析结果到Markdown文件: {md_filepath}")
                            except Exception as e:
                                logger.error(f"保存学者分析Markdown文件失败: {e}", exc_info=True)
                            
                            # 更新discussion_state，保存文件路径
                            try:
                                discussion_state['scholar_analysis'] = {
                                    "json_file": json_filepath,
                                    "md_file": md_filepath,
                                    "relative_json_file": os.path.relpath(json_filepath, discussion_base_path),
                                    "relative_md_file": os.path.relpath(md_filepath, discussion_base_path),
                                    "timestamp": timestamp,
                                    "datetime": datetime.now().isoformat()
                                }
                                discussion_state['updated_at'] = datetime.now().isoformat()
                                self._save_discussion_state(discussion_base_path, discussion_state)
                                logger.info(f"已更新discussion_state.json，添加学者分析文件路径")
                            except Exception as e:
                                logger.error(f"更新discussion_state失败: {e}", exc_info=True)
                            
                            # 只在前端显示文件路径
                            abs_md_filepath = os.path.abspath(md_filepath)
                            abs_json_filepath = os.path.abspath(json_filepath)
                            
                            # 记录学者分析完成信息
                            logger.info(f"📚 学者分析完成，分析结果已保存到文件：{abs_md_filepath}")
                            
                            # JSON文件路径不发送给前端（不生成chunk）
                    
                    elif step_type == "topic_profiling":
                        logger.info(f"话题画像: {init_step['message']}")
                    
                    elif step_type == "topic_profiling_llm":
                        logger.info(f"话题画像LLM: {init_step['message']}")
                    
                    elif step_type == "topic_profiling_parsing":
                        logger.info(f"话题画像解析: {init_step['message']}")
                    
                    elif step_type == "topic_profiling_fallback":
                        logger.info(f"话题画像回退: {init_step['message']}")
                    
                    elif step_type == "topic_profile_complete":
                        # 记录话题画像信息
                        topic_profile = init_step.get("topic_profile")
                        if topic_profile:
                            characteristics = topic_profile.get('topic_characteristics', {})
                            strategy = topic_profile.get('discussion_strategy', {})
                            logger.info(f"🎨 话题画像完成 - 范围: {characteristics.get('scope', '未确定')}, 紧急性: {characteristics.get('urgency', '未确定')}, 影响程度: {characteristics.get('impact', '未确定')}")
                    
                    elif step_type == "agent_creation_start":
                        logger.info(f"智能体创建开始: {init_step['message']}")
                    
                    elif step_type == "agent_created":
                        # 记录创建的智能体
                        agent_name = init_step.get('agent_name', 'unknown')
                        agent_role = init_step.get('agent_role', '未知')
                        agent_config = init_step.get('agent_config', None)
                        
                        logger.info(f"智能体创建: {init_step.get('message', '')} - 角色: {agent_role}, 职责: {init_step.get('description', '未指定')}")
                        
                        # 保存智能体配置到 roles 目录
                        if agent_config:
                            config_filepath = self._save_agent_config(discussion_base_path, agent_name, agent_config)
                            if config_filepath:
                                logger.info(f"智能体配置已保存: {config_filepath}")
                    
                    elif step_type == "agent_creation_complete":
                        participants = init_step.get('participants', [])
                        logger.info(f"✅ 智能体创建完成，总计 {len(participants)} 个智能体角色已就位: {participants}")
                    
                    elif step_type == "agent_creation_error":
                        logger.warning(f"智能体创建错误: {init_step.get('message', '智能体创建遇到问题')}")
                    
                    elif step_type == "moderator_opening":
                        logger.info(f"主持人开场: {init_step['message']}")
                    
                    elif step_type == "meeting_opened":
                        # 保存主持人开场白到文件
                        opening_speech = init_step.get('opening_speech', '会议开始')
                        meeting_message = init_step.get('message', '会议开始')
                        
                        # 第一层讨论结果保存到 discuss/
                        discuss_dir = os.path.join(discussion_base_path, "discuss")
                        os.makedirs(discuss_dir, exist_ok=True)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        md_filename = f"moderator_opening_{timestamp}.md"
                        md_filepath = os.path.join(discuss_dir, md_filename)
                        
                        try:
                            md_content = f"""# 🏛️ 主持人开场白

**会议时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 会议信息

{meeting_message}

## 开场白内容

{opening_speech}
"""
                            
                            with open(md_filepath, 'w', encoding='utf-8') as f:
                                f.write(md_content)
                            logger.info(f"保存主持人开场白到文件: {md_filepath}")
                        except Exception as e:
                            logger.error(f"保存主持人开场白文件失败: {e}", exc_info=True)
                        
                        # 保存到JSON文件（结构化数据）
                        json_filename = f"moderator_opening_{timestamp}.json"
                        json_filepath = os.path.join(discuss_dir, json_filename)
                        
                        try:
                            opening_data = {
                                "datetime": datetime.now().isoformat(),
                                "meeting_message": meeting_message,
                                "opening_speech": opening_speech,
                                "moderator": "主持人"
                            }
                            
                            with open(json_filepath, 'w', encoding='utf-8') as f:
                                json.dump(opening_data, f, ensure_ascii=False, indent=2)
                            logger.info(f"保存主持人开场白到JSON文件: {json_filepath}")
                        except Exception as e:
                            logger.error(f"保存主持人开场白JSON文件失败: {e}", exc_info=True)
                        
                        # 更新discussion_state，保存文件路径
                        try:
                            discussion_state['moderator_opening'] = {
                                "md_file": md_filepath,
                                "json_file": json_filepath,
                                "relative_md_file": os.path.relpath(md_filepath, discussion_base_path),
                                "relative_json_file": os.path.relpath(json_filepath, discussion_base_path),
                                "timestamp": timestamp,
                                "datetime": datetime.now().isoformat()
                            }
                            discussion_state['updated_at'] = datetime.now().isoformat()
                            self._save_discussion_state(discussion_base_path, discussion_state)
                            logger.info(f"已更新discussion_state.json，添加主持人开场文件路径")
                        except Exception as e:
                            logger.error(f"更新discussion_state失败: {e}", exc_info=True)
                        
                        # 只在前端显示文件路径
                        abs_md_filepath = os.path.abspath(md_filepath)
                        abs_json_filepath = os.path.abspath(json_filepath)
                        
                        # 记录主持人开场白信息
                        logger.info(f"🏛️ {meeting_message}，主持人开场白已保存到文件：{abs_md_filepath}")
                        
                        # JSON文件路径不发送给前端（不生成chunk）
                    
                    elif step_type == "discussion_ready":
                        participants = init_step.get('participants', [])
                        logger.info(f"🎯 {init_step.get('message', '')} - 最终参与者阵容 ({len(participants)}人): {participants}")
                        initialization_complete = True
                        
                        # 更新会议状态 - 初始化完成
                        discussion_state['status'] = 'active'
                        discussion_state['participants'] = participants
                        self._save_discussion_state(discussion_base_path, discussion_state)
                    
                    else:
                        # 未知步骤，记录日志但不中断流程
                        # import logging
                        logging.warning(f"未知的初始化步骤: {step_type}, 消息: {init_step.get('message', '')}")
                        if init_step.get("message"):
                            logger.info(f"⚠️ {init_step['message']}")
                
            except Exception as e:
                logger.error(f"初始化讨论系统时出错: {str(e)}", exc_info=True)
                logger.error(f"❌ 初始化讨论系统失败: {str(e)}")
                initialization_error = True
                return False
            
            # 检查初始化是否成功完成
            if initialization_error or not initialization_complete:
                logger.warning("⚠️ 讨论系统初始化未完成，无法继续讨论")
                return False

            # 设置讨论轮次参数
            round_number = 1
            max_rounds = discussion_state.get('max_rounds', 5) if discussion_state else 5
            max_rounds = 1
            while round_number <= max_rounds:
                logger.info(f"🔄 第 {round_number} 轮讨论开始")

                # 本轮已发言的智能体（重启时从状态恢复，避免重复发言；优先 rounds，并合并 layer1.speeches）
                already_spoken = set()
                rounds_list = discussion_state.get("rounds") or []
                if round_number <= len(rounds_list):
                    round_data = rounds_list[round_number - 1]
                    already_spoken = {s.get("speaker") for s in round_data.get("speeches", []) if s.get("speaker")}
                layer1_speeches = (discussion_state.get("layer1") or {}).get("speeches") or []
                for rec in layer1_speeches:
                    if rec.get("round_number") == round_number and rec.get("speaker"):
                        already_spoken.add(rec["speaker"])
                if already_spoken:
                    logger.info(f"第 {round_number} 轮已发言智能体（将跳过，避免重复执行）: {already_spoken}")

                # 执行一轮讨论
                round_complete = False
                # 若本轮在 state 中已有发言（恢复场景），视为本轮已有发言，避免误报「没有产生任何发言」
                has_speeches = bool(round_number <= len(rounds_list) and (rounds_list[round_number - 1].get("speeches")))

                for step_result in discussion_system.conduct_discussion_round(round_number, already_spoken_speakers=already_spoken):
                    if "error" in step_result:
                        logger.error(f"❌ 讨论轮次错误: {step_result['error']}")
                        return False

                    step_type = step_result.get("step")
                    
                    # 记录是否有发言
                    if step_type == "speech":
                        has_speeches = True
                    
                    # 处理警告信息
                    if step_type == "warning":
                        logger.warning(f"⚠️ {step_result.get('message', '警告')}")
                        continue
                    
                    # 处理发言错误
                    if step_type == "speech_error":
                        logger.warning(f"⚠️ {step_result.get('message', '发言出错')}")
                        continue

                    if step_type == "round_start":
                        logger.info(f"📝 {step_result.get('message', f'开始第{round_number}轮讨论')}")

                    elif step_type == "coordination":
                        # 保存协调者结果到文件
                        content = step_result.get('content', {})
                        coordination_result = content.get('coordination_result', {}) if isinstance(content, dict) else str(content)
                        
                        # 提取协调计划内容
                        coordination_plan = ""
                        if isinstance(coordination_result, dict):
                            coordination_plan = coordination_result.get('coordination_plan', str(coordination_result))
                        else:
                            coordination_plan = str(coordination_result)
                        
                        # 第一层讨论结果保存到 discuss/
                        discuss_dir = os.path.join(discussion_base_path, "discuss")
                        os.makedirs(discuss_dir, exist_ok=True)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        md_filename = f"facilitator_coordination_round{round_number}_{timestamp}.md"
                        md_filepath = os.path.join(discuss_dir, md_filename)
                        
                        try:
                            md_content = f"""# 👨‍⚖️ 协调者发言安排

**轮次**: 第 {round_number} 轮讨论
**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 协调计划

{coordination_plan}
"""
                            
                            with open(md_filepath, 'w', encoding='utf-8') as f:
                                f.write(md_content)
                            logger.info(f"保存协调者结果到文件: {md_filepath}")
                        except Exception as e:
                            logger.error(f"保存协调者结果文件失败: {e}", exc_info=True)
                        
                        # 保存到JSON文件（结构化数据）
                        json_filename = f"facilitator_coordination_round{round_number}_{timestamp}.json"
                        json_filepath = os.path.join(discuss_dir, json_filename)
                        
                        try:
                            coordination_data = {
                                "round_number": round_number,
                                "datetime": datetime.now().isoformat(),
                                "coordination_result": coordination_result if isinstance(coordination_result, dict) else {"plan": coordination_result},
                                "coordination_plan": coordination_plan,
                                "facilitator": "协调者"
                            }
                            
                            with open(json_filepath, 'w', encoding='utf-8') as f:
                                json.dump(coordination_data, f, ensure_ascii=False, indent=2)
                            logger.info(f"保存协调者结果到JSON文件: {json_filepath}")
                        except Exception as e:
                            logger.error(f"保存协调者结果JSON文件失败: {e}", exc_info=True)
                        
                        # 更新discussion_state，保存文件路径到当前轮次
                        try:
                            current_round_idx = round_number - 1
                            # 确保轮次数据存在
                            while len(discussion_state['rounds']) <= current_round_idx:
                                discussion_state['rounds'].append({
                                    "round_number": len(discussion_state['rounds']) + 1,
                                    "status": "in_progress",
                                    "speeches": [],
                                    "timestamp": datetime.now().isoformat()
                                })
                            
                            round_data = discussion_state['rounds'][current_round_idx]
                            round_data['facilitator_coordination'] = {
                                "md_file": md_filepath,
                                "json_file": json_filepath,
                                "relative_md_file": os.path.relpath(md_filepath, discussion_base_path),
                                "relative_json_file": os.path.relpath(json_filepath, discussion_base_path),
                                "timestamp": timestamp,
                                "datetime": datetime.now().isoformat()
                            }
                            round_data['updated_at'] = datetime.now().isoformat()
                            discussion_state['updated_at'] = datetime.now().isoformat()
                            self._save_discussion_state(discussion_base_path, discussion_state)
                            logger.info(f"已更新discussion_state.json，添加协调者结果文件路径到第{round_number}轮")
                        except Exception as e:
                            logger.error(f"更新discussion_state失败: {e}", exc_info=True)
                        
                        # 只在前端显示文件路径
                        abs_md_filepath = os.path.abspath(md_filepath)
                        abs_json_filepath = os.path.abspath(json_filepath)
                        
                        # 记录协调者结果信息
                        logger.info(f"👨‍⚖️ 协调者发言安排已保存到文件：{abs_md_filepath}")
                        
                        # JSON文件路径不发送给前端（不生成chunk）

                    elif step_type == "speech_start":
                        speaker = step_result.get('speaker', '未知')
                        logger.info(f"🎤 {speaker} 开始发言")

                    elif step_type == "speech":
                        speaker = step_result.get('speaker', '未知')
                        thinking = step_result.get('thinking', '')
                        speech = step_result.get('speech', '')
                        target_expert = step_result.get('target_expert', '')  # 质疑者针对的专家
                        
                        # 如果 thinking 或 speech 是字典，提取内容
                        if isinstance(thinking, dict):
                            thinking = thinking.get('raw_response', thinking.get('content', str(thinking)))
                        if isinstance(speech, dict):
                            speech = speech.get('content', str(speech))

                        # 判断是否是质疑者
                        is_skeptic = "skeptic" in speaker.lower()
                        
                        # 第一层：每个智能体发言保存到 discuss/
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        safe_speaker = re.sub(r'[^\w\u4e00-\u9fa5]', '_', speaker)
                        discuss_dir = os.path.join(discussion_base_path, "discuss")
                        os.makedirs(discuss_dir, exist_ok=True)
                        
                        md_filename = f"{safe_speaker}_round{round_number}_{timestamp}.md"
                        md_filepath = os.path.join(discuss_dir, md_filename)
                        
                        json_filename = f"{safe_speaker}_round{round_number}_{timestamp}.json"
                        json_filepath = os.path.join(discuss_dir, json_filename)
                        
                        # 构建 Markdown 文件内容
                        if is_skeptic and target_expert:
                            # 质疑者的发言格式
                            md_content = f"""# {speaker} 的质疑

**轮次**: 第 {round_number} 轮讨论
**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**针对专家**: {target_expert}

## 质疑内容

{speech if speech else '无'}
"""
                        else:
                            # 普通发言的格式
                            md_content = f"""# {speaker} 的发言

**轮次**: 第 {round_number} 轮讨论
**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 思考过程

{thinking if thinking else '无'}

## 发言内容

{speech if speech else '无'}
"""
                        
                        # 构建 JSON 数据
                        speech_json_data = {
                            "discussion_id": discussion_id,
                            "round_number": round_number,
                            "agent_name": safe_speaker,
                            "speaker": speaker,
                            "thinking": thinking if thinking else '',
                            "speech": speech if speech else '',
                            "target_expert": target_expert if is_skeptic else None,
                            "is_skeptic": is_skeptic,
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        # 写入 Markdown 文件
                        try:
                            with open(md_filepath, 'w', encoding='utf-8') as f:
                                f.write(md_content)
                            logger.info(f"保存发言到文件: {md_filepath}")
                        except Exception as e:
                            logger.error(f"保存发言 Markdown 文件失败: {e}")
                        
                        # 写入 JSON 文件
                        try:
                            with open(json_filepath, 'w', encoding='utf-8') as f:
                                json.dump(speech_json_data, f, ensure_ascii=False, indent=2)
                            logger.info(f"保存发言 JSON 到文件: {json_filepath}")
                        except Exception as e:
                            logger.error(f"保存发言 JSON 文件失败: {e}")
                        
                        # 使用 Markdown 文件路径作为主引用
                        filepath = md_filepath

                        # 更新discussion_state，将发言信息添加到当前轮次
                        try:
                            # 确保当前轮次存在
                            current_round_idx = round_number - 1
                            while len(discussion_state['rounds']) <= current_round_idx:
                                discussion_state['rounds'].append({
                                    "round_number": len(discussion_state['rounds']) + 1,
                                    "status": "in_progress",
                                    "speeches": [],
                                    "timestamp": datetime.now().isoformat()
                                })
                            
                            # 获取或创建当前轮次数据
                            round_data = discussion_state['rounds'][current_round_idx]
                            if 'speeches' not in round_data:
                                round_data['speeches'] = []
                            
                            # 添加发言信息到轮次数据
                            speech_data = {
                                "speaker": speaker,
                                "thinking": thinking if thinking else '',
                                "speech": speech if speech else '',
                                "file_path": filepath,
                                "json_file_path": json_filepath,
                                "relative_file_path": os.path.relpath(filepath, discussion_base_path),
                                "relative_json_path": os.path.relpath(json_filepath, discussion_base_path),
                                "timestamp": timestamp,
                                "datetime": datetime.now().isoformat(),
                                "is_skeptic": is_skeptic,
                                "target_expert": target_expert if is_skeptic else None
                            }
                            round_data['speeches'].append(speech_data)
                            round_data['round_number'] = round_number
                            round_data['status'] = 'in_progress'
                            round_data['updated_at'] = datetime.now().isoformat()
                            # 第一层发言记录：统一写入 layer1.speeches，任务再次启动时可据此避免重复执行
                            if 'layer1' not in discussion_state:
                                discussion_state['layer1'] = {}
                            if 'speeches' not in discussion_state['layer1']:
                                discussion_state['layer1']['speeches'] = []
                            discussion_state['layer1']['speeches'].append({
                                "speaker": speaker,
                                "round_number": round_number,
                                "relative_file_path": speech_data["relative_file_path"],
                                "relative_json_path": speech_data["relative_json_path"],
                                "timestamp": timestamp,
                                "datetime": speech_data["datetime"],
                            })
                            discussion_state['layer1']['updated_at'] = datetime.now().isoformat()
                            # 更新discussion_state的updated_at
                            discussion_state['updated_at'] = datetime.now().isoformat()
                            # 保存更新后的状态
                            self._save_discussion_state(discussion_base_path, discussion_state)
                            logger.info(f"已更新discussion_state.json，添加{speaker}的发言到第{round_number}轮（已记录至 layer1.speeches，再次启动将跳过该角色）")
                        except Exception as e:
                            logger.error(f"更新discussion_state失败: {e}", exc_info=True)

                        # 返回文件路径链接（使用绝对路径）
                        abs_filepath = os.path.abspath(filepath)
                        
                        # 记录文件路径信息
                        if is_skeptic and target_expert:
                            logger.info(f"🔍 {speaker}的质疑（针对{target_expert}）已保存到文件：{abs_filepath}")
                        else:
                            logger.info(f"📄 {speaker}的发言已保存到文件：{abs_filepath}")

                    elif step_type == "speech_end":
                        speaker = step_result.get('speaker', '未知')
                        logger.info(f"✅ {speaker} 发言结束")

                    elif step_type == "synthesis":
                        content = step_result.get('content', {})
                        synthesis_result = content.get('synthesis_result', '') if isinstance(content, dict) else str(content)
                        if isinstance(synthesis_result, dict):
                            synthesis_result = synthesis_result.get('content', synthesis_result.get('synthesis_report', str(synthesis_result)))
                        
                        # 更新discussion_state，保存综合者观点
                        try:
                            current_round_idx = round_number - 1
                            if current_round_idx < len(discussion_state['rounds']):
                                round_data = discussion_state['rounds'][current_round_idx]
                                round_data['synthesis'] = {
                                    "content": synthesis_result if isinstance(synthesis_result, str) else str(synthesis_result),
                                    "timestamp": datetime.now().isoformat()
                                }
                                round_data['updated_at'] = datetime.now().isoformat()
                                discussion_state['updated_at'] = datetime.now().isoformat()
                                self._save_discussion_state(discussion_base_path, discussion_state)
                                logger.info(f"已保存综合者观点到第{round_number}轮")
                        except Exception as e:
                            logger.error(f"保存综合者观点失败: {e}", exc_info=True)
                        
                        logger.info(f"🔄 综合者整合观点: {synthesis_result[:200] if isinstance(synthesis_result, str) else str(synthesis_result)[:200]}...")

                    elif step_type == "consensus_update":
                        report = step_result.get('report', {})
                        overall_consensus = report.get('overall_consensus', {})
                        consensus_level = overall_consensus.get('overall_level', 0.0)
                        consensus_desc = overall_consensus.get('analysis', '未分析')
                        key_consensus_points = report.get('key_consensus_points', [])
                        key_divergence_points = report.get('key_divergence_points', [])

                        # 更新discussion_state，保存共识信息
                        try:
                            # 更新整体共识数据
                            discussion_state['consensus_data']['overall_level'] = consensus_level
                            discussion_state['consensus_data']['key_points'] = [
                                cp.get('content', str(cp)) if isinstance(cp, dict) else str(cp) 
                                for cp in key_consensus_points[:10]  # 最多保存10个关键共识点
                            ]
                            discussion_state['consensus_data']['divergences'] = [
                                dp.get('content', str(dp)) if isinstance(dp, dict) else str(dp) 
                                for dp in key_divergence_points[:10]  # 最多保存10个分歧点
                            ]
                            
                            # 更新当前轮次的共识信息
                            current_round_idx = round_number - 1
                            if current_round_idx < len(discussion_state['rounds']):
                                round_data = discussion_state['rounds'][current_round_idx]
                                round_data['consensus_update'] = {
                                    "consensus_level": consensus_level,
                                    "consensus_analysis": consensus_desc,
                                    "key_consensus_points": [
                                        cp.get('content', str(cp)) if isinstance(cp, dict) else str(cp) 
                                        for cp in key_consensus_points[:5]
                                    ],
                                    "key_divergence_points": [
                                        dp.get('content', str(dp)) if isinstance(dp, dict) else str(dp) 
                                        for dp in key_divergence_points[:5]
                                    ],
                                    "timestamp": datetime.now().isoformat()
                                }
                                round_data['updated_at'] = datetime.now().isoformat()
                            
                            discussion_state['updated_at'] = datetime.now().isoformat()
                            self._save_discussion_state(discussion_base_path, discussion_state)
                            logger.info(f"已更新共识信息到discussion_state.json，共识水平: {consensus_level:.2f}")
                        except Exception as e:
                            logger.error(f"保存共识信息失败: {e}", exc_info=True)

                        logger.info(f"📊 共识更新 - 共识水平: {consensus_level:.2f}, 共识点: {len(key_consensus_points)}个, 分歧点: {len(key_divergence_points)}个")

                    elif step_type == "round_summary":
                        summary = step_result.get('summary', {})
                        round_summary = summary.get('round_summary', '未生成总结') if isinstance(summary, dict) else str(summary)

                        # 更新discussion_state，保存轮次总结
                        try:
                            current_round_idx = round_number - 1
                            if current_round_idx < len(discussion_state['rounds']):
                                round_data = discussion_state['rounds'][current_round_idx]
                                round_data['summary'] = {
                                    "content": round_summary if isinstance(round_summary, str) else str(round_summary),
                                    "timestamp": datetime.now().isoformat()
                                }
                        except Exception as e:
                            logger.warning(f"保存轮次总结失败: {e}")

                        # 记录轮次总结
                        logger.info(f"📋 第{round_number}轮讨论总结: {round_summary[:200] if isinstance(round_summary, str) else str(round_summary)[:200]}...")

                    elif step_type == "exception_report":
                        exception_report = step_result.get('report', '')
                        logger.info(f"收到异常报告: {exception_report}")

                        # 记录异常报告chunk
                        logger.info(f"异常报告: {exception_report}")

                        # 如果有严重异常，添加警告信息
                        if "需要人工干预" in exception_report:
                            logger.warning("⚠️ 系统检测到需要人工干预的异常，请及时处理以确保讨论质量。")
                        summary = step_result.get('summary', {})
                        round_summary = summary.get('round_summary', '未生成总结') if isinstance(summary, dict) else str(summary)

                        # 更新discussion_state，保存轮次总结
                        try:
                            current_round_idx = round_number - 1
                            if current_round_idx < len(discussion_state['rounds']):
                                round_data = discussion_state['rounds'][current_round_idx]
                                round_data['summary'] = {
                                    "content": round_summary if isinstance(round_summary, str) else str(round_summary),
                                    "timestamp": datetime.now().isoformat()
                                }
                                round_data['updated_at'] = datetime.now().isoformat()
                                discussion_state['updated_at'] = datetime.now().isoformat()
                                self._save_discussion_state(discussion_base_path, discussion_state)
                                logger.info(f"已保存第{round_number}轮总结到discussion_state.json")
                        except Exception as e:
                            logger.error(f"保存轮次总结失败: {e}", exc_info=True)
                        
                        logger.info(f"📋 本轮总结: {round_summary[:200] if isinstance(round_summary, str) else str(round_summary)[:200]}...")

                    elif step_type == "user_decision":
                        consensus_level = step_result.get('consensus_level', 0.0)
                        options = step_result.get('options', [])

                        # 更新本轮状态（保留已有的发言记录）
                        try:
                            current_round_idx = round_number - 1
                            # 确保轮次数据存在
                            while len(discussion_state['rounds']) <= current_round_idx:
                                discussion_state['rounds'].append({
                                    "round_number": len(discussion_state['rounds']) + 1,
                                    "status": "in_progress",
                                    "speeches": [],
                                    "timestamp": datetime.now().isoformat()
                                })
                            
                            # 获取当前轮次数据（保留已有的speeches）
                            round_data = discussion_state['rounds'][current_round_idx]
                            round_data['round_number'] = round_number
                            round_data['status'] = 'completed'
                            round_data['consensus_level'] = consensus_level
                            round_data['completed_at'] = datetime.now().isoformat()
                            round_data['updated_at'] = datetime.now().isoformat()
                            
                            # 如果speeches不存在，初始化为空列表
                            if 'speeches' not in round_data:
                                round_data['speeches'] = []
                            
                            logger.info(f"第{round_number}轮完成，共{len(round_data['speeches'])}条发言记录")
                        except Exception as e:
                            logger.error(f"更新轮次状态失败: {e}", exc_info=True)
                            # 如果出错，创建新的轮次数据
                            round_data = {
                                "round_number": round_number,
                                "status": "completed",
                                "consensus_level": consensus_level,
                                "speeches": [],
                                "timestamp": datetime.now().isoformat()
                            }
                            discussion_state['rounds'].append(round_data)
                        
                        # 更新整体状态 - 一轮完成，状态改为 paused（等待用户决策）
                        discussion_state['current_round'] = round_number
                        discussion_state['consensus_data']['overall_level'] = consensus_level
                        discussion_state['status'] = 'paused'  # 一轮完成，等待用户决策
                        discussion_state['updated_at'] = datetime.now().isoformat()
                        # 确保状态被保存
                        try:
                            self._save_discussion_state(discussion_base_path, discussion_state)
                            logger.info(f"第{round_number}轮完成，状态已更新为 paused")
                        except Exception as save_error:
                            logger.error(f"保存讨论状态失败: {save_error}", exc_info=True)

                        # 记录本轮完成信息
                        logger.info(f"✅ 第 {round_number} 轮讨论完成，共识水平: {consensus_level:.2f}")
                        
                        # 检查是否达到共识阈值
                        if consensus_level >= 0.8:
                            logger.info(f"🎉 达到较高共识水平 ({consensus_level:.2f})，结束讨论")
                            break  # 达到共识，跳出循环
                        else:
                            # 未达到共识，继续下一轮讨论
                            logger.info(f"🔄 共识水平未达标 ({consensus_level:.2f} < 0.8)，继续第 {round_number + 1} 轮讨论")
                            round_number += 1
                            continue  # 继续下一轮

                # 如果本轮没有发言，记录警告
                if not has_speeches:
                    logger.warning(f"⚠️ 第 {round_number} 轮讨论没有产生任何发言，可能存在问题。")
                    # 即使没有发言，也标记为完成并继续下一轮
                    try:
                        current_round_idx = round_number - 1
                        while len(discussion_state['rounds']) <= current_round_idx:
                            discussion_state['rounds'].append({
                                "round_number": len(discussion_state['rounds']) + 1,
                                "status": "completed",
                                "speeches": [],
                                "timestamp": datetime.now().isoformat()
                            })
                        round_data = discussion_state['rounds'][current_round_idx]
                        round_data['round_number'] = round_number
                        round_data['status'] = 'completed'
                        round_data['completed_at'] = datetime.now().isoformat()
                        discussion_state['current_round'] = round_number
                        discussion_state['status'] = 'active'  # 保持活跃状态，继续讨论
                        discussion_state['updated_at'] = datetime.now().isoformat()
                        self._save_discussion_state(discussion_base_path, discussion_state)
                        logger.info(f"第{round_number}轮完成（无发言），继续下一轮")
                    except Exception as e:
                        logger.error(f"更新轮次状态失败: {e}", exc_info=True)
                    
                    logger.info(f"🔄 第 {round_number} 轮讨论完成（无发言），继续第 {round_number + 1} 轮")
                    round_number += 1
                    continue  # 继续下一轮

                # 如果本轮正常完成但没有 user_decision 步骤
                # 检查是否达到共识阈值
                try:
                    status = discussion_system.get_discussion_status()
                    consensus_level = status.get('consensus_level', 0.0) if isinstance(status, dict) else 0.0
                    
                    # 更新当前轮次状态
                    try:
                        current_round_idx = round_number - 1
                        if current_round_idx < len(discussion_state['rounds']):
                            round_data = discussion_state['rounds'][current_round_idx]
                            round_data['status'] = 'completed'
                            round_data['completed_at'] = datetime.now().isoformat()
                            discussion_state['current_round'] = round_number
                            discussion_state['consensus_data']['overall_level'] = consensus_level
                            discussion_state['updated_at'] = datetime.now().isoformat()
                            self._save_discussion_state(discussion_base_path, discussion_state)
                    except Exception as e:
                        logger.error(f"更新轮次状态失败: {e}", exc_info=True)
                    
                    if consensus_level >= 0.8:
                        logger.info(f"🎉 第 {round_number} 轮讨论完成，达到较高共识水平 ({consensus_level:.2f})，结束讨论")
                        break  # 达到共识，跳出循环
                    else:
                        # 未达到共识，继续下一轮讨论
                        logger.info(f"🔄 第 {round_number} 轮讨论完成，共识水平: {consensus_level:.2f}，继续第 {round_number + 1} 轮")
                        round_number += 1
                        continue  # 继续下一轮
                except Exception as e:
                    logger.warning(f"获取讨论状态失败: {str(e)}")
                    # 获取状态失败，继续下一轮
                    try:
                        current_round_idx = round_number - 1
                        if current_round_idx < len(discussion_state['rounds']):
                            round_data = discussion_state['rounds'][current_round_idx]
                            round_data['status'] = 'completed'
                            round_data['completed_at'] = datetime.now().isoformat()
                        discussion_state['current_round'] = round_number
                        discussion_state['status'] = 'active'
                        self._save_discussion_state(discussion_base_path, discussion_state)
                    except Exception as update_error:
                        logger.error(f"更新轮次状态失败: {update_error}", exc_info=True)
                    
                    logger.info(f"🔄 第 {round_number} 轮讨论完成，继续第 {round_number + 1} 轮")
                    round_number += 1
                    continue  # 继续下一轮

            # 如果循环正常结束（达到最大轮次），确保有最终报告与第一层汇总（再次启动时若缺失则补充）
            final_report = None
            if discussion_state.get('status') == 'completed' and discussion_state.get('final_report'):
                # 再次启动：第一层已在之前完成，直接使用状态中的最终报告
                final_report = discussion_state['final_report']
                logger.info("📄 第一层已完成，使用已有最终报告")
            else:
                try:
                    logger.info("📄 正在生成最终讨论报告...")
                    gen_report = discussion_system.generate_final_report()
                    if gen_report:
                        consensus_report = gen_report.get('consensus_report', {})
                        overall_consensus = consensus_report.get('overall_consensus', {}) if isinstance(consensus_report, dict) else {}
                        consensus_level = overall_consensus.get('overall_level', 0.0) if isinstance(overall_consensus, dict) else 0.0
                        logger.info(f"🎭 圆桌讨论最终报告 - 讨论主题: {gen_report.get('discussion_topic', '未指定')}, 总轮次: {gen_report.get('total_rounds', 0)}, 最终共识水平: {consensus_level:.2f}")
                        discussion_state['status'] = 'completed'
                        discussion_state['consensus_data']['overall_level'] = consensus_level
                        final_report = {
                            'total_rounds': gen_report.get('total_rounds', 0),
                            'consensus_level': consensus_level,
                            'key_insights': gen_report.get('key_insights', []),
                            'action_recommendations': gen_report.get('action_recommendations', [])
                        }
                        discussion_state['final_report'] = final_report
                        self._save_discussion_state(discussion_base_path, discussion_state)
                        if session_id and discussion_id:
                            try:
                                cSingleSqlite.update_discussion_task_status(
                                    session_id=session_id,
                                    discussion_id=discussion_id,
                                    task_status='completed'
                                )
                                logger.info(f"更新任务状态为已完成: session_id={session_id}, discussion_id={discussion_id}")
                            except Exception as e:
                                logger.warning(f"更新任务状态失败: {e}")
                    else:
                        logger.warning("⚠️ 无法生成最终报告")
                except Exception as e:
                    logger.error(f"生成最终报告失败: {str(e)}", exc_info=True)
                    logger.warning(f"⚠️ 生成最终报告时出错: {str(e)}")
                if not final_report:
                    final_report = discussion_state.get('final_report', {})

            logger.info("✅ 第一层：圆桌讨论完成！")
            
            # ==================================================
            # 先完成第一层汇总，再进入第二层（确保第一层汇总文档存在；缺失则补充后再跑第二层）
            # 路径解析：优先用 relative_md_file（相对 discussion_base_path），避免 md_file 含 "discussion/xxx" 时与 base 拼接成重复路径
            # ==================================================
            layer1_meta = discussion_state.get('layer1_summary') or {}
            rel_md = layer1_meta.get('relative_md_file')
            abs_or_rel_md = layer1_meta.get('md_file') or rel_md
            if rel_md and not os.path.isabs(rel_md):
                md_path = os.path.join(discussion_base_path, rel_md)
            elif abs_or_rel_md and os.path.isabs(abs_or_rel_md):
                md_path = abs_or_rel_md
            elif abs_or_rel_md and ('discuss' in abs_or_rel_md or abs_or_rel_md.startswith('discuss')):
                # md_file 可能是 "discussion/xxx/discuss/..." 或 "discuss/..."，只取 discuss/ 及以后与 base 拼接
                tail = abs_or_rel_md[abs_or_rel_md.find('discuss'):] if 'discuss' in abs_or_rel_md else abs_or_rel_md
                md_path = os.path.join(discussion_base_path, tail)
            else:
                md_path = os.path.join(discussion_base_path, abs_or_rel_md) if abs_or_rel_md else ''
            need_summary = not md_path or not os.path.isfile(md_path)
            if need_summary:
                try:
                    final_report_for_summary = final_report or discussion_state.get('final_report', {})
                    # 主题优先从 discussion_state.json 的 topic 读取，避免使用当前聊天内容（如「xxx 任务启动」）
                    topic_for_summary = (discussion_state.get('topic') or '').strip() or query
                    summary_path = self._generate_layer1_summary_document(
                        discussion_base_path, discussion_state, final_report_for_summary, topic_for_summary
                    )
                    if summary_path:
                        logger.info(f"📚 第一层汇总文档已生成: {summary_path}")
                        self._save_discussion_state(discussion_base_path, discussion_state)
                    else:
                        logger.warning("⚠️ 第一层汇总文档生成失败")
                except Exception as summary_error:
                    logger.error(f"生成第一层汇总文档异常: {summary_error}")
            else:
                logger.info("第一层汇总文档已存在，跳过生成（再次启动无需重复汇总）")
            
            # ==================================================
            # 第二层: 实施讨论组（重复启动时若已完成则跳过；智能体与发言状态见 discussion_state['layer2']/implementation_layer）
            # ==================================================
            try:
                impl_done = (discussion_state.get("implementation_layer") or {}).get("status") == "completed"
                conc_done = (discussion_state.get("concretization_layer") or {}).get("status") == "completed"

                if impl_done:
                    logger.info("🔄 第二层已在本任务中完成，跳过实施讨论组（可复用 discussion_state['layer2'] 与 roles 下 layer_2_* 智能体）")

                if conc_done:
                    logger.info("🔄 第三层具像化已在本任务中完成，跳过具像化层")

                # 将第一层结果转换为 DecisionOutput
                decision_output = self._convert_to_decision_output(
                    discussion_state,
                    final_report or {},
                    query
                )

                # 只有当有任务且第二层未完成时才运行第二层
                if decision_output.tasks and not impl_done:
                    logger.info(f"\n📦 决策层输出: {len(decision_output.tasks)} 个任务, {len(decision_output.objectives)} 个目标")

                    impl_outputs, impl_result = self._run_implementation_layer(
                        decision_output,
                        discussion_state,
                        discussion_base_path
                    )
                elif decision_output.tasks and impl_done:
                    impl_outputs, impl_result = [], None

                # 第三层：仅在本层未完成时运行（依赖 implement/，第二层跳过时仍可执行）
                # 支持部分恢复：从 discussion_state 中获取已处理的专家列表
                if (decision_output.tasks and not conc_done):
                    # 获取已处理的专家列表（用于任务恢复时跳过）
                    layer3_state = discussion_state.get("concretization_layer") or {}
                    processed_experts_names = [
                        p.get("base_name") for p in layer3_state.get("processed_experts", [])
                        if p.get("base_name") and p.get("status") == "completed"
                    ]
                    
                    conc_result = self._run_concretization_layer(
                        discussion_base_path,
                        discussion_state.get("discussion_id", ""),
                        processed_experts=processed_experts_names,
                    )
                    
                    # 合并已处理的专家列表（已有 + 本次新处理）
                    existing_processed = layer3_state.get("processed_experts", [])
                    new_processed = conc_result.get("processed_experts", [])
                    all_processed = existing_processed + [
                        p for p in new_processed
                        if p.get("status") == "completed" and p.get("base_name") not in processed_experts_names
                    ]
                    
                    discussion_state["concretization_layer"] = {
                        "status": "completed",
                        "timestamp": datetime.now().isoformat(),
                        "processed_experts": all_processed,
                    }
                    if conc_result.get("output_files"):
                        # 合并输出文件列表
                        existing_files = discussion_state.get("concretization_summary_output_files", [])
                        new_files = conc_result["output_files"]
                        all_files = existing_files + [f for f in new_files if f not in existing_files]
                        discussion_state["concretization_summary_output_files"] = all_files
                    self._save_discussion_state(discussion_base_path, discussion_state)
                elif not decision_output.tasks:
                    logger.info("⚠️ 没有可执行任务，跳过实施层与具像化层")
                    
            except Exception as layer_error:
                logger.error(f"❌ 第二层执行失败: {layer_error}", exc_info=True)
                discussion_state['layer_error'] = {
                    'message': str(layer_error),
                    'timestamp': datetime.now().isoformat()
                }
                self._save_discussion_state(discussion_base_path, discussion_state)
            
            logger.info("\n" + "=" * 60)
            logger.info("🎉 三层讨论系统全部完成（讨论层 → 实施层 → 具像化层）！")
            logger.info("=" * 60)
            try:
                self._build_speech_search_index(discussion_base_path)
            except Exception as idx_err:
                logger.warning(f"发言检索索引构建失败: {idx_err}")
            return True

        except Exception as e:
            logger.error(f"Error in chat_with_discussion: {str(e)}")
            import traceback
            error_traceback = traceback.format_exc()
            _id = f"roundtable-error-{int(time.time())}"
            
            # 更新会议状态为错误
            try:
                if 'discussion_state' in locals() and 'discussion_base_path' in locals():
                    discussion_state['status'] = 'error'
                    discussion_state['error'] = {
                        'message': str(e),
                        'traceback': error_traceback,
                        'timestamp': datetime.now().isoformat()
                    }
                    self._save_discussion_state(discussion_base_path, discussion_state)
            except Exception as save_error:
                logger.error(f"保存错误状态失败: {save_error}")
            
            logger.error(f"❌ 圆桌讨论系统错误: {str(e)}")
            return False

   