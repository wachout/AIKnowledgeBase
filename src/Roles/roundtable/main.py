"""
圆桌讨论系统主类模块

包含 RoundtableDiscussion 主类，负责协调整个圆桌讨论流程。
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Generator, TYPE_CHECKING

# 导入本包内模块
from .communication import MessageBus, CommunicationProtocol
from .dialogue import FreeDiscussionCoordinator
from .interaction_mode import InteractionModeManager
from .state_management import StateManager
from .exception_context import AgentExceptionContext
from .discussion_round import DiscussionRound

# 导入项目内其他模块
from ..tools.topic_profiler import TopicProfiler, TaskAnalysis
from ..tools.consensus_tracker import ConsensusTracker
from ..tools.tool_manager import ToolManager
from ..tools.knowledge_search_tool import KnowledgeSearchTool
from ..tools.web_search_tool import WebSearchTool
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
from ..personnel.synthesizer import Synthesizer
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
        
        # 初始化自由讨论协调器和交互模式管理器
        self.free_discussion_coordinator = FreeDiscussionCoordinator(
            self.message_bus, self.communication_protocol
        )
        self.interaction_mode_manager = InteractionModeManager(self)

        # 智能体实例
        self.agents: Dict[str, BaseAgent] = {}
        self.discussion_rounds: List[DiscussionRound] = []
        self.current_round: Optional[DiscussionRound] = None

        # 讨论状态
        self.discussion_topic = ""
        self.discussion_status = "idle"  # idle, analyzing, active, paused, completed
        self.participants = []
        self.discussion_history = []

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
        self.tool_manager.register_tool(DataAnalysisTool())
        self.tool_manager.register_tool(CommunicationTool())
        
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
        if role_type in ["scholar", "expert", "domain_expert"]:
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

            # 步骤1: 学者智能体分析任务
            yield {
                "step": "init_start",
                "message": "🎭 正在初始化圆桌讨论系统...",
                "progress": "开始"
            }

            yield {
                "step": "scholar_analysis",
                "message": "📚 学者智能体正在分析您的任务...",
                "progress": "任务分析中"
            }

            scholar = Scholar(llm_instance=self.llm_instance)
            self.agents["scholar"] = scholar
            if hasattr(scholar, 'set_communication_system'):
                scholar.set_communication_system(self.message_bus, self.communication_protocol)
            self._setup_agent_tools_and_skills(scholar, "scholar")

            task_analysis = scholar.analyze_task(user_task)
            print(f"📚 学者分析完成: {task_analysis}")

            # 将学者分析结果转换为 TaskAnalysis 对象
            task_analysis_obj = self._convert_scholar_result_to_task_analysis(task_analysis, user_task)

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

            # 确保至少创建了基础智能体
            if len(self.agents) == 0:
                logger.warning("没有创建任何智能体，创建基础智能体")
                # 创建基础智能体
                try:
                    moderator = Moderator(llm_instance=self.llm_instance)
                    self.agents["moderator"] = moderator
                    facilitator = Facilitator(llm_instance=self.llm_instance)
                    self.agents["facilitator"] = facilitator
                    synthesizer = Synthesizer(llm_instance=self.llm_instance)
                    self.agents["synthesizer"] = synthesizer

                    # 设置通信系统和工具/技能
                    for agent_name, agent in [("moderator", moderator), ("facilitator", facilitator), ("synthesizer", synthesizer)]:
                        if hasattr(agent, 'set_communication_system'):
                            agent.set_communication_system(self.message_bus, self.communication_protocol)
                        self._setup_agent_tools_and_skills(agent, agent_name)
                except Exception as e:
                    logger.error(f"创建基础智能体失败: {str(e)}", exc_info=True)
                    raise
            else:
                # 确保至少有 facilitator 和 synthesizer
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
                
                if "synthesizer" not in self.agents:
                    try:
                        synthesizer = Synthesizer(llm_instance=self.llm_instance)
                        self.agents["synthesizer"] = synthesizer
                        if hasattr(synthesizer, 'set_communication_system'):
                            synthesizer.set_communication_system(self.message_bus, self.communication_protocol)
                        self._setup_agent_tools_and_skills(synthesizer, "synthesizer")
                        logger.info("补充创建 synthesizer 智能体")
                    except Exception as e:
                        logger.error(f"创建 synthesizer 失败: {str(e)}")

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
            # 步骤6: 协调者安排发言顺序
            facilitator = self.agents.get("facilitator")
            if facilitator:
                coordination = facilitator.coordinate_round(
                    discussion_context={"topic": self.discussion_topic, "round": round_number},
                    previous_speeches=self._get_recent_speeches(5),
                    consensus_points=self._get_consensus_points(),
                    divergence_points=self._get_divergence_points()
                )

                current_round.coordination_notes.append(coordination)
                yield {"step": "coordination", "content": coordination}

            # 确定发言顺序（可以根据协调结果调整）
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

            # 每个角色发言
            for speaker_name in speaking_order:
                logger.info(f"开始处理智能体发言: {speaker_name}")
                speaker = self.agents.get(speaker_name)
                if not speaker:
                    logger.warning(f"智能体 {speaker_name} 不存在，跳过")
                    continue

                try:
                    logger.info(f"为智能体 {speaker_name} 生成 speech_start 步骤")
                    yield {"step": "speech_start", "speaker": speaker_name}

                    # 智能体思考和发言（带重试机制）
                    context = self._get_discussion_context()
                    topic = context.get("topic", self.discussion_topic)
                    previous_speeches = self._get_recent_speeches(10)
                    
                    # ⭐ 新增：获取针对当前专家的质疑（用于多轮讨论时回应质疑）
                    my_challenges = self._get_unanswered_challenges(speaker_name, round_number)
                    if my_challenges:
                        context['my_challenges'] = my_challenges
                        context['has_pending_challenges'] = True
                        logger.info(f"📝 {speaker_name} 有 {len(my_challenges)} 条待回应的质疑")
                    else:
                        context['my_challenges'] = []
                        context['has_pending_challenges'] = False

                    logger.info(f"智能体 {speaker_name} 开始思考和发言，主题: {topic}")

                    # 实现发言重试机制（带详细异常上下文记录）
                    speech_result = None
                    thinking_result = None
                    max_speech_retries = 2  # 最多重试2次
                    thinking_success = False
                    speech_success = False

                    # 构建上下文信息，用于异常记录
                    exception_context_info = {
                        "discussion_topic": topic,
                        "round_number": round_number,
                        "speaker_order": list(speaking_order),
                        "speaker_position": speaking_order.index(speaker_name),
                        "previous_speeches_count": len(previous_speeches),
                        "agent_role": speaker.role_definition,
                        "agent_skills": speaker.professional_skills,
                        "agent_working_style": speaker.working_style.value
                    }

                    for speech_attempt in range(max_speech_retries + 1):  # 包括初始尝试
                        current_attempt = speech_attempt + 1

                        # 可选：使用 AgentScope 统一执行该智能体的 think+speak（第一层）
                        if current_attempt == 1 and get_agentscope_enabled() and is_agentscope_available():
                            if not hasattr(self, '_agentscope_adapters') or self._agentscope_adapters is None:
                                self._agentscope_adapters = create_roundtable_agents_agentscope(self.agents, use_memory=True)
                            if speaker_name in getattr(self, '_agentscope_adapters', {}):
                                tr, sr = run_agent_reply_sync(
                                    self._agentscope_adapters[speaker_name], topic, context, previous_speeches
                                )
                                if tr is not None and sr is not None and (sr.get("content") or "").strip():
                                    thinking_result, speech_result = tr, sr
                                    thinking_success, speech_success = True, True
                                    logger.info(f"✅ 智能体 {speaker_name} 通过 AgentScope 完成思考与发言")
                                    break

                        # === 思考阶段 ===
                        if not thinking_success:
                            try:
                                logger.info(f"智能体 {speaker_name} 第{current_attempt}次尝试 - 思考阶段")
                                thinking_result = speaker.think(topic, context)
                                thinking_success = True
                                logger.info(f"✅ 智能体 {speaker_name} 思考成功")

                            except Exception as e:
                                error_msg = str(e)
                                exception_type = self._classify_exception(e)
                                import traceback
                                stack_trace = traceback.format_exc()

                                # 记录思考阶段异常
                                requires_intervention = self._requires_human_intervention(exception_type, "thinking", current_attempt)
                                intervention_suggestions = self._get_intervention_suggestions(exception_type, "thinking", speaker_name)

                                # 获取 LLM 请求信息（如果可用）
                                llm_request_info = {
                                    "prompt_topic": topic,
                                    "context_keys": list(context.keys()) if context else [],
                                    "agent_type": type(speaker).__name__
                                }

                                self.exception_context.record_exception(
                                    discussion_id=self.discussion_id,
                                    round_number=round_number,
                                    speaker_name=speaker_name,
                                    exception_type=exception_type,
                                    error_message=error_msg,
                                    stage="thinking",
                                    attempt_count=current_attempt,
                                    context_info=exception_context_info,
                                    requires_human_intervention=requires_intervention,
                                    intervention_suggestions=intervention_suggestions,
                                    llm_request_info=llm_request_info,
                                    stack_trace=stack_trace,
                                    recovery_action="retry" if current_attempt <= max_speech_retries else "fallback"
                                )

                                if current_attempt <= max_speech_retries:
                                    retry_delay = current_attempt * 2
                                    logger.info(f"⏳ 思考失败，等待 {retry_delay} 秒后重试...")
                                    # 发送重试通知给用户
                                    yield {
                                        "step": "retry_notification",
                                        "speaker": speaker_name,
                                        "stage": "thinking",
                                        "attempt": current_attempt,
                                        "max_attempts": max_speech_retries + 1,
                                        "error_type": exception_type,
                                        "error_message": error_msg,
                                        "retry_delay": retry_delay,
                                        "message": f"⚠️ {speaker_name} 思考失败 ({exception_type})\n第 {current_attempt}/{max_speech_retries + 1} 次尝试\n{retry_delay} 秒后重试..."
                                    }
                                    import time
                                    time.sleep(retry_delay)
                                    continue
                                else:
                                    # 思考失败，创建后备思考结果
                                    thinking_result = {
                                        "raw_response": f"{speaker_name}的思考过程因多次失败而被简化。",
                                        "error": error_msg,
                                        "error_type": exception_type,
                                        "is_fallback": True,
                                        "stack_trace": stack_trace
                                    }
                                    logger.error(f"❌ 智能体 {speaker_name} 思考失败，已达到最大重试次数")
                                    # 发送失败通知
                                    yield {
                                        "step": "stage_failed",
                                        "speaker": speaker_name,
                                        "stage": "thinking",
                                        "error_type": exception_type,
                                        "error_message": error_msg,
                                        "requires_intervention": requires_intervention,
                                        "intervention_suggestions": intervention_suggestions,
                                        "message": f"❌ {speaker_name} 思考阶段失败\n错误类型: {exception_type}\n是否需要人工干预: {'是' if requires_intervention else '否'}"
                                    }

                        # === 发言阶段 ===
                        if thinking_success:
                            try:
                                logger.info(f"智能体 {speaker_name} 第{current_attempt}次尝试 - 发言阶段")
                                speech_result = speaker.speak(context, previous_speeches)

                                # 检查发言结果是否有效
                                if speech_result and speech_result.get('content') and speech_result.get('content').strip():
                                    speech_success = True
                                    logger.info(f"✅ 智能体 {speaker_name} 发言成功")
                                    break  # 发言成功，跳出重试循环
                                else:
                                    # 发言内容为空，当作异常处理
                                    raise ValueError("发言内容为空")

                            except Exception as e:
                                error_msg = str(e)
                                exception_type = self._classify_exception(e)
                                import traceback
                                stack_trace = traceback.format_exc()

                                # 记录发言阶段异常
                                requires_intervention = self._requires_human_intervention(exception_type, "speaking", current_attempt)
                                intervention_suggestions = self._get_intervention_suggestions(exception_type, "speaking", speaker_name)

                                # 获取 LLM 请求信息
                                llm_request_info = {
                                    "prompt_topic": topic,
                                    "context_keys": list(context.keys()) if context else [],
                                    "previous_speeches_count": len(previous_speeches),
                                    "agent_type": type(speaker).__name__
                                }

                                self.exception_context.record_exception(
                                    discussion_id=self.discussion_id,
                                    round_number=round_number,
                                    speaker_name=speaker_name,
                                    exception_type=exception_type,
                                    error_message=error_msg,
                                    stage="speaking",
                                    attempt_count=current_attempt,
                                    context_info=exception_context_info,
                                    requires_human_intervention=requires_intervention,
                                    intervention_suggestions=intervention_suggestions,
                                    llm_request_info=llm_request_info,
                                    stack_trace=stack_trace,
                                    recovery_action="retry" if current_attempt <= max_speech_retries else "fallback"
                                )

                                if current_attempt <= max_speech_retries:
                                    retry_delay = current_attempt * 2
                                    logger.info(f"⏳ 发言失败，等待 {retry_delay} 秒后重试...")
                                    # 发送重试通知给用户
                                    yield {
                                        "step": "retry_notification",
                                        "speaker": speaker_name,
                                        "stage": "speaking",
                                        "attempt": current_attempt,
                                        "max_attempts": max_speech_retries + 1,
                                        "error_type": exception_type,
                                        "error_message": error_msg,
                                        "retry_delay": retry_delay,
                                        "message": f"⚠️ {speaker_name} 发言失败 ({exception_type})\n第 {current_attempt}/{max_speech_retries + 1} 次尝试\n{retry_delay} 秒后重试..."
                                    }
                                    import time
                                    time.sleep(retry_delay)
                                    continue
                                else:
                                    # 发言失败，创建后备发言内容
                                    speech_result = {
                                        "agent_name": speaker_name,
                                        "role": speaker.role_definition,
                                        "content": f"{speaker_name}经过多次尝试后仍无法正常发言，建议讨论继续进行，其他专家可以补充相关观点。",
                                        "timestamp": speaker._get_timestamp(),
                                        "working_style": speaker.working_style.value,
                                        "professional_skills": speaker.professional_skills,
                                        "is_fallback": True,
                                        "error": error_msg,
                                        "error_type": exception_type,
                                        "retry_count": current_attempt,
                                        "stack_trace": stack_trace
                                    }
                                    logger.error(f"❌ 智能体 {speaker_name} 发言失败，已达到最大重试次数")
                                    
                                    # 记录失败发言，以便后续手动重试
                                    last_exception = self.exception_context.exception_history[-1] if self.exception_context.exception_history else {}
                                    exception_id = last_exception.get("exception_id", "unknown")
                                    failed_speech_id = self.exception_context.record_failed_speech(
                                        discussion_id=self.discussion_id,
                                        round_number=round_number,
                                        speaker_name=speaker_name,
                                        stage="speaking",
                                        context=context,
                                        topic=topic,
                                        previous_speeches=previous_speeches,
                                        exception_id=exception_id
                                    )
                                    self.exception_context.add_to_retry_queue(failed_speech_id)
                                    
                                    # 发送失败通知
                                    yield {
                                        "step": "stage_failed",
                                        "speaker": speaker_name,
                                        "stage": "speaking",
                                        "error_type": exception_type,
                                        "error_message": error_msg,
                                        "requires_intervention": requires_intervention,
                                        "intervention_suggestions": intervention_suggestions,
                                        "failed_speech_id": failed_speech_id,
                                        "can_retry_later": True,
                                        "message": f"❌ {speaker_name} 发言阶段失败\n错误类型: {exception_type}\n是否需要人工干预: {'是' if requires_intervention else '否'}\n已加入重试队列: {failed_speech_id}"
                                    }

                    # 如果整个过程都失败了，确保有基本的后备结果
                    if not thinking_success and not speech_success:
                        thinking_result = thinking_result or {
                            "raw_response": f"{speaker_name}的思考和发言过程完全失败。",
                            "error": "Complete failure",
                            "is_fallback": True
                        }
                        speech_result = speech_result or {
                            "agent_name": speaker_name,
                            "role": speaker.role_definition,
                            "content": f"{speaker_name}由于系统错误无法参与本次讨论，建议跳过此智能体继续讨论。",
                            "timestamp": speaker._get_timestamp(),
                            "working_style": speaker.working_style.value,
                            "professional_skills": speaker.professional_skills,
                            "is_fallback": True,
                            "error": "Complete failure",
                            "retry_count": max_speech_retries + 1
                        }
                    
                    # 提取发言内容（speech_result 是字典）
                    speech_content = speech_result.get('content', '') if isinstance(speech_result, dict) else str(speech_result)
                    thinking_content = thinking_result.get('raw_response', '') if isinstance(thinking_result, dict) else str(thinking_result)
                    
                    # 如果发言内容为空，使用默认内容
                    if not speech_content or speech_content.strip() == '':
                        speech_content = f"{speaker_name} 就讨论主题发表了观点，但内容为空。"
                        logger.warning(f"智能体 {speaker_name} 的发言内容为空")
                    
                    # 保存发言到轮次记录
                    current_round.add_speech(speaker_name, speech_content, "expert_opinion")

                    yield {
                        "step": "speech",
                        "speaker": speaker_name,
                        "thinking": thinking_content,
                        "speech": speech_content
                    }

                    # 每个专家发言后：对应质疑者发言 → 专家根据质疑修订发言 → 循环两次
                    if "skeptic" in speaker_name.lower():
                        pass
                    elif hasattr(speaker, "revise_speech_after_skeptic"):
                        # 支持「质疑→专家修订」循环两次
                        context = self._get_discussion_context()
                        revision_cycles = 2
                        try:
                            for cycle in range(1, revision_cycles + 1):
                                # 质疑者针对当前版本发言提出质疑
                                skeptic_response = self._generate_skeptic_response(
                                    speaker_name, speech_content, current_round
                                )
                                if not skeptic_response:
                                    break
                                skeptic_name = skeptic_response.get("skeptic_name", f"skeptic_{speaker_name}")
                                question_content = skeptic_response.get("question_content", "").strip()
                                thinking_content = skeptic_response.get("thinking", "")
                                if not question_content:
                                    break
                                # yield 质疑者发言
                                yield {"step": "speech_start", "speaker": skeptic_name}
                                yield {
                                    "step": "speech",
                                    "speaker": skeptic_name,
                                    "thinking": thinking_content,
                                    "speech": question_content,
                                    "target_expert": speaker_name,
                                }
                                yield {"step": "speech_end", "speaker": skeptic_name}
                                # 专家根据质疑修订发言
                                revised_result = speaker.revise_speech_after_skeptic(
                                    speech_content,
                                    question_content,
                                    context,
                                    revision_round=cycle,
                                )
                                revised_content = (
                                    revised_result.get("content", "") if isinstance(revised_result, dict) else str(revised_result)
                                )
                                if not revised_content or not revised_content.strip():
                                    revised_content = speech_content
                                else:
                                    speech_content = revised_content
                                    current_round.add_speech(
                                        speaker_name,
                                        revised_content,
                                        "expert_revision",
                                    )
                                yield {"step": "speech_start", "speaker": speaker_name}
                                yield {
                                    "step": "speech",
                                    "speaker": speaker_name,
                                    "thinking": "",
                                    "speech": revised_content,
                                    "is_revision": True,
                                    "revision_round": cycle,
                                }
                                yield {"step": "speech_end", "speaker": speaker_name}
                        except Exception as e:
                            logger.error(f"质疑→修订循环失败 ({speaker_name}): {str(e)}", exc_info=True)
                    else:
                        # 无修订能力的角色：仅一次质疑
                        try:
                            skeptic_response = self._generate_skeptic_response(
                                speaker_name, speech_content, current_round
                            )
                            if skeptic_response:
                                skeptic_name = skeptic_response.get("skeptic_name", f"skeptic_{speaker_name}")
                                question_content = skeptic_response.get("question_content", "")
                                thinking_content = skeptic_response.get("thinking", "")
                                if question_content and question_content.strip():
                                    yield {"step": "speech_start", "speaker": skeptic_name}
                                    yield {
                                        "step": "speech",
                                        "speaker": skeptic_name,
                                        "thinking": thinking_content,
                                        "speech": question_content,
                                        "target_expert": speaker_name,
                                    }
                                    yield {"step": "speech_end", "speaker": skeptic_name}
                        except Exception as e:
                            logger.error(f"生成质疑者响应失败 ({speaker_name}): {str(e)}", exc_info=True)

                    yield {"step": "speech_end", "speaker": speaker_name}
                    
                except Exception as e:
                    logger.error(f"智能体 {speaker_name} 发言失败: {str(e)}", exc_info=True)
                    yield {
                        "step": "speech_error",
                        "speaker": speaker_name,
                        "error": str(e),
                        "message": f"⚠️ {speaker_name} 发言时出错: {str(e)}"
                    }
                    # 继续下一个智能体，不中断整个流程
                    continue

            # 步骤6.5: 深度讨论阶段 - 专家间直接交互
            yield from self._conduct_depth_discussion_phase(current_round, round_number)

            # 步骤7: 综合者整合观点
            logger.info("开始综合者整合观点")
            synthesizer = self.agents.get("synthesizer")
            if synthesizer:
                all_speeches = [s for round_obj in self.discussion_rounds for s in round_obj.speeches]
                logger.info(f"综合者将整合 {len(all_speeches)} 条发言")

                synthesis_result = synthesizer.synthesize_opinions(
                    opinions=self._extract_opinions_from_speeches(all_speeches),
                    discussion_context=self._get_discussion_context()
                )
                logger.info("综合者整合观点完成")
            else:
                synthesis_result = {"content": "综合者不可用"}
                logger.warning("综合者智能体不存在")

            # 提取综合内容
            synthesis_content = synthesis_result.get('synthesis_report', '') if isinstance(synthesis_result, dict) else str(synthesis_result)
            if not synthesis_content and isinstance(synthesis_result, dict):
                synthesis_content = synthesis_result.get('content', str(synthesis_result))

            current_round.add_speech("synthesizer", synthesis_content, "synthesis")
            yield {"step": "synthesis", "content": {"synthesis_result": synthesis_content}}

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
        """创建角色智能体（流式返回）"""
        llm = self.llm_instance

        # 主持人
        moderator = Moderator(llm_instance=llm)
        self.agents["moderator"] = moderator
        if hasattr(moderator, 'set_communication_system'):
            moderator.set_communication_system(self.message_bus, self.communication_protocol)
        self._setup_agent_tools_and_skills(moderator, "moderator")
        yield {
            "step": "agent_created",
            "agent_name": "moderator",
            "agent_role": "主持人",
            "message": "🎙️ 创建主持人智能体",
            "description": "控制议程、引导讨论",
            "progress": f"创建智能体: 主持人",
            "agent_config": moderator.to_config_dict() if hasattr(moderator, 'to_config_dict') else None
        }

        # 协调者
        facilitator = Facilitator(llm_instance=llm)
        self.agents["facilitator"] = facilitator
        if hasattr(facilitator, 'set_communication_system'):
            facilitator.set_communication_system(self.message_bus, self.communication_protocol)
        self._setup_agent_tools_and_skills(facilitator, "facilitator")
        yield {
            "step": "agent_created",
            "agent_name": "facilitator",
            "agent_role": "协调者",
            "message": "👨‍⚖️ 创建协调者智能体",
            "description": "促进和谐讨论、沟通协调、冲突解决",
            "progress": f"创建智能体: 协调者",
            "agent_config": facilitator.to_config_dict() if hasattr(facilitator, 'to_config_dict') else None
        }

        # 综合者
        synthesizer = Synthesizer(llm_instance=llm)
        self.agents["synthesizer"] = synthesizer
        if hasattr(synthesizer, 'set_communication_system'):
            synthesizer.set_communication_system(self.message_bus, self.communication_protocol)
        self._setup_agent_tools_and_skills(synthesizer, "synthesizer")
        yield {
            "step": "agent_created",
            "agent_name": "synthesizer",
            "agent_role": "综合者",
            "message": "🔄 创建综合者智能体",
            "description": "整合各方观点、系统思维、方案比较",
            "progress": f"创建智能体: 综合者",
            "agent_config": synthesizer.to_config_dict() if hasattr(synthesizer, 'to_config_dict') else None
        }

        # 数据分析师
        data_analyst = DataAnalyst(llm_instance=llm)
        self.agents["data_analyst"] = data_analyst
        if hasattr(data_analyst, 'set_communication_system'):
            data_analyst.set_communication_system(self.message_bus, self.communication_protocol)
        self._setup_agent_tools_and_skills(data_analyst, "data_analyst")
        yield {
            "step": "agent_created",
            "agent_name": "data_analyst",
            "agent_role": "数据分析师",
            "message": "📊 创建数据分析师智能体",
            "description": "数据支撑分析、可视化、数据洞察",
            "progress": f"创建智能体: 数据分析师",
            "agent_config": data_analyst.to_config_dict() if hasattr(data_analyst, 'to_config_dict') else None
        }

        # 风险管理者
        risk_manager = RiskManager(llm_instance=llm)
        self.agents["risk_manager"] = risk_manager
        if hasattr(risk_manager, 'set_communication_system'):
            risk_manager.set_communication_system(self.message_bus, self.communication_protocol)
        self._setup_agent_tools_and_skills(risk_manager, "risk_manager")
        yield {
            "step": "agent_created",
            "agent_name": "risk_manager",
            "agent_role": "风险管理者",
            "message": "⚠️ 创建风险管理者智能体",
            "description": "风险评估、识别、缓解建议",
            "progress": f"创建智能体: 风险管理者",
            "agent_config": risk_manager.to_config_dict() if hasattr(risk_manager, 'to_config_dict') else None
        }

        # 根据任务分析创建领域专家
        for i, role_info in enumerate(task_analysis.recommended_roles):
            role_name = role_info.get("role", "领域专家")
            # 清理角色名称，移除空格和特殊字符，用于生成 agent_name
            clean_role_name = role_name.lower().replace(' ', '_').replace('-', '_').replace('（', '').replace('）', '').replace('(', '').replace(')', '')
            agent_name = f"expert_{clean_role_name}"

            # 构建专家分析字典
            # 将优先级从英文转换为中文（如果必要）
            priority_map = {
                "high": "高",
                "medium": "中",
                "low": "低",
                "高": "高",
                "中": "中",
                "低": "低"
            }
            priority = role_info.get("priority", "medium")
            priority_cn = priority_map.get(priority.lower() if isinstance(priority, str) else "中", "中")
            
            expert_analysis = {
                "domain": role_name,
                "expertise_area": role_info.get("reason", role_name),
                "priority": priority_cn
            }
            
            expert = DomainExpert.create_from_analysis(
                expert_analysis=expert_analysis,
                llm_instance=llm
            )
            self.agents[agent_name] = expert
            if hasattr(expert, 'set_communication_system'):
                expert.set_communication_system(self.message_bus, self.communication_protocol)
            self._setup_agent_tools_and_skills(expert, "domain_expert")
            
            # 为每个专家创建领域专家智能体
            yield {
                "step": "agent_created",
                "agent_name": agent_name,
                "agent_role": f"领域专家 - {role_name}",
                "message": f"🎓 创建{role_name}领域专家",
                "description": f"提供{role_name}领域的专业观点和深度分析",
                "progress": f"创建专家智能体: {role_name}",
                "agent_config": expert.to_config_dict() if hasattr(expert, 'to_config_dict') else None
            }

            # 为每个专家创建质疑者
            skeptic_name = f"skeptic_{agent_name}"

            # 使用专家对象创建质疑者，而不是字符串
            skeptic = Skeptic.create_for_expert(expert=expert, llm_instance=llm)
            self.agents[skeptic_name] = skeptic

            # 为智能体设置通信系统和工具/技能
            if hasattr(skeptic, 'set_communication_system'):
                skeptic.set_communication_system(self.message_bus, self.communication_protocol)
            self._setup_agent_tools_and_skills(skeptic, "skeptic")
            
            yield {
                "step": "agent_created",
                "agent_name": skeptic_name,
                "agent_role": f"质疑者 - {role_name}",
                "message": f"🔍 创建{role_name}质疑者",
                "description": f"对{role_name}专家的观点进行质疑和批判性审查",
                "progress": f"创建质疑者: {role_name}",
                "agent_config": skeptic.to_config_dict() if hasattr(skeptic, 'to_config_dict') else None
            }

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
                ("synthesizer", Synthesizer),
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

            # 设置参与者分析
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

    def _determine_speaking_order(self) -> List[str]:
        """确定发言顺序"""
        # 基本发言顺序：专家们先发言，然后是质疑者，最后是数据分析师和风险管理者
        order = []
        
        # 排除不需要发言的角色
        excluded_roles = {"scholar", "moderator"}  # synthesizer 需要在最后整合观点
        
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

        # 其他角色（数据分析师、风险管理者、协调者）
        other_roles = ["data_analyst", "risk_manager", "facilitator"]
        for role in other_roles:
            if role in self.agents and role not in excluded_roles:
                order.append(role)
        logger.info(f"其他角色: {[r for r in other_roles if r in self.agents]}")
        
        # 最后是综合者整合观点
        if "synthesizer" in self.agents:
            order.append("synthesizer")

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

    def _generate_skeptic_response(self, target_expert: str, expert_speech: str, current_round: DiscussionRound):
        """生成质疑者回应（使用标准化通信协议）"""
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

            # 让质疑者处理消息并生成质疑内容
            question_result = skeptic.question_expert(
                expert_opinion={
                    "content": expert_speech if isinstance(expert_speech, str) else expert_speech.get('content', ''),
                    "speaker": target_expert
                },
                context=self._get_discussion_context()
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
        """获取讨论上下文"""
        return {
            "topic": self.discussion_topic,
            "rounds_completed": len(self.discussion_rounds),
            "current_participants": list(self.agents.keys()),
            "consensus_status": self.consensus_tracker.get_consensus_status(),
            "recent_speeches": self._get_recent_speeches(10)
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

    def _conduct_depth_discussion_phase(self, current_round: DiscussionRound, round_number: int) -> Generator[Dict[str, Any], None, None]:
        """
        进行深度讨论阶段 - 专家间直接交互（增强版）

        Args:
            current_round: 当前轮次
            round_number: 轮次编号

        Yields:
            深度讨论过程的各个步骤结果
        """
        logger.info(f"开始第{round_number}轮深度讨论阶段")
        
        # 获取当前交互模式和建议的模式切换
        current_mode = self.interaction_mode_manager.current_mode
        
        # 构建上下文用于模式建议
        mode_context = {
            "divergence_count": len(self.consensus_tracker.divergence_points),
            "consensus_level": self.consensus_tracker.get_consensus_level() if hasattr(self.consensus_tracker, 'get_consensus_level') else 0.0,
            "expert_speech_count": len([s for s in current_round.speeches if s.get('role', '').startswith('expert')])
        }
        
        # 检查是否需要切换模式
        suggested_mode = self.interaction_mode_manager.suggest_mode_switch(mode_context)
        if suggested_mode and suggested_mode != current_mode:
            self.interaction_mode_manager.switch_mode(suggested_mode, f"基于讨论上下文自动切换")
            current_mode = suggested_mode
            
            yield {
                "step": "interaction_mode_switch",
                "round": round_number,
                "from_mode": self.interaction_mode_manager.mode_history[-1]["from_mode"] if self.interaction_mode_manager.mode_history else "structured",
                "to_mode": current_mode.value,
                "message": f"🔄 交互模式切换为: {self.interaction_mode_manager.get_mode_description(current_mode)}"
            }

        yield {
            "step": "depth_discussion_start",
            "round": round_number,
            "message": f"🎯 开始第{round_number}轮深度讨论阶段 - 专家间直接交互",
            "description": "专家们现在可以直接回应彼此的观点，进行更深入的讨论",
            "interaction_mode": current_mode.value,
            "allowed_interactions": self.interaction_mode_manager.get_allowed_interactions()
        }
        
        # 更新自由讨论协调器的智能体引用
        self.free_discussion_coordinator.set_agents(self.agents)

        try:
            # 获取所有专家智能体（排除主持人、协调者、综合者、质疑者等）
            expert_agents = {
                name: agent for name, agent in self.agents.items()
                if not any(role in name.lower() for role in ['moderator', 'facilitator', 'synthesizer', 'data_analyst', 'risk_manager', 'scholar']) and
                not name.startswith('skeptic_')
            }

            if not expert_agents:
                logger.warning("没有找到专家智能体，跳过深度讨论阶段")
                yield {
                    "step": "depth_discussion_skip",
                    "reason": "no_expert_agents",
                    "message": "⚠️ 未找到专家智能体，跳过深度讨论阶段"
                }
                return

            # 步骤1: 协调者发起深度讨论邀请
            facilitator = self.agents.get("facilitator")
            if facilitator:
                invitation = facilitator.initiate_depth_discussion(
                    expert_list=list(expert_agents.keys()),
                    discussion_context=self._get_discussion_context(),
                    previous_round=current_round
                )

                yield {
                    "step": "depth_discussion_invitation",
                    "content": invitation,
                    "participants": list(expert_agents.keys())
                }

                # 保存邀请到轮次记录
                current_round.add_speech("facilitator", invitation, "depth_discussion_invitation")

            # 步骤2: 专家间直接交互
            discussion_interactions = []
            max_interactions = min(len(expert_agents) * 2, 10)  # 最多交互次数
            interaction_count = 0
            discussion_quality_score = 0.0

            # 分析本轮发言，识别需要进一步讨论的观点
            round_speeches = current_round.speeches
            discussion_topics = self._identify_discussion_topics(round_speeches)

            # 设置讨论调控参数
            discussion_config = {
                "max_duration_minutes": 5,  # 最大持续时间（分钟）
                "min_interactions_per_topic": 2,  # 每个话题最少交互次数
                "max_interactions_per_topic": 4,  # 每个话题最多交互次数
                "quality_threshold": 0.6,  # 质量阈值
                "moderation_interval": 3  # 每3次交互进行一次调控检查
            }

            start_time = datetime.now()

            for topic_idx, topic in enumerate(discussion_topics[:3]):  # 最多讨论3个话题
                yield {
                    "step": "depth_discussion_topic",
                    "topic_index": topic_idx + 1,
                    "topic": topic,
                    "message": f"📋 讨论话题 {topic_idx + 1}: {topic['description']}",
                    "config": discussion_config
                }

                # 为每个话题进行专家间交互，包含调控逻辑
                topic_interactions = self._conduct_topic_discussion_with_moderation(
                    topic, expert_agents, round_number,
                    discussion_config, start_time
                )

                topic_quality_scores = []
                for interaction in topic_interactions:
                    yield interaction
                    discussion_interactions.append(interaction)
                    interaction_count += 1

                    # 评估交互质量
                    quality_score = self._assess_interaction_quality(interaction)
                    topic_quality_scores.append(quality_score)

                    # 定期进行调控检查
                    if interaction_count % discussion_config["moderation_interval"] == 0:
                        moderation_action = self._check_discussion_moderation(
                            discussion_interactions[-discussion_config["moderation_interval"]:],
                            discussion_config
                        )

                        if moderation_action:
                            yield moderation_action

                    # 检查是否需要提前结束讨论
                    elapsed_time = (datetime.now() - start_time).total_seconds() / 60
                    if elapsed_time > discussion_config["max_duration_minutes"]:
                        yield {
                            "step": "depth_discussion_timeout",
                            "message": f"⏰ 深度讨论已达到时间限制 ({discussion_config['max_duration_minutes']}分钟)，进入下一阶段",
                            "elapsed_minutes": elapsed_time
                        }
                        break

                    if interaction_count >= max_interactions:
                        break

                # 计算话题质量得分
                if topic_quality_scores:
                    topic_avg_quality = sum(topic_quality_scores) / len(topic_quality_scores)
                    discussion_quality_score = max(discussion_quality_score, topic_avg_quality)

                if interaction_count >= max_interactions:
                    break

            # 步骤2.5: 质量评估和调控总结
            quality_assessment = self._assess_discussion_quality(
                discussion_interactions, discussion_quality_score, discussion_config
            )

            if quality_assessment["needs_improvement"]:
                yield {
                    "step": "depth_discussion_quality_feedback",
                    "assessment": quality_assessment,
                    "message": "📊 深度讨论质量评估：发现需要改进的地方",
                    "suggestions": quality_assessment["suggestions"]
                }

            # 步骤3: 深度讨论总结
            if facilitator:
                depth_summary = facilitator.summarize_depth_discussion(
                    interactions=discussion_interactions,
                    discussion_context=self._get_discussion_context()
                )

                current_round.add_speech("facilitator", depth_summary, "depth_discussion_summary")

                yield {
                    "step": "depth_discussion_summary",
                    "content": depth_summary,
                    "total_interactions": interaction_count
                }

            yield {
                "step": "depth_discussion_complete",
                "round": round_number,
                "message": f"✅ 第{round_number}轮深度讨论阶段完成，共进行 {interaction_count} 次交互",
                "interactions": interaction_count
            }

        except Exception as e:
            logger.error(f"深度讨论阶段执行失败: {str(e)}", exc_info=True)
            yield {
                "step": "depth_discussion_error",
                "error": str(e),
                "message": f"⚠️ 深度讨论阶段出现错误: {str(e)}"
            }

    def _identify_discussion_topics(self, round_speeches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从本轮发言中识别需要进一步讨论的话题

        Args:
            round_speeches: 本轮发言列表

        Returns:
            需要讨论的话题列表
        """
        topics = []

        try:
            # 分析发言内容，识别分歧点和需要澄清的观点
            speech_contents = [speech.get('content', '') for speech in round_speeches
                             if speech.get('type') == 'expert_opinion']

            # 简单的启发式分析：寻找包含特定关键词的发言
            discussion_keywords = [
                '不同意', '反对', '质疑', '澄清', '进一步', '补充',
                'disagree', 'oppose', 'question', 'clarify', 'further', 'additional'
            ]

            for i, content in enumerate(speech_contents):
                speaker = round_speeches[i].get('speaker', f'专家{i+1}')

                # 检查是否包含讨论关键词
                if any(keyword in content.lower() for keyword in discussion_keywords):
                    topics.append({
                        "description": f"{speaker}的观点需要进一步讨论",
                        "initiator": speaker,
                        "content": content[:200] + "..." if len(content) > 200 else content,
                        "reason": "包含讨论关键词"
                    })

            # 如果没有找到足够的话题，添加通用话题
            if len(topics) < 2:
                topics.append({
                    "description": "专家们对解决方案的异同点",
                    "initiator": "system",
                    "content": "比较各专家提出的解决方案",
                    "reason": "通用讨论话题"
                })

        except Exception as e:
            logger.error(f"识别讨论话题失败: {str(e)}")
            # 返回默认话题
            topics = [{
                "description": "各专家观点的综合讨论",
                "initiator": "system",
                "content": "讨论各专家的观点和建议",
                "reason": "fallback_topic"
            }]

        return topics[:3]  # 最多返回3个话题

    def _conduct_topic_discussion_with_moderation(self, topic: Dict[str, Any],
                                                 expert_agents: Dict[str, 'BaseAgent'],
                                                 round_number: int,
                                                 config: Dict[str, Any],
                                                 start_time: datetime) -> Generator[Dict[str, Any], None, None]:
        """
        带调控的专家间话题讨论

        Args:
            topic: 讨论话题
            expert_agents: 专家智能体字典
            round_number: 轮次编号
            config: 讨论配置
            start_time: 开始时间

        Yields:
            讨论交互结果
        """
        interaction_count = 0
        conversation_id = str(uuid.uuid4())
        topic_start_time = datetime.now()

        try:
            # 选择相关专家
            relevant_experts = list(expert_agents.keys())[:min(4, len(expert_agents))]
            active_participants = set()  # 跟踪活跃参与者

            # 轮流让专家发言讨论这个话题
            for i, expert_name in enumerate(relevant_experts):
                if interaction_count >= config["max_interactions_per_topic"]:
                    break

                # 检查时间限制
                elapsed_topic_time = (datetime.now() - topic_start_time).total_seconds() / 60
                if elapsed_topic_time > config["max_duration_minutes"] / len(self._identify_discussion_topics([])):
                    break

                expert = expert_agents.get(expert_name)
                if not expert:
                    continue

                try:
                    # 生成专家对这个话题的深入讨论
                    discussion_response = self._generate_expert_topic_discussion(
                        expert, topic, round_number, conversation_id
                    )

                    if discussion_response and discussion_response.get('content'):
                        active_participants.add(expert_name)
                        interaction_count += 1

                        yield {
                            "step": "depth_discussion_interaction",
                            "speaker": expert_name,
                            "topic": topic['description'],
                            "content": discussion_response['content'],
                            "interaction_type": "topic_discussion",
                            "conversation_id": conversation_id,
                            "interaction_number": interaction_count
                        }

                        # 如果不是最后一个专家，让下一个专家回应
                        if i < len(relevant_experts) - 1 and interaction_count < config["max_interactions_per_topic"]:
                            next_expert_name = relevant_experts[i + 1]
                            next_expert = expert_agents.get(next_expert_name)

                            if next_expert:
                                response_discussion = self._generate_expert_response_discussion(
                                    next_expert, expert_name, discussion_response['content'],
                                    topic, round_number, conversation_id
                                )

                                if response_discussion and response_discussion.get('content'):
                                    active_participants.add(next_expert_name)
                                    interaction_count += 1

                                    yield {
                                        "step": "depth_discussion_interaction",
                                        "speaker": next_expert_name,
                                        "responding_to": expert_name,
                                        "topic": topic['description'],
                                        "content": response_discussion['content'],
                                        "interaction_type": "peer_response",
                                        "conversation_id": conversation_id,
                                        "interaction_number": interaction_count
                                    }

                except Exception as e:
                    logger.error(f"专家 {expert_name} 深度讨论失败: {str(e)}")
                    continue

            # 检查参与度
            participation_rate = len(active_participants) / len(relevant_experts) if relevant_experts else 0
            if participation_rate < 0.5:  # 少于50%专家参与
                yield {
                    "step": "depth_discussion_participation_warning",
                    "message": f"⚠️ 话题 '{topic['description']}' 参与度较低 ({participation_rate:.1%})",
                    "active_participants": list(active_participants),
                    "total_invited": len(relevant_experts)
                }

        except Exception as e:
            logger.error(f"带调控的话题讨论执行失败: {str(e)}")

    def _generate_expert_topic_discussion(self, expert: 'BaseAgent', topic: Dict[str, Any],
                                        round_number: int, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        生成专家对特定话题的深入讨论

        Args:
            expert: 专家智能体
            topic: 讨论话题
            round_number: 轮次编号
            conversation_id: 对话ID

        Returns:
            讨论内容
        """
        try:
            discussion_prompt = f"""作为{expert.role_definition}，请对以下话题进行深入讨论：

话题：{topic['description']}

相关内容：{topic.get('content', '无具体内容')}

请从您的专业角度出发，提供：
1. 对这个话题的分析和观点
2. 与其他专家观点的比较或回应
3. 可能的解决方案或建议

请保持建设性和专业性。"""

            # 使用专家的LLM进行推理
            response = expert.llm.invoke(discussion_prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            return {
                "content": content,
                "topic": topic['description'],
                "expert": expert.name,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"生成专家话题讨论失败 ({expert.name}): {str(e)}")
            return None

    def _generate_expert_response_discussion(self, expert: 'BaseAgent', target_expert: str,
                                           original_content: str, topic: Dict[str, Any],
                                           round_number: int, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        生成专家对其他专家观点的回应讨论

        Args:
            expert: 回应专家
            target_expert: 被回应的专家
            original_content: 原始讨论内容
            topic: 讨论话题
            round_number: 轮次编号
            conversation_id: 对话ID

        Returns:
            回应内容
        """
        try:
            response_prompt = f"""作为{expert.role_definition}，请回应{target_expert}的观点：

话题：{topic['description']}

{target_expert}的观点：
{original_content[:500]}...

请从您的专业角度出发：
1. 表达您对这个观点的理解
2. 指出同意或不同意的部分
3. 提供补充意见或建议
4. 寻求可能的共识点

请保持建设性和专业性。"""

            # 使用专家的LLM进行推理
            response = expert.llm.invoke(response_prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            return {
                "content": content,
                "responding_to": target_expert,
                "topic": topic['description'],
                "expert": expert.name,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"生成专家回应讨论失败 ({expert.name}): {str(e)}")
            return None

    def _assess_interaction_quality(self, interaction: Dict[str, Any]) -> float:
        """
        评估交互质量

        Args:
            interaction: 交互记录

        Returns:
            质量得分 (0.0-1.0)
        """
        try:
            content = interaction.get('content', '')
            if not content or len(content.strip()) < 50:
                return 0.3  # 内容太短

            # 简单的质量评估指标
            quality_indicators = [
                len(content) > 200,  # 有足够长度
                any(keyword in content.lower() for keyword in ['分析', '建议', '观点', '经验', '同意', '不同意']),  # 包含专业术语
                '?' in content or '？' in content,  # 包含问题
                any(word in content.lower() for word in ['因此', '所以', '因为', '由于', '根据']),  # 包含逻辑连接词
            ]

            quality_score = sum(quality_indicators) / len(quality_indicators)
            return min(1.0, quality_score + 0.2)  # 基础分数加成

        except Exception as e:
            logger.error(f"评估交互质量失败: {str(e)}")
            return 0.5  # 默认中等质量

    def _check_discussion_moderation(self, recent_interactions: List[Dict[str, Any]],
                                   config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        检查讨论是否需要调控

        Args:
            recent_interactions: 最近的交互记录
            config: 讨论配置

        Returns:
            调控行动（如果需要）
        """
        try:
            if not recent_interactions:
                return None

            # 检查是否重复内容过多
            contents = [interaction.get('content', '') for interaction in recent_interactions]
            unique_contents = set(content[:100] for content in contents if content)  # 取前100字符比较

            if len(unique_contents) < len(recent_interactions) * 0.6:  # 重复率过高
                return {
                    "step": "depth_discussion_moderation",
                    "action": "redirect_topic",
                    "message": "🔄 检测到讨论内容重复，建议转向新的讨论角度",
                    "reason": "content_repetition",
                    "suggestion": "请专家们从不同角度重新审视这个问题"
                }

            # 检查是否偏离主题
            topic_keywords = []
            for interaction in recent_interactions:
                topic = interaction.get('topic', '')
                # 提取关键词（简单实现）
                words = [word for word in topic.split() if len(word) > 1]
                topic_keywords.extend(words)

            off_topic_count = 0
            for interaction in recent_interactions:
                content = interaction.get('content', '').lower()
                topic_relevance = sum(1 for keyword in topic_keywords if keyword.lower() in content)
                if topic_relevance < len(topic_keywords) * 0.3:  # 相关性太低
                    off_topic_count += 1

            if off_topic_count > len(recent_interactions) * 0.5:  # 超过一半偏离主题
                return {
                    "step": "depth_discussion_moderation",
                    "action": "refocus_topic",
                    "message": "🎯 讨论似乎偏离了主题，建议回到核心问题",
                    "reason": "off_topic",
                    "suggestion": "请重新聚焦于原始话题"
                }

            return None

        except Exception as e:
            logger.error(f"检查讨论调控失败: {str(e)}")
            return None

    def _assess_discussion_quality(self, interactions: List[Dict[str, Any]],
                                 overall_quality: float, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估整个深度讨论阶段的质量

        Args:
            interactions: 所有交互记录
            overall_quality: 整体质量得分
            config: 讨论配置

        Returns:
            质量评估结果
        """
        try:
            assessment = {
                "overall_quality_score": overall_quality,
                "total_interactions": len(interactions),
                "needs_improvement": False,
                "strengths": [],
                "weaknesses": [],
                "suggestions": []
            }

            # 评估交互数量
            if len(interactions) < config.get("min_interactions_per_topic", 2) * 2:
                assessment["weaknesses"].append("交互次数不足")
                assessment["suggestions"].append("增加专家间的直接交流")
                assessment["needs_improvement"] = True

            # 评估质量得分
            if overall_quality < config["quality_threshold"]:
                assessment["weaknesses"].append("讨论质量有待提高")
                assessment["suggestions"].append("鼓励更深入的专业分析和建设性意见")
                assessment["needs_improvement"] = True
            else:
                assessment["strengths"].append("讨论质量良好")

            # 评估参与度
            speakers = set(interaction.get('speaker', '') for interaction in interactions)
            if len(speakers) < 3:  # 至少需要3个不同专家参与
                assessment["weaknesses"].append("参与专家数量不足")
                assessment["suggestions"].append("鼓励更多专家参与讨论")
                assessment["needs_improvement"] = True
            else:
                assessment["strengths"].append("参与度良好")

            # 评估交互多样性
            interaction_types = set(interaction.get('interaction_type', '') for interaction in interactions)
            if len(interaction_types) > 1:
                assessment["strengths"].append("交互形式多样")
            else:
                assessment["weaknesses"].append("交互形式较为单一")
                assessment["suggestions"].append("尝试不同类型的交流方式")

            return assessment

        except Exception as e:
            logger.error(f"评估讨论质量失败: {str(e)}")
            return {
                "overall_quality_score": 0.5,
                "total_interactions": len(interactions),
                "needs_improvement": True,
                "strengths": [],
                "weaknesses": ["评估过程出错"],
                "suggestions": ["需要人工检查讨论质量"]
            }
