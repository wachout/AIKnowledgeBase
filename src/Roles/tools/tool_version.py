"""
工具版本管理模块

提供语义版本解析、兼容性检查和优雅降级处理。
"""

import re
import logging
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from functools import total_ordering
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# 异常定义
# ============================================================================

class VersionError(Exception):
    """版本相关错误基类"""
    pass


class VersionParseError(VersionError):
    """版本解析错误"""
    pass


class VersionMismatchError(VersionError):
    """版本不兼容错误"""

    def __init__(self, tool_name: str, required_version: str, actual_version: str,
                 message: str = None):
        self.tool_name = tool_name
        self.required_version = required_version
        self.actual_version = actual_version
        self.message = message or (
            f"Tool '{tool_name}' version mismatch: "
            f"required {required_version}, got {actual_version}"
        )
        super().__init__(self.message)


# ============================================================================
# 语义版本类
# ============================================================================

@total_ordering
@dataclass
class ToolVersion:
    """
    语义版本 (Semantic Version)

    遵循 SemVer 2.0.0 规范:
    - MAJOR: 不兼容的 API 变更
    - MINOR: 向后兼容的功能添加
    - PATCH: 向后兼容的问题修复
    """
    major: int = 1
    minor: int = 0
    patch: int = 0
    prerelease: str = ""  # alpha, beta, rc.1 等
    build_metadata: str = ""

    VERSION_PATTERN = re.compile(
        r'^(\d+)\.(\d+)\.(\d+)'
        r'(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
        r'(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$'
    )

    @classmethod
    def parse(cls, version_string: str) -> 'ToolVersion':
        """
        解析版本字符串

        Args:
            version_string: 版本字符串，如 "1.2.3", "2.0.0-beta.1", "1.0.0+build.123"

        Returns:
            ToolVersion 实例

        Raises:
            VersionParseError: 版本字符串格式无效
        """
        if not version_string:
            raise VersionParseError("Version string cannot be empty")

        version_string = version_string.strip()

        # 简化格式支持 (如 "1.0" -> "1.0.0")
        parts = version_string.split('-')[0].split('+')[0].split('.')
        if len(parts) == 2:
            version_string = f"{parts[0]}.{parts[1]}.0"

        match = cls.VERSION_PATTERN.match(version_string)
        if not match:
            raise VersionParseError(f"Invalid version string: '{version_string}'")

        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=match.group(4) or "",
            build_metadata=match.group(5) or ""
        )

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build_metadata:
            version += f"+{self.build_metadata}"
        return version

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            other = ToolVersion.parse(other)
        if not isinstance(other, ToolVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch, self.prerelease) == \
               (other.major, other.minor, other.patch, other.prerelease)

    def __lt__(self, other) -> bool:
        if isinstance(other, str):
            other = ToolVersion.parse(other)
        if not isinstance(other, ToolVersion):
            return NotImplemented

        # 主要版本比较
        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

        # 预发布版本比较 (无预发布 > 有预发布)
        if not self.prerelease and other.prerelease:
            return False
        if self.prerelease and not other.prerelease:
            return True
        return self.prerelease < other.prerelease

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch, self.prerelease))

    @property
    def tuple(self) -> tuple:
        """返回版本元组"""
        return (self.major, self.minor, self.patch)

    def is_compatible_with(self, other: 'ToolVersion') -> bool:
        """
        检查与另一个版本的兼容性

        遵循语义版本兼容性规则:
        - 主版本号不同 -> 不兼容
        - 主版本号相同，当前版本 >= 目标版本 -> 兼容
        """
        if isinstance(other, str):
            other = ToolVersion.parse(other)
        return self.major == other.major and self >= other

    def bump_major(self) -> 'ToolVersion':
        """增加主版本号"""
        return ToolVersion(self.major + 1, 0, 0)

    def bump_minor(self) -> 'ToolVersion':
        """增加次版本号"""
        return ToolVersion(self.major, self.minor + 1, 0)

    def bump_patch(self) -> 'ToolVersion':
        """增加补丁版本号"""
        return ToolVersion(self.major, self.minor, self.patch + 1)


# ============================================================================
# 兼容性检查策略
# ============================================================================

class CompatibilityLevel(Enum):
    """兼容性级别"""
    FULL = "full"              # 完全兼容
    BACKWARD = "backward"      # 向后兼容
    FORWARD = "forward"        # 向前兼容
    NONE = "none"              # 不兼容


@dataclass
class CompatibilityResult:
    """兼容性检查结果"""
    is_compatible: bool
    level: CompatibilityLevel
    tool_name: str
    required_version: str
    actual_version: str
    message: str = ""
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_compatible": self.is_compatible,
            "level": self.level.value,
            "tool_name": self.tool_name,
            "required_version": self.required_version,
            "actual_version": self.actual_version,
            "message": self.message,
            "suggestions": self.suggestions
        }


class CompatibilityChecker:
    """
    版本兼容性检查器

    检查工具版本是否满足要求，并提供兼容性建议。
    """

    def __init__(self, strict_mode: bool = False):
        """
        初始化兼容性检查器

        Args:
            strict_mode: 严格模式，任何版本不匹配都会抛出异常
        """
        self.strict_mode = strict_mode
        self._check_history: List[CompatibilityResult] = []

    def check(
        self,
        tool_name: str,
        required_version: str,
        actual_version: str,
        min_compatible_version: str = None
    ) -> CompatibilityResult:
        """
        检查版本兼容性

        Args:
            tool_name: 工具名称
            required_version: 要求的版本
            actual_version: 实际版本
            min_compatible_version: 最低兼容版本

        Returns:
            兼容性检查结果

        Raises:
            VersionMismatchError: 严格模式下版本不兼容时抛出
        """
        try:
            required = ToolVersion.parse(required_version)
            actual = ToolVersion.parse(actual_version)
            min_compat = ToolVersion.parse(min_compatible_version) if min_compatible_version else actual
        except VersionParseError as e:
            result = CompatibilityResult(
                is_compatible=False,
                level=CompatibilityLevel.NONE,
                tool_name=tool_name,
                required_version=required_version,
                actual_version=actual_version,
                message=f"Version parse error: {e}",
                suggestions=["Check version string format"]
            )
            self._check_history.append(result)
            if self.strict_mode:
                raise VersionMismatchError(tool_name, required_version, actual_version, str(e))
            return result

        # 判断兼容性级别
        is_compatible = False
        level = CompatibilityLevel.NONE
        message = ""
        suggestions = []

        if actual == required:
            # 完全匹配
            is_compatible = True
            level = CompatibilityLevel.FULL
            message = "Exact version match"
        elif actual.major == required.major:
            if actual >= required and actual >= min_compat:
                # 向后兼容
                is_compatible = True
                level = CompatibilityLevel.BACKWARD
                message = f"Backward compatible (actual {actual} >= required {required})"
            elif actual < required and actual.major == required.major:
                # 可能的向前兼容（有风险）
                is_compatible = False
                level = CompatibilityLevel.FORWARD
                message = f"Forward compatibility required (actual {actual} < required {required})"
                suggestions.append(f"Consider upgrading tool to version {required}")
        else:
            # 主版本不同
            level = CompatibilityLevel.NONE
            message = f"Major version mismatch: {actual.major} vs {required.major}"
            suggestions.append(f"Major version change detected, migration may be required")
            if actual.major > required.major:
                suggestions.append("The tool is newer, check for breaking changes")
            else:
                suggestions.append(f"Upgrade tool to version {required_version}")

        result = CompatibilityResult(
            is_compatible=is_compatible,
            level=level,
            tool_name=tool_name,
            required_version=required_version,
            actual_version=actual_version,
            message=message,
            suggestions=suggestions
        )

        self._check_history.append(result)

        if self.strict_mode and not is_compatible:
            raise VersionMismatchError(tool_name, required_version, actual_version, message)

        return result

    def get_check_history(self) -> List[CompatibilityResult]:
        """获取检查历史"""
        return self._check_history.copy()

    def clear_history(self):
        """清空检查历史"""
        self._check_history.clear()


# ============================================================================
# 优雅降级处理器
# ============================================================================

@dataclass
class DegradeConfig:
    """降级配置"""
    tool_name: str
    from_version: str
    to_version: str
    adapter_func: Optional[Callable] = None
    parameter_mapping: Dict[str, str] = field(default_factory=dict)
    removed_parameters: List[str] = field(default_factory=list)
    default_values: Dict[str, Any] = field(default_factory=dict)


class GracefulDegradeHandler:
    """
    优雅降级处理器

    当工具版本不完全兼容时，尝试通过参数适配实现优雅降级。
    """

    def __init__(self):
        self._degrade_configs: Dict[str, List[DegradeConfig]] = {}
        self._degrade_history: List[Dict[str, Any]] = []

    def register_degrade_path(self, config: DegradeConfig):
        """
        注册降级路径

        Args:
            config: 降级配置
        """
        if config.tool_name not in self._degrade_configs:
            self._degrade_configs[config.tool_name] = []
        self._degrade_configs[config.tool_name].append(config)
        logger.info(
            f"Registered degrade path: {config.tool_name} "
            f"{config.from_version} -> {config.to_version}"
        )

    def can_degrade(self, tool_name: str, from_version: str, to_version: str) -> bool:
        """
        检查是否可以降级

        Args:
            tool_name: 工具名称
            from_version: 源版本
            to_version: 目标版本

        Returns:
            是否存在可用的降级路径
        """
        configs = self._degrade_configs.get(tool_name, [])
        for config in configs:
            try:
                from_v = ToolVersion.parse(from_version)
                to_v = ToolVersion.parse(to_version)
                config_from = ToolVersion.parse(config.from_version)
                config_to = ToolVersion.parse(config.to_version)

                # 检查版本范围
                if from_v >= config_from and to_v <= config_to:
                    return True
            except VersionParseError:
                continue
        return False

    def degrade_parameters(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        from_version: str,
        to_version: str
    ) -> Dict[str, Any]:
        """
        降级参数

        Args:
            tool_name: 工具名称
            parameters: 原始参数
            from_version: 源版本
            to_version: 目标版本

        Returns:
            适配后的参数
        """
        adapted_params = parameters.copy()
        configs = self._degrade_configs.get(tool_name, [])

        applied_config = None
        for config in configs:
            try:
                from_v = ToolVersion.parse(from_version)
                to_v = ToolVersion.parse(to_version)
                config_from = ToolVersion.parse(config.from_version)
                config_to = ToolVersion.parse(config.to_version)

                if from_v >= config_from and to_v <= config_to:
                    applied_config = config
                    break
            except VersionParseError:
                continue

        if not applied_config:
            logger.warning(
                f"No degrade config found for {tool_name}: "
                f"{from_version} -> {to_version}"
            )
            return adapted_params

        # 应用参数映射
        for old_name, new_name in applied_config.parameter_mapping.items():
            if old_name in adapted_params:
                adapted_params[new_name] = adapted_params.pop(old_name)
                logger.debug(f"Parameter mapped: {old_name} -> {new_name}")

        # 移除不支持的参数
        for removed_param in applied_config.removed_parameters:
            if removed_param in adapted_params:
                del adapted_params[removed_param]
                logger.debug(f"Parameter removed: {removed_param}")

        # 添加默认值
        for param_name, default_value in applied_config.default_values.items():
            if param_name not in adapted_params:
                adapted_params[param_name] = default_value
                logger.debug(f"Default value added: {param_name}={default_value}")

        # 应用自定义适配函数
        if applied_config.adapter_func:
            try:
                adapted_params = applied_config.adapter_func(adapted_params)
            except Exception as e:
                logger.error(f"Adapter function error: {e}")

        # 记录降级历史
        self._degrade_history.append({
            "tool_name": tool_name,
            "from_version": from_version,
            "to_version": to_version,
            "original_params": list(parameters.keys()),
            "adapted_params": list(adapted_params.keys()),
            "timestamp": datetime.now().isoformat()
        })

        return adapted_params

    def get_degrade_history(self) -> List[Dict[str, Any]]:
        """获取降级历史"""
        return self._degrade_history.copy()


# ============================================================================
# 版本注册表
# ============================================================================

class ToolVersionRegistry:
    """
    工具版本注册表

    集中管理所有工具的版本信息和兼容性关系。
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
        self._versions: Dict[str, Dict[str, Any]] = {}
        self._compatibility_checker = CompatibilityChecker()
        self._degrade_handler = GracefulDegradeHandler()
        self._initialized = True

    def register(
        self,
        tool_name: str,
        version: str,
        min_compatible_version: str = None,
        deprecated: bool = False,
        successor: str = None
    ):
        """
        注册工具版本

        Args:
            tool_name: 工具名称
            version: 版本号
            min_compatible_version: 最低兼容版本
            deprecated: 是否已废弃
            successor: 替代工具名称
        """
        self._versions[tool_name] = {
            "version": version,
            "min_compatible_version": min_compatible_version or version,
            "deprecated": deprecated,
            "successor": successor,
            "registered_at": datetime.now().isoformat()
        }

    def get_version(self, tool_name: str) -> Optional[str]:
        """获取工具版本"""
        info = self._versions.get(tool_name)
        return info["version"] if info else None

    def check_compatibility(self, tool_name: str, required_version: str) -> CompatibilityResult:
        """检查工具版本兼容性"""
        info = self._versions.get(tool_name)
        if not info:
            return CompatibilityResult(
                is_compatible=False,
                level=CompatibilityLevel.NONE,
                tool_name=tool_name,
                required_version=required_version,
                actual_version="unknown",
                message=f"Tool '{tool_name}' not registered",
                suggestions=["Register the tool first"]
            )

        return self._compatibility_checker.check(
            tool_name,
            required_version,
            info["version"],
            info["min_compatible_version"]
        )

    def list_tools(self) -> Dict[str, Dict[str, Any]]:
        """列出所有注册的工具"""
        return self._versions.copy()

    @property
    def degrade_handler(self) -> GracefulDegradeHandler:
        """获取降级处理器"""
        return self._degrade_handler


# 全局版本注册表实例
tool_version_registry = ToolVersionRegistry()
