"""
工具流水线模块

提供声明式的工具组合与编排能力，支持串行、并行执行策略。
"""

import re
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable, Union, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

if TYPE_CHECKING:
    from .base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


# ============================================================================
# 枚举与配置
# ============================================================================

class ExecutionStrategy(Enum):
    """执行策略"""
    SEQUENTIAL = "sequential"  # 串行执行
    PARALLEL = "parallel"      # 并行执行
    CONDITIONAL = "conditional"  # 条件执行


class FailurePolicy(Enum):
    """失败策略"""
    ABORT = "abort"      # 终止流水线
    SKIP = "skip"        # 跳过当前步骤
    RETRY = "retry"      # 重试
    FALLBACK = "fallback"  # 使用回退方案


class StepStatus(Enum):
    """步骤状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    RETRYING = "retrying"


# ============================================================================
# 步骤定义
# ============================================================================

@dataclass
class ToolPipelineStep:
    """
    流水线步骤定义

    支持动态参数模板，使用 {input.xxx} 或 {step_N.xxx} 引用。
    """
    tool_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    step_id: str = ""
    name: str = ""
    condition: str = ""  # Python 表达式，如 "len(prev.data.results) < 3"
    on_failure: FailurePolicy = FailurePolicy.ABORT
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    fallback_tool: str = ""
    fallback_parameters: Dict[str, Any] = field(default_factory=dict)

    # 运行时状态
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str = ""
    attempts: int = 0
    started_at: str = ""
    completed_at: str = ""

    def __post_init__(self):
        if not self.step_id:
            self.step_id = f"step_{id(self)}"
        if not self.name:
            self.name = f"{self.tool_name}_step"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "name": self.name,
            "parameters": self.parameters,
            "condition": self.condition,
            "on_failure": self.on_failure.value,
            "max_retries": self.max_retries,
            "status": self.status.value,
            "result": self.result.to_dict() if hasattr(self.result, 'to_dict') else self.result,
            "error": self.error,
            "attempts": self.attempts
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolPipelineStep':
        return cls(
            step_id=data.get("step_id", ""),
            tool_name=data["tool_name"],
            name=data.get("name", ""),
            parameters=data.get("parameters", {}),
            condition=data.get("condition", ""),
            on_failure=FailurePolicy(data.get("on_failure", "abort")),
            max_retries=data.get("max_retries", 3),
            retry_delay=data.get("retry_delay", 1.0),
            timeout=data.get("timeout", 30.0),
            fallback_tool=data.get("fallback_tool", ""),
            fallback_parameters=data.get("fallback_parameters", {})
        )


# ============================================================================
# 流水线上下文
# ============================================================================

@dataclass
class PipelineContext:
    """流水线执行上下文"""
    input_data: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    current_step_index: int = 0
    previous_result: Any = None

    def get(self, path: str) -> Any:
        """
        根据路径获取值

        支持的路径格式:
        - input.xxx: 输入数据
        - step_N.xxx: 步骤结果
        - prev.xxx: 上一步结果
        - vars.xxx: 变量
        """
        parts = path.split(".")
        if not parts:
            return None

        root = parts[0]
        rest = ".".join(parts[1:]) if len(parts) > 1 else ""

        if root == "input":
            obj = self.input_data
        elif root == "prev":
            obj = self.previous_result
        elif root == "vars":
            obj = self.variables
        elif root.startswith("step_"):
            step_key = root
            obj = self.step_results.get(step_key)
        else:
            return None

        if not rest:
            return obj

        return self._get_nested(obj, rest)

    def _get_nested(self, obj: Any, path: str) -> Any:
        """获取嵌套值"""
        parts = path.split(".")
        current = obj

        for part in parts:
            if current is None:
                return None

            # 支持数组索引，如 results[0]
            match = re.match(r'(\w+)\[(\d+)\]', part)
            if match:
                key, index = match.groups()
                if isinstance(current, dict):
                    current = current.get(key, [])
                if isinstance(current, list) and int(index) < len(current):
                    current = current[int(index)]
                else:
                    return None
            elif isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            elif hasattr(current, 'to_dict'):
                current = current.to_dict().get(part)
            else:
                return None

        return current

    def set_step_result(self, step_id: str, result: Any):
        """设置步骤结果"""
        self.step_results[step_id] = result
        self.previous_result = result


# ============================================================================
# 参数解析器
# ============================================================================

class ParameterResolver:
    """参数模板解析器"""

    PATTERN = re.compile(r'\{([^}]+)\}')

    @classmethod
    def resolve(cls, template: Any, context: PipelineContext) -> Any:
        """解析参数模板"""
        if isinstance(template, str):
            return cls._resolve_string(template, context)
        elif isinstance(template, dict):
            return {k: cls.resolve(v, context) for k, v in template.items()}
        elif isinstance(template, list):
            return [cls.resolve(item, context) for item in template]
        else:
            return template

    @classmethod
    def _resolve_string(cls, template: str, context: PipelineContext) -> Any:
        """解析字符串模板"""
        # 完全匹配的情况，返回原始值（保持类型）
        full_match = re.fullmatch(r'\{([^}]+)\}', template)
        if full_match:
            path = full_match.group(1)
            return context.get(path)

        # 部分匹配，进行字符串替换
        def replacer(match):
            path = match.group(1)
            value = context.get(path)
            return str(value) if value is not None else ""

        return cls.PATTERN.sub(replacer, template)


# ============================================================================
# 条件评估器
# ============================================================================

class ConditionEvaluator:
    """条件表达式评估器"""

    @staticmethod
    def evaluate(condition: str, context: PipelineContext) -> bool:
        """
        评估条件表达式

        支持的变量:
        - prev: 上一步结果
        - input: 输入数据
        - step_N: 步骤结果
        """
        if not condition:
            return True

        try:
            # 构建评估环境
            eval_context = {
                "prev": context.previous_result,
                "input": context.input_data,
                "vars": context.variables,
                "len": len,
                "bool": bool,
                "str": str,
                "int": int,
                "float": float,
            }

            # 添加步骤结果
            for step_id, result in context.step_results.items():
                eval_context[step_id] = result

            # 安全评估
            result = eval(condition, {"__builtins__": {}}, eval_context)
            return bool(result)

        except Exception as e:
            logger.warning(f"Condition evaluation failed: {condition}, error: {e}")
            return True  # 默认执行


# ============================================================================
# 流水线执行器
# ============================================================================

class PipelineExecutor:
    """流水线执行器"""

    def __init__(self, tool_manager: 'ToolManager' = None, max_workers: int = 4):
        self.tool_manager = tool_manager
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def execute(
        self,
        pipeline: 'ToolPipeline',
        input_data: Dict[str, Any] = None
    ) -> 'PipelineResult':
        """
        执行流水线

        Args:
            pipeline: 流水线定义
            input_data: 输入数据

        Returns:
            执行结果
        """
        context = PipelineContext(input_data=input_data or {})
        start_time = datetime.now()

        results = []
        errors = []
        step_index = 0

        for group in pipeline.step_groups:
            if group.strategy == ExecutionStrategy.PARALLEL:
                # 并行执行
                group_results = self._execute_parallel(group.steps, context)
            else:
                # 串行执行
                group_results = self._execute_sequential(group.steps, context)

            for step, result in group_results:
                results.append((step, result))
                context.current_step_index = step_index
                step_index += 1

                if not result.success and step.on_failure == FailurePolicy.ABORT:
                    errors.append(step.error)
                    break

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        return PipelineResult(
            pipeline_name=pipeline.name,
            success=len(errors) == 0,
            step_results=[s[0].to_dict() for s in results],
            final_output=context.previous_result,
            errors=errors,
            duration=duration,
            started_at=start_time.isoformat(),
            completed_at=end_time.isoformat()
        )

    def _execute_sequential(
        self,
        steps: List[ToolPipelineStep],
        context: PipelineContext
    ) -> List[tuple]:
        """串行执行步骤"""
        results = []

        for step in steps:
            result = self._execute_step(step, context)
            results.append((step, result))

            if result.success:
                context.set_step_result(step.step_id, result)
            elif step.on_failure == FailurePolicy.ABORT:
                break

        return results

    def _execute_parallel(
        self,
        steps: List[ToolPipelineStep],
        context: PipelineContext
    ) -> List[tuple]:
        """并行执行步骤"""
        results = []
        futures = {}

        for step in steps:
            future = self._executor.submit(self._execute_step, step, context)
            futures[future] = step

        for future in as_completed(futures):
            step = futures[future]
            try:
                result = future.result()
                results.append((step, result))
                context.set_step_result(step.step_id, result)
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
                from .base_tool import ToolResult
                results.append((step, ToolResult(success=False, error=str(e))))

        return results

    def _execute_step(
        self,
        step: ToolPipelineStep,
        context: PipelineContext
    ) -> 'ToolResult':
        """执行单个步骤"""
        from .base_tool import ToolResult

        step.started_at = datetime.now().isoformat()
        step.status = StepStatus.RUNNING

        # 检查条件
        if step.condition:
            should_execute = ConditionEvaluator.evaluate(step.condition, context)
            if not should_execute:
                step.status = StepStatus.SKIPPED
                step.completed_at = datetime.now().isoformat()
                return ToolResult(
                    success=True,
                    data={"skipped": True, "reason": "Condition not met"},
                    metadata={"step_id": step.step_id}
                )

        # 解析参数
        resolved_params = ParameterResolver.resolve(step.parameters, context)

        # 获取工具
        if not self.tool_manager:
            step.status = StepStatus.FAILED
            step.error = "Tool manager not configured"
            return ToolResult(success=False, error=step.error)

        tool = self.tool_manager.get_tool(step.tool_name)
        if not tool:
            step.status = StepStatus.FAILED
            step.error = f"Tool '{step.tool_name}' not found"
            return ToolResult(success=False, error=step.error)

        # 执行工具（带重试）
        result = None
        for attempt in range(step.max_retries):
            step.attempts = attempt + 1

            try:
                if hasattr(tool, 'safe_execute'):
                    result = tool.safe_execute(resolved_params)
                else:
                    result = tool.execute(resolved_params)

                if result.success:
                    break

                # 失败但可重试
                if step.on_failure == FailurePolicy.RETRY and attempt < step.max_retries - 1:
                    step.status = StepStatus.RETRYING
                    import time
                    time.sleep(step.retry_delay * (attempt + 1))
                else:
                    break

            except Exception as e:
                logger.error(f"Step {step.step_id} execution error: {e}")
                result = ToolResult(success=False, error=str(e))

                if step.on_failure != FailurePolicy.RETRY or attempt >= step.max_retries - 1:
                    break

        # 处理失败情况
        if result and not result.success:
            if step.on_failure == FailurePolicy.FALLBACK and step.fallback_tool:
                result = self._execute_fallback(step, context)
            elif step.on_failure == FailurePolicy.SKIP:
                result = ToolResult(
                    success=True,
                    data={"skipped": True, "original_error": result.error},
                    metadata={"step_id": step.step_id}
                )

        # 更新状态
        step.result = result
        step.completed_at = datetime.now().isoformat()
        step.status = StepStatus.COMPLETED if result.success else StepStatus.FAILED
        if not result.success:
            step.error = result.error or "Unknown error"

        return result

    def _execute_fallback(
        self,
        step: ToolPipelineStep,
        context: PipelineContext
    ) -> 'ToolResult':
        """执行回退方案"""
        from .base_tool import ToolResult

        fallback_tool = self.tool_manager.get_tool(step.fallback_tool)
        if not fallback_tool:
            return ToolResult(
                success=False,
                error=f"Fallback tool '{step.fallback_tool}' not found"
            )

        resolved_params = ParameterResolver.resolve(step.fallback_parameters, context)

        try:
            return fallback_tool.execute(resolved_params)
        except Exception as e:
            return ToolResult(success=False, error=f"Fallback failed: {e}")

    def shutdown(self):
        """关闭执行器"""
        self._executor.shutdown(wait=True)


# ============================================================================
# 步骤组（支持并行）
# ============================================================================

@dataclass
class StepGroup:
    """步骤组，支持不同执行策略"""
    steps: List[ToolPipelineStep] = field(default_factory=list)
    strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL
    name: str = ""


# ============================================================================
# 流水线定义
# ============================================================================

@dataclass
class PipelineResult:
    """流水线执行结果"""
    pipeline_name: str
    success: bool
    step_results: List[Dict[str, Any]]
    final_output: Any
    errors: List[str]
    duration: float
    started_at: str
    completed_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_name": self.pipeline_name,
            "success": self.success,
            "step_results": self.step_results,
            "final_output": self.final_output.to_dict() if hasattr(self.final_output, 'to_dict') else self.final_output,
            "errors": self.errors,
            "duration": self.duration,
            "started_at": self.started_at,
            "completed_at": self.completed_at
        }


class ToolPipeline:
    """
    工具流水线

    支持声明式的工具组合配置。
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.step_groups: List[StepGroup] = []
        self._current_group: StepGroup = StepGroup(strategy=ExecutionStrategy.SEQUENTIAL)
        self.created_at = datetime.now().isoformat()
        self.version = "1.0.0"

    def add_step(self, step: ToolPipelineStep) -> 'ToolPipeline':
        """添加步骤（串行）"""
        self._current_group.steps.append(step)
        return self

    def add_sequential_steps(self, steps: List[ToolPipelineStep]) -> 'ToolPipeline':
        """添加串行步骤组"""
        if self._current_group.steps:
            self.step_groups.append(self._current_group)

        self._current_group = StepGroup(
            steps=steps,
            strategy=ExecutionStrategy.SEQUENTIAL
        )
        return self

    def add_parallel_steps(self, steps: List[ToolPipelineStep]) -> 'ToolPipeline':
        """添加并行步骤组"""
        if self._current_group.steps:
            self.step_groups.append(self._current_group)
            self._current_group = StepGroup(strategy=ExecutionStrategy.SEQUENTIAL)

        self.step_groups.append(StepGroup(
            steps=steps,
            strategy=ExecutionStrategy.PARALLEL
        ))
        return self

    def finalize(self) -> 'ToolPipeline':
        """完成流水线定义"""
        if self._current_group.steps:
            self.step_groups.append(self._current_group)
            self._current_group = StepGroup(strategy=ExecutionStrategy.SEQUENTIAL)
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.finalize()
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "step_groups": [
                {
                    "strategy": g.strategy.value,
                    "steps": [s.to_dict() for s in g.steps]
                }
                for g in self.step_groups
            ],
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolPipeline':
        """从字典创建流水线"""
        pipeline = cls(
            name=data["name"],
            description=data.get("description", "")
        )
        pipeline.version = data.get("version", "1.0.0")

        for group_data in data.get("step_groups", []):
            steps = [
                ToolPipelineStep.from_dict(s)
                for s in group_data.get("steps", [])
            ]
            strategy = ExecutionStrategy(group_data.get("strategy", "sequential"))

            pipeline.step_groups.append(StepGroup(
                steps=steps,
                strategy=strategy
            ))

        return pipeline

    @classmethod
    def from_yaml(cls, yaml_content: str) -> 'ToolPipeline':
        """从YAML创建流水线"""
        try:
            import yaml
            data = yaml.safe_load(yaml_content)
            return cls.from_dict(data)
        except ImportError:
            raise ImportError("PyYAML is required for YAML parsing")


# ============================================================================
# 预定义流水线模板
# ============================================================================

class PipelineTemplates:
    """预定义流水线模板"""

    @staticmethod
    def research_pipeline() -> ToolPipeline:
        """研究型流水线：知识搜索 -> 网络搜索 -> 结果合并"""
        pipeline = ToolPipeline(
            name="research_pipeline",
            description="综合研究流水线，先搜索知识库，不足则搜索网络"
        )

        # 知识库搜索
        pipeline.add_step(ToolPipelineStep(
            step_id="step_0",
            tool_name="knowledge_search",
            parameters={"query": "{input.query}", "limit": 10},
            on_failure=FailurePolicy.SKIP
        ))

        # 条件网络搜索
        pipeline.add_step(ToolPipelineStep(
            step_id="step_1",
            tool_name="web_search",
            parameters={"query": "{input.query}", "limit": 5},
            condition="not prev or len(prev.data.get('results', [])) < 3",
            on_failure=FailurePolicy.SKIP
        ))

        return pipeline.finalize()

    @staticmethod
    def analysis_pipeline() -> ToolPipeline:
        """分析型流水线：数据分析 -> 通信结果"""
        pipeline = ToolPipeline(
            name="analysis_pipeline",
            description="数据分析流水线"
        )

        pipeline.add_step(ToolPipelineStep(
            step_id="step_0",
            tool_name="data_analysis",
            parameters={
                "data": "{input.data}",
                "analysis_type": "{input.analysis_type}"
            },
            on_failure=FailurePolicy.ABORT
        ))

        pipeline.add_step(ToolPipelineStep(
            step_id="step_1",
            tool_name="communication",
            parameters={
                "action": "notify",
                "message": "分析完成: {step_0.data}",
                "message_type": "info"
            },
            on_failure=FailurePolicy.SKIP
        ))

        return pipeline.finalize()
