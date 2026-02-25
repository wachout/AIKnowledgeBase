"""
智能体工具基类
定义工具的基本接口和功能，包含版本管理和质量评估支持。
"""

import warnings
import logging
from typing import Dict, Any, List, Optional, Union, TYPE_CHECKING
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from .tool_evaluator import QualityMetrics

logger = logging.getLogger(__name__)


# ============================================================================
# 参数类型定义
# ============================================================================

class ParameterType(Enum):
    """参数类型枚举"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    ANY = "any"


@dataclass
class ParameterDefinition:
    """参数定义"""
    name: str
    param_type: ParameterType
    description: str = ""
    required: bool = False
    default: Any = None
    constraints: Dict[str, Any] = field(default_factory=dict)  # min, max, pattern, enum, etc.

    def validate(self, value: Any) -> tuple:
        """验证参数值"""
        if value is None:
            if self.required:
                return False, f"Required parameter '{self.name}' is missing"
            return True, None

        # 类型检查
        type_map = {
            ParameterType.STRING: str,
            ParameterType.INTEGER: int,
            ParameterType.FLOAT: (int, float),
            ParameterType.BOOLEAN: bool,
            ParameterType.LIST: list,
            ParameterType.DICT: dict,
        }

        if self.param_type != ParameterType.ANY:
            expected_type = type_map.get(self.param_type)
            if expected_type and not isinstance(value, expected_type):
                return False, f"Parameter '{self.name}' expects {self.param_type.value}, got {type(value).__name__}"

        # 约束检查
        if "min" in self.constraints and value < self.constraints["min"]:
            return False, f"Parameter '{self.name}' must be >= {self.constraints['min']}"
        if "max" in self.constraints and value > self.constraints["max"]:
            return False, f"Parameter '{self.name}' must be <= {self.constraints['max']}"
        if "enum" in self.constraints and value not in self.constraints["enum"]:
            return False, f"Parameter '{self.name}' must be one of {self.constraints['enum']}"

        return True, None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.param_type.value,
            "description": self.description,
            "required": self.required,
            "default": self.default,
            "constraints": self.constraints
        }


@dataclass
class ParameterSchema:
    """参数模式定义"""
    parameters: List[ParameterDefinition] = field(default_factory=list)
    version: str = "1.0.0"  # 参数结构版本

    def add_parameter(self, param: ParameterDefinition):
        self.parameters.append(param)

    def validate_all(self, values: Dict[str, Any]) -> tuple:
        """验证所有参数"""
        errors = []
        for param in self.parameters:
            value = values.get(param.name, param.default)
            valid, error = param.validate(value)
            if not valid:
                errors.append(error)
        return len(errors) == 0, errors

    def get_required_params(self) -> List[str]:
        return [p.name for p in self.parameters if p.required]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "parameters": [p.to_dict() for p in self.parameters]
        }


# ============================================================================
# 质量评估数据类
# ============================================================================

@dataclass
class QualityAssessment:
    """工具结果质量评估"""
    relevance_score: float = 0.0      # 相关性评分 (0-1)
    confidence_score: float = 0.0     # 可信度评分 (0-1)
    completeness_score: float = 0.0   # 完整性评分 (0-1)
    quality_level: str = "UNKNOWN"    # HIGH, MEDIUM, LOW, UNKNOWN
    assessment_details: Dict[str, Any] = field(default_factory=dict)
    assessed_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def overall_score(self) -> float:
        """计算综合评分"""
        return (self.relevance_score * 0.4 +
                self.confidence_score * 0.35 +
                self.completeness_score * 0.25)

    def determine_quality_level(self):
        """根据评分确定质量级别"""
        if self.relevance_score >= 0.8 and self.confidence_score >= 0.7:
            self.quality_level = "HIGH"
        elif self.relevance_score >= 0.5 and self.confidence_score >= 0.5:
            self.quality_level = "MEDIUM"
        else:
            self.quality_level = "LOW"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relevance_score": self.relevance_score,
            "confidence_score": self.confidence_score,
            "completeness_score": self.completeness_score,
            "overall_score": self.overall_score,
            "quality_level": self.quality_level,
            "assessment_details": self.assessment_details,
            "assessed_at": self.assessed_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QualityAssessment':
        return cls(
            relevance_score=data.get("relevance_score", 0.0),
            confidence_score=data.get("confidence_score", 0.0),
            completeness_score=data.get("completeness_score", 0.0),
            quality_level=data.get("quality_level", "UNKNOWN"),
            assessment_details=data.get("assessment_details", {}),
            assessed_at=data.get("assessed_at", datetime.now().isoformat())
        )


# ============================================================================
# 工具执行结果
# ============================================================================

class ToolResult:
    """工具执行结果（增强版）"""

    def __init__(self, success: bool, data: Any = None, error: str = None,
                 metadata: Dict[str, Any] = None,
                 quality_assessment: QualityAssessment = None):
        self.success = success
        self.data = data
        self.error = error
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()
        self.quality_assessment = quality_assessment

    @property
    def is_high_quality(self) -> bool:
        """检查结果是否为高质量"""
        if not self.quality_assessment:
            return False
        return self.quality_assessment.quality_level == "HIGH"

    @property
    def quality_score(self) -> float:
        """获取质量评分"""
        if not self.quality_assessment:
            return 0.0
        return self.quality_assessment.overall_score

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }
        if self.quality_assessment:
            result["quality_assessment"] = self.quality_assessment.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolResult':
        quality_data = data.get("quality_assessment")
        quality_assessment = QualityAssessment.from_dict(quality_data) if quality_data else None
        result = cls(
            success=data.get("success", False),
            data=data.get("data"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
            quality_assessment=quality_assessment
        )
        result.timestamp = data.get("timestamp", result.timestamp)
        return result


# ============================================================================
# 工具基类
# ============================================================================

class BaseTool(ABC):
    """
    智能体工具基类（增强版）

    支持:
    - 版本管理和兼容性检查
    - 参数模式验证
    - 废弃标记和迁移提示
    - 生命周期钩子
    """

    # 类级别默认版本
    DEFAULT_VERSION = "1.0.0"

    def __init__(
        self,
        name: str,
        description: str,
        tool_type: str = "utility",
        version: str = None,
        min_compatible_version: str = None,
        parameter_schema: ParameterSchema = None,
        deprecated: bool = False,
        deprecation_message: str = None,
        successor_tool: str = None
    ):
        """
        初始化工具

        Args:
            name: 工具名称
            description: 工具描述
            tool_type: 工具类型 (utility, search, analysis, communication, etc.)
            version: 工具版本 (语义版本号，如 "1.2.3")
            min_compatible_version: 最低兼容版本
            parameter_schema: 参数模式定义
            deprecated: 是否已废弃
            deprecation_message: 废弃提示信息
            successor_tool: 替代工具名称
        """
        self.name = name
        self.description = description
        self.tool_type = tool_type

        # 版本管理
        self.version = version or self.DEFAULT_VERSION
        self.min_compatible_version = min_compatible_version or self.version

        # 参数模式
        self.parameter_schema = parameter_schema or ParameterSchema()

        # 废弃标记
        self.deprecated = deprecated
        self.deprecation_message = deprecation_message
        self.successor_tool = successor_tool

        # 使用统计
        self.usage_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.last_used = None
        self.created_at = datetime.now().isoformat()

        # 生命周期钩子
        self._before_execute_hooks: List[callable] = []
        self._after_execute_hooks: List[callable] = []

    def add_before_execute_hook(self, hook: callable):
        """添加执行前钩子"""
        self._before_execute_hooks.append(hook)

    def add_after_execute_hook(self, hook: callable):
        """添加执行后钩子"""
        self._after_execute_hooks.append(hook)

    def _run_before_hooks(self, parameters: Dict[str, Any]):
        """运行执行前钩子"""
        for hook in self._before_execute_hooks:
            try:
                hook(self, parameters)
            except Exception as e:
                logger.warning(f"Before execute hook failed: {e}")

    def _run_after_hooks(self, parameters: Dict[str, Any], result: ToolResult):
        """运行执行后钩子"""
        for hook in self._after_execute_hooks:
            try:
                hook(self, parameters, result)
            except Exception as e:
                logger.warning(f"After execute hook failed: {e}")

    @abstractmethod
    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        执行工具 (子类必须实现)

        Args:
            parameters: 工具参数

        Returns:
            执行结果
        """
        pass

    def safe_execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        安全执行工具（带废弃检查和参数验证）

        Args:
            parameters: 工具参数

        Returns:
            执行结果
        """
        # 废弃警告
        if self.deprecated:
            message = self.deprecation_message or f"Tool '{self.name}' is deprecated."
            if self.successor_tool:
                message += f" Please use '{self.successor_tool}' instead."
            warnings.warn(message, DeprecationWarning, stacklevel=2)
            logger.warning(f"⚠️ {message}")

        # 参数验证
        if self.parameter_schema.parameters:
            valid, errors = self.parameter_schema.validate_all(parameters)
            if not valid:
                return self.create_error_result(
                    f"Parameter validation failed: {'; '.join(errors)}",
                    metadata={"validation_errors": errors}
                )

        # 运行前置钩子
        self._run_before_hooks(parameters)

        # 执行工具
        self._record_usage()
        try:
            result = self.execute(parameters)
            if result.success:
                self.success_count += 1
            else:
                self.failure_count += 1
        except Exception as e:
            self.failure_count += 1
            result = self.create_error_result(f"Tool execution error: {str(e)}")

        # 运行后置钩子
        self._run_after_hooks(parameters, result)

        return result

    def get_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        info = {
            "name": self.name,
            "description": self.description,
            "tool_type": self.tool_type,
            "version": self.version,
            "min_compatible_version": self.min_compatible_version,
            "deprecated": self.deprecated,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_count / max(self.usage_count, 1),
            "last_used": self.last_used,
            "created_at": self.created_at
        }
        if self.deprecated:
            info["deprecation_message"] = self.deprecation_message
            info["successor_tool"] = self.successor_tool
        if self.parameter_schema.parameters:
            info["parameter_schema"] = self.parameter_schema.to_dict()
        return info

    def _record_usage(self):
        """记录工具使用"""
        self.usage_count += 1
        self.last_used = datetime.now().isoformat()

    def validate_parameters(self, parameters: Dict[str, Any], required_params: List[str]) -> bool:
        """
        验证参数（向后兼容的简单验证）

        Args:
            parameters: 参数字典
            required_params: 必需参数列表

        Returns:
            参数是否有效
        """
        for param in required_params:
            if param not in parameters or parameters[param] is None:
                return False
        return True

    def validate_parameters_with_schema(self, parameters: Dict[str, Any]) -> tuple:
        """
        使用参数模式验证

        Returns:
            (is_valid, errors)
        """
        return self.parameter_schema.validate_all(parameters)

    def create_error_result(self, error_message: str, metadata: Dict[str, Any] = None) -> ToolResult:
        """创建错误结果"""
        return ToolResult(success=False, error=error_message, metadata=metadata)

    def create_success_result(
        self,
        data: Any,
        metadata: Dict[str, Any] = None,
        quality_assessment: QualityAssessment = None
    ) -> ToolResult:
        """创建成功结果"""
        return ToolResult(
            success=True,
            data=data,
            metadata=metadata,
            quality_assessment=quality_assessment
        )

    def is_compatible_with(self, required_version: str) -> bool:
        """
        检查是否与指定版本兼容

        Args:
            required_version: 要求的版本

        Returns:
            是否兼容
        """
        from .tool_version import ToolVersion
        try:
            current = ToolVersion.parse(self.version)
            required = ToolVersion.parse(required_version)
            min_compat = ToolVersion.parse(self.min_compatible_version)
            return required >= min_compat and required.major == current.major
        except (ImportError, Exception):
            # 如果 tool_version 模块不可用，使用简单比较
            return self.version >= required_version


class KnowledgeSearchTool(BaseTool):
    """
    知识库搜索工具
    用于在知识库中搜索相关信息
    """

    def __init__(self, knowledge_base_interface=None):
        super().__init__(
            name="knowledge_search",
            description="在知识库中搜索相关信息和文档",
            tool_type="search"
        )
        self.knowledge_base = knowledge_base_interface

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        执行知识库搜索

        Args:
            parameters: 搜索参数
                - query: 搜索查询
                - limit: 返回结果数量限制 (默认10)
                - filters: 搜索过滤器

        Returns:
            搜索结果
        """
        self._record_usage()

        if not self.validate_parameters(parameters, ["query"]):
            return self.create_error_result("Missing required parameter: query")

        query = parameters["query"]
        limit = parameters.get("limit", 10)
        filters = parameters.get("filters", {})

        try:
            # 这里应该调用实际的知识库搜索接口
            # 暂时返回模拟结果
            search_results = {
                "query": query,
                "total_results": 5,
                "results": [
                    {
                        "title": f"相关文档 {i+1}",
                        "content": f"这是关于 '{query}' 的搜索结果 {i+1}",
                        "relevance_score": 0.9 - i * 0.1,
                        "source": f"source_{i+1}"
                    }
                    for i in range(min(limit, 5))
                ]
            }

            return self.create_success_result(search_results, {"query": query, "limit": limit})

        except Exception as e:
            return self.create_error_result(f"Knowledge search failed: {str(e)}")


class WebSearchTool(BaseTool):
    """
    网络搜索工具
    用于在互联网上搜索信息
    """

    def __init__(self, search_engine_interface=None):
        super().__init__(
            name="web_search",
            description="在互联网上搜索最新信息和资源",
            tool_type="search"
        )
        self.search_engine = search_engine_interface

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        执行网络搜索

        Args:
            parameters: 搜索参数
                - query: 搜索查询
                - limit: 返回结果数量限制 (默认5)
                - time_range: 时间范围 (day, week, month, year)

        Returns:
            搜索结果
        """
        self._record_usage()

        if not self.validate_parameters(parameters, ["query"]):
            return self.create_error_result("Missing required parameter: query")

        query = parameters["query"]
        limit = parameters.get("limit", 5)
        time_range = parameters.get("time_range", "month")

        try:
            # 这里应该调用实际的网络搜索接口
            # 暂时返回模拟结果
            search_results = {
                "query": query,
                "time_range": time_range,
                "total_results": 10,
                "results": [
                    {
                        "title": f"网络搜索结果 {i+1}",
                        "url": f"https://example.com/result{i+1}",
                        "snippet": f"这是关于 '{query}' 的网络搜索摘要 {i+1}",
                        "source": f"search_engine_{i%3 + 1}",
                        "published_date": f"2024-01-{i+1:02d}"
                    }
                    for i in range(min(limit, 10))
                ]
            }

            return self.create_success_result(search_results, {"query": query, "time_range": time_range})

        except Exception as e:
            return self.create_error_result(f"Web search failed: {str(e)}")


class DataAnalysisTool(BaseTool):
    """
    数据分析工具
    用于执行基本的数据分析任务
    """

    def __init__(self, analysis_engine=None):
        super().__init__(
            name="data_analysis",
            description="执行数据分析、统计计算和可视化",
            tool_type="analysis"
        )
        self.analysis_engine = analysis_engine

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        执行数据分析

        Args:
            parameters: 分析参数
                - data: 要分析的数据
                - analysis_type: 分析类型 (statistics, correlation, trend, etc.)
                - options: 分析选项

        Returns:
            分析结果
        """
        self._record_usage()

        if not self.validate_parameters(parameters, ["data", "analysis_type"]):
            return self.create_error_result("Missing required parameters: data and analysis_type")

        data = parameters["data"]
        analysis_type = parameters["analysis_type"]
        options = parameters.get("options", {})

        try:
            # 这里应该调用实际的数据分析引擎
            # 暂时返回模拟结果
            analysis_result = {
                "analysis_type": analysis_type,
                "data_summary": {
                    "rows": len(data) if isinstance(data, list) else "unknown",
                    "columns": len(data[0]) if isinstance(data, list) and data else "unknown"
                },
                "results": {
                    "statistics": {"mean": 0.5, "std": 0.2, "min": 0.0, "max": 1.0},
                    "insights": [f"数据分析洞察 {i+1}" for i in range(3)]
                },
                "visualization_suggestions": ["柱状图", "趋势图", "分布图"]
            }

            return self.create_success_result(analysis_result, {"analysis_type": analysis_type})

        except Exception as e:
            return self.create_error_result(f"Data analysis failed: {str(e)}")


class CommunicationTool(BaseTool):
    """
    沟通协调工具
    用于智能体间的通信和协调
    """

    def __init__(self, communication_channel=None):
        super().__init__(
            name="communication",
            description="智能体间通信、消息传递和协调",
            tool_type="communication"
        )
        self.communication_channel = communication_channel
        self.message_history = []

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        执行通信任务

        Args:
            parameters: 通信参数
                - action: 通信动作 (send, broadcast, request, respond)
                - target: 目标智能体
                - message: 消息内容
                - message_type: 消息类型 (info, request, response, alert)

        Returns:
            通信结果
        """
        self._record_usage()

        if not self.validate_parameters(parameters, ["action", "message"]):
            return self.create_error_result("Missing required parameters: action and message")

        action = parameters["action"]
        target = parameters.get("target")
        message = parameters["message"]
        message_type = parameters.get("message_type", "info")

        try:
            # 记录消息
            message_record = {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "target": target,
                "message": message,
                "message_type": message_type,
                "sender": self.name
            }

            self.message_history.append(message_record)

            # 这里应该调用实际的通信机制
            # 暂时返回模拟结果
            communication_result = {
                "action": action,
                "target": target,
                "message_delivered": True,
                "response_expected": action in ["request"],
                "message_id": f"msg_{len(self.message_history)}"
            }

            return self.create_success_result(communication_result, {"message_type": message_type})

        except Exception as e:
            return self.create_error_result(f"Communication failed: {str(e)}")


class ToolManager:
    """
    工具管理器
    负责注册、管理和分发工具
    """

    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self.tool_categories: Dict[str, List[str]] = {}

    def register_tool(self, tool: BaseTool):
        """注册工具"""
        self.tools[tool.name] = tool

        # 按类别组织
        if tool.tool_type not in self.tool_categories:
            self.tool_categories[tool.tool_type] = []
        self.tool_categories[tool.tool_type].append(tool.name)

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self.tools.get(tool_name)

    def list_tools(self, tool_type: str = None) -> Dict[str, Any]:
        """列出工具"""
        if tool_type:
            tool_names = self.tool_categories.get(tool_type, [])
            tools_info = {name: self.tools[name].get_info() for name in tool_names if name in self.tools}
        else:
            tools_info = {name: tool.get_info() for name, tool in self.tools.items()}

        return {
            "tools": tools_info,
            "categories": list(self.tool_categories.keys()),
            "total_count": len(self.tools)
        }

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """执行工具"""
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{tool_name}' not found")

        return tool.execute(parameters)


# ============================================================================
# 兼容层 - 重导出拆分的模块，保持向后兼容
# ============================================================================

# 重导出拆分的工具类
try:
    from .knowledge_search_tool import KnowledgeSearchTool
    from .web_search_tool import WebSearchTool
    from .data_analysis_tool import DataAnalysisTool
    from .communication_tool import CommunicationTool
except ImportError as e:
    logger.warning(f"无法导入拆分的工具类: {e}")
    # 保留原有的占位符以保持兼容
    KnowledgeSearchTool = None
    WebSearchTool = None
    DataAnalysisTool = None
    CommunicationTool = None

# 重导出工具管理器增强版
try:
    from .tool_manager import ToolManager as EnhancedToolManager
except ImportError:
    EnhancedToolManager = None

# 重导出版本管理
try:
    from .tool_version import (
        ToolVersion,
        CompatibilityChecker,
        GracefulDegradeHandler,
        ToolVersionRegistry,
        VersionMismatchError
    )
except ImportError as e:
    logger.warning(f"无法导入版本管理模块: {e}")
    ToolVersion = None
    CompatibilityChecker = None
    GracefulDegradeHandler = None
    ToolVersionRegistry = None
    VersionMismatchError = None

# 重导出流水线
try:
    from .tool_pipeline import (
        ToolPipelineStep,
        ToolPipeline,
        PipelineExecutor,
        FailurePolicy,
        ExecutionStrategy
    )
except ImportError as e:
    logger.warning(f"无法导入流水线模块: {e}")
    ToolPipelineStep = None
    ToolPipeline = None
    PipelineExecutor = None
    FailurePolicy = None
    ExecutionStrategy = None

# 重导出评估器
try:
    from .tool_evaluator import (
        QualityMetrics,
        QualityThreshold,
        QualityLevel,
        ResultQualityEvaluator,
        SearchResultEvaluator
    )
except ImportError as e:
    logger.warning(f"无法导入评估器模块: {e}")
    QualityMetrics = None
    QualityThreshold = None
    QualityLevel = None
    ResultQualityEvaluator = None
    SearchResultEvaluator = None

# 重导出技能系统
try:
    from .skill_registry import (
        Skill,
        SkillContext,
        SkillResult,
        SkillRegistry,
        AgentSkillSet,
        KnowledgeQuerySkill,
        WebResearchSkill,
        DataInsightSkill,
        FactCheckSkill,
        CollaborativeCommunicationSkill
    )
except ImportError as e:
    logger.warning(f"无法导入技能系统模块: {e}")
    Skill = None
    SkillContext = None
    SkillResult = None
    SkillRegistry = None
    AgentSkillSet = None
    KnowledgeQuerySkill = None
    WebResearchSkill = None
    DataInsightSkill = None
    FactCheckSkill = None
    CollaborativeCommunicationSkill = None


# 公开导出的符号列表
__all__ = [
    # 基础类
    "BaseTool",
    "ToolResult",
    "ToolManager",
    "ParameterType",
    "ParameterDefinition",
    "ParameterSchema",
    "QualityAssessment",
    # 工具类
    "KnowledgeSearchTool",
    "WebSearchTool",
    "DataAnalysisTool",
    "CommunicationTool",
    # 版本管理
    "ToolVersion",
    "CompatibilityChecker",
    "GracefulDegradeHandler",
    "ToolVersionRegistry",
    "VersionMismatchError",
    # 流水线
    "ToolPipelineStep",
    "ToolPipeline",
    "PipelineExecutor",
    "FailurePolicy",
    "ExecutionStrategy",
    # 评估器
    "QualityMetrics",
    "QualityThreshold",
    "QualityLevel",
    "ResultQualityEvaluator",
    "SearchResultEvaluator",
    # 技能系统
    "Skill",
    "SkillContext",
    "SkillResult",
    "SkillRegistry",
    "AgentSkillSet",
    "KnowledgeQuerySkill",
    "WebResearchSkill",
    "DataInsightSkill",
    "FactCheckSkill",
    "CollaborativeCommunicationSkill",
    # 增强版
    "EnhancedToolManager",
]