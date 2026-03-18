# -*- coding: utf-8 -*-
"""
写代码工具智能体

为第三层具象化智能体提供代码编写能力，实现软件功能、算法功能等。
支持多种编程语言，可根据任务需求生成对应的代码实现。
"""

import logging
import uuid
import json
import re
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime

from .base_tool import (
    BaseTool,
    ToolResult,
    ParameterType,
    ParameterDefinition,
    ParameterSchema,
    QualityAssessment
)

try:
    from Config.llm_config import get_chat, get_chat_long
except Exception:
    get_chat = None
    get_chat_long = None

logger = logging.getLogger(__name__)


# ============================================================================
# 代码类型枚举
# ============================================================================

class CodeLanguage:
    """支持的编程语言"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CPP = "cpp"
    C = "c"
    RUST = "rust"
    GO = "go"
    SHELL = "shell"
    SQL = "sql"
    HTML = "html"
    CSS = "css"
    YAML = "yaml"
    JSON = "json"
    MARKDOWN = "markdown"
    OTHER = "other"


class CodeType:
    """代码类型"""
    ALGORITHM = "algorithm"      # 算法实现
    FUNCTION = "function"        # 函数/方法
    CLASS = "class"              # 类定义
    MODULE = "module"            # 模块/包
    SCRIPT = "script"            # 脚本
    API = "api"                  # API接口
    DATABASE = "database"        # 数据库操作
    CONFIG = "config"            # 配置文件
    TEST = "test"                # 测试代码
    UTILITY = "utility"          # 工具函数


# ============================================================================
# 代码生成结果
# ============================================================================

@dataclass
class CodeGenerationResult:
    """代码生成结果"""
    success: bool
    language: str
    code_type: str
    code: str
    filename: str = ""
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    usage_example: str = ""
    error: str = ""
    raw_response: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "language": self.language,
            "code_type": self.code_type,
            "code": self.code,
            "filename": self.filename,
            "description": self.description,
            "dependencies": self.dependencies,
            "usage_example": self.usage_example,
            "error": self.error,
            "raw_response": self.raw_response[:2000] if self.raw_response else "",
            "generated_at": self.generated_at
        }


# ============================================================================
# 写代码工具智能体
# ============================================================================

class CodeWriterTool(BaseTool):
    """
    写代码工具智能体

    为第三层具象化智能体提供代码编写能力：
    - 根据具象化描述生成对应的代码实现
    - 支持多种编程语言（Python、JavaScript、Java等）
    - 支持多种代码类型（算法、函数、类、模块等）
    - 自动生成依赖列表和使用示例
    """

    def __init__(
        self,
        tool_id: str = None,
        llm_adapter=None,
        default_language: str = CodeLanguage.PYTHON
    ):
        # 定义参数模式
        schema = ParameterSchema(
            parameters=[
                ParameterDefinition(
                    name="task_description",
                    param_type=ParameterType.STRING,
                    description="任务描述：需要实现的功能或算法",
                    required=True
                ),
                ParameterDefinition(
                    name="language",
                    param_type=ParameterType.STRING,
                    description="编程语言",
                    required=False,
                    default=CodeLanguage.PYTHON,
                    constraints={"enum": [
                        CodeLanguage.PYTHON, CodeLanguage.JAVASCRIPT, 
                        CodeLanguage.TYPESCRIPT, CodeLanguage.JAVA,
                        CodeLanguage.CPP, CodeLanguage.C, CodeLanguage.RUST,
                        CodeLanguage.GO, CodeLanguage.SHELL, CodeLanguage.SQL,
                        CodeLanguage.OTHER
                    ]}
                ),
                ParameterDefinition(
                    name="code_type",
                    param_type=ParameterType.STRING,
                    description="代码类型",
                    required=False,
                    default=CodeType.FUNCTION,
                    constraints={"enum": [
                        CodeType.ALGORITHM, CodeType.FUNCTION, CodeType.CLASS,
                        CodeType.MODULE, CodeType.SCRIPT, CodeType.API,
                        CodeType.DATABASE, CodeType.CONFIG, CodeType.TEST,
                        CodeType.UTILITY
                    ]}
                ),
                ParameterDefinition(
                    name="context",
                    param_type=ParameterType.STRING,
                    description="上下文信息（如具象化描述、数字化描述等）",
                    required=False,
                    default=""
                ),
                ParameterDefinition(
                    name="constraints",
                    param_type=ParameterType.LIST,
                    description="代码约束条件（如性能要求、兼容性要求等）",
                    required=False,
                    default=[]
                )
            ],
            version="1.0.0"
        )

        super().__init__(
            name="code_writer",
            description="写代码工具智能体：根据具象化描述生成代码实现，支持多种编程语言和代码类型",
            tool_type="implementation",
            version="1.0.0",
            parameter_schema=schema
        )

        self.tool_id = tool_id or f"code_writer_{uuid.uuid4().hex[:6]}"
        self.llm_adapter = llm_adapter
        self.default_language = default_language
        self.generation_history: List[CodeGenerationResult] = []

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        同步执行代码生成（使用同步LLM调用）

        Args:
            parameters: 包含 task_description, language, code_type, context, constraints

        Returns:
            ToolResult 包含生成的代码
        """
        try:
            task_description = parameters.get("task_description", "")
            if not task_description:
                return ToolResult(
                    success=False,
                    error="缺少任务描述(task_description)",
                    metadata={"tool_id": self.tool_id}
                )

            language = parameters.get("language", self.default_language)
            code_type = parameters.get("code_type", CodeType.FUNCTION)
            context = parameters.get("context", "")
            constraints = parameters.get("constraints", [])

            # 构建提示词
            prompt = self._build_code_generation_prompt(
                task_description=task_description,
                language=language,
                code_type=code_type,
                context=context,
                constraints=constraints
            )

            # 调用LLM
            response = self._invoke_llm_sync(prompt)
            if not response:
                return ToolResult(
                    success=False,
                    error="LLM调用失败或返回为空",
                    metadata={"tool_id": self.tool_id}
                )

            # 解析响应
            result = self._parse_code_response(response, language, code_type)
            self.generation_history.append(result)

            if result.success:
                return ToolResult(
                    success=True,
                    data=result.to_dict(),
                    metadata={
                        "tool_id": self.tool_id,
                        "language": language,
                        "code_type": code_type
                    },
                    quality_assessment=self._assess_code_quality(result)
                )
            else:
                return ToolResult(
                    success=False,
                    data=result.to_dict(),
                    error=result.error or "代码生成失败",
                    metadata={"tool_id": self.tool_id}
                )

        except Exception as e:
            logger.exception(f"代码生成异常: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"tool_id": self.tool_id}
            )

    async def execute_async(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        异步执行代码生成

        Args:
            parameters: 包含 task_description, language, code_type, context, constraints

        Returns:
            ToolResult 包含生成的代码
        """
        try:
            task_description = parameters.get("task_description", "")
            if not task_description:
                return ToolResult(
                    success=False,
                    error="缺少任务描述(task_description)",
                    metadata={"tool_id": self.tool_id}
                )

            language = parameters.get("language", self.default_language)
            code_type = parameters.get("code_type", CodeType.FUNCTION)
            context = parameters.get("context", "")
            constraints = parameters.get("constraints", [])

            # 构建提示词
            prompt = self._build_code_generation_prompt(
                task_description=task_description,
                language=language,
                code_type=code_type,
                context=context,
                constraints=constraints
            )

            # 异步调用LLM
            response = await self._invoke_llm_async(prompt)
            if not response:
                return ToolResult(
                    success=False,
                    error="LLM调用失败或返回为空",
                    metadata={"tool_id": self.tool_id}
                )

            # 解析响应
            result = self._parse_code_response(response, language, code_type)
            self.generation_history.append(result)

            if result.success:
                return ToolResult(
                    success=True,
                    data=result.to_dict(),
                    metadata={
                        "tool_id": self.tool_id,
                        "language": language,
                        "code_type": code_type
                    },
                    quality_assessment=self._assess_code_quality(result)
                )
            else:
                return ToolResult(
                    success=False,
                    data=result.to_dict(),
                    error=result.error or "代码生成失败",
                    metadata={"tool_id": self.tool_id}
                )

        except Exception as e:
            logger.exception(f"代码生成异常: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"tool_id": self.tool_id}
            )

    async def generate_code_stream(
        self,
        task_description: str,
        language: str = None,
        code_type: str = None,
        context: str = "",
        constraints: List[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        流式生成代码

        Args:
            task_description: 任务描述
            language: 编程语言
            code_type: 代码类型
            context: 上下文信息
            constraints: 约束条件

        Yields:
            生成的代码片段
        """
        language = language or self.default_language
        code_type = code_type or CodeType.FUNCTION
        constraints = constraints or []

        prompt = self._build_code_generation_prompt(
            task_description=task_description,
            language=language,
            code_type=code_type,
            context=context,
            constraints=constraints
        )

        response_parts = []
        async for chunk in self._invoke_llm_stream(prompt):
            yield chunk
            response_parts.append(chunk)

        # 解析完整响应并保存到历史
        full_response = "".join(response_parts)
        result = self._parse_code_response(full_response, language, code_type)
        self.generation_history.append(result)

    def _build_code_generation_prompt(
        self,
        task_description: str,
        language: str,
        code_type: str,
        context: str = "",
        constraints: List[str] = None
    ) -> str:
        """构建代码生成提示词"""
        constraints = constraints or []
        constraints_block = ""
        if constraints:
            constraints_list = "\n".join(f"- {c}" for c in constraints)
            constraints_block = f"""
## 代码约束条件

{constraints_list}
"""

        context_block = ""
        if context:
            context_block = f"""
## 上下文信息（来自具象化描述）

{context}
"""

        return f"""# Role：代码实现专家

## Background
你是一位经验丰富的软件工程师，擅长将具象化的需求描述转化为高质量的代码实现。
你需要根据任务描述和上下文信息，生成符合要求的代码。

## 任务信息

- **任务描述**: {task_description}
- **编程语言**: {language}
- **代码类型**: {code_type}
{context_block}{constraints_block}
## 代码要求

1. **代码质量**：代码应清晰、简洁、易于维护
2. **注释完善**：关键逻辑需添加注释说明
3. **错误处理**：包含必要的异常处理和边界检查
4. **性能考虑**：在满足功能的前提下优化性能
5. **最佳实践**：遵循{language}语言的最佳实践和编码规范

## 输出格式（JSON，放在 ```json 代码块中）

```json
{{
  "filename": "建议的文件名",
  "description": "代码功能描述",
  "code": "完整的代码内容（使用转义的换行符）",
  "dependencies": ["依赖项1", "依赖项2"],
  "usage_example": "使用示例代码"
}}
```

请生成代码：
"""

    def _invoke_llm_sync(self, prompt: str) -> Optional[str]:
        """同步调用LLM"""
        try:
            if self.llm_adapter:
                response = self.llm_adapter.invoke(prompt)
                return response.content if hasattr(response, "content") else str(response)

            if get_chat:
                llm = get_chat(temperature=0.2, streaming=False)
                response = llm.invoke(prompt)
                return response.content if hasattr(response, "content") else str(response)

            logger.warning("无可用LLM适配器")
            return None
        except Exception as e:
            logger.exception(f"LLM同步调用失败: {e}")
            return None

    async def _invoke_llm_async(self, prompt: str) -> Optional[str]:
        """异步调用LLM"""
        try:
            import asyncio

            if self.llm_adapter:
                if hasattr(self.llm_adapter, "ainvoke"):
                    response = await self.llm_adapter.ainvoke(prompt)
                else:
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None, lambda: self.llm_adapter.invoke(prompt)
                    )
                return response.content if hasattr(response, "content") else str(response)

            if get_chat:
                llm = get_chat(temperature=0.2, streaming=False)
                if hasattr(llm, "ainvoke"):
                    response = await llm.ainvoke(prompt)
                else:
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None, lambda: llm.invoke(prompt)
                    )
                return response.content if hasattr(response, "content") else str(response)

            logger.warning("无可用LLM适配器")
            return None
        except Exception as e:
            logger.exception(f"LLM异步调用失败: {e}")
            return None

    async def _invoke_llm_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """流式调用LLM"""
        try:
            if self.llm_adapter and hasattr(self.llm_adapter, "astream"):
                async for chunk in self.llm_adapter.astream(prompt):
                    if hasattr(chunk, "content"):
                        yield chunk.content
                    else:
                        yield str(chunk)
                return

            if get_chat:
                llm = get_chat(temperature=0.2, streaming=True)
                if hasattr(llm, "astream"):
                    async for chunk in llm.astream(prompt):
                        if hasattr(chunk, "content"):
                            yield chunk.content
                        else:
                            yield str(chunk)
                    return

            # 回退到同步调用
            response = await self._invoke_llm_async(prompt)
            if response:
                yield response
        except Exception as e:
            logger.exception(f"LLM流式调用失败: {e}")
            yield f"[错误] LLM调用失败: {e}"

    def _parse_code_response(
        self, response: str, language: str, code_type: str
    ) -> CodeGenerationResult:
        """解析LLM返回的代码响应"""
        result = CodeGenerationResult(
            success=False,
            language=language,
            code_type=code_type,
            code="",
            raw_response=response
        )

        try:
            # 尝试解析JSON
            m = re.search(r"```json\s*([\s\S]*?)\s*```", response)
            if m:
                json_str = m.group(1)
                # 清理控制字符
                json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', ' ', json_str)
                data = json.loads(json_str)

                result.success = True
                result.filename = data.get("filename", "")
                result.description = data.get("description", "")
                result.code = data.get("code", "")
                result.dependencies = data.get("dependencies", [])
                result.usage_example = data.get("usage_example", "")
                return result

            # 尝试提取代码块
            code_pattern = rf"```{language}\s*([\s\S]*?)\s*```"
            m = re.search(code_pattern, response, re.IGNORECASE)
            if not m:
                # 尝试通用代码块
                m = re.search(r"```\s*([\s\S]*?)\s*```", response)

            if m:
                result.success = True
                result.code = m.group(1).strip()
                result.description = "从响应中提取的代码"
                return result

            # 无法解析，将整个响应作为代码
            if response.strip():
                result.success = True
                result.code = response.strip()
                result.description = "原始响应（未能解析结构化输出）"

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"解析代码响应失败: {e}")
            result.error = f"解析失败: {e}"
            # 尝试提取任何代码块
            m = re.search(r"```[\w]*\s*([\s\S]*?)\s*```", response)
            if m:
                result.success = True
                result.code = m.group(1).strip()

        return result

    def _assess_code_quality(self, result: CodeGenerationResult) -> QualityAssessment:
        """评估代码质量"""
        assessment = QualityAssessment()

        if not result.success or not result.code:
            assessment.relevance_score = 0.0
            assessment.confidence_score = 0.0
            assessment.completeness_score = 0.0
            assessment.quality_level = "LOW"
            return assessment

        # 基于代码长度和结构评估
        code_lines = len(result.code.split("\n"))
        has_comments = "#" in result.code or "//" in result.code or "/*" in result.code
        has_functions = "def " in result.code or "function " in result.code or "fn " in result.code
        has_error_handling = "try" in result.code or "except" in result.code or "catch" in result.code

        # 相关性：基于是否生成了代码和描述
        assessment.relevance_score = 0.8 if result.code else 0.0
        if result.description:
            assessment.relevance_score += 0.1
        if result.usage_example:
            assessment.relevance_score += 0.1

        # 可信度：基于代码结构
        confidence = 0.5
        if has_comments:
            confidence += 0.15
        if has_functions:
            confidence += 0.15
        if has_error_handling:
            confidence += 0.1
        if code_lines > 5:
            confidence += 0.1
        assessment.confidence_score = min(confidence, 1.0)

        # 完整性：基于输出字段
        completeness = 0.3  # 有代码基础分
        if result.filename:
            completeness += 0.15
        if result.description:
            completeness += 0.15
        if result.dependencies:
            completeness += 0.2
        if result.usage_example:
            completeness += 0.2
        assessment.completeness_score = min(completeness, 1.0)

        assessment.determine_quality_level()
        assessment.assessment_details = {
            "code_lines": code_lines,
            "has_comments": has_comments,
            "has_functions": has_functions,
            "has_error_handling": has_error_handling
        }

        return assessment

    def get_supported_languages(self) -> List[str]:
        """获取支持的编程语言列表"""
        return [
            CodeLanguage.PYTHON, CodeLanguage.JAVASCRIPT, CodeLanguage.TYPESCRIPT,
            CodeLanguage.JAVA, CodeLanguage.CPP, CodeLanguage.C, CodeLanguage.RUST,
            CodeLanguage.GO, CodeLanguage.SHELL, CodeLanguage.SQL, CodeLanguage.OTHER
        ]

    def get_supported_code_types(self) -> List[str]:
        """获取支持的代码类型列表"""
        return [
            CodeType.ALGORITHM, CodeType.FUNCTION, CodeType.CLASS, CodeType.MODULE,
            CodeType.SCRIPT, CodeType.API, CodeType.DATABASE, CodeType.CONFIG,
            CodeType.TEST, CodeType.UTILITY
        ]

    def get_generation_history(self) -> List[Dict[str, Any]]:
        """获取代码生成历史"""
        return [r.to_dict() for r in self.generation_history]

    def clear_history(self):
        """清空生成历史"""
        self.generation_history.clear()
