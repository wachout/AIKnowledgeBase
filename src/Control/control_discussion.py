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
from typing import Dict, Any, List, Optional
from datetime import datetime

from Db.sqlite_db import cSingleSqlite
from Config.llm_config import get_chat_tongyi
from Roles import RoundtableDiscussion

# 导入三层系统组件
from Roles.hierarchy import (
    # 类型定义
    Task, Objective, Constraint, DecisionOutput, ImplementationOutput,
    ExecutionStatus, ImplementationRole,
    # 实施层
    ImplementationLayer,
    # 检验层  
    ValidationLayer
)
from Roles.hierarchy.layers.implementation_layer import ImplementGroupScheduler, ImplementationGroup
from Roles.hierarchy.layers.implementation_roundtable import ImplementationDiscussion
from Roles.hierarchy.layers.concretization_roundtable import ConcretizationDiscussion

logger = logging.getLogger(__name__)


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
        
        try:
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
                # 第二层智能体信息保存到 roles/，以 layer_2_ 前缀区分第一层
                layer2_participants = []
                layer2_agents = []
                for expert in (result.experts_created or []):
                    name = expert.get('name') or expert.get('role') or expert.get('domain') or 'expert'
                    self._save_agent_config(discussion_base_path, f"layer_2_{name}", expert)
                    layer2_participants.append(name)
                    layer2_agents.append({
                        "name": name,
                        "domain": expert.get("domain", ""),
                        "role": expert.get("role", ""),
                    })
                layer2_speeches = []
                # 第二层实施方案保存到 implement/
                impl_dir = os.path.join(discussion_base_path, "implement")
                os.makedirs(impl_dir, exist_ok=True)
                for i, prop in enumerate(result.expert_proposals or []):
                    safe = re.sub(r'[^\w\u4e00-\u9fa5]', '_', (prop.get('expert_name') or f'proposal_{i}')[:50])
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    rel_md = f"implement/impl_expert_{safe}_proposal_{ts}.md"
                    try:
                        with open(os.path.join(impl_dir, f"impl_expert_{safe}_proposal_{ts}.md"), 'w', encoding='utf-8') as f:
                            f.write(prop.get('content', ''))
                        with open(os.path.join(impl_dir, f"impl_expert_{safe}_proposal_{ts}.json"), 'w', encoding='utf-8') as f:
                            json.dump({"expert_name": prop.get("expert_name"), "domain": prop.get("domain"), "structured": prop.get("structured")}, f, ensure_ascii=False, indent=2)
                        layer2_speeches.append({
                            "speaker": prop.get("expert_name") or f"专家_{i}",
                            "relative_file_path": rel_md,
                            "timestamp": ts,
                        })
                    except Exception as ex:
                        logger.warning(f"保存第二层专家发言失败: {ex}")
                discussion_state['layer2'] = {
                    'participants': layer2_participants,
                    'agents': layer2_agents,
                    'speeches': layer2_speeches,
                    'completed_at': datetime.now().isoformat(),
                }
                    
        except Exception as e:
            logger.error(f"❌ 实施讨论失败: {e}", exc_info=True)
            impl_output = ImplementationOutput(
                task_id=task_list[0].get('task_id', '') if task_list else '',
                status=ExecutionStatus.FAILED
            )
            impl_outputs.append(impl_output)
        
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
    ):
        """
        运行第三层具像化层：阅读 implement/ 中的实施步骤，按领域创建具像化智能体，
        执行数字化+具像化（符合第一性原理、物理守恒、材料约束等），结果保存到 concretization/。
        """
        try:
            llm_instance = self._get_llm_instance()
            conc_discussion = ConcretizationDiscussion(llm_adapter=llm_instance)

            async def run_conc():
                outputs = []
                async for chunk in conc_discussion.run_concretization(
                    discussion_base_path=discussion_base_path,
                    discussion_id=discussion_id,
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
        except Exception as e:
            logger.error(f"❌ 第三层具像化层执行失败: {e}", exc_info=True)

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
        生成第一层圆桌讨论的汇总文档（带目录索引）
        
        将所有智能体的发言、质疑者发言、共识数据等汇总为带目录的文档，
        供第二层实施层专家按领域快速查阅，节省 token。
        
        生成两个文件:
        1. Markdown 可读文档（带目录）
        2. JSON 结构化索引（供程序化查询）
        
        Args:
            discussion_base_path: 讨论文件夹路径
            discussion_state: 完整讨论状态
            final_report: 最终报告
            query: 用户原始查询
            
        Returns:
            汇总文档路径，失败返回 None
        """
        try:
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
            
            # ---- Markdown 汇总文档 ----
            md = []
            total_rounds = len(rounds_data)
            total_speeches = sum(len(r.get('speeches', [])) for r in rounds_data)
            participants = discussion_state.get('participants', [])
            consensus_level = discussion_state.get('consensus_data', {}).get('overall_level', 0.0)
            
            md.append(f"""# 圆桌讨论汇总文档

**讨论主题**: {query}
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**总轮次**: {total_rounds} | **总发言**: {total_speeches} | **参与者**: {len(participants)} | **共识**: {consensus_level:.2f}

---

""")
            
            # ---- 目录 (TOC) ----
            md.append("## 目录\n\n")
            toc_idx = 1
            
            md.append(f"{toc_idx}. [专家发言索引（按角色）](#专家发言索引按角色)\n")
            toc_idx += 1
            for speaker_name in all_speeches_by_speaker:
                safe_anchor = re.sub(r'[^\w\u4e00-\u9fa5]', '', speaker_name)
                any_skeptic = any(s['is_skeptic'] for s in all_speeches_by_speaker[speaker_name])
                label = f"{speaker_name}（质疑者）" if any_skeptic else speaker_name
                md.append(f"  - [{label}](#{safe_anchor})\n")
            
            if skeptic_speeches:
                md.append(f"{toc_idx}. [质疑者发言汇总](#质疑者发言汇总)\n")
                toc_idx += 1
            
            md.append(f"{toc_idx}. [各轮次讨论记录](#各轮次讨论记录)\n")
            toc_idx += 1
            for rn in sorted(all_speeches_by_round.keys()):
                md.append(f"  - [第{rn}轮](#第{rn}轮讨论)\n")
            
            md.append(f"{toc_idx}. [共识与分歧](#共识与分歧)\n")
            toc_idx += 1
            md.append(f"{toc_idx}. [最终报告与行动建议](#最终报告与行动建议)\n")
            md.append("\n---\n\n")
            
            # ---- 专家发言索引 ----
            md.append("## 专家发言索引（按角色）\n\n")
            md.append("> 第二层实施专家可根据角色名称快速定位相关领域的讨论内容。\n\n")
            
            for speaker_name, speeches in all_speeches_by_speaker.items():
                any_skeptic = any(s['is_skeptic'] for s in speeches)
                role_label = f"{speaker_name}（质疑者）" if any_skeptic else speaker_name
                md.append(f"### {role_label}\n\n")
                md.append(f"**发言次数**: {len(speeches)}\n\n")
                
                for idx, sp in enumerate(speeches, 1):
                    md.append(f"#### 第{sp['round']}轮 发言#{idx}\n\n")
                    if sp['is_skeptic'] and sp.get('target_expert'):
                        md.append(f"**针对**: {sp['target_expert']}\n\n")
                    if sp.get('thinking'):
                        md.append(f"**思考**: {sp['thinking'][:500]}\n\n")
                    md.append(f"**内容**: {sp.get('speech', '无')}\n\n")
                md.append("---\n\n")
            
            # ---- 质疑者发言汇总 ----
            if skeptic_speeches:
                md.append("## 质疑者发言汇总\n\n")
                for idx, sk in enumerate(skeptic_speeches, 1):
                    md.append(f"### 质疑#{idx} (第{sk['round']}轮)\n\n")
                    md.append(f"**质疑者**: {sk['speaker']}\n")
                    if sk.get('target_expert'):
                        md.append(f"**针对**: {sk['target_expert']}\n")
                    md.append(f"\n{sk.get('speech', '无')}\n\n")
                md.append("---\n\n")
            
            # ---- 各轮次记录 ----
            md.append("## 各轮次讨论记录\n\n")
            for rn in sorted(all_speeches_by_round.keys()):
                sps = all_speeches_by_round[rn]
                md.append(f"### 第{rn}轮讨论\n\n")
                md.append(f"**发言数**: {len(sps)}\n\n")
                for sp in sps:
                    if sp.get('is_skeptic') and sp.get('target_expert'):
                        md.append(f"**{sp['speaker']}** (质疑 -> {sp['target_expert']}):\n\n")
                    else:
                        md.append(f"**{sp['speaker']}**:\n\n")
                    md.append(f"{sp.get('speech', '无')[:800]}\n\n")
                md.append("---\n\n")
            
            # ---- 共识与分歧 ----
            md.append("## 共识与分歧\n\n")
            consensus_data = discussion_state.get('consensus_data', {})
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
            
            # ---- 最终报告 ----
            md.append("## 最终报告与行动建议\n\n")
            if final_report:
                for i, ins in enumerate(final_report.get('key_insights', []), 1):
                    md.append(f"{i}. {ins}\n")
                md.append("\n")
                for i, rec in enumerate(final_report.get('action_recommendations', []), 1):
                    md.append(f"{i}. {rec}\n")
                md.append("\n")
            md.append("---\n*此文档由圆桌讨论系统自动生成，供第二层实施专家按目录索引查阅。*\n")
            
            # ---- 写入 Markdown（第一层汇总保存到 discuss/） ----
            md_filename = f"layer1_discussion_summary_{timestamp}.md"
            md_filepath = os.path.join(discuss_dir, md_filename)
            with open(md_filepath, 'w', encoding='utf-8') as f:
                f.write("".join(md))
            logger.info(f"生成第一层汇总文档: {md_filepath}")
            
            # ---- JSON 结构化索引 ----
            json_index = {
                "document_type": "layer1_discussion_summary",
                "discussion_id": discussion_state.get('discussion_id', ''),
                "topic": query,
                "generated_at": datetime.now().isoformat(),
                "summary_md_file": md_filepath,
                "statistics": {
                    "total_rounds": total_rounds,
                    "total_speeches": total_speeches,
                    "participants_count": len(participants),
                    "consensus_level": consensus_level
                },
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
                    "key_points": key_points,
                    "divergences": divergences
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
            
            # 更新 discussion_state
            discussion_state['layer1_summary'] = {
                'md_file': md_filepath,
                'json_index_file': json_filepath,
                'relative_md_file': os.path.relpath(md_filepath, discussion_base_path),
                'relative_json_file': os.path.relpath(json_filepath, discussion_base_path),
                'timestamp': timestamp,
                'statistics': json_index['statistics'],
                'table_of_contents': json_index['table_of_contents']
            }
            
            return md_filepath
            
        except Exception as e:
            logger.error(f"生成第一层汇总文档失败: {e}", exc_info=True)
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
            self._run_concretization_layer(discussion_base_path, discussion_state.get("discussion_id", ""))
            discussion_state["concretization_layer"] = {"status": "completed", "timestamp": datetime.now().isoformat()}
            self._save_discussion_state(discussion_base_path, discussion_state)
        elif modified_layer == 2:
            discussion_state.pop("concretization_layer", None)
            self._save_discussion_state(discussion_base_path, discussion_state)
            self._run_concretization_layer(discussion_base_path, discussion_state.get("discussion_id", ""))
            discussion_state["concretization_layer"] = {"status": "completed", "timestamp": datetime.now().isoformat()}
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
        保存智能体配置到 roles 目录
        
        Args:
            discussion_base_path: 讨论文件夹路径
            agent_name: 智能体名称
            agent_config: 智能体配置字典（可能含 DomainExpert 等对象，会先转为可序列化）
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
            logger.info(f"保存智能体配置: {json_filepath}")
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
            
            # 创建文件夹结构：discuss/ 第一层讨论发言；implement/ 第二层实施方案；concretization/ 第三层具像化
            os.makedirs(os.path.join(discussion_base_path, "discuss"), exist_ok=True)
            os.makedirs(os.path.join(discussion_base_path, "implement"), exist_ok=True)
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

                # 本轮已发言的智能体（重启时从状态恢复，避免重复发言）
                already_spoken = set()
                rounds_list = discussion_state.get("rounds") or []
                if round_number <= len(rounds_list):
                    round_data = rounds_list[round_number - 1]
                    already_spoken = {s.get("speaker") for s in round_data.get("speeches", []) if s.get("speaker")}
                if already_spoken:
                    logger.info(f"第 {round_number} 轮已发言智能体（将跳过）: {already_spoken}")

                # 执行一轮讨论
                round_complete = False
                has_speeches = False
                
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
                            
                            # 更新discussion_state的updated_at
                            discussion_state['updated_at'] = datetime.now().isoformat()
                            
                            # 保存更新后的状态
                            self._save_discussion_state(discussion_base_path, discussion_state)
                            logger.info(f"已更新discussion_state.json，添加{speaker}的发言到第{round_number}轮")
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

            # 如果循环正常结束（达到最大轮次），生成最终报告
            try:
                logger.info("📄 正在生成最终讨论报告...")

                final_report = discussion_system.generate_final_report()
                
                if final_report:
                    consensus_report = final_report.get('consensus_report', {})
                    overall_consensus = consensus_report.get('overall_consensus', {}) if isinstance(consensus_report, dict) else {}
                    consensus_level = overall_consensus.get('overall_level', 0.0) if isinstance(overall_consensus, dict) else 0.0
                    consensus_analysis = overall_consensus.get('analysis', '未分析') if isinstance(overall_consensus, dict) else '未分析'
                    
                    logger.info(f"🎭 圆桌讨论最终报告 - 讨论主题: {final_report.get('discussion_topic', '未指定')}, 总轮次: {final_report.get('total_rounds', 0)}, 最终共识水平: {consensus_level:.2f}")
                    
                    # 更新会议状态为完成
                    discussion_state['status'] = 'completed'
                    discussion_state['consensus_data']['overall_level'] = consensus_level
                    discussion_state['final_report'] = {
                        'total_rounds': final_report.get('total_rounds', 0),
                        'consensus_level': consensus_level,
                        'key_insights': final_report.get('key_insights', []),
                        'action_recommendations': final_report.get('action_recommendations', [])
                    }
                    self._save_discussion_state(discussion_base_path, discussion_state)
                    
                    # 更新任务状态为已完成
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

            logger.info("✅ 第一层：圆桌讨论完成！")
            
            # ==================================================
            # 生成第一层汇总文档（带目录索引，供第二层使用）
            # ==================================================
            try:
                final_report_for_summary = final_report if 'final_report' in locals() and final_report else {}
                summary_path = self._generate_layer1_summary_document(
                    discussion_base_path, discussion_state, final_report_for_summary, query
                )
                if summary_path:
                    logger.info(f"📚 第一层汇总文档已生成: {summary_path}")
                    self._save_discussion_state(discussion_base_path, discussion_state)
                else:
                    logger.warning("⚠️ 第一层汇总文档生成失败")
            except Exception as summary_error:
                logger.error(f"生成第一层汇总文档异常: {summary_error}")
            
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
                    final_report if 'final_report' in locals() and final_report else {},
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
                if (decision_output.tasks and not conc_done):
                    self._run_concretization_layer(
                        discussion_base_path,
                        discussion_state.get("discussion_id", ""),
                    )
                    discussion_state["concretization_layer"] = {
                        "status": "completed",
                        "timestamp": datetime.now().isoformat(),
                    }
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

   