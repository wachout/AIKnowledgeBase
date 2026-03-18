"""
圆桌讨论系统主类模块

包含 RoundtableDiscussion 主类，负责协调整个圆桌讨论流程。
"""

import json
import logging
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Any, List, Optional, Generator, TYPE_CHECKING

# 导入本包内模块
from .communication import MessageBus, CommunicationProtocol
from .state_management import StateManager
from .exception_context import AgentExceptionContext
from .discussion_round import DiscussionRound

# 导入项目内其他模块
from ..tools.topic_profiler import TopicProfiler, TaskAnalysis
from ..tools.consensus_tracker import ConsensusTracker
from ..tools.tool_manager import ToolManager
from ..tools.knowledge_search_tool import KnowledgeSearchTool
from ..tools.web_search_tool import WebSearchTool, WikipediaSearchTool, AcademicPaperSearchTool
from ..tools.data_analysis_tool import DataAnalysisTool
from ..tools.communication_tool import CommunicationTool

# 导入技能系统
from ..tools.skill_registry import SkillRegistry, AgentSkillSet

# 导入工具流水线
from ..tools.tool_pipeline import ToolPipeline, ToolPipelineStep, PipelineExecutor, FailurePolicy

# 导入结果评估器
from ..tools.tool_evaluator import SearchResultEvaluator

# 导入智能体
from ..personnel.base_agent import BaseAgent
from ..personnel.scholar import Scholar
from ..personnel.ideation_agent import IdeationAgent
# AgentScope 桥接（可选）：统一三层智能体消息与执行，需安装 agentscope 并设置 USE_AGENTSCOPE=1
try:
    from .agentscope_bridge import (
        is_agentscope_available,
        get_agentscope_enabled,
        create_roundtable_agents_agentscope,
        run_agent_reply_sync,
    )
except ImportError:
    is_agentscope_available = lambda: False
    get_agentscope_enabled = lambda: False
    create_roundtable_agents_agentscope = lambda agents_dict, use_memory=True: {}
    run_agent_reply_sync = lambda a, t, c, p: ({}, {})
from ..personnel.moderator import Moderator
from ..personnel.facilitator import Facilitator
from ..personnel.domain_expert import DomainExpert
from ..personnel.skeptic import Skeptic
from ..personnel.data_analyst import DataAnalyst
from ..personnel.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class RoundtableDiscussion:
    """
    圆桌讨论头脑风暴会议系统
    主要功能：
    - 多智能体协作讨论
    - 深度思考分析框架
    - 共识追踪和分歧管理
    - 交互式用户控制
    """

    def __init__(self, llm_instance=None, discussion_id: str = None, storage_path: str = "./discussion"):
        self.llm_instance = llm_instance

        # 初始化工具管理器
        self.tool_manager = ToolManager()
        self._initialize_tools()

        # 初始化系统组件
        self.topic_profiler = TopicProfiler(llm_instance)
        self.consensus_tracker = ConsensusTracker()

        # 初始化通信系统
        self.message_bus = MessageBus()
        self.communication_protocol = CommunicationProtocol(self.message_bus)

        # 智能体实例
        self.agents: Dict[str, BaseAgent] = {}
        self.discussion_rounds: List[DiscussionRound] = []
        self.current_round: Optional[DiscussionRound] = None

        # 讨论状态
        self.discussion_topic = ""
        self.discussion_status = "idle"  # idle, analyzing, active, paused, completed
        self.participants = []
        self.discussion_history = []

        # 自主构思产出的论文（供第一层质疑者阅读 discussion/discussion_id/files 并引用）
        self._ideation_papers: List[Dict[str, Any]] = []
        self._papers_downloaded_to: str = ""

        # 异常上下文记录器
        self.exception_context = AgentExceptionContext()
        print("RoundtableDiscussion initialized")
        print("Discussion ID: ", discussion_id)
        # 使用调用方传入的 discussion_id，重启指定任务时沿用原任务ID与文件夹，不生成新ID
        self.discussion_id = (discussion_id and str(discussion_id).strip()) or f"discussion_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.state_manager = StateManager(self.discussion_id, storage_path)

        # 状态同步设置 - 将状态管理器与所有组件关联
        self._setup_state_synchronization()

        # 注册状态变更监听器，确保所有状态变更都能被捕获和同步
        self._register_state_listeners()

        # 尝试加载现有状态
        self._load_existing_state()

        # 设置自动检查点机制
        self._setup_auto_checkpoint()

        # 初始化恢复标志
        self.is_resuming = False
        self.resume_point = None

    def _initialize_tools(self):
        """初始化工具和技能系统"""
        # 注册基础工具
        self.tool_manager.register_tool(KnowledgeSearchTool())
        self.tool_manager.register_tool(WebSearchTool())
        self.tool_manager.register_tool(WikipediaSearchTool())
        self.tool_manager.register_tool(DataAnalysisTool())
        self.tool_manager.register_tool(CommunicationTool())
        # 学术论文检索（Semantic Scholar + arXiv），供自主构思智能体使用
        self.tool_manager.register_tool(AcademicPaperSearchTool())
        
        # 初始化技能注册中心（单例模式，内置技能已自动注册）
        self.skill_registry = SkillRegistry()
        
        # 初始化结果评估器
        self.result_evaluator = SearchResultEvaluator()
        
        # 初始化流水线执行器
        self.pipeline_executor = PipelineExecutor(self.tool_manager)
        
        # 创建默认研究流水线
        self._create_default_pipelines()
        
        logger.info("工具和技能系统初始化完成")
    
    def _create_default_pipelines(self):
        """创建默认的工具流水线"""
        # 研究流水线：先搜索知识库，然后补充Web搜索
        research_pipeline = ToolPipeline(
            name="research_pipeline",
            description="综合研究流水线：知识库+Web搜索"
        )
        research_pipeline.add_step(ToolPipelineStep(
            step_id="kb_search",
            tool_name="knowledge_search",
            parameters={"query": "{input.query}", "top_k": 5},
            on_failure=FailurePolicy.SKIP
        ))
        research_pipeline.add_step(ToolPipelineStep(
            step_id="web_search",
            tool_name="web_search",
            parameters={"query": "{input.query}", "max_results": 5},
            condition="len(steps.kb_search.data.results if steps.kb_search.success else []) < 3",
            on_failure=FailurePolicy.SKIP
        ))
        self.tool_manager.register_pipeline(research_pipeline)
        
        # 数据分析流水线
        analysis_pipeline = ToolPipeline(
            name="analysis_pipeline",
            description="数据分析流水线"
        )
        analysis_pipeline.add_step(ToolPipelineStep(
            step_id="data_analysis",
            tool_name="data_analysis",
            parameters={"data": "{input.data}", "analysis_type": "{input.analysis_type}"},
            on_failure=FailurePolicy.ABORT
        ))
        self.tool_manager.register_pipeline(analysis_pipeline)
    
    def _setup_agent_tools_and_skills(self, agent: 'BaseAgent', role_type: str = "generic"):
        """
        为智能体设置工具和技能
        
        Args:
            agent: 智能体实例
            role_type: 角色类型，用于确定应该启用哪些技能
        """
        # 设置工具管理器
        if hasattr(agent, 'set_tool_manager'):
            agent.set_tool_manager(self.tool_manager)
        
        # 设置技能注册中心
        if hasattr(agent, 'set_skill_registry'):
            agent.set_skill_registry(self.skill_registry)
        
        # 根据角色类型创建并设置技能集
        skill_set = self._create_skill_set_for_role(agent.name, role_type)
        if hasattr(agent, 'set_skill_set'):
            agent.set_skill_set(skill_set)
        
        logger.debug(f"已为 {agent.name} 设置工具和技能")
    
    def _create_skill_set_for_role(self, agent_name: str, role_type: str) -> AgentSkillSet:
        """
        根据角色类型创建技能集
        
        Args:
            agent_name: 智能体名称
            role_type: 角色类型
            
        Returns:
            AgentSkillSet 实例
        """
        skill_set = AgentSkillSet(agent_name=agent_name)
        
        # 根据角色类型启用不同的技能
        if role_type == "ideation":
            # 自主构思：检索论文、文献理解
            skill_set.add_skill("knowledge_query")
            skill_set.add_skill("web_research")
            skill_set.add_skill("fact_check")
            skill_set.add_skill("collaborative_communication")
        elif role_type in ["scholar", "expert", "domain_expert"]:
            # 学者和专家启用研究类技能
            skill_set.add_skill("knowledge_query")
            skill_set.add_skill("web_research")
            skill_set.add_skill("fact_check")
            skill_set.add_skill("collaborative_communication")
        
        elif role_type in ["data_analyst", "analyst"]:
            # 数据分析师启用数据类技能
            skill_set.add_skill("knowledge_query")
            skill_set.add_skill("data_insight")
            skill_set.add_skill("collaborative_communication")
        
        elif role_type in ["skeptic", "risk_manager"]:
            # 质疑者和风险管理者启用核查类技能
            skill_set.add_skill("knowledge_query")
            skill_set.add_skill("fact_check")
            skill_set.add_skill("web_research")
            skill_set.add_skill("collaborative_communication")
        
        elif role_type in ["moderator", "facilitator", "synthesizer"]:
            # 协调类角色启用沟通技能
            skill_set.add_skill("collaborative_communication")
            skill_set.add_skill("knowledge_query")
        
        else:
            # 默认启用基础技能
            skill_set.add_skill("knowledge_query")
            skill_set.add_skill("collaborative_communication")
        
        return skill_set

    def _setup_state_synchronization(self):
        """设置状态同步"""
        # 添加状态变更监听器，保持各组件状态同步
        self.state_manager.add_change_listener(self._on_state_changed)

        # 为ConsensusTracker添加状态同步 - 包装所有状态变更方法
        self._wrap_consensus_tracker_methods()

    def _wrap_consensus_tracker_methods(self):
        """
        包装 ConsensusTracker 的所有状态变更方法，实现自动同步到 StateManager
        """
        tracker = self.consensus_tracker
        state_mgr = self.state_manager
        
        # 保存原始方法引用
        original_add_consensus = tracker.add_consensus_point
        original_add_divergence = tracker.add_divergence_point
        original_update_support = tracker.update_consensus_support
        original_set_round = tracker.set_current_round
        original_execute_resolution = tracker.execute_resolution
        
        def _get_tracker_state():
            """获取 ConsensusTracker 的完整状态"""
            return {
                "consensus_points": [cp.to_dict() for cp in tracker.consensus_points],
                "divergence_points": [dp.to_dict() for dp in tracker.divergence_points],
                "current_round": tracker.current_round,
                "discussion_summary": tracker.discussion_summary,
                "consensus_history": tracker.consensus_history
            }
        
        # 包装 add_consensus_point
        def synced_add_consensus(content, supporters, evidence=None, 
                                consensus_type=None, priority=None, topic_keywords=None):
            # 调用原始方法
            kwargs = {"content": content, "supporters": supporters}
            if evidence is not None:
                kwargs["evidence"] = evidence
            if consensus_type is not None:
                kwargs["consensus_type"] = consensus_type
            if priority is not None:
                kwargs["priority"] = priority
            if topic_keywords is not None:
                kwargs["topic_keywords"] = topic_keywords
            
            consensus_id = original_add_consensus(**kwargs)
            
            # 同步状态
            state_mgr.update_consensus_state(
                **_get_tracker_state(),
                last_action={"type": "add_consensus", "id": consensus_id, "content": content}
            )
            return consensus_id
        
        # 包装 add_divergence_point
        def synced_add_divergence(content, proponents, consensus_type=None):
            kwargs = {"content": content, "proponents": proponents}
            if consensus_type is not None:
                kwargs["consensus_type"] = consensus_type
            
            divergence_id = original_add_divergence(**kwargs)
            
            # 同步状态
            state_mgr.update_consensus_state(
                **_get_tracker_state(),
                last_action={"type": "add_divergence", "id": divergence_id, "content": content}
            )
            return divergence_id
        
        # 包装 update_consensus_support
        def synced_update_support(consensus_id, supporter, action="add"):
            result = original_update_support(consensus_id, supporter, action)
            
            # 同步状态
            state_mgr.update_consensus_state(
                **_get_tracker_state(),
                last_action={"type": "update_support", "consensus_id": consensus_id, 
                            "supporter": supporter, "action": action}
            )
            return result
        
        # 包装 set_current_round
        def synced_set_round(round_number):
            original_set_round(round_number)
            
            # 同步状态
            state_mgr.update_consensus_state(
                **_get_tracker_state(),
                last_action={"type": "set_round", "round_number": round_number}
            )
        
        # 包装 execute_resolution
        def synced_execute_resolution(resolution_id, success, result):
            exec_result = original_execute_resolution(resolution_id, success, result)
            
            # 同步状态
            state_mgr.update_consensus_state(
                **_get_tracker_state(),
                conflict_resolutions=[{
                    "divergence_id": cr.divergence_id,
                    "strategy": cr.strategy.value if hasattr(cr.strategy, 'value') else str(cr.strategy),
                    "executed": cr.executed,
                    "result": cr.execution_result
                } for cr in tracker.conflict_resolutions],
                last_action={"type": "execute_resolution", "resolution_id": resolution_id, 
                            "success": success}
            )
            return exec_result
        
        # 替换方法
        tracker.add_consensus_point = synced_add_consensus
        tracker.add_divergence_point = synced_add_divergence
        tracker.update_consensus_support = synced_update_support
        tracker.set_current_round = synced_set_round
        tracker.execute_resolution = synced_execute_resolution
        
        # 保存原始方法引用，以便需要时可以访问
        tracker._original_methods = {
            "add_consensus_point": original_add_consensus,
            "add_divergence_point": original_add_divergence,
            "update_consensus_support": original_update_support,
            "set_current_round": original_set_round,
            "execute_resolution": original_execute_resolution
        }

    def _load_existing_state(self):
        """
        加载现有状态并完整恢复讨论上下文
        """
        if self.state_manager.load_state():
            logger.info(f"✅ 加载讨论状态成功: {self.discussion_id}")
            
            # 设置恢复标志
            self.is_resuming = True
            
            try:
                # 1. 恢复基本讨论状态
                self._restore_discussion_state()
                
                # 2. 重建 DiscussionRound 对象
                self._rebuild_discussion_rounds()
                
                # 3. 恢复 ConsensusTracker 状态
                self._restore_consensus_state()
                
                # 4. 恢复异常上下文状态
                self._restore_exception_state()
                
                # 5. 确定恢复点
                self.resume_point = self._determine_resume_point()
                
                logger.info(f"🔄 状态恢复完成: 轮次={len(self.discussion_rounds)}, "
                           f"状态={self.discussion_status}, 恢复点={self.resume_point}")
            
            except Exception as e:
                logger.error(f"❌ 状态恢复失败: {e}")
                # 恢复失败时重置为新状态
                self.is_resuming = False
                self.resume_point = None
            
            finally:
                # 恢复完成后清除标志
                self.is_resuming = False
        
        else:
            logger.info(f"📝 创建新的讨论状态: {self.discussion_id}")
            self.is_resuming = False
            self.resume_point = None

    def _restore_discussion_state(self):
        """恢复基本讨论状态"""
        discussion_state = self.state_manager.states.get("discussion", {})
        
        if discussion_state:
            self.discussion_topic = discussion_state.get("topic", "")
            self.discussion_status = discussion_state.get("status", "idle")
            self.participants = discussion_state.get("participants", [])
            self.discussion_history = discussion_state.get("history", [])
            
            logger.debug(f"恢复讨论状态: topic={self.discussion_topic}, status={self.discussion_status}")

    def _rebuild_discussion_rounds(self):
        """
        从持久化状态重建 DiscussionRound 对象
        """
        round_states = self.state_manager.states.get("rounds", {})
        
        # 收集所有轮次数据
        rounds_data = []
        for round_key, round_state in round_states.items():
            if round_key.startswith("round_") and isinstance(round_state, dict):
                rounds_data.append(round_state)
        
        # 按轮次号排序
        rounds_data.sort(key=lambda x: x.get("round_number", 0))
        
        # 重建轮次对象
        self.discussion_rounds.clear() if hasattr(self.discussion_rounds, 'clear') else None
        for round_data in rounds_data:
            round_obj = DiscussionRound.from_dict(round_data)
            # 直接添加到列表，避免触发同步
            list.append(self.discussion_rounds, round_obj)
        
        # 设置当前轮次
        if self.discussion_rounds:
            self.current_round = self.discussion_rounds[-1]
        
        logger.info(f"重建轮次对象: {len(self.discussion_rounds)} 个")

    def _restore_consensus_state(self):
        """
        恢复 ConsensusTracker 状态
        """
        consensus_state = self.state_manager.states.get("consensus", {})
        
        if not consensus_state:
            return
        
        # 构建 ConsensusTracker 可导入的数据格式
        import_data = {
            "consensus_points": consensus_state.get("consensus_points", []),
            "divergence_points": consensus_state.get("divergence_points", []),
            "discussion_summary": consensus_state.get("discussion_summary", {})
        }
        
        try:
            # 使用 ConsensusTracker 的 import_data 方法
            json_data = json.dumps(import_data, ensure_ascii=False)
            
            # 使用原始方法避免触发同步
            if hasattr(self.consensus_tracker, '_original_methods'):
                # 直接调用 import_data
                self.consensus_tracker.import_data(json_data)
            else:
                self.consensus_tracker.import_data(json_data)
            
            # 恢复当前轮次
            current_round = consensus_state.get("current_round", 0)
            if current_round > 0:
                self.consensus_tracker.current_round = current_round
            
            logger.info(f"恢复共识状态: {len(self.consensus_tracker.consensus_points)} 个共识点, "
                        f"{len(self.consensus_tracker.divergence_points)} 个分歧点")
        
        except Exception as e:
            logger.warning(f"恢复共识状态失败: {e}")

    def _restore_exception_state(self):
        """恢复异常上下文状态"""
        exception_state = self.state_manager.states.get("exceptions", {})
        
        if exception_state:
            # 恢复异常历史
            self.exception_context.exception_history = exception_state.get("exception_history", [])
            self.exception_context.agent_health_records = exception_state.get("agent_health_records", {})
            self.exception_context.failed_speeches = exception_state.get("failed_speeches", {})
            
            logger.debug(f"恢复异常状态: {len(self.exception_context.exception_history)} 条记录")

    def _determine_resume_point(self) -> Dict[str, Any]:
        """
        确定恢复点，返回可以继续讨论的位置
        
        Returns:
            恢复点信息字典
        """
        resume_point = {
            "can_resume": False,
            "resume_type": None,
            "round_number": 0,
            "last_speaker": None,
            "pending_actions": []
        }
        
        # 检查讨论状态
        if self.discussion_status not in ["active", "paused"]:
            resume_point["resume_type"] = "new_discussion"
            return resume_point
        
        resume_point["can_resume"] = True
        
        # 检查最后一轮的状态
        if self.discussion_rounds:
            last_round = self.discussion_rounds[-1]
            resume_point["round_number"] = last_round.round_number
            
            # 检查轮次是否完成
            round_status = last_round.get_status()
            
            if round_status == "completed":
                resume_point["resume_type"] = "new_round"
                resume_point["round_number"] = last_round.round_number + 1
            elif round_status == "in_progress":
                resume_point["resume_type"] = "continue_round"
                # 找出最后一个发言者
                if last_round.speeches:
                    resume_point["last_speaker"] = last_round.speeches[-1].get("speaker")
            else:
                resume_point["resume_type"] = "start_round"
        else:
            resume_point["resume_type"] = "first_round"
            resume_point["round_number"] = 1
        
        # 检查是否有待重试的失败发言
        retry_candidates = self.exception_context.get_retry_candidates(self.discussion_id)
        if retry_candidates:
            resume_point["pending_actions"].append({
                "type": "retry_failed_speeches",
                "count": len(retry_candidates)
            })
        
        return resume_point

    def can_resume_discussion(self) -> bool:
        """检查是否可以恢复讨论"""
        return self.resume_point is not None and self.resume_point.get("can_resume", False)

    def get_resume_info(self) -> Dict[str, Any]:
        """
        获取恢复信息
        
        Returns:
            恢复信息字典
        """
        return {
            "discussion_id": self.discussion_id,
            "can_resume": self.can_resume_discussion(),
            "resume_point": self.resume_point,
            "discussion_status": self.discussion_status,
            "total_rounds": len(self.discussion_rounds),
            "consensus_points": len(self.consensus_tracker.consensus_points),
            "divergence_points": len(self.consensus_tracker.divergence_points)
        }

    def _on_state_changed(self, state_type: str, changes: Dict[str, Any]):
        """状态变更回调"""
        logger.debug(f"状态变更: {state_type} -> {list(changes.keys())}")

        # 根据状态类型执行相应的同步操作
        if state_type == "discussion":
            self._sync_discussion_state(changes)
        elif state_type == "rounds":
            self._sync_round_state(changes)
        elif state_type == "agents":
            self._sync_agent_state(changes)
        elif state_type == "consensus":
            self._sync_consensus_state(changes)

    def _sync_discussion_state(self, changes: Dict[str, Any]):
        """同步讨论状态"""
        for key, value in changes.items():
            if key == "topic":
                self.discussion_topic = value
            elif key == "status":
                self.discussion_status = value
            elif key == "participants":
                self.participants = value

    def _sync_round_state(self, changes: Dict[str, Any]):
        """
        同步轮次状态到内存对象
        
        Args:
            changes: 状态变更字典
        """
        for round_key, round_data in changes.items():
            if not isinstance(round_data, dict):
                continue
            
            # 跳过元数据字段
            if round_key in ["rounds_count", "last_action"]:
                continue
            
            # 解析轮次号
            if round_key.startswith("round_"):
                try:
                    round_number = int(round_key.split("_")[1])
                except (IndexError, ValueError):
                    continue
                
                # 查找现有的轮次对象
                existing_round = self._find_round_by_number(round_number)
                
                if existing_round:
                    # 更新现有轮次
                    existing_round.update_from_dict(round_data)
                    logger.debug(f"同步更新轮次 {round_number}")
                else:
                    # 创建新轮次（仅在恢复状态时）
                    if self.is_resuming:
                        new_round = DiscussionRound.from_dict(round_data)
                        # 直接添加到列表，避免触发同步
                        list.append(self.discussion_rounds, new_round)
                        logger.info(f"恢复轮次 {round_number}")

    def _find_round_by_number(self, round_number: int) -> Optional[DiscussionRound]:
        """
        根据轮次号查找轮次对象
        
        Args:
            round_number: 轮次号
            
        Returns:
            DiscussionRound 对象或 None
        """
        for round_obj in self.discussion_rounds:
            if round_obj.round_number == round_number:
                return round_obj
        return None

    def _sync_agent_state(self, changes: Dict[str, Any]):
        """
        同步智能体状态
        
        Args:
            changes: 状态变更字典
        """
        # 同步智能体列表
        if "agent_list" in changes:
            # 检查是否有新的智能体需要初始化
            current_agents = set(self.agents.keys())
            state_agents = set(changes.get("agent_list", []))
            
            # 记录差异
            new_agents = state_agents - current_agents
            removed_agents = current_agents - state_agents
            
            if new_agents:
                logger.info(f"检测到新智能体: {new_agents}")
            if removed_agents:
                logger.info(f"检测到移除的智能体: {removed_agents}")
        
        # 同步智能体健康状态
        for agent_name, agent_state in changes.items():
            if agent_name in ["agent_list", "last_action"]:
                continue
            
            if isinstance(agent_state, dict) and agent_name in self.agents:
                agent = self.agents[agent_name]
                # 同步健康状态
                if hasattr(agent, 'health_status'):
                    agent.health_status = agent_state.get("health_status", "healthy")

    def _sync_consensus_state(self, changes: Dict[str, Any]):
        """
        同步共识状态
        
        注: 大部分同步已通过包装方法处理，这里主要处理恢复场景
        """
        if not self.is_resuming:
            return
        
        # 恢复时同步共识状态
        if "consensus_points" in changes:
            logger.debug(f"同步共识点: {len(changes['consensus_points'])} 个")
        
        if "divergence_points" in changes:
            logger.debug(f"同步分歧点: {len(changes['divergence_points'])} 个")

    def _register_state_listeners(self):
        """注册状态变更监听器"""
        # 监听轮次状态变更 - 通过包装add_round方法
        original_discussion_rounds = self.discussion_rounds

        class SyncedList(list):
            def __init__(self, parent, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.parent = parent

            def append(self, round_obj):
                super().append(round_obj)
                self.parent.state_manager.update_rounds_state(
                    rounds=[r.to_dict() for r in self],
                    last_round_action={"type": "add_round", "round_number": round_obj.round_number}
                )
                # 触发自动检查点
                self.parent._maybe_create_checkpoint()

        self.discussion_rounds = SyncedList(self, original_discussion_rounds)

        # 监听智能体状态变更 - 通过包装update方法
        original_agents = self.agents

        class SyncedDict(dict):
            def __init__(self, parent, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.parent = parent

            def update(self, *args, **kwargs):
                super().update(*args, **kwargs)
                self.parent.state_manager.update_agents_state(
                    agents=list(self.keys()),
                    last_agent_action={"type": "update_agents", "agent_count": len(self)}
                )
                # 触发自动检查点
                self.parent._maybe_create_checkpoint()

        self.agents = SyncedDict(self, original_agents)

    def _setup_auto_checkpoint(self):
        """
        设置自动检查点机制
        配置检查点策略参数
        """
        # 配置检查点策略
        strategy = self.state_manager.checkpoint_strategy
        
        # 可以根据业务需求调整策略参数
        strategy.min_interval_seconds = 30      # 最小间隔 30 秒
        strategy.max_interval_seconds = 180     # 最大间隔 3 分钟
        strategy.max_changes_before_checkpoint = 5  # 5 次变更后检查点
        
        logger.debug("自动检查点机制已配置")

    def _maybe_create_checkpoint(self, event_type: str = None):
        """
        可能创建检查点 - 使用智能检查点策略
        
        Args:
            event_type: 事件类型 (round_complete, consensus_change, error, agent_join)
        """
        try:
            # 记录状态变更
            self.state_manager.checkpoint_strategy.record_change()
            
            # 使用智能检查点策略
            checkpoint_name = self.state_manager.smart_checkpoint(event_type)
            
            if checkpoint_name:
                logger.debug(f"创建智能检查点: {checkpoint_name}")
        except Exception as e:
            logger.warning(f"创建自动检查点失败: {e}")

    def force_checkpoint(self, checkpoint_name: str = None) -> str:
        """
        强制创建检查点，不受策略限制
        
        Args:
            checkpoint_name: 检查点名称
            
        Returns:
            检查点名称
        """
        return self.state_manager.create_checkpoint(checkpoint_name, "forced")

    def start_discussion(self, user_task: str, is_resuming: bool = False):
        """
        开始圆桌讨论（逐步返回消息）

        Args:
            user_task: 用户任务描述
            is_resuming: 是否重启任务；为 True 时从 roles 加载智能体，跳过 scholar/创建，已发言的由 discussion_state 控制跳过
        """
        try:
            self.discussion_status = "analyzing"
            self.discussion_topic = user_task

            # 重启任务：从 roles 加载智能体，跳过 scholar 与创建流程
            if is_resuming:
                roles_dir = os.path.join(str(self.state_manager.storage_path), "roles")
                if os.path.isdir(roles_dir):
                    loaded = self._load_agents_from_roles(roles_dir)
                    if loaded:
                        logger.info(f"从 roles 加载 {len(loaded)} 个智能体完成，跳过 scholar 与创建")
                        self.discussion_status = "active"
                        yield {"step": "init_start", "message": "🔄 恢复已有任务，从 roles 加载智能体...", "progress": "恢复中"}
                        yield {"step": "agent_creation_complete", "message": f"✅ 已加载 {len(loaded)} 个智能体", "participants": list(loaded.keys()), "progress": "加载完成"}
                        yield {"step": "discussion_ready", "message": "🎯 圆桌讨论已恢复，可继续讨论", "status": "success", "participants": list(loaded.keys()), "progress": "准备就绪"}
                        return

            # 步骤1: 自主构思智能体（检索论文至 discussion/discussion_id/files，产生产生想法与论文依据，协助学者）
            yield {
                "step": "init_start",
                "message": "🎭 正在初始化圆桌讨论系统...",
                "progress": "开始"
            }

            ideation_events = []
            def _ideation_progress(step_name: str, message: str, data: dict):
                ideation_events.append({"step": step_name, "message": message, "data": data or {}})
            ideation_result = {}
            try:
                ideation_agent = IdeationAgent(llm_instance=self.llm_instance)
                self.agents["ideation"] = ideation_agent
                if hasattr(ideation_agent, 'set_communication_system'):
                    ideation_agent.set_communication_system(self.message_bus, self.communication_protocol)
                self._setup_agent_tools_and_skills(ideation_agent, "ideation")
                # 论文 PDF 保存到 discussion/discussion_id/files（与 state_manager 一致）
                papers_save_path = str(self.state_manager.storage_path / "files")
                ideation_result = ideation_agent.run_ideation(
                    user_task,
                    task_id=self.discussion_id,
                    yield_progress=_ideation_progress,
                    save_path=papers_save_path,
                )
                for ev in ideation_events:
                    yield {
                        "step": "ideation_agent",
                        "ideation_step": ev["step"],
                        "message": ev["message"],
                        "progress": ev["message"],
                        **(ev.get("data") or {}),
                    }
                yield {
                    "step": "ideation_agent_complete",
                    "message": "✅ 自主构思完成：已检索论文并生成有文献支撑的想法，供学者进行任务分析与角色确定",
                    "ideation_result": ideation_result,
                    "progress": "自主构思完成"
                }
            except Exception as e:
                logger.warning(f"自主构思智能体执行异常: {e}", exc_info=True)
                yield {
                    "step": "ideation_agent_skip",
                    "message": "⚠️ 自主构思跳过，学者将仅基于任务描述进行分析",
                    "progress": "自主构思跳过"
                }

            # 步骤2: 学者智能体（任务分析与角色确定），使用自主构思的想法与论文依据
            yield {
                "step": "scholar_analysis",
                "message": "📚 学者智能体正在分析您的任务（含自主构思的想法与论文依据）...",
                "progress": "任务分析中"
            }

            scholar = Scholar(llm_instance=self.llm_instance)
            self.agents["scholar"] = scholar
            if hasattr(scholar, 'set_communication_system'):
                scholar.set_communication_system(self.message_bus, self.communication_protocol)
            self._setup_agent_tools_and_skills(scholar, "scholar")

            task_analysis = scholar.analyze_task(user_task, context={"ideation": ideation_result})
            print(f"📚 学者分析完成: {task_analysis}")

            # 将学者分析结果转换为 TaskAnalysis 对象
            task_analysis_obj = self._convert_scholar_result_to_task_analysis(task_analysis, user_task)
            # 将自主构思结果写入任务分析，供后续话题画像与讨论使用
            if ideation_result.get("ideas"):
                setattr(task_analysis_obj, "ideation_ideas", [
                    {"content": idea.get("content", ""), "supporting_paper_ids": idea.get("supporting_paper_ids", [])}
                    for idea in ideation_result["ideas"]
                ])
            if ideation_result.get("supporting_papers"):
                setattr(task_analysis_obj, "ideation_papers", ideation_result["supporting_papers"])
                self._ideation_papers = ideation_result["supporting_papers"]
            if ideation_result.get("downloaded_to"):
                setattr(task_analysis_obj, "papers_downloaded_to", ideation_result["downloaded_to"])
                self._papers_downloaded_to = ideation_result["downloaded_to"]

            # 返回学者分析结果
            yield {
                "step": "scholar_result",
                "message": f"📊 学者分析完成",
                "task_analysis": task_analysis_obj.to_dict(),
                "progress": "学者分析完成"
            }

            # 步骤2: 创建话题画像（流式）
            topic_name = f"讨论_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            for profile_step in self.topic_profiler.create_topic_profile(topic_name, task_analysis_obj):
                if profile_step["step"] == "profile_analysis_start":
                    yield {
                        "step": "topic_profiling",
                        "message": "\n🎯 正在分析话题特征...",
                        "progress": "画像分析中"
                    }

                elif profile_step["step"] == "llm_analysis":
                    yield {
                        "step": "topic_profiling_llm",
                        "message": "\n🧠 正在生成画像策略...",
                        "progress": "AI分析中"
                    }

                elif profile_step["step"] == "profile_parsing":
                    yield {
                        "step": "topic_profiling_parsing",
                        "message": "\n📋 正在整理画像结果...",
                        "progress": "结果整理中"
                    }

                elif profile_step["step"] == "profile_complete":
                    yield {
                        "step": "topic_profile_complete",
                        "message": "\n✅ 话题画像创建完成",
                        "topic_profile": profile_step["topic_profile"],
                        "progress": "画像创建完成"
                    }

                elif profile_step["step"] == "profile_error_fallback":
                    yield {
                        "step": "topic_profiling_fallback",
                        "message": "⚠️ 使用智能默认配置...",
                        "progress": "使用默认配置"
                    }

            # 获取创建的话题画像
            topic_profile = self.topic_profiler.get_topic_profile(topic_name)
            if topic_profile is None:
                logger.warning(f"话题画像获取失败，使用默认配置继续")
                # 如果画像创建失败，使用默认配置继续
                topic_profile = self.topic_profiler._create_default_topic_profile(topic_name, task_analysis_obj)
                self.topic_profiler.analyzed_topics[topic_name] = topic_profile

            # 步骤3: 自动创建角色智能体
            yield {
                "step": "agent_creation_start",
                "message": "🤖 正在创建智能体角色...",
                "progress": "智能体创建中"
            }

            try:
                # 逐步创建和报告每个智能体
                for agent_info in self._create_role_agents_stream(task_analysis_obj):
                    yield agent_info
            except Exception as e:
                logger.error(f"创建智能体时出错: {str(e)}", exc_info=True)
                yield {
                    "step": "agent_creation_error",
                    "message": f"⚠️ 创建智能体时遇到问题: {str(e)}，使用基础智能体继续...",
                    "progress": "智能体创建部分完成"
                }

            # 确保至少创建了基础智能体（已取消综合者/梳理逻辑智能体）
            if len(self.agents) == 0:
                logger.warning("没有创建任何智能体，创建基础智能体")
                # 创建基础智能体（主持人 + 协调者）
                try:
                    moderator = Moderator(llm_instance=self.llm_instance)
                    self.agents["moderator"] = moderator
                    facilitator = Facilitator(llm_instance=self.llm_instance)
                    self.agents["facilitator"] = facilitator

                    # 设置通信系统和工具/技能
                    for agent_name, agent in [("moderator", moderator), ("facilitator", facilitator)]:
                        if hasattr(agent, 'set_communication_system'):
                            agent.set_communication_system(self.message_bus, self.communication_protocol)
                        self._setup_agent_tools_and_skills(agent, agent_name)
                except Exception as e:
                    logger.error(f"创建基础智能体失败: {str(e)}", exc_info=True)
                    raise
            else:
                # 确保至少有 facilitator
                if "facilitator" not in self.agents:
                    try:
                        facilitator = Facilitator(llm_instance=self.llm_instance)
                        self.agents["facilitator"] = facilitator
                        if hasattr(facilitator, 'set_communication_system'):
                            facilitator.set_communication_system(self.message_bus, self.communication_protocol)
                        self._setup_agent_tools_and_skills(facilitator, "facilitator")
                        logger.info("补充创建 facilitator 智能体")
                    except Exception as e:
                        logger.error(f"创建 facilitator 失败: {str(e)}")

            yield {
                "step": "agent_creation_complete",
                "message": f"✅ 已创建 {len(self.agents)} 个智能体角色",
                "participants": list(self.agents.keys()),
                "progress": "智能体创建完成"
            }

            # 步骤4: 初始化共识追踪器
            # consensus_tracker 已在初始化时创建

            # 步骤5: 主持人开场
            yield {
                "step": "moderator_opening",
                "message": "🎤 主持人正在开场...",
                "progress": "会议开场中"
            }

            try:
                moderator = self.agents.get("moderator")
                if moderator:
                    # 准备参与者信息
                    participants_info = []
                    for agent_name, agent in self.agents.items():
                        if agent_name != "moderator":  # 主持人不需要介绍自己
                            participants_info.append({
                                "name": agent.name,
                                "role": agent.role_definition,
                                "skills": agent.professional_skills
                            })
                    
                    # 获取讨论主题
                    topic = task_analysis_obj.core_problem if hasattr(task_analysis_obj, 'core_problem') else str(task_analysis_obj)
                    
                    opening = moderator.open_meeting(topic, participants_info)
                    self.discussion_history.append({
                        "type": "opening",
                        "content": opening,
                        "timestamp": datetime.now().isoformat()
                    })

                    yield {
                        "step": "meeting_opened",
                        "message": "🏛️ 会议正式开始",
                        "opening_speech": opening,
                        "progress": "会议开始"
                    }
                else:
                    logger.warning("主持人智能体不存在，跳过开场")
                    yield {
                        "step": "meeting_opened",
                        "message": "🏛️ 会议正式开始（跳过开场）",
                        "opening_speech": "会议开始",
                        "progress": "会议开始"
                    }
            except Exception as e:
                logger.error(f"主持人开场失败: {str(e)}", exc_info=True)
                yield {
                    "step": "meeting_opened",
                    "message": f"⚠️ 会议开始（开场遇到问题: {str(e)}）",
                    "opening_speech": "会议开始",
                    "progress": "会议开始"
                }

            self.discussion_status = "active"

            yield {
                "step": "discussion_ready",
                "message": "🎯 圆桌讨论系统准备就绪，可以开始讨论！",
                "status": "success",
                "participants": list(self.agents.keys()),
                "progress": "准备就绪"
            }

        except Exception as e:
            logger.error(f"启动讨论失败: {str(e)}", exc_info=True)
            self.discussion_status = "error"
            yield {
                "step": "error",
                "message": f"❌ 启动讨论失败: {str(e)}\n\n请检查日志获取详细信息。",
                "status": "error",
                "progress": "初始化失败",
                "error_details": str(e)
            }

    def conduct_discussion_round(self, round_number: int = None, already_spoken_speakers: set = None) -> Generator[Dict[str, Any], None, None]:
        """
        进行一轮讨论

        Args:
            round_number: 轮次编号
            already_spoken_speakers: 本轮已发言的智能体名称集合（重启恢复时跳过，避免重复发言）

        Yields:
            讨论过程的各个步骤结果
        """
        if self.discussion_status != "active":
            yield {"error": "讨论未启动或已暂停"}
            return

        if round_number is None:
            round_number = len(self.discussion_rounds) + 1
        if already_spoken_speakers is None:
            already_spoken_speakers = set()

        # 创建新轮次
        current_round = DiscussionRound(round_number, self.discussion_topic)
        self.discussion_rounds.append(current_round)
        self.current_round = current_round

        yield {"step": "round_start", "round": round_number, "message": f"开始第{round_number}轮讨论"}

        try:
            # 确定发言顺序（无协调者，直接按智能体顺序）
            speaking_order = self._determine_speaking_order()
            # 排除本轮已发言的智能体（重启时从状态恢复，不重复发言）
            speaking_order = [name for name in speaking_order if name not in already_spoken_speakers]
            
            # 调试信息：显示所有智能体名称
            all_agent_names = list(self.agents.keys())
            logger.info(f"第{round_number}轮讨论：所有智能体: {all_agent_names}")
            logger.info(f"第{round_number}轮讨论：确定的发言顺序（已排除已发言）: {speaking_order}")
            if already_spoken_speakers:
                logger.info(f"第{round_number}轮讨论：已跳过已发言智能体: {already_spoken_speakers}")
            
            # 如果没有发言顺序：若为重启且本轮已全部发言则不再安排；否则使用所有智能体
            if not speaking_order:
                if already_spoken_speakers:
                    logger.info(f"第{round_number}轮讨论：本轮已发言的智能体均已发言，无需重复发言")
                else:
                    logger.warning(f"第{round_number}轮讨论：没有找到可发言的智能体，使用所有智能体")
                    speaking_order = list(self.agents.keys())
                    yield {"step": "warning", "message": f"⚠️ 第{round_number}轮讨论：没有找到可发言的智能体，使用所有智能体\n\n**当前智能体列表**: {', '.join(all_agent_names)}"}

            # 分组：固定角色、领域专家、质疑者
            fixed_speakers = []  # 主持人、协调者、数据分析师、风险管理者
            experts = []         # 领域专家列表
            skeptics = []        # 质疑者列表
            expert_skeptic_map = {}  # 专家 -> 质疑者 映射
            
            for speaker_name in speaking_order:
                if speaker_name.startswith("expert_") and not speaker_name.startswith("skeptic_"):
                    experts.append(speaker_name)
                    # 找到对应的质疑者
                    skeptic_name = f"skeptic_{speaker_name}"
                    if skeptic_name in self.agents:
                        skeptics.append(skeptic_name)
                        expert_skeptic_map[speaker_name] = skeptic_name
                elif speaker_name.startswith("skeptic_"):
                    # 单独的质疑者（没有对应专家的）
                    if speaker_name not in skeptics:
                        skeptics.append(speaker_name)
                else:
                    # 固定角色
                    fixed_speakers.append(speaker_name)
            
            # 准备并行执行的参数
            context = self._get_discussion_context()
            topic = context.get("topic", self.discussion_topic)
            previous_speeches = self._get_recent_speeches(10)
            
            # ========== 阶段0: 固定角色并行发言 ==========
            if fixed_speakers:
                yield {"step": "phase_0_start", "message": f"📢 阶段0: 固定角色并行发言（{len(fixed_speakers)}位）..."}
                
                fixed_results = []
                with ThreadPoolExecutor(max_workers=min(len(fixed_speakers), 30)) as executor:
                    futures = {}
                    for speaker_name in fixed_speakers:
                        speaker = self.agents.get(speaker_name)
                        if speaker:
                            speaker_context = context.copy()
                            future = executor.submit(
                                self._execute_single_agent_speech,
                                speaker_name, speaker, topic, speaker_context, previous_speeches, round_number
                            )
                            futures[future] = speaker_name
                    
                    for future in as_completed(futures):
                        speaker_name = futures[future]
                        try:
                            result = future.result()
                            fixed_results.append(result)
                            logger.info(f"固定角色 {speaker_name} 发言完成")
                        except Exception as e:
                            logger.error(f"固定角色 {speaker_name} 发言失败: {e}")
                            fixed_results.append({
                                "speaker_name": speaker_name,
                                "speech_result": {"content": f"{speaker_name}发言失败: {e}", "is_fallback": True},
                                "speech_success": False, "error": str(e)
                            })
                
                # 输出固定角色发言结果
                for result in fixed_results:
                    yield from self._process_speech_result(result["speaker_name"], result, current_round)
                
                yield {"step": "phase_0_done", "message": f"✅ 阶段0完成: {len(fixed_results)}位固定角色发言完毕"}
            
            # ========== 阶段1: 所有领域专家并行发言 ==========
            expert_speeches = {}  # 保存专家发言内容，供质疑者和反馈阶段使用
            
            if experts:
                yield {"step": "phase_1_start", "message": f"🎓 阶段1: 领域专家并行发言（{len(experts)}位）..."}
                
                expert_results = []
                with ThreadPoolExecutor(max_workers=min(len(experts), 30)) as executor:
                    futures = {}
                    for expert_name in experts:
                        expert = self.agents.get(expert_name)
                        if expert:
                            expert_context = context.copy()
                            my_challenges = self._get_unanswered_challenges(expert_name, round_number)
                            expert_context['my_challenges'] = my_challenges
                            expert_context['has_pending_challenges'] = bool(my_challenges)
                            
                            future = executor.submit(
                                self._execute_single_agent_speech,
                                expert_name, expert, topic, expert_context, previous_speeches, round_number
                            )
                            futures[future] = expert_name
                    
                    for future in as_completed(futures):
                        expert_name = futures[future]
                        try:
                            result = future.result()
                            expert_results.append(result)
                            # 保存专家发言内容
                            expert_speeches[expert_name] = result.get("speech_result", {}).get("content", "")
                            logger.info(f"专家 {expert_name} 发言完成")
                        except Exception as e:
                            logger.error(f"专家 {expert_name} 发言失败: {e}")
                            expert_results.append({
                                "speaker_name": expert_name,
                                "speech_result": {"content": f"{expert_name}发言失败: {e}", "is_fallback": True},
                                "speech_success": False, "error": str(e)
                            })
                            expert_speeches[expert_name] = ""
                
                # 输出专家发言结果
                for result in expert_results:
                    yield from self._process_speech_result(result["speaker_name"], result, current_round)
                
                yield {"step": "phase_1_done", "message": f"✅ 阶段1完成: {len(expert_results)}位专家发言完毕"}
            
            # ========== 阶段2: 所有质疑者并行发言（针对专家发言进行质疑） ==========
            skeptic_speeches = {}  # 保存质疑者发言内容，供专家反馈阶段使用
            
            if skeptics:
                yield {"step": "phase_2_start", "message": f"🔍 阶段2: 质疑者并行发言（{len(skeptics)}位）..."}
                
                # 更新 previous_speeches，包含阶段1的专家发言
                updated_speeches = previous_speeches.copy()
                for expert_name, speech in expert_speeches.items():
                    updated_speeches.append({"speaker": expert_name, "content": speech})
                
                skeptic_results = []
                with ThreadPoolExecutor(max_workers=min(len(skeptics), 30)) as executor:
                    futures = {}
                    for skeptic_name in skeptics:
                        skeptic = self.agents.get(skeptic_name)
                        if skeptic:
                            skeptic_context = context.copy()
                            # 找到对应的专家发言
                            target_expert = skeptic_name.replace("skeptic_", "")
                            if target_expert in expert_speeches:
                                skeptic_context['expert_speech'] = expert_speeches[target_expert]
                                skeptic_context['target_expert'] = target_expert
                            skeptic_context['all_expert_speeches'] = expert_speeches
                            
                            future = executor.submit(
                                self._execute_single_agent_speech,
                                skeptic_name, skeptic, topic, skeptic_context, updated_speeches, round_number
                            )
                            futures[future] = skeptic_name
                    
                    for future in as_completed(futures):
                        skeptic_name = futures[future]
                        try:
                            result = future.result()
                            skeptic_results.append(result)
                            # 保存质疑者发言内容
                            skeptic_speeches[skeptic_name] = result.get("speech_result", {}).get("content", "")
                            logger.info(f"质疑者 {skeptic_name} 发言完成")
                        except Exception as e:
                            logger.error(f"质疑者 {skeptic_name} 发言失败: {e}")
                            skeptic_results.append({
                                "speaker_name": skeptic_name,
                                "speech_result": {"content": f"{skeptic_name}发言失败: {e}", "is_fallback": True},
                                "speech_success": False, "error": str(e)
                            })
                            skeptic_speeches[skeptic_name] = ""
                
                # 输出质疑者发言结果
                for result in skeptic_results:
                    yield from self._process_speech_result(result["speaker_name"], result, current_round)
                
                yield {"step": "phase_2_done", "message": f"✅ 阶段2完成: {len(skeptic_results)}位质疑者发言完毕"}
            
            # ========== 阶段3: 专家根据质疑反馈再次并行发言 ==========
            if experts and skeptics:
                yield {"step": "phase_3_start", "message": f"💬 阶段3: 专家根据质疑反馈再次并行发言（{len(experts)}位）..."}
                
                # 更新 previous_speeches，包含质疑者发言
                feedback_speeches = updated_speeches.copy()
                for skeptic_name, speech in skeptic_speeches.items():
                    feedback_speeches.append({"speaker": skeptic_name, "content": speech})
                
                feedback_results = []
                with ThreadPoolExecutor(max_workers=min(len(experts), 30)) as executor:
                    futures = {}
                    for expert_name in experts:
                        expert = self.agents.get(expert_name)
                        if expert:
                            expert_context = context.copy()
                            expert_context['is_feedback_round'] = True
                            expert_context['my_previous_speech'] = expert_speeches.get(expert_name, "")
                            
                            # 找到对应质疑者的反馈
                            skeptic_name = expert_skeptic_map.get(expert_name)
                            if skeptic_name:
                                expert_context['skeptic_feedback'] = skeptic_speeches.get(skeptic_name, "")
                                expert_context['skeptic_name'] = skeptic_name
                            expert_context['all_skeptic_speeches'] = skeptic_speeches
                            
                            future = executor.submit(
                                self._execute_single_agent_speech,
                                expert_name, expert, topic, expert_context, feedback_speeches, round_number
                            )
                            futures[future] = expert_name
                    
                    for future in as_completed(futures):
                        expert_name = futures[future]
                        try:
                            result = future.result()
                            # 标记为反馈发言
                            result["is_feedback"] = True
                            feedback_results.append(result)
                            logger.info(f"专家 {expert_name} 反馈发言完成")
                        except Exception as e:
                            logger.error(f"专家 {expert_name} 反馈发言失败: {e}")
                            feedback_results.append({
                                "speaker_name": expert_name,
                                "speech_result": {"content": f"{expert_name}反馈发言失败: {e}", "is_fallback": True},
                                "speech_success": False, "error": str(e), "is_feedback": True
                            })
                
                # 输出专家反馈发言结果
                for result in feedback_results:
                    yield from self._process_speech_result(result["speaker_name"], result, current_round, is_feedback=True)
                
                yield {"step": "phase_3_done", "message": f"✅ 阶段3完成: {len(feedback_results)}位专家反馈发言完毕"}
            
            yield {"step": "all_phases_done", "message": f"🎉 三阶段发言全部完成（固定角色{len(fixed_speakers)}位 + 专家{len(experts)}位 + 质疑者{len(skeptics)}位）"}

            # 已取消步骤6.5（深度讨论阶段）与步骤7（梳理逻辑/综合者智能体）：第一层各智能体输出直接通过 rounds 传给第二层对应实施智能体

            # 步骤8: 更新共识追踪器
            round_consensus = self._extract_round_consensus(current_round)
            self.consensus_tracker.record_discussion_round(
                round_number=round_number,
                participants=list(self.agents.keys()),
                consensus_updates=round_consensus.get("consensus_updates", []),
                divergence_updates=round_consensus.get("divergence_updates", [])
            )

            consensus_report = self.consensus_tracker.generate_consensus_report()
            yield {"step": "consensus_update", "report": consensus_report}

            # 步骤9: 主持人总结本轮
            moderator = self.agents.get("moderator")
            if moderator:
                round_summary = moderator.guide_discussion(
                    progress_summary=self._summarize_round_progress(current_round),
                    consensus_status=consensus_report,
                    next_steps=self._suggest_next_steps(consensus_report)
                )

                current_round.set_summary(round_summary)
                yield {"step": "round_summary", "summary": round_summary}

            # 步骤9.5: 冲突检测与自动处理
            yield from self._check_and_handle_conflicts(round_number)

            # 步骤10: 生成异常状态报告
            exception_summary = self.get_exception_summary()
            if exception_summary["total_exceptions"] > 0:
                exception_report = self._generate_exception_report(exception_summary)
                yield {"step": "exception_report", "report": exception_report}
                logger.info(f"第{round_number}轮异常报告: {exception_summary}")

            # 等待用户决策
            yield {
                "step": "user_decision",
                "message": "本轮讨论完成，请选择下一步行动:",
                "options": ["continue", "stop", "adjust_direction", "question"],
                "consensus_level": consensus_report.get("overall_consensus", {}).get("overall_level", 0.0)
            }

        except Exception as e:
            yield {"step": "error", "message": f"讨论轮次执行失败: {str(e)}"}

    def handle_user_decision(self, decision: str, additional_input: str = None) -> Dict[str, Any]:
        """
        处理用户决策

        Args:
            decision: 用户决策 (continue, stop, adjust_direction, question)
            additional_input: 附加输入

        Returns:
            处理结果
        """
        if decision == "continue":
            return {"action": "continue", "message": "继续下一轮讨论"}

        elif decision == "stop":
            self.discussion_status = "completed"
            final_report = self.generate_final_report()
            return {"action": "stop", "message": "讨论结束", "final_report": final_report}

        elif decision == "adjust_direction":
            if additional_input:
                # 调整讨论方向
                self.discussion_topic = additional_input
                return {"action": "adjusted", "message": f"讨论方向已调整为: {additional_input}"}

        elif decision == "question":
            if additional_input:
                # 处理用户问题
                answer = self._answer_user_question(additional_input)
                return {"action": "answered", "answer": answer}

        return {"action": "unknown", "message": "未知决策"}

    def generate_final_report(self) -> Dict[str, Any]:
        """
        生成最终报告

        Returns:
            最终讨论报告
        """
        consensus_report = self.consensus_tracker.generate_consensus_report()

        final_report = {
            "discussion_topic": self.discussion_topic,
            "total_rounds": len(self.discussion_rounds),
            "participants": list(self.agents.keys()),
            "duration": self._calculate_discussion_duration(),
            "consensus_report": consensus_report,
            "key_insights": self._extract_key_insights(),
            "action_recommendations": self._generate_action_recommendations(),
            "discussion_summary": self._generate_discussion_summary(),
            "generated_at": datetime.now().isoformat()
        }

        return final_report

    def _create_role_agents_stream(self, task_analysis):
        """创建角色智能体（并行创建，流式返回）"""
        llm = self.llm_instance
        
        # 定义单个智能体创建函数
        def create_single_agent(agent_type: str, role_info: dict = None):
            """
            创建单个智能体
            Args:
                agent_type: 智能体类型 (moderator/facilitator/data_analyst/risk_manager/expert_with_skeptic)
                role_info: 领域专家需要的角色信息
            Returns:
                单个智能体: (agent_name, agent_instance, yield_info)
                专家+质疑者: ((expert_name, expert, expert_info), (skeptic_name, skeptic, skeptic_info))
            """
            try:
                if agent_type == "moderator":
                    agent = Moderator(llm_instance=llm)
                    return ("moderator", agent, {
                        "step": "agent_created",
                        "agent_name": "moderator",
                        "agent_role": "主持人",
                        "message": "🎙️ 创建主持人智能体",
                        "description": "控制议程、引导讨论",
                        "progress": "创建智能体: 主持人",
                        "agent_config": agent.to_config_dict() if hasattr(agent, 'to_config_dict') else None
                    })
                
                elif agent_type == "facilitator":
                    agent = Facilitator(llm_instance=llm)
                    return ("facilitator", agent, {
                        "step": "agent_created",
                        "agent_name": "facilitator",
                        "agent_role": "协调者",
                        "message": "🤝 创建协调者智能体",
                        "description": "协调讨论、促进共识",
                        "progress": "创建智能体: 协调者",
                        "agent_config": agent.to_config_dict() if hasattr(agent, 'to_config_dict') else None
                    })
                
                elif agent_type == "data_analyst":
                    agent = DataAnalyst(llm_instance=llm)
                    return ("data_analyst", agent, {
                        "step": "agent_created",
                        "agent_name": "data_analyst",
                        "agent_role": "数据分析师",
                        "message": "📊 创建数据分析师智能体",
                        "description": "数据支撑分析、可视化、数据洞察",
                        "progress": "创建智能体: 数据分析师",
                        "agent_config": agent.to_config_dict() if hasattr(agent, 'to_config_dict') else None
                    })
                
                elif agent_type == "risk_manager":
                    agent = RiskManager(llm_instance=llm)
                    return ("risk_manager", agent, {
                        "step": "agent_created",
                        "agent_name": "risk_manager",
                        "agent_role": "风险管理者",
                        "message": "⚠️ 创建风险管理者智能体",
                        "description": "风险评估、识别、缓解建议",
                        "progress": "创建智能体: 风险管理者",
                        "agent_config": agent.to_config_dict() if hasattr(agent, 'to_config_dict') else None
                    })
                
                elif agent_type == "expert_with_skeptic" and role_info:
                    # 在同一个线程中创建专家和对应的质疑者
                    role_name = role_info.get("role", "领域专家")
                    clean_role_name = role_name.lower().replace(' ', '_').replace('-', '_').replace('（', '').replace('）', '').replace('(', '').replace(')', '')
                    expert_name = f"expert_{clean_role_name}"
                    skeptic_name = f"skeptic_{expert_name}"
                    
                    priority_map = {"high": "高", "medium": "中", "low": "低", "高": "高", "中": "中", "低": "低"}
                    priority = role_info.get("priority", "medium")
                    priority_cn = priority_map.get(priority.lower() if isinstance(priority, str) else "中", "中")
                    
                    expert_analysis = {
                        "domain": role_name,
                        "expertise_area": role_info.get("reason", role_name),
                        "priority": priority_cn
                    }
                    
                    # 创建专家
                    expert = DomainExpert.create_from_analysis(expert_analysis=expert_analysis, llm_instance=llm)
                    expert_info = {
                        "step": "agent_created",
                        "agent_name": expert_name,
                        "agent_role": f"领域专家 - {role_name}",
                        "message": f"🎓 创建{role_name}领域专家",
                        "description": f"提供{role_name}领域的专业观点和深度分析",
                        "progress": f"创建专家智能体: {role_name}",
                        "agent_config": expert.to_config_dict() if hasattr(expert, 'to_config_dict') else None
                    }
                    
                    # 创建质疑者
                    skeptic = Skeptic.create_for_expert(expert=expert, llm_instance=llm)
                    skeptic_info = {
                        "step": "agent_created",
                        "agent_name": skeptic_name,
                        "agent_role": f"质疑者 - {role_name}",
                        "message": f"🔍 创建{role_name}质疑者",
                        "description": f"对{role_name}专家的观点进行质疑和批判性审查",
                        "progress": f"创建质疑者: {role_name}",
                        "agent_config": skeptic.to_config_dict() if hasattr(skeptic, 'to_config_dict') else None
                    }
                    
                    # 返回专家+质疑者组合
                    return ("expert_with_skeptic", (expert_name, expert, expert_info), (skeptic_name, skeptic, skeptic_info))
                
                return None
            except Exception as e:
                logger.error(f"创建智能体 {agent_type} 失败: {e}")
                return None
        
        # 收集所有创建任务
        creation_tasks = []
        
        # 固定角色智能体（含协调者）
        fixed_roles = ["moderator", "facilitator", "data_analyst", "risk_manager"]
        for role in fixed_roles:
            creation_tasks.append((role, None, 0))  # (type, role_info, order)
        
        # 动态领域专家+质疑者（绑定创建）
        num_roles = len(task_analysis.recommended_roles)
        logger.info(f"将并行创建 {4 + num_roles * 2} 个智能体（4个固定角色 + {num_roles}组专家+质疑者）")
        
        for i, role_info in enumerate(task_analysis.recommended_roles):
            creation_tasks.append(("expert_with_skeptic", role_info, 10 + i))
        
        # 并行创建所有智能体（专家+质疑者在同一线程中创建）
        yield {"step": "parallel_agent_creation_start", "message": f"开始并行创建 {4 + num_roles} 组智能体..."}
        
        all_results = []
        with ThreadPoolExecutor(max_workers=min(4 + num_roles, 30)) as executor:
            futures = {}
            for task_type, role_info, order in creation_tasks:
                future = executor.submit(create_single_agent, task_type, role_info)
                futures[future] = (task_type, order)
            
            for future in as_completed(futures):
                task_type, order = futures[future]
                try:
                    result = future.result()
                    if result:
                        all_results.append((order, task_type, result))
                        if task_type == "expert_with_skeptic":
                            logger.info(f"专家+质疑者组 {result[1][0]} 并行创建完成")
                        else:
                            logger.info(f"智能体 {result[0]} 并行创建完成")
                except Exception as e:
                    logger.error(f"创建智能体 {task_type} 失败: {e}")
        
        # 按顺序注册智能体并 yield 进度
        all_results.sort(key=lambda x: x[0])
        
        for _, task_type, result in all_results:
            if task_type == "expert_with_skeptic":
                # 处理专家+质疑者组合
                _, (expert_name, expert, expert_info), (skeptic_name, skeptic, skeptic_info) = result
                
                # 注册专家
                self.agents[expert_name] = expert
                if hasattr(expert, 'set_communication_system'):
                    expert.set_communication_system(self.message_bus, self.communication_protocol)
                self._setup_agent_tools_and_skills(expert, "domain_expert")
                yield expert_info
                
                # 注册质疑者
                self.agents[skeptic_name] = skeptic
                if hasattr(skeptic, 'set_communication_system'):
                    skeptic.set_communication_system(self.message_bus, self.communication_protocol)
                self._setup_agent_tools_and_skills(skeptic, "skeptic")
                yield skeptic_info
            else:
                # 处理固定角色
                agent_name, agent, yield_info = result
                self.agents[agent_name] = agent
                if hasattr(agent, 'set_communication_system'):
                    agent.set_communication_system(self.message_bus, self.communication_protocol)
                self._setup_agent_tools_and_skills(agent, agent_name)
                yield yield_info
        
        yield {"step": "parallel_agent_creation_done", "message": f"并行创建完成，共 {len(self.agents)} 个智能体"}

    def _create_role_agents(self, task_analysis):
        """创建角色智能体（原有方法，保持兼容性）"""
        # 消费流式方法但不返回任何内容
        for _ in self._create_role_agents_stream(task_analysis):
            pass

    def _load_agents_from_roles(self, roles_dir: str) -> Optional[Dict[str, Any]]:
        """
        从 roles 目录加载智能体配置，重建 agents（重启任务时使用）。
        返回 {agent_name: agent}，若失败或为空则返回 None。
        """
        try:
            files = [f for f in os.listdir(roles_dir) if f.endswith(".json") and not f.startswith("layer_2_")]
            if not files:
                return None
            by_name = {}
            for f in files:
                m = re.match(r"^(.+)_\d{8}_\d{6}\.json$", f)
                if m:
                    base = m.group(1)
                    path = os.path.join(roles_dir, f)
                    try:
                        mtime = os.path.getmtime(path)
                        if base not in by_name or mtime > by_name[base][0]:
                            with open(path, "r", encoding="utf-8") as fp:
                                cfg = json.load(fp)
                            by_name[base] = (mtime, cfg)
                    except (OSError, json.JSONDecodeError):
                        continue
            if not by_name:
                return None
            loaded = {}
            llm = self.llm_instance
            for name, (_, cfg) in sorted(by_name.items()):
                if name.startswith("expert_") and not name.startswith("skeptic_"):
                    try:
                        expert = DomainExpert.create_from_config(cfg, llm)
                        expert.set_communication_system(self.message_bus, self.communication_protocol)
                        self._setup_agent_tools_and_skills(expert, "domain_expert")
                        loaded[name] = expert
                    except Exception as e:
                        logger.warning(f"加载智能体 {name} 失败: {e}")
            for name, (_, cfg) in sorted(by_name.items()):
                if name.startswith("skeptic_expert_"):
                    try:
                        target_domain = name.replace("skeptic_expert_", "").strip()
                        expert_name = f"expert_{target_domain}"
                        target_expert = loaded.get(expert_name)
                        if target_expert is None:
                            continue
                        skeptic = Skeptic.create_from_config(cfg, target_expert, llm)
                        skeptic.set_communication_system(self.message_bus, self.communication_protocol)
                        self._setup_agent_tools_and_skills(skeptic, "skeptic")
                        loaded[name] = skeptic
                    except Exception as e:
                        logger.warning(f"加载智能体 {name} 失败: {e}")
            for role, cls in [
                ("moderator", Moderator),
                ("facilitator", Facilitator),
                ("data_analyst", DataAnalyst),
                ("risk_manager", RiskManager),
            ]:
                for name, (_, cfg) in by_name.items():
                    if name == role:
                        try:
                            agent = cls(llm_instance=llm)
                            if hasattr(agent, "set_communication_system"):
                                agent.set_communication_system(self.message_bus, self.communication_protocol)
                            self._setup_agent_tools_and_skills(agent, role)
                            loaded[name] = agent
                        except Exception as e:
                            logger.warning(f"加载智能体 {name} 失败: {e}")
                        break
            if not loaded:
                return None
            self.agents.update(loaded)
            return loaded
        except Exception as e:
            logger.warning(f"从 roles 加载智能体失败: {e}")
            return None

    def _convert_scholar_result_to_task_analysis(self, scholar_result: Dict[str, Any], user_task: str) -> TaskAnalysis:
        """将学者分析结果转换为 TaskAnalysis 对象"""
        task_analysis = TaskAnalysis(user_task, "user")

        try:
            analysis_data = scholar_result.get("task_analysis", {})

            # 设置核心问题分析
            core_problem = analysis_data.get("core_problem", f"分析任务：{user_task}")
            sub_problems = analysis_data.get("sub_problems", [])
            complexity_level = analysis_data.get("complexity_level", "medium")

            # 标准化复杂度级别
            if isinstance(complexity_level, str):
                if "高" in complexity_level.lower() or "high" in complexity_level.lower():
                    complexity_level = "high"
                elif "低" in complexity_level.lower() or "low" in complexity_level.lower():
                    complexity_level = "low"
                else:
                    complexity_level = "medium"

            # 预估时间
            time_estimate = analysis_data.get("estimated_time", "2-4周")

            task_analysis.set_core_analysis(core_problem, sub_problems, complexity_level, time_estimate)

            # 设置领域分析
            primary_domain = analysis_data.get("primary_domain", "综合分析")
            secondary_domains = analysis_data.get("secondary_domains", [])
            cross_domain_aspects = analysis_data.get("cross_domain_aspects", [])

            task_analysis.set_domain_analysis(primary_domain, secondary_domains, cross_domain_aspects)

            # 设置参与者分析：学者输出的每一个角色都会自动创建对应智能体，不遗漏
            required_experts = analysis_data.get("required_experts", [])
            recommended_roles = []

            for expert in required_experts:
                if isinstance(expert, dict):
                    role_info = {
                        "role": expert.get("domain", expert.get("role", "专家")),
                        "reason": expert.get("reason", "需要专业知识"),
                        "priority": expert.get("priority", "medium")
                    }
                    recommended_roles.append(role_info)

            # 若解析结果无任何角色，使用默认角色确保至少创建一批智能体
            if not recommended_roles:
                logger.warning("学者分析未产出 required_experts，使用默认角色列表以确保创建智能体")
                recommended_roles = [
                    {"role": "综合分析", "reason": "任务分析与多领域协调", "priority": "高"},
                    {"role": "技术实现", "reason": "方案落地与实施", "priority": "中"},
                    {"role": "风险评估", "reason": "风险识别与应对", "priority": "中"},
                ]

            participant_count = max(len(recommended_roles), 3)  # 最少3个参与者
            collaboration_patterns = analysis_data.get("collaboration_mechanism", {}).get("patterns", ["专家协作", "信息共享"])

            task_analysis.set_participant_analysis(recommended_roles, participant_count, collaboration_patterns)

            # 设置需求和成功标准
            resource_requirements = analysis_data.get("resource_requirements", ["专业知识", "分析工具", "协作平台"])
            success_criteria = analysis_data.get("success_criteria", ["问题分析清晰", "解决方案可行", "专家意见整合"])

            task_analysis.set_requirements(resource_requirements, success_criteria)

            # 设置风险分析
            risk_factors = analysis_data.get("risk_factors", ["分析不够全面", "专家意见分歧", "时间限制"])
            mitigation_strategies = analysis_data.get("mitigation_strategies", ["多方验证", "时间管理", "共识机制"])

            task_analysis.set_risks(risk_factors, mitigation_strategies)

        except Exception as e:
            print(f"Warning: Failed to convert scholar result to TaskAnalysis: {str(e)}")
            # 使用默认值
            task_analysis.set_core_analysis(f"分析任务：{user_task}", ["任务分解"], "medium", "2-4周")

        return task_analysis

    def _process_speech_result(self, speaker_name: str, result: dict, current_round: DiscussionRound, is_feedback: bool = False):
        """
        处理单个智能体的发言结果并 yield 输出
        
        Args:
            speaker_name: 发言者名称
            result: 发言结果字典
            current_round: 当前讨论轮次
            is_feedback: 是否是专家反馈发言（阶段3）
            
        Yields:
            发言处理过程的各个步骤
        """
        try:
            step_prefix = "feedback_" if is_feedback else ""
            yield {"step": f"{step_prefix}speech_start", "speaker": speaker_name, "is_feedback": is_feedback}
            
            thinking_result = result.get("thinking_result", {})
            speech_result = result.get("speech_result", {})
            
            speech_content = speech_result.get('content', '') if isinstance(speech_result, dict) else str(speech_result)
            thinking_content = thinking_result.get('raw_response', '') if isinstance(thinking_result, dict) else str(thinking_result)
            
            if not speech_content or speech_content.strip() == '':
                speech_content = f"{speaker_name} 就讨论主题发表了观点，但内容为空。"
            
            # 保存发言到轮次记录
            if is_feedback:
                speech_type = "expert_feedback"
            elif speaker_name.startswith("skeptic_"):
                speech_type = "skeptic_question"
            else:
                speech_type = "expert_opinion"
            current_round.add_speech(speaker_name, speech_content, speech_type)
            
            yield {
                "step": f"{step_prefix}speech",
                "speaker": speaker_name,
                "thinking": thinking_content,
                "speech": speech_content,
                "is_feedback": is_feedback
            }
            
            yield {"step": f"{step_prefix}speech_end", "speaker": speaker_name, "is_feedback": is_feedback}
            
        except Exception as e:
            logger.error(f"智能体 {speaker_name} 发言处理失败: {str(e)}", exc_info=True)
            yield {
                "step": "speech_error",
                "speaker": speaker_name,
                "error": str(e),
                "message": f"⚠️ {speaker_name} 发言时出错: {str(e)}",
                "is_feedback": is_feedback
            }

    def _determine_speaking_order(self) -> List[str]:
        """确定发言顺序"""
        # 基本发言顺序：专家们先发言，然后是质疑者，最后是数据分析师和风险管理者
        order = []
        
        # 排除不需要发言的角色
        excluded_roles = {"scholar", "moderator", "ideation"}  # ideation 仅协助学者；已取消 synthesizer，第一层各智能体输出直接按领域传第二层
        
        # 获取所有智能体名称用于调试
        all_agent_names = list(self.agents.keys())
        logger.info(f"所有智能体名称: {all_agent_names}")

        # 领域专家发言（排除 scholar）
        # 匹配 expert 开头的名称（支持 expert_ 和 expert 两种格式）
        experts = [name for name in all_agent_names 
                  if (name.startswith("expert_") or name.startswith("expert")) 
                  and name not in excluded_roles 
                  and name != "expert"]  # 排除单独的 "expert"
        order.extend(sorted(experts))  # 排序保证顺序一致
        logger.info(f"找到的专家: {experts}")

        # 质疑者发言（对应每个专家）
        # 匹配 skeptic 开头的名称（支持多种格式）
        skeptics = [name for name in all_agent_names 
                   if (name.startswith("skeptic_") or name.startswith("skepticexpert") or name.startswith("skeptic"))
                   and name not in excluded_roles
                   and name != "skeptic"]  # 排除单独的 "skeptic"
        order.extend(sorted(skeptics))
        logger.info(f"找到的质疑者: {skeptics}")

        # 其他角色（协调者、数据分析师、风险管理者）
        other_roles = ["facilitator", "data_analyst", "risk_manager"]
        for role in other_roles:
            if role in self.agents and role not in excluded_roles:
                order.append(role)
        logger.info(f"其他角色: {[r for r in other_roles if r in self.agents]}")

        # 已取消综合者：第一层结果直接按领域传给第二层实施智能体，不再经过梳理逻辑智能体

        logger.info(f"最终确定的发言顺序: {order}, 总智能体数: {len(self.agents)}")
        
        # 如果还是没有找到发言者，返回所有非排除角色
        if not order:
            logger.warning("没有找到匹配的发言顺序，返回所有非排除角色")
            order = [name for name in all_agent_names if name not in excluded_roles]
            logger.info(f"使用所有非排除角色: {order}")
        
        # 确保至少有一个智能体发言
        if not order:
            logger.warning("仍然没有找到发言者，使用所有智能体")
            order = all_agent_names.copy()
            logger.info(f"使用所有智能体: {order}")
        
        return order

    def _execute_single_agent_speech(
        self,
        speaker_name: str,
        speaker,
        topic: str,
        context: Dict[str, Any],
        previous_speeches: List[Dict[str, Any]],
        round_number: int,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        执行单个智能体的思考和发言（用于并行执行）
        
        Args:
            speaker_name: 智能体名称
            speaker: 智能体实例
            topic: 讨论主题
            context: 讨论上下文
            previous_speeches: 之前的发言列表
            round_number: 轮次编号
            max_retries: 最大重试次数
        
        Returns:
            包含 thinking_result, speech_result, success 等信息的字典
        """
        result = {
            "speaker_name": speaker_name,
            "thinking_result": None,
            "speech_result": None,
            "thinking_success": False,
            "speech_success": False,
            "error": None
        }
        
        # 可选：AgentScope 统一执行
        if get_agentscope_enabled() and is_agentscope_available():
            if hasattr(self, '_agentscope_adapters') and self._agentscope_adapters:
                if speaker_name in self._agentscope_adapters:
                    tr, sr = run_agent_reply_sync(
                        self._agentscope_adapters[speaker_name], topic, context, previous_speeches
                    )
                    if tr is not None and sr is not None and (sr.get("content") or "").strip():
                        result["thinking_result"] = tr
                        result["speech_result"] = sr
                        result["thinking_success"] = True
                        result["speech_success"] = True
                        logger.info(f"✅ 智能体 {speaker_name} 通过 AgentScope 完成思考与发言")
                        return result
        
        # 重试循环
        for attempt in range(max_retries + 1):
            current_attempt = attempt + 1
            
            # 思考阶段
            if not result["thinking_success"]:
                try:
                    logger.info(f"智能体 {speaker_name} 第{current_attempt}次尝试 - 思考阶段")
                    result["thinking_result"] = speaker.think(topic, context)
                    result["thinking_success"] = True
                    logger.info(f"✅ 智能体 {speaker_name} 思考成功")
                except Exception as e:
                    logger.warning(f"智能体 {speaker_name} 思考失败 (尝试 {current_attempt}): {e}")
                    if current_attempt <= max_retries:
                        import time
                        time.sleep(current_attempt * 2)
                        continue
                    else:
                        result["thinking_result"] = {
                            "raw_response": f"{speaker_name}的思考过程因多次失败而被简化。",
                            "error": str(e),
                            "is_fallback": True
                        }
            
            # 发言阶段
            if result["thinking_success"]:
                try:
                    logger.info(f"智能体 {speaker_name} 第{current_attempt}次尝试 - 发言阶段")
                    speech = speaker.speak(context, previous_speeches)
                    if speech and speech.get('content') and speech.get('content').strip():
                        result["speech_result"] = speech
                        result["speech_success"] = True
                        logger.info(f"✅ 智能体 {speaker_name} 发言成功")
                        break
                    else:
                        raise ValueError("发言内容为空")
                except Exception as e:
                    logger.warning(f"智能体 {speaker_name} 发言失败 (尝试 {current_attempt}): {e}")
                    if current_attempt <= max_retries:
                        import time
                        time.sleep(current_attempt * 2)
                        continue
                    else:
                        result["speech_result"] = {
                            "agent_name": speaker_name,
                            "role": speaker.role_definition,
                            "content": f"{speaker_name}经过多次尝试后仍无法正常发言。",
                            "timestamp": speaker._get_timestamp(),
                            "is_fallback": True,
                            "error": str(e)
                        }
                        result["error"] = str(e)
        
        # 确保有后备结果
        if not result["thinking_success"] and not result["speech_success"]:
            result["thinking_result"] = result["thinking_result"] or {
                "raw_response": f"{speaker_name}的思考和发言过程完全失败。",
                "is_fallback": True
            }
            result["speech_result"] = result["speech_result"] or {
                "agent_name": speaker_name,
                "role": speaker.role_definition,
                "content": f"{speaker_name}由于系统错误无法参与本次讨论。",
                "timestamp": speaker._get_timestamp(),
                "is_fallback": True
            }
        
        return result

    def _generate_skeptic_response(
        self,
        target_expert: str,
        expert_speech: str,
        current_round: DiscussionRound,
        revision_round: int = 1,
    ):
        """生成质疑者回应。revision_round=2 时为第二层：侧重实施参数/指标/数据查询并反馈给发言者。"""
        skeptic_name = f"skeptic_{target_expert}"
        skeptic = self.agents.get(skeptic_name)

        if skeptic:
            # 创建质疑消息
            questioning_message = self.communication_protocol.create_questioning_message(
                sender=skeptic_name,
                receiver=target_expert,
                target_expert=target_expert,
                questioning_content=expert_speech if isinstance(expert_speech, str) else expert_speech.get('content', ''),
                round_number=current_round.round_number
            )

            # 发送质疑消息到消息总线
            self.message_bus.send_message(questioning_message)

            # 讨论上下文：第二层时注入 revision_round/skeptic_layer 供质疑者做实施参数与数据反馈
            context = self._get_discussion_context()
            context["revision_round"] = revision_round
            context["skeptic_layer"] = revision_round

            # 让质疑者处理消息并生成质疑内容
            question_result = skeptic.question_expert(
                expert_opinion={
                    "content": expert_speech if isinstance(expert_speech, str) else expert_speech.get('content', ''),
                    "speaker": target_expert
                },
                context=context,
            )

            # 提取质疑内容
            question_content = question_result.get('content', '') if isinstance(question_result, dict) else str(question_result)

            # 创建质疑者回应消息
            response_message = self.communication_protocol.create_response_message(
                sender=skeptic_name,
                receiver=target_expert,
                response_content=question_content,
                parent_message_id=questioning_message.message_id,
                round_number=current_round.round_number,
                conversation_id=questioning_message.conversation_id
            )

            # 发送回应消息
            self.message_bus.send_message(response_message)

            # 保存到轮次记录
            current_round.add_speech(skeptic_name, question_content, "skeptic_question")

            # 返回质疑内容，以便外部可以 yield
            return {
                "skeptic_name": skeptic_name,
                "question_content": question_content,
                "thinking": "",  # 质疑者通常不需要思考过程
                "target_expert": target_expert,
                "conversation_id": questioning_message.conversation_id,
                "message_id": response_message.message_id
            }

        return None

    def _get_discussion_context(self) -> Dict[str, Any]:
        """获取讨论上下文（含 discussion_id 与 discussion/discussion_id/files 中的论文摘要，供质疑者网络检索与阅读本地论文）"""
        local_papers_summary = ""
        if self._ideation_papers:
            lines = []
            for i, p in enumerate(self._ideation_papers[:15], 1):
                title = p.get("title", "")
                authors = p.get("authors", [])
                auth = ", ".join(authors[:3]) if isinstance(authors, list) else str(authors)
                abstract = (p.get("abstract") or "")[:300]
                year = p.get("year", "")
                lines.append(f"[{i}] {title} | {auth} | {year}\n{abstract}")
            local_papers_summary = "\n\n".join(lines)
        # 论文 PDF 保存在 discussion/discussion_id/files（与 web_search_tool 下载路径一致）
        local_pdf_dir = str(self.state_manager.storage_path / "files")
        local_pdf_files = []
        try:
            if os.path.isdir(local_pdf_dir):
                local_pdf_files = [f for f in os.listdir(local_pdf_dir) if f.lower().endswith(".pdf")]
        except Exception:
            pass
        return {
            "topic": self.discussion_topic,
            "rounds_completed": len(self.discussion_rounds),
            "current_participants": list(self.agents.keys()),
            "consensus_status": self.consensus_tracker.get_consensus_status(),
            "recent_speeches": self._get_recent_speeches(10),
            "discussion_id": self.discussion_id,
            "local_papers_dir": local_pdf_dir,
            "local_papers_summary": local_papers_summary,
            "local_pdf_files": local_pdf_files,
            "papers_downloaded_to": self._papers_downloaded_to or local_pdf_dir,
        }

    def _get_recent_speeches(self, limit: int) -> List[Dict[str, Any]]:
        """获取最近的发言"""
        all_speeches = []
        for round_obj in self.discussion_rounds[-3:]:  # 最近3轮
            all_speeches.extend(round_obj.speeches)

        return all_speeches[-limit:] if limit > 0 else all_speeches

    def _get_challenges_for_speaker(self, speaker_name: str) -> List[Dict[str, Any]]:
        """
        获取针对特定专家的所有质疑
        
        Args:
            speaker_name: 专家名称
            
        Returns:
            针对该专家的质疑列表，按时间顺序排列
        """
        challenges = []
        
        # 遍历所有历史轮次
        for round_obj in self.discussion_rounds:
            for speech in round_obj.speeches:
                # 检查是否是针对该专家的质疑
                target_expert = speech.get('target_expert', '')
                speech_type = speech.get('type', '')
                
                # 质疑者发言通常有 target_expert 字段，或者 type 为 skeptic_question
                if target_expert == speaker_name or (
                    speech_type == 'skeptic_question' and 
                    speaker_name in speech.get('content', '')
                ):
                    challenges.append({
                        'round': round_obj.round_number,
                        'skeptic': speech.get('agent_name', speech.get('speaker', '质疑者')),
                        'content': speech.get('content', ''),
                        'timestamp': speech.get('timestamp', ''),
                        'type': speech_type
                    })
        
        return challenges

    def _get_unanswered_challenges(self, speaker_name: str, current_round: int) -> List[Dict[str, Any]]:
        """
        获取未回应的质疑（上一轮提出但本轮未回应的）
        
        Args:
            speaker_name: 专家名称
            current_round: 当前轮次
            
        Returns:
            未回应的质疑列表
        """
        all_challenges = self._get_challenges_for_speaker(speaker_name)
        
        # 只获取上一轮的质疑
        unanswered = [
            c for c in all_challenges 
            if c['round'] == current_round - 1
        ]
        
        return unanswered

    def _get_consensus_points(self) -> List[str]:
        """获取共识点"""
        status = self.consensus_tracker.get_consensus_status()
        return [cp["content"] for cp in status.get("strong_consensus_points", [])]

    def _get_divergence_points(self) -> List[str]:
        """获取分歧点"""
        status = self.consensus_tracker.get_consensus_status()
        return [dp["content"] for dp in status.get("intense_divergences", [])]

    def retry_failed_speech(self, failed_speech_id: str) -> Generator[Dict[str, Any], None, None]:
        """
        重试失败的发言
        
        Args:
            failed_speech_id: 失败发言的ID
            
        Yields:
            重试过程中的状态信息
        """
        failed_speech = self.exception_context.get_failed_speech(failed_speech_id)
        if not failed_speech:
            yield {
                "step": "retry_error",
                "error": f"未找到失败发言记录: {failed_speech_id}",
                "success": False
            }
            return
        
        if failed_speech["status"] == "success":
            yield {
                "step": "retry_skip",
                "message": f"该发言已经成功重试过",
                "failed_speech_id": failed_speech_id,
                "success": True
            }
            return
        
        if failed_speech["retry_count"] >= failed_speech["max_retries"]:
            yield {
                "step": "retry_exhausted",
                "message": f"已达到最大重试次数 ({failed_speech['max_retries']})",
                "failed_speech_id": failed_speech_id,
                "success": False
            }
            return
        
        speaker_name = failed_speech["speaker_name"]
        speaker = self.agents.get(speaker_name)
        
        if not speaker:
            yield {
                "step": "retry_error",
                "error": f"智能体 {speaker_name} 不存在",
                "failed_speech_id": failed_speech_id,
                "success": False
            }
            return
        
        # 更新状态为重试中
        self.exception_context.update_failed_speech_status(failed_speech_id, "retrying")
        self.exception_context.increment_retry_count(failed_speech_id)
        
        yield {
            "step": "retry_start",
            "speaker": speaker_name,
            "failed_speech_id": failed_speech_id,
            "attempt": failed_speech["retry_count"] + 1,
            "max_attempts": failed_speech["max_retries"],
            "message": f"🔄 开始重试 {speaker_name} 的发言 (第 {failed_speech['retry_count'] + 1}/{failed_speech['max_retries']} 次)"
        }
        
        context = failed_speech["context"]
        topic = failed_speech["topic"]
        previous_speeches = failed_speech["previous_speeches"]
        stage = failed_speech["stage"]
        round_number = failed_speech["round_number"]
        
        try:
            if stage == "thinking":
                # 重试思考阶段
                yield {
                    "step": "retry_thinking",
                    "speaker": speaker_name,
                    "message": f"🧠 {speaker_name} 正在重新思考..."
                }
                thinking_result = speaker.think(topic, context)
                
                # 思考成功，继续发言
                yield {
                    "step": "retry_speaking",
                    "speaker": speaker_name,
                    "message": f"💬 {speaker_name} 正在重新发言..."
                }
                speech_result = speaker.speak(context, previous_speeches)
                
            else:  # stage == "speaking"
                # 直接重试发言阶段
                yield {
                    "step": "retry_speaking",
                    "speaker": speaker_name,
                    "message": f"💬 {speaker_name} 正在重新发言..."
                }
                speech_result = speaker.speak(context, previous_speeches)
            
            # 检查发言结果
            if speech_result and speech_result.get('content') and speech_result.get('content').strip():
                speech_content = speech_result.get('content', '')
                
                # 更新状态为成功
                self.exception_context.update_failed_speech_status(
                    failed_speech_id, 
                    "success",
                    result={"content": speech_content, "timestamp": datetime.now().isoformat()}
                )
                
                # 将发言添加到对应的轮次
                for round_obj in self.discussion_rounds:
                    if round_obj.round_number == round_number:
                        round_obj.add_speech(speaker_name, speech_content, "expert_opinion_retry")
                        break
                
                yield {
                    "step": "retry_success",
                    "speaker": speaker_name,
                    "failed_speech_id": failed_speech_id,
                    "speech": speech_content,
                    "success": True,
                    "message": f"✅ {speaker_name} 重试发言成功!"
                }
            else:
                raise ValueError("重试发言内容为空")
                
        except Exception as e:
            error_msg = str(e)
            exception_type = self._classify_exception(e)
            import traceback
            stack_trace = traceback.format_exc()
            
            # 记录重试失败
            self.exception_context.update_failed_speech_status(
                failed_speech_id,
                "pending" if failed_speech["retry_count"] < failed_speech["max_retries"] else "abandoned",
                result={"error": error_msg, "stack_trace": stack_trace}
            )
            
            requires_intervention = self._requires_human_intervention(
                exception_type, 
                stage, 
                failed_speech["retry_count"] + 1
            )
            
            yield {
                "step": "retry_failed",
                "speaker": speaker_name,
                "failed_speech_id": failed_speech_id,
                "error_type": exception_type,
                "error_message": error_msg,
                "attempt": failed_speech["retry_count"] + 1,
                "can_retry_again": failed_speech["retry_count"] < failed_speech["max_retries"],
                "requires_intervention": requires_intervention,
                "success": False,
                "message": f"❌ {speaker_name} 重试失败\n错误类型: {exception_type}\n剩余重试次数: {failed_speech['max_retries'] - failed_speech['retry_count'] - 1}"
            }

    def retry_all_failed_speeches(self, discussion_id: str = None) -> Generator[Dict[str, Any], None, None]:
        """
        重试所有失败的发言
        
        Args:
            discussion_id: 可选，限制只重试特定讨论的失败发言
            
        Yields:
            重试过程中的状态信息
        """
        candidates = self.exception_context.get_retry_candidates(discussion_id)
        
        if not candidates:
            yield {
                "step": "no_candidates",
                "message": "没有可重试的失败发言",
                "success": True
            }
            return
        
        yield {
            "step": "retry_batch_start",
            "total": len(candidates),
            "message": f"🔄 开始批量重试 {len(candidates)} 个失败发言"
        }
        
        success_count = 0
        fail_count = 0
        
        for i, candidate in enumerate(candidates):
            failed_speech_id = candidate["failed_speech_id"]
            
            yield {
                "step": "retry_batch_progress",
                "current": i + 1,
                "total": len(candidates),
                "speaker": candidate["speaker_name"],
                "message": f"正在重试 {i + 1}/{len(candidates)}: {candidate['speaker_name']}"
            }
            
            # 执行重试
            for result in self.retry_failed_speech(failed_speech_id):
                yield result
                if result.get("step") == "retry_success":
                    success_count += 1
                elif result.get("step") == "retry_failed":
                    fail_count += 1
        
        yield {
            "step": "retry_batch_complete",
            "success_count": success_count,
            "fail_count": fail_count,
            "total": len(candidates),
            "message": f"✅ 批量重试完成: {success_count} 成功, {fail_count} 失败"
        }

    def get_failed_speeches_info(self, discussion_id: str = None) -> Dict[str, Any]:
        """
        获取失败发言的详细信息
        
        Args:
            discussion_id: 可选，限制只获取特定讨论的失败发言
            
        Returns:
            包含失败发言详情和统计信息的字典
        """
        summary = self.exception_context.get_failed_speeches_summary(discussion_id)
        candidates = self.exception_context.get_retry_candidates(discussion_id)
        
        # 获取每个失败发言的关联异常信息
        detailed_failures = []
        for fs_id, fs_info in self.exception_context.failed_speeches.items():
            if discussion_id and fs_info["discussion_id"] != discussion_id:
                continue
            
            exception_info = self.exception_context.get_exception_by_id(fs_info.get("exception_id"))
            
            detailed_failures.append({
                "failed_speech_id": fs_id,
                "speaker_name": fs_info["speaker_name"],
                "stage": fs_info["stage"],
                "round_number": fs_info["round_number"],
                "status": fs_info["status"],
                "retry_count": fs_info["retry_count"],
                "max_retries": fs_info["max_retries"],
                "can_retry": fs_info["status"] == "pending" and fs_info["retry_count"] < fs_info["max_retries"],
                "created_at": fs_info["created_at"],
                "last_retry_at": fs_info["last_retry_at"],
                "exception_type": exception_info.get("exception_type") if exception_info else "unknown",
                "error_message": exception_info.get("error_message") if exception_info else "unknown",
                "requires_intervention": exception_info.get("requires_human_intervention", False) if exception_info else False,
                "intervention_suggestions": exception_info.get("intervention_suggestions", []) if exception_info else []
            })
        
        return {
            "summary": summary,
            "retry_candidates": len(candidates),
            "detailed_failures": detailed_failures
        }

    def _extract_opinions_from_speeches(self, speeches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从发言中提取观点"""
        opinions = []
        for speech in speeches:
            opinions.append({
                "speaker": speech["speaker"],
                "opinion": speech["content"],
                "type": speech.get("speech_type", "normal")
            })
        return opinions

    def _extract_round_consensus(self, round_obj: DiscussionRound) -> Dict[str, Any]:
        """提取轮次共识"""
        # 简单的共识提取逻辑
        consensus_updates = []
        divergence_updates = []

        # 分析发言内容，提取共识和分歧
        speeches_by_speaker = {}
        for speech in round_obj.speeches:
            speaker = speech["speaker"]
            if speaker not in speeches_by_speaker:
                speeches_by_speaker[speaker] = []
            speeches_by_speaker[speaker].append(speech["content"])

        # 这里应该有更复杂的共识分析逻辑
        # 暂时返回空结果
        return {
            "consensus_updates": consensus_updates,
            "divergence_updates": divergence_updates
        }

    def _summarize_round_progress(self, round_obj: DiscussionRound) -> str:
        """总结轮次进展"""
        return f"第{round_obj.round_number}轮完成，共有{len(round_obj.speeches)}条发言"

    def _suggest_next_steps(self, consensus_report: Dict[str, Any]) -> List[str]:
        """建议下一步行动"""
        # 安全获取共识水平
        overall_consensus = consensus_report.get("overall_consensus", {})
        level = overall_consensus.get("overall_level", 0.0) if isinstance(overall_consensus, dict) else 0.0
        
        if level > 0.8:
            return ["可以考虑结束讨论并制定行动计划"]
        elif level > 0.6:
            return ["继续讨论剩余的分歧点", "深化对共识点的理解"]
        else:
            return ["重新审视讨论目标和目标", "考虑调整参与者", "可能需要邀请更多相关专家"]

    def _answer_user_question(self, question: str) -> str:
        """回答用户问题"""
        # 这里可以调用相关的智能体来回答问题
        # 暂时返回简单回答
        return f"关于您的问题 '{question}'，讨论系统正在分析中..."

    def _calculate_discussion_duration(self) -> str:
        """计算讨论总时长"""
        if not self.discussion_rounds:
            return "0分钟"

        try:
            start_time_str = self.discussion_rounds[0].start_time
            end_time_str = self.discussion_rounds[-1].end_time or datetime.now().isoformat()
            
            # 解析时间字符串
            start_time = datetime.fromisoformat(start_time_str)
            end_time = datetime.fromisoformat(end_time_str)
            
            # 计算时间差
            duration = end_time - start_time
            total_seconds = int(duration.total_seconds())
            
            if total_seconds < 60:
                return f"{total_seconds}秒"
            elif total_seconds < 3600:
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                if seconds > 0:
                    return f"{minutes}分钟{seconds}秒"
                return f"{minutes}分钟"
            else:
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                if minutes > 0:
                    return f"{hours}小时{minutes}分钟"
                return f"{hours}小时"
                
        except Exception as e:
            logger.warning(f"计算讨论时长失败: {e}")
            return "无法计算"

    def _classify_exception(self, exception: Exception) -> str:
        """对异常进行分类"""
        error_str = str(exception).lower()
        error_type = type(exception).__name__.lower()

        # 基于异常类型和错误信息进行分类
        if any(keyword in error_str for keyword in ['timeout', 'time out']):
            return "timeout"
        elif any(keyword in error_str for keyword in ['network', 'connection', 'connect']):
            return "network"
        elif any(keyword in error_str for keyword in ['content', 'audit', 'filter', 'sensitive']):
            return "content_filter"
        elif any(keyword in error_str for keyword in ['rate limit', 'quota', '429']):
            return "rate_limit"
        elif any(keyword in error_str for keyword in ['format', 'parse', 'json']):
            return "format_error"
        elif any(keyword in error_str for keyword in ['llm', 'ai', 'model']) and 'error' in error_str:
            return "llm_error"
        elif 'value' in error_type and 'empty' in error_str:
            return "empty_response"
        else:
            return "unknown"

    def _requires_human_intervention(self, exception_type: str, stage: str, attempt_count: int) -> bool:
        """判断是否需要人工干预"""
        # 高优先级异常类型
        critical_exceptions = ["content_filter", "rate_limit", "llm_error"]

        # 如果是严重异常类型，立即需要人工干预
        if exception_type in critical_exceptions:
            return True

        # 如果是多次重试仍然失败，需要人工干预
        if attempt_count >= 3:
            return True

        # 发言阶段的网络错误可能需要人工干预
        if stage == "speaking" and exception_type == "network":
            return True

        # 其他情况暂时不需要人工干预
        return False

    def _get_intervention_suggestions(self, exception_type: str, stage: str, agent_name: str) -> List[str]:
        """获取人工干预建议"""
        suggestions = []

        if exception_type == "content_filter":
            suggestions.extend([
                f"检查智能体 {agent_name} 的发言内容是否符合内容政策",
                "考虑调整讨论主题或重新定义智能体角色",
                "验证LLM服务的安全设置"
            ])
        elif exception_type == "rate_limit":
            suggestions.extend([
                "检查API使用配额和限制",
                f"考虑为智能体 {agent_name} 单独配置API密钥",
                "实现更智能的请求频率控制"
            ])
        elif exception_type == "network":
            suggestions.extend([
                "检查网络连接稳定性",
                "考虑使用备用LLM服务",
                f"检查智能体 {agent_name} 的网络配置"
            ])
        elif exception_type == "timeout":
            suggestions.extend([
                f"为智能体 {agent_name} 调整超时设置",
                "考虑使用更快的LLM模型",
                "简化智能体的思考和发言任务"
            ])
        elif exception_type == "llm_error":
            suggestions.extend([
                "检查LLM服务状态",
                f"重新初始化智能体 {agent_name}",
                "考虑切换到备用LLM提供商"
            ])
        elif exception_type == "format_error":
            suggestions.extend([
                f"检查智能体 {agent_name} 的输出格式要求",
                "更新智能体的提示词以确保格式正确",
                "实现更健壮的响应解析逻辑"
            ])

        if stage == "thinking" and len(suggestions) == 0:
            suggestions.append(f"检查智能体 {agent_name} 的思考过程逻辑")

        if stage == "speaking" and len(suggestions) == 0:
            suggestions.append(f"检查智能体 {agent_name} 的发言生成逻辑")

        return suggestions

    def _generate_exception_report(self, exception_summary: Dict[str, Any]) -> str:
        """生成异常状态报告"""
        total_exceptions = exception_summary["total_exceptions"]
        unresolved = exception_summary["unresolved_exceptions"]
        human_intervention = exception_summary["human_intervention_required"]

        report = f"📊 异常状态报告\n"
        report += f"总异常数: {total_exceptions}\n"
        report += f"未解决异常: {unresolved}\n"
        report += f"需要人工干预: {human_intervention}\n\n"

        if exception_summary["exceptions_by_type"]:
            report += "异常类型分布:\n"
            for ex_type, count in exception_summary["exceptions_by_type"].items():
                report += f"  • {ex_type}: {count} 次\n"

        if exception_summary["exceptions_by_agent"]:
            report += "\n智能体异常统计:\n"
            for agent, count in exception_summary["exceptions_by_agent"].items():
                health_status = exception_summary["agent_health_status"].get(agent, {}).get("health_status", "unknown")
                status_emoji = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴"}.get(health_status, "⚪")
                report += f"  • {agent}: {count} 次 {status_emoji}\n"

        if human_intervention > 0:
            report += f"\n⚠️ 发现 {human_intervention} 个需要人工干预的异常，请及时处理！"

        return report

    def get_exception_summary(self) -> Dict[str, Any]:
        """获取当前讨论的异常汇总"""
        return self.exception_context.get_exception_summary(self.discussion_id)

    def get_recent_exceptions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的异常记录"""
        return self.exception_context.get_recent_exceptions(limit)

    def export_exception_report(self) -> Dict[str, Any]:
        """导出异常报告"""
        summary = self.get_exception_summary()
        recent_exceptions = self.get_recent_exceptions(20)

        return {
            "discussion_id": self.discussion_id,
            "discussion_topic": self.discussion_topic,
            "total_rounds": len(self.discussion_rounds),
            "participants": self.participants,
            "exception_summary": summary,
            "recent_exceptions": recent_exceptions,
            "generated_at": datetime.now().isoformat()
        }

    def _extract_key_insights(self) -> List[str]:
        """提取关键洞察"""
        insights = []
        consensus_status = self.consensus_tracker.get_consensus_status()

        for cp in consensus_status.get("strong_consensus_points", []):
            insights.append(cp["content"])

        return insights

    def _generate_action_recommendations(self) -> List[str]:
        """生成行动建议"""
        recommendations = []
        
        try:
            consensus_report = self.consensus_tracker.generate_consensus_report()
            
            # 优先使用 recommendations 字段
            if "recommendations" in consensus_report:
                recs = consensus_report["recommendations"]
                if isinstance(recs, list):
                    recommendations.extend(recs)
                elif isinstance(recs, str):
                    recommendations.append(recs)
            
            # 如果没有，基于共识点生成建议
            if not recommendations:
                strong_points = consensus_report.get("strong_consensus_points", [])
                for point in strong_points[:5]:  # 最多5条
                    content = point.get("content", "") if isinstance(point, dict) else str(point)
                    if content:
                        recommendations.append(f"落实共识: {content}")
            
            # 基于分歧点生成建议
            divergences = consensus_report.get("intense_divergences", [])
            for div in divergences[:3]:  # 最多3条
                content = div.get("content", "") if isinstance(div, dict) else str(div)
                if content:
                    recommendations.append(f"需进一步讨论: {content}")
                    
        except Exception as e:
            logger.warning(f"生成行动建议失败: {e}")
            recommendations.append("建议继续深入讨论以达成更多共识")
        
        return recommendations if recommendations else ["暂无具体行动建议"]

    def _generate_discussion_summary(self) -> str:
        """生成讨论总结"""
        total_rounds = len(self.discussion_rounds)
        total_speeches = sum(len(r.speeches) for r in self.discussion_rounds)

        return f"本次圆桌讨论进行了{total_rounds}轮，共有{total_speeches}条发言，参与者包括{len(self.agents)}个角色。"

    def get_discussion_status(self) -> Dict[str, Any]:
        """获取讨论状态"""
        return {
            "status": self.discussion_status,
            "topic": self.discussion_topic,
            "rounds_completed": len(self.discussion_rounds),
            "participants": list(self.agents.keys()),
            "consensus_level": self.consensus_tracker.calculate_overall_consensus()["overall_level"]
        }

    def export_discussion_data(self) -> str:
        """
        导出讨论数据

        Returns:
            JSON格式的讨论数据
        """
        data = {
            "discussion_topic": self.discussion_topic,
            "status": self.discussion_status,
            "rounds": [r.to_dict() for r in self.discussion_rounds],
            "agents": {name: agent.get_status() for name, agent in self.agents.items()},
            "consensus_data": self.consensus_tracker.export_data(),
            "topic_profile_data": self.topic_profiler.export_profiles(),
            "exported_at": datetime.now().isoformat()
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _check_and_handle_conflicts(self, round_number: int) -> Generator[Dict[str, Any], None, None]:
        """
        检查并处理冲突
        
        在每轮讨论结束后调用，自动检测并处理需要干预的冲突。
        
        Args:
            round_number: 当前轮次
            
        Yields:
            冲突检测和处理的状态更新
        """
        try:
            # 从 consensus_tracker 获取冲突检测结果
            for step in self.consensus_tracker.check_and_handle_conflicts(round_number):
                # 转换步骤格式以适应讨论流程
                if step.get("step") == "conflicts_detected":
                    conflict_count = step.get("count", 0)
                    if conflict_count > 0:
                        yield {
                            "step": "conflict_check_result",
                            "conflicts_found": conflict_count,
                            "message": f"⚠️ 检测到 {conflict_count} 个需要处理的冲突",
                            "alerts": step.get("alerts", [])
                        }
                    else:
                        yield {
                            "step": "conflict_check_result",
                            "conflicts_found": 0,
                            "message": "✅ 未检测到需要立即处理的冲突"
                        }
                
                elif step.get("step") == "conflict_acknowledged":
                    yield {
                        "step": "conflict_resolution_starting",
                        "divergence_id": step.get("divergence_id"),
                        "strategy": step.get("strategy"),
                        "message": f"🛠️ 启动冲突解决流程: {step.get('strategy')}"
                    }
                
                elif step.get("step") == "resolution_started":
                    yield {
                        "step": "conflict_resolution_in_progress",
                        "session_id": step.get("session_id"),
                        "strategy": step.get("strategy"),
                        "message": f"🔄 正在执行 {step.get('strategy')} 策略..."
                    }
                
                elif step.get("step") == "resolution_completed":
                    success = step.get("success", False)
                    yield {
                        "step": "conflict_resolution_result",
                        "success": success,
                        "outcome": step.get("outcome"),
                        "new_consensus_count": step.get("new_consensus_count", 0),
                        "message": "✅ 冲突解决成功" if success else "⚠️ 冲突部分解决"
                    }
                
                elif step.get("step") == "resolution_escalated":
                    yield {
                        "step": "conflict_resolution_escalated",
                        "new_strategy": step.get("new_strategy"),
                        "message": f"🔼 升级到新策略: {step.get('new_strategy')}"
                    }
                
                elif step.get("step") == "resolution_failed":
                    yield {
                        "step": "conflict_resolution_failed",
                        "session_id": step.get("session_id"),
                        "message": f"❌ 冲突解决失败: {step.get('message', '无法解决')}"
                    }
                
                else:
                    # 传递其他步骤
                    yield step
                    
        except Exception as e:
            logger.error(f"冲突检查失败: {str(e)}")
            yield {
                "step": "conflict_check_error",
                "error": str(e),
                "message": f"⚠️ 冲突检查过程中发生错误: {str(e)}"
            }

    def _handle_urgent_conflict(self, alert_data: Dict[str, Any]
                                ) -> Generator[Dict[str, Any], None, None]:
        """
        处理紧急冲突
        
        当检测到高优先级冲突时调用。
        
        Args:
            alert_data: 冲突警报数据
            
        Yields:
            冲突处理过程的状态更新
        """
        divergence_id = alert_data.get("divergence_id")
        strategy = alert_data.get("recommended_strategy")
        
        yield {
            "step": "urgent_conflict_detected",
            "alert": alert_data,
            "message": f"🚨 检测到紧急冲突，启动 {strategy} 解决流程"
        }
        
        # 启动解决流程
        session_id = self.consensus_tracker.start_conflict_resolution(
            divergence_id, 
            strategy
        )
        
        if not session_id:
            yield {
                "step": "urgent_conflict_error",
                "error": "无法启动解决流程",
                "divergence_id": divergence_id
            }
            return
        
        yield {
            "step": "urgent_conflict_resolution_started",
            "session_id": session_id,
            "strategy": strategy,
            "message": f"✅ 解决会话已启动 (ID: {session_id})"
        }

    def get_conflict_resolution_status(self) -> Dict[str, Any]:
        """
        获取冲突解决状态
        
        Returns:
            冲突解决的详细状态信息
        """
        return self.consensus_tracker.get_conflict_resolution_status()

    def get_pending_conflicts(self) -> List[Dict[str, Any]]:
        """
        获取待处理的冲突列表
        
        Returns:
            待处理的冲突警报列表
        """
        return self.consensus_tracker.get_pending_conflicts()

    def start_manual_conflict_resolution(self, divergence_id: str,
                                          strategy: str = None
                                         ) -> Generator[Dict[str, Any], None, None]:
        """
        手动启动冲突解决
        
        Args:
            divergence_id: 分歧ID
            strategy: 策略名称（可选）
            
        Yields:
            解决过程的状态更新
        """
        from ..tools.consensus_tracker import ConflictResolutionStrategy
        
        strategy_enum = None
        if strategy:
            try:
                strategy_enum = ConflictResolutionStrategy(strategy)
            except ValueError:
                yield {
                    "step": "error",
                    "message": f"无效的策略: {strategy}"
                }
                return
        
        yield {
            "step": "manual_resolution_starting",
            "divergence_id": divergence_id,
            "strategy": strategy or "auto",
            "message": f"🛠️ 手动启动冲突解决: {divergence_id}"
        }
        
        session_id = self.consensus_tracker.start_conflict_resolution(
            divergence_id, strategy_enum
        )
        
        if session_id:
            yield {
                "step": "manual_resolution_started",
                "session_id": session_id,
                "message": f"✅ 解决会话已创建: {session_id}"
            }
        else:
            yield {
                "step": "manual_resolution_failed",
                "divergence_id": divergence_id,
                "message": f"❌ 无法创建解决会话"
            }

