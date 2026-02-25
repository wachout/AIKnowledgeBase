"""
Skills 注册与管理模块

提供智能体技能系统，支持技能注册、组合和执行。
"""

import logging
from typing import Dict, Any, List, Optional, Set, Callable, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from .tool_manager import ToolManager
    from .base_tool import ToolResult

logger = logging.getLogger(__name__)


# ============================================================================
# 技能类别
# ============================================================================

class SkillCategory(Enum):
    """技能类别"""
    RESEARCH = "research"           # 研究类
    ANALYSIS = "analysis"           # 分析类
    COMMUNICATION = "communication" # 沟通类
    REASONING = "reasoning"         # 推理类
    SYNTHESIS = "synthesis"         # 综合类
    VALIDATION = "validation"       # 验证类
    CUSTOM = "custom"               # 自定义


class SkillLevel(Enum):
    """技能级别"""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


# ============================================================================
# 技能执行上下文
# ============================================================================

@dataclass
class SkillContext:
    """技能执行上下文"""
    agent_name: str = ""
    query: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "query": self.query,
            "parameters": self.parameters,
            "history": self.history,
            "metadata": self.metadata
        }


@dataclass
class SkillResult:
    """技能执行结果"""
    success: bool
    data: Any = None
    error: str = ""
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    executed_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "tool_results": self.tool_results,
            "metadata": self.metadata,
            "executed_at": self.executed_at
        }


# ============================================================================
# 技能基类
# ============================================================================

class Skill(ABC):
    """
    技能基类

    每个技能可以组合多个工具完成特定任务。
    """

    def __init__(
        self,
        name: str,
        description: str,
        category: SkillCategory = SkillCategory.CUSTOM,
        level: SkillLevel = SkillLevel.BASIC,
        required_tools: List[str] = None,
        optional_tools: List[str] = None
    ):
        self.name = name
        self.description = description
        self.category = category
        self.level = level
        self.required_tools = required_tools or []
        self.optional_tools = optional_tools or []

        # 运行时属性
        self._tool_manager: Optional['ToolManager'] = None
        self.usage_count = 0
        self.success_count = 0
        self.created_at = datetime.now().isoformat()

    def bind_tool_manager(self, tool_manager: 'ToolManager'):
        """绑定工具管理器"""
        self._tool_manager = tool_manager

    def validate_tools(self) -> tuple:
        """验证必需工具是否可用"""
        if not self._tool_manager:
            return False, ["Tool manager not bound"]

        missing = []
        for tool_name in self.required_tools:
            if not self._tool_manager.get_tool(tool_name):
                missing.append(tool_name)

        return len(missing) == 0, missing

    @abstractmethod
    def execute(self, context: SkillContext) -> SkillResult:
        """
        执行技能

        Args:
            context: 执行上下文

        Returns:
            执行结果
        """
        pass

    def safe_execute(self, context: SkillContext) -> SkillResult:
        """安全执行技能（带验证）"""
        # 验证工具
        valid, missing = self.validate_tools()
        if not valid:
            return SkillResult(
                success=False,
                error=f"Missing required tools: {', '.join(missing)}"
            )

        # 执行技能
        self.usage_count += 1
        try:
            result = self.execute(context)
            if result.success:
                self.success_count += 1
            return result
        except Exception as e:
            logger.error(f"Skill execution error: {self.name}, {e}")
            return SkillResult(success=False, error=str(e))

    def get_info(self) -> Dict[str, Any]:
        """获取技能信息"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "level": self.level.value,
            "required_tools": self.required_tools,
            "optional_tools": self.optional_tools,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "success_rate": self.success_count / max(self.usage_count, 1)
        }

    def _execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Optional['ToolResult']:
        """执行工具"""
        if not self._tool_manager:
            return None
        return self._tool_manager.execute_tool(tool_name, parameters)


# ============================================================================
# 内置技能实现
# ============================================================================

class KnowledgeQuerySkill(Skill):
    """知识库查询技能"""

    def __init__(self):
        super().__init__(
            name="knowledge_query",
            description="在知识库中搜索信息并评估结果质量",
            category=SkillCategory.RESEARCH,
            level=SkillLevel.BASIC,
            required_tools=["knowledge_search"]
        )

    def execute(self, context: SkillContext) -> SkillResult:
        query = context.query or context.parameters.get("query", "")
        if not query:
            return SkillResult(success=False, error="Query is required")

        # 执行搜索
        search_result = self._execute_tool("knowledge_search", {
            "query": query,
            "limit": context.parameters.get("limit", 10),
            "knowledge_id": context.parameters.get("knowledge_id")
        })

        if not search_result or not search_result.success:
            return SkillResult(
                success=False,
                error=search_result.error if search_result else "Search failed",
                tool_results=[search_result.to_dict() if search_result else {}]
            )

        return SkillResult(
            success=True,
            data=search_result.data,
            tool_results=[search_result.to_dict()],
            metadata={
                "query": query,
                "quality_level": search_result.quality_assessment.quality_level
                if search_result.quality_assessment else "UNKNOWN"
            }
        )


class WebResearchSkill(Skill):
    """网络研究技能"""

    def __init__(self):
        super().__init__(
            name="web_research",
            description="在网络上搜索信息并评估来源可信度",
            category=SkillCategory.RESEARCH,
            level=SkillLevel.INTERMEDIATE,
            required_tools=["web_search"],
            optional_tools=["knowledge_search"]
        )

    def execute(self, context: SkillContext) -> SkillResult:
        query = context.query or context.parameters.get("query", "")
        if not query:
            return SkillResult(success=False, error="Query is required")

        tool_results = []

        # 先尝试知识库搜索
        kb_result = None
        if "knowledge_search" in [t for t in (self.optional_tools or [])]:
            kb_result = self._execute_tool("knowledge_search", {
                "query": query,
                "limit": 5
            })
            if kb_result:
                tool_results.append(kb_result.to_dict())

        # 执行网络搜索
        web_result = self._execute_tool("web_search", {
            "query": query,
            "limit": context.parameters.get("limit", 5),
            "time_range": context.parameters.get("time_range", "month")
        })

        if web_result:
            tool_results.append(web_result.to_dict())

        # 合并结果
        combined_results = []
        if kb_result and kb_result.success and kb_result.data:
            kb_items = kb_result.data.get("results", [])
            combined_results.extend(kb_items)

        if web_result and web_result.success and web_result.data:
            web_items = web_result.data.get("results", [])
            combined_results.extend(web_items)

        if not combined_results:
            return SkillResult(
                success=False,
                error="No results found from any source",
                tool_results=tool_results
            )

        return SkillResult(
            success=True,
            data={
                "query": query,
                "total_results": len(combined_results),
                "results": combined_results
            },
            tool_results=tool_results,
            metadata={
                "kb_results_count": len(kb_result.data.get("results", [])) if kb_result and kb_result.success else 0,
                "web_results_count": len(web_result.data.get("results", [])) if web_result and web_result.success else 0
            }
        )


class DataInsightSkill(Skill):
    """数据洞察技能"""

    def __init__(self):
        super().__init__(
            name="data_insight",
            description="分析数据并生成洞察",
            category=SkillCategory.ANALYSIS,
            level=SkillLevel.INTERMEDIATE,
            required_tools=["data_analysis"]
        )

    def execute(self, context: SkillContext) -> SkillResult:
        data = context.parameters.get("data")
        if not data:
            return SkillResult(success=False, error="Data is required")

        analysis_type = context.parameters.get("analysis_type", "summary")

        # 执行数据分析
        analysis_result = self._execute_tool("data_analysis", {
            "data": data,
            "analysis_type": analysis_type,
            "options": context.parameters.get("options", {})
        })

        if not analysis_result or not analysis_result.success:
            return SkillResult(
                success=False,
                error=analysis_result.error if analysis_result else "Analysis failed",
                tool_results=[analysis_result.to_dict() if analysis_result else {}]
            )

        return SkillResult(
            success=True,
            data=analysis_result.data,
            tool_results=[analysis_result.to_dict()],
            metadata={
                "analysis_type": analysis_type,
                "data_shape": analysis_result.data.get("data_summary", {}) if analysis_result.data else {}
            }
        )


class FactCheckSkill(Skill):
    """事实核查技能"""

    def __init__(self):
        super().__init__(
            name="fact_check",
            description="核查信息的准确性和可信度",
            category=SkillCategory.VALIDATION,
            level=SkillLevel.ADVANCED,
            required_tools=["knowledge_search", "web_search"]
        )

    def execute(self, context: SkillContext) -> SkillResult:
        claim = context.query or context.parameters.get("claim", "")
        if not claim:
            return SkillResult(success=False, error="Claim to verify is required")

        tool_results = []
        evidence = []

        # 从知识库查找证据
        kb_result = self._execute_tool("knowledge_search", {
            "query": claim,
            "limit": 5
        })
        if kb_result:
            tool_results.append(kb_result.to_dict())
            if kb_result.success and kb_result.data:
                for item in kb_result.data.get("results", []):
                    evidence.append({
                        "source": "knowledge_base",
                        "content": item.get("content", ""),
                        "relevance": item.get("relevance_score", 0)
                    })

        # 从网络查找证据
        web_result = self._execute_tool("web_search", {
            "query": f"verify fact: {claim}",
            "limit": 5
        })
        if web_result:
            tool_results.append(web_result.to_dict())
            if web_result.success and web_result.data:
                for item in web_result.data.get("results", []):
                    evidence.append({
                        "source": item.get("source", "web"),
                        "url": item.get("url", ""),
                        "content": item.get("snippet", ""),
                        "relevance": item.get("relevance_score", 0)
                    })

        # 评估可信度
        if not evidence:
            verification_status = "unverifiable"
            confidence = 0.0
        else:
            avg_relevance = sum(e.get("relevance", 0) for e in evidence) / len(evidence)
            if avg_relevance >= 0.8:
                verification_status = "likely_true"
                confidence = avg_relevance
            elif avg_relevance >= 0.5:
                verification_status = "partially_verified"
                confidence = avg_relevance
            else:
                verification_status = "uncertain"
                confidence = avg_relevance

        return SkillResult(
            success=True,
            data={
                "claim": claim,
                "verification_status": verification_status,
                "confidence": confidence,
                "evidence_count": len(evidence),
                "evidence": evidence[:5]  # 返回前5条证据
            },
            tool_results=tool_results,
            metadata={
                "kb_evidence_count": len([e for e in evidence if e.get("source") == "knowledge_base"]),
                "web_evidence_count": len([e for e in evidence if e.get("source") != "knowledge_base"])
            }
        )


class CollaborativeCommunicationSkill(Skill):
    """协作沟通技能"""

    def __init__(self):
        super().__init__(
            name="collaborative_communication",
            description="与其他智能体进行协作沟通",
            category=SkillCategory.COMMUNICATION,
            level=SkillLevel.BASIC,
            required_tools=["communication"]
        )

    def execute(self, context: SkillContext) -> SkillResult:
        action = context.parameters.get("action", "send")
        message = context.parameters.get("message")
        target = context.parameters.get("target")

        if not message:
            return SkillResult(success=False, error="Message is required")

        # 执行通信
        comm_result = self._execute_tool("communication", {
            "action": action,
            "message": message,
            "target": target,
            "message_type": context.parameters.get("message_type", "info"),
            "priority": context.parameters.get("priority", "normal")
        })

        if not comm_result or not comm_result.success:
            return SkillResult(
                success=False,
                error=comm_result.error if comm_result else "Communication failed",
                tool_results=[comm_result.to_dict() if comm_result else {}]
            )

        return SkillResult(
            success=True,
            data=comm_result.data,
            tool_results=[comm_result.to_dict()],
            metadata={
                "action": action,
                "target": target,
                "delivered": comm_result.data.get("message_delivered", False) if comm_result.data else False
            }
        )


# ============================================================================
# 智能体技能集
# ============================================================================

@dataclass
class AgentSkillSet:
    """智能体技能集配置"""
    agent_name: str
    skills: Set[str] = field(default_factory=set)
    skill_levels: Dict[str, SkillLevel] = field(default_factory=dict)
    custom_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def add_skill(self, skill_name: str, level: SkillLevel = SkillLevel.BASIC):
        """添加技能"""
        self.skills.add(skill_name)
        self.skill_levels[skill_name] = level

    def remove_skill(self, skill_name: str):
        """移除技能"""
        self.skills.discard(skill_name)
        self.skill_levels.pop(skill_name, None)

    def has_skill(self, skill_name: str) -> bool:
        """检查是否有技能"""
        return skill_name in self.skills

    def get_skill_level(self, skill_name: str) -> Optional[SkillLevel]:
        """获取技能级别"""
        return self.skill_levels.get(skill_name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "skills": list(self.skills),
            "skill_levels": {k: v.value for k, v in self.skill_levels.items()},
            "custom_configs": self.custom_configs
        }


# ============================================================================
# 技能注册中心
# ============================================================================

class SkillRegistry:
    """
    技能注册中心

    管理所有可用技能和智能体技能配置。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._skills: Dict[str, Skill] = {}
        self._agent_skill_sets: Dict[str, AgentSkillSet] = {}
        self._tool_manager: Optional['ToolManager'] = None
        self._initialized = True

        # 注册内置技能
        self._register_builtin_skills()

    def _register_builtin_skills(self):
        """注册内置技能"""
        builtin_skills = [
            KnowledgeQuerySkill(),
            WebResearchSkill(),
            DataInsightSkill(),
            FactCheckSkill(),
            CollaborativeCommunicationSkill(),
        ]

        for skill in builtin_skills:
            self.register_skill(skill)

    def bind_tool_manager(self, tool_manager: 'ToolManager'):
        """绑定工具管理器"""
        self._tool_manager = tool_manager

        # 为所有技能绑定工具管理器
        for skill in self._skills.values():
            skill.bind_tool_manager(tool_manager)

    def register_skill(self, skill: Skill) -> bool:
        """注册技能"""
        if skill.name in self._skills:
            logger.warning(f"Skill '{skill.name}' already registered, replacing")

        self._skills[skill.name] = skill

        # 如果有工具管理器，立即绑定
        if self._tool_manager:
            skill.bind_tool_manager(self._tool_manager)

        logger.info(f"Registered skill: {skill.name} ({skill.category.value})")
        return True

    def unregister_skill(self, skill_name: str) -> bool:
        """注销技能"""
        if skill_name in self._skills:
            del self._skills[skill_name]
            logger.info(f"Unregistered skill: {skill_name}")
            return True
        return False

    def get_skill(self, skill_name: str) -> Optional[Skill]:
        """获取技能"""
        return self._skills.get(skill_name)

    def list_skills(
        self,
        category: SkillCategory = None,
        level: SkillLevel = None
    ) -> Dict[str, Dict[str, Any]]:
        """列出技能"""
        result = {}

        for name, skill in self._skills.items():
            if category and skill.category != category:
                continue
            if level and skill.level != level:
                continue

            result[name] = skill.get_info()

        return result

    def execute_skill(
        self,
        skill_name: str,
        context: SkillContext
    ) -> SkillResult:
        """执行技能"""
        skill = self.get_skill(skill_name)
        if not skill:
            return SkillResult(success=False, error=f"Skill '{skill_name}' not found")

        return skill.safe_execute(context)

    # =========================================================================
    # 智能体技能集管理
    # =========================================================================

    def create_agent_skill_set(self, agent_name: str) -> AgentSkillSet:
        """为智能体创建技能集"""
        if agent_name not in self._agent_skill_sets:
            self._agent_skill_sets[agent_name] = AgentSkillSet(agent_name=agent_name)
        return self._agent_skill_sets[agent_name]

    def get_agent_skill_set(self, agent_name: str) -> Optional[AgentSkillSet]:
        """获取智能体技能集"""
        return self._agent_skill_sets.get(agent_name)

    def assign_skill_to_agent(
        self,
        agent_name: str,
        skill_name: str,
        level: SkillLevel = SkillLevel.BASIC
    ) -> bool:
        """为智能体分配技能"""
        if skill_name not in self._skills:
            logger.error(f"Skill '{skill_name}' not registered")
            return False

        skill_set = self.create_agent_skill_set(agent_name)
        skill_set.add_skill(skill_name, level)

        logger.info(f"Assigned skill '{skill_name}' to agent '{agent_name}'")
        return True

    def remove_skill_from_agent(self, agent_name: str, skill_name: str) -> bool:
        """从智能体移除技能"""
        skill_set = self._agent_skill_sets.get(agent_name)
        if skill_set:
            skill_set.remove_skill(skill_name)
            return True
        return False

    def get_agent_skills(self, agent_name: str) -> List[str]:
        """获取智能体的所有技能"""
        skill_set = self._agent_skill_sets.get(agent_name)
        return list(skill_set.skills) if skill_set else []

    def execute_agent_skill(
        self,
        agent_name: str,
        skill_name: str,
        context: SkillContext
    ) -> SkillResult:
        """执行智能体的技能"""
        skill_set = self._agent_skill_sets.get(agent_name)
        if not skill_set or not skill_set.has_skill(skill_name):
            return SkillResult(
                success=False,
                error=f"Agent '{agent_name}' does not have skill '{skill_name}'"
            )

        context.agent_name = agent_name
        return self.execute_skill(skill_name, context)


# 全局技能注册中心实例
skill_registry = SkillRegistry()
