"""
增强的工具管理器模块

提供工具注册、版本管理、流水线编排和生命周期钩子功能。
"""

import logging
from typing import Dict, Any, List, Optional, Callable, Set, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass, field

from .base_tool import BaseTool, ToolResult
from .tool_version import (
    ToolVersion, CompatibilityChecker, CompatibilityResult,
    CompatibilityLevel, GracefulDegradeHandler, tool_version_registry
)
from .tool_pipeline import (
    ToolPipeline, PipelineExecutor, PipelineResult,
    ToolPipelineStep, PipelineTemplates
)

if TYPE_CHECKING:
    from .tool_evaluator import ResultQualityEvaluator

logger = logging.getLogger(__name__)


# ============================================================================
# 工具依赖管理
# ============================================================================

@dataclass
class ToolDependency:
    """工具依赖定义"""
    tool_name: str
    required_version: str = ""
    optional: bool = False


@dataclass
class ToolMetadata:
    """工具元数据"""
    tool: BaseTool
    dependencies: List[ToolDependency] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)
    registered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.tool.name,
            "type": self.tool.tool_type,
            "version": getattr(self.tool, 'version', '1.0.0'),
            "deprecated": getattr(self.tool, 'deprecated', False),
            "dependencies": [
                {"name": d.tool_name, "version": d.required_version, "optional": d.optional}
                for d in self.dependencies
            ],
            "tags": list(self.tags),
            "registered_at": self.registered_at,
            "enabled": self.enabled
        }


# ============================================================================
# 生命周期钩子
# ============================================================================

class ToolLifecycleHooks:
    """工具生命周期钩子管理"""

    def __init__(self):
        self._before_execute: List[Callable] = []
        self._after_execute: List[Callable] = []
        self._on_error: List[Callable] = []
        self._on_register: List[Callable] = []
        self._on_unregister: List[Callable] = []

    def add_before_execute(self, hook: Callable):
        """添加执行前钩子"""
        self._before_execute.append(hook)

    def add_after_execute(self, hook: Callable):
        """添加执行后钩子"""
        self._after_execute.append(hook)

    def add_on_error(self, hook: Callable):
        """添加错误钩子"""
        self._on_error.append(hook)

    def add_on_register(self, hook: Callable):
        """添加注册钩子"""
        self._on_register.append(hook)

    def add_on_unregister(self, hook: Callable):
        """添加注销钩子"""
        self._on_unregister.append(hook)

    def run_before_execute(self, tool: BaseTool, parameters: Dict[str, Any]):
        """运行执行前钩子"""
        for hook in self._before_execute:
            try:
                hook(tool, parameters)
            except Exception as e:
                logger.warning(f"Before execute hook error: {e}")

    def run_after_execute(self, tool: BaseTool, parameters: Dict[str, Any], result: ToolResult):
        """运行执行后钩子"""
        for hook in self._after_execute:
            try:
                hook(tool, parameters, result)
            except Exception as e:
                logger.warning(f"After execute hook error: {e}")

    def run_on_error(self, tool: BaseTool, error: Exception):
        """运行错误钩子"""
        for hook in self._on_error:
            try:
                hook(tool, error)
            except Exception as e:
                logger.warning(f"On error hook error: {e}")

    def run_on_register(self, tool: BaseTool):
        """运行注册钩子"""
        for hook in self._on_register:
            try:
                hook(tool)
            except Exception as e:
                logger.warning(f"On register hook error: {e}")

    def run_on_unregister(self, tool_name: str):
        """运行注销钩子"""
        for hook in self._on_unregister:
            try:
                hook(tool_name)
            except Exception as e:
                logger.warning(f"On unregister hook error: {e}")


# ============================================================================
# 增强的工具管理器
# ============================================================================

class ToolManager:
    """
    增强的工具管理器

    功能:
    - 工具注册与管理
    - 版本兼容性检查
    - 依赖管理
    - 流水线编排
    - 生命周期钩子
    - 优雅降级支持
    """

    def __init__(
        self,
        strict_version_check: bool = False,
        enable_quality_evaluation: bool = True
    ):
        """
        初始化工具管理器

        Args:
            strict_version_check: 是否启用严格版本检查
            enable_quality_evaluation: 是否启用质量评估
        """
        # 工具存储
        self._tools: Dict[str, ToolMetadata] = {}
        self._tool_categories: Dict[str, List[str]] = {}

        # 流水线存储
        self._pipelines: Dict[str, ToolPipeline] = {}
        self._pipeline_executor: Optional[PipelineExecutor] = None

        # 版本管理
        self._compatibility_checker = CompatibilityChecker(strict_mode=strict_version_check)
        self._degrade_handler = GracefulDegradeHandler()

        # 生命周期钩子
        self._hooks = ToolLifecycleHooks()

        # 质量评估
        self._enable_quality_evaluation = enable_quality_evaluation
        self._quality_evaluator: Optional['ResultQualityEvaluator'] = None

        # 执行统计
        self._execution_stats: Dict[str, Dict[str, Any]] = {}

    # =========================================================================
    # 工具注册与管理
    # =========================================================================

    def register_tool(
        self,
        tool: BaseTool,
        dependencies: List[ToolDependency] = None,
        tags: Set[str] = None
    ) -> bool:
        """
        注册工具

        Args:
            tool: 工具实例
            dependencies: 依赖列表
            tags: 标签集合

        Returns:
            是否注册成功
        """
        # 检查是否已存在
        if tool.name in self._tools:
            existing = self._tools[tool.name]
            existing_version = getattr(existing.tool, 'version', '1.0.0')
            new_version = getattr(tool, 'version', '1.0.0')

            # 版本比较
            try:
                if ToolVersion.parse(new_version) <= ToolVersion.parse(existing_version):
                    logger.warning(
                        f"Tool '{tool.name}' version {new_version} is not newer than "
                        f"existing version {existing_version}"
                    )
                    return False
            except Exception:
                pass

        # 检查依赖
        if dependencies:
            for dep in dependencies:
                if not dep.optional and dep.tool_name not in self._tools:
                    logger.error(f"Required dependency '{dep.tool_name}' not found")
                    return False

        # 创建元数据
        metadata = ToolMetadata(
            tool=tool,
            dependencies=dependencies or [],
            tags=tags or set()
        )

        # 存储工具
        self._tools[tool.name] = metadata

        # 按类别组织
        tool_type = tool.tool_type
        if tool_type not in self._tool_categories:
            self._tool_categories[tool_type] = []
        if tool.name not in self._tool_categories[tool_type]:
            self._tool_categories[tool_type].append(tool.name)

        # 注册到版本注册表
        tool_version_registry.register(
            tool_name=tool.name,
            version=getattr(tool, 'version', '1.0.0'),
            min_compatible_version=getattr(tool, 'min_compatible_version', None),
            deprecated=getattr(tool, 'deprecated', False),
            successor=getattr(tool, 'successor_tool', None)
        )

        # 运行注册钩子
        self._hooks.run_on_register(tool)

        logger.info(f"Registered tool: {tool.name} v{getattr(tool, 'version', '1.0.0')}")
        return True

    def unregister_tool(self, tool_name: str) -> bool:
        """注销工具"""
        if tool_name not in self._tools:
            return False

        metadata = self._tools[tool_name]

        # 检查是否有其他工具依赖此工具
        for name, meta in self._tools.items():
            for dep in meta.dependencies:
                if dep.tool_name == tool_name and not dep.optional:
                    logger.error(f"Cannot unregister '{tool_name}': required by '{name}'")
                    return False

        # 从类别中移除
        tool_type = metadata.tool.tool_type
        if tool_type in self._tool_categories:
            if tool_name in self._tool_categories[tool_type]:
                self._tool_categories[tool_type].remove(tool_name)

        # 运行注销钩子
        self._hooks.run_on_unregister(tool_name)

        # 删除
        del self._tools[tool_name]

        logger.info(f"Unregistered tool: {tool_name}")
        return True

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """获取工具"""
        metadata = self._tools.get(tool_name)
        if metadata and metadata.enabled:
            return metadata.tool
        return None

    def get_tool_metadata(self, tool_name: str) -> Optional[ToolMetadata]:
        """获取工具元数据"""
        return self._tools.get(tool_name)

    def list_tools(self, tool_type: str = None, tags: Set[str] = None) -> Dict[str, Any]:
        """
        列出工具

        Args:
            tool_type: 过滤工具类型
            tags: 过滤标签

        Returns:
            工具列表信息
        """
        tools_info = {}

        for name, metadata in self._tools.items():
            # 类型过滤
            if tool_type and metadata.tool.tool_type != tool_type:
                continue

            # 标签过滤
            if tags and not tags.intersection(metadata.tags):
                continue

            tools_info[name] = {
                **metadata.tool.get_info(),
                "tags": list(metadata.tags),
                "enabled": metadata.enabled
            }

        return {
            "tools": tools_info,
            "categories": list(self._tool_categories.keys()),
            "total_count": len(tools_info)
        }

    def enable_tool(self, tool_name: str) -> bool:
        """启用工具"""
        if tool_name in self._tools:
            self._tools[tool_name].enabled = True
            return True
        return False

    def disable_tool(self, tool_name: str) -> bool:
        """禁用工具"""
        if tool_name in self._tools:
            self._tools[tool_name].enabled = False
            return True
        return False

    # =========================================================================
    # 工具执行
    # =========================================================================

    def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        required_version: str = None
    ) -> ToolResult:
        """
        执行工具

        Args:
            tool_name: 工具名称
            parameters: 参数
            required_version: 要求的版本

        Returns:
            执行结果
        """
        # 获取工具
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{tool_name}' not found or disabled")

        # 版本兼容性检查
        if required_version:
            actual_version = getattr(tool, 'version', '1.0.0')
            compat_result = self._compatibility_checker.check(
                tool_name, required_version, actual_version,
                getattr(tool, 'min_compatible_version', None)
            )

            if not compat_result.is_compatible:
                # 尝试降级
                if self._degrade_handler.can_degrade(tool_name, actual_version, required_version):
                    parameters = self._degrade_handler.degrade_parameters(
                        tool_name, parameters, actual_version, required_version
                    )
                    logger.info(f"Parameters degraded for {tool_name}")
                else:
                    return ToolResult(
                        success=False,
                        error=compat_result.message,
                        metadata={"compatibility": compat_result.to_dict()}
                    )

        # 运行执行前钩子
        self._hooks.run_before_execute(tool, parameters)

        # 初始化统计
        if tool_name not in self._execution_stats:
            self._execution_stats[tool_name] = {
                "total": 0, "success": 0, "failure": 0, "total_time": 0
            }

        start_time = datetime.now()

        try:
            # 执行工具
            if hasattr(tool, 'safe_execute'):
                result = tool.safe_execute(parameters)
            else:
                result = tool.execute(parameters)

            # 更新统计
            elapsed = (datetime.now() - start_time).total_seconds()
            self._execution_stats[tool_name]["total"] += 1
            self._execution_stats[tool_name]["total_time"] += elapsed

            if result.success:
                self._execution_stats[tool_name]["success"] += 1
            else:
                self._execution_stats[tool_name]["failure"] += 1

            # 运行执行后钩子
            self._hooks.run_after_execute(tool, parameters, result)

            return result

        except Exception as e:
            # 运行错误钩子
            self._hooks.run_on_error(tool, e)

            self._execution_stats[tool_name]["total"] += 1
            self._execution_stats[tool_name]["failure"] += 1

            logger.error(f"Tool execution error: {tool_name}, {e}")
            return ToolResult(success=False, error=str(e))

    # =========================================================================
    # 流水线管理
    # =========================================================================

    def register_pipeline(self, pipeline: ToolPipeline) -> bool:
        """注册流水线"""
        self._pipelines[pipeline.name] = pipeline
        logger.info(f"Registered pipeline: {pipeline.name}")
        return True

    def get_pipeline(self, name: str) -> Optional[ToolPipeline]:
        """获取流水线"""
        return self._pipelines.get(name)

    def execute_pipeline(
        self,
        pipeline_name: str,
        input_data: Dict[str, Any] = None
    ) -> PipelineResult:
        """
        执行流水线

        Args:
            pipeline_name: 流水线名称
            input_data: 输入数据

        Returns:
            流水线执行结果
        """
        pipeline = self.get_pipeline(pipeline_name)
        if not pipeline:
            return PipelineResult(
                pipeline_name=pipeline_name,
                success=False,
                step_results=[],
                final_output=None,
                errors=[f"Pipeline '{pipeline_name}' not found"],
                duration=0,
                started_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat()
            )

        # 确保执行器已初始化
        if not self._pipeline_executor:
            self._pipeline_executor = PipelineExecutor(tool_manager=self)

        return self._pipeline_executor.execute(pipeline, input_data)

    def create_pipeline(self, name: str, description: str = "") -> ToolPipeline:
        """创建新流水线"""
        pipeline = ToolPipeline(name=name, description=description)
        return pipeline

    def list_pipelines(self) -> Dict[str, Dict[str, Any]]:
        """列出所有流水线"""
        return {
            name: pipeline.to_dict()
            for name, pipeline in self._pipelines.items()
        }

    # =========================================================================
    # 预定义流水线
    # =========================================================================

    def register_default_pipelines(self):
        """注册预定义流水线"""
        self.register_pipeline(PipelineTemplates.research_pipeline())
        self.register_pipeline(PipelineTemplates.analysis_pipeline())

    # =========================================================================
    # 钩子管理
    # =========================================================================

    @property
    def hooks(self) -> ToolLifecycleHooks:
        """获取钩子管理器"""
        return self._hooks

    # =========================================================================
    # 统计信息
    # =========================================================================

    def get_execution_stats(self, tool_name: str = None) -> Dict[str, Any]:
        """获取执行统计"""
        if tool_name:
            stats = self._execution_stats.get(tool_name, {})
            if stats:
                stats["avg_time"] = stats["total_time"] / max(stats["total"], 1)
                stats["success_rate"] = stats["success"] / max(stats["total"], 1)
            return stats

        all_stats = {}
        for name, stats in self._execution_stats.items():
            all_stats[name] = {
                **stats,
                "avg_time": stats["total_time"] / max(stats["total"], 1),
                "success_rate": stats["success"] / max(stats["total"], 1)
            }
        return all_stats

    def reset_stats(self, tool_name: str = None):
        """重置统计"""
        if tool_name:
            if tool_name in self._execution_stats:
                self._execution_stats[tool_name] = {
                    "total": 0, "success": 0, "failure": 0, "total_time": 0
                }
        else:
            self._execution_stats.clear()

    # =========================================================================
    # 版本兼容性
    # =========================================================================

    def check_compatibility(self, tool_name: str, required_version: str) -> CompatibilityResult:
        """检查工具版本兼容性"""
        return tool_version_registry.check_compatibility(tool_name, required_version)

    def register_degrade_path(
        self,
        tool_name: str,
        from_version: str,
        to_version: str,
        parameter_mapping: Dict[str, str] = None,
        removed_parameters: List[str] = None
    ):
        """
        注册降级路径

        Args:
            tool_name: 工具名称
            from_version: 源版本
            to_version: 目标版本
            parameter_mapping: 参数映射
            removed_parameters: 移除的参数
        """
        from .tool_version import DegradeConfig

        config = DegradeConfig(
            tool_name=tool_name,
            from_version=from_version,
            to_version=to_version,
            parameter_mapping=parameter_mapping or {},
            removed_parameters=removed_parameters or []
        )
        self._degrade_handler.register_degrade_path(config)

    # =========================================================================
    # 工具查询
    # =========================================================================

    def find_tools_by_type(self, tool_type: str) -> List[str]:
        """按类型查找工具"""
        return self._tool_categories.get(tool_type, [])

    def find_tools_by_tags(self, tags: Set[str]) -> List[str]:
        """按标签查找工具"""
        result = []
        for name, metadata in self._tools.items():
            if tags.intersection(metadata.tags):
                result.append(name)
        return result

    def get_tool_dependencies(self, tool_name: str) -> List[ToolDependency]:
        """获取工具依赖"""
        metadata = self._tools.get(tool_name)
        return metadata.dependencies if metadata else []

    # =========================================================================
    # 清理
    # =========================================================================

    def shutdown(self):
        """关闭管理器"""
        if self._pipeline_executor:
            self._pipeline_executor.shutdown()
        logger.info("ToolManager shutdown complete")
