# -*- coding: utf-8 -*-
"""
第三层具像化层 - 智能体

- 数字工程师：用数字、公式、量纲描述实施内容
- 具像化工程师：用文字、实物/过程描述、模拟场景描述实施内容
- 抽象化工程师：提炼抽象模型与接口
- 领域具像化智能体：按领域自动创建，具备数字化+具像化能力，遵守第一性原理等约束
- 工具智能体集成：写代码工具、3D打印工具，为具象化层提供软硬件实现能力
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, AsyncGenerator, Callable
import asyncio
import uuid
import json
import re
import logging

from ...agents.base_hierarchical_agent import (
    BaseHierarchicalAgent,
    HierarchicalAgentConfig,
    AgentCapability,
)
from ...types import LayerType, AgentAction
from .constraints import get_constraint_prompt_for_domain, CONCRETIZATION_CONSTRAINTS
from .concretization_role_prompt_template import build_concretization_role_prompt

# 导入工具智能体
try:
    from ...tools.code_writer_tool import CodeWriterTool, CodeLanguage, CodeType
except ImportError:
    CodeWriterTool = None
    CodeLanguage = None
    CodeType = None

try:
    from ...tools.three_d_print_tool import ThreeDPrintTool, PrintMaterial, DesignType, PrintTechnology
except ImportError:
    ThreeDPrintTool = None
    PrintMaterial = None
    DesignType = None
    PrintTechnology = None

try:
    from Config.llm_config import get_chat_long
except Exception:
    get_chat_long = None

logger = logging.getLogger(__name__)


@dataclass
class ConcretizationOutput:
    """单次具像化输出"""
    domain: str
    step_name: str
    step_description: str
    digital_description: str = ""   # 数字化：数字、公式、量纲
    textual_description: str = ""   # 文字描述
    simulation_description: str = ""  # 模拟/场景描述
    constraints_check: List[str] = field(default_factory=list)  # 已考虑的约束项
    raw_response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "step_name": self.step_name,
            "step_description": self.step_description,
            "digital_description": self.digital_description,
            "textual_description": self.textual_description,
            "simulation_description": self.simulation_description,
            "constraints_check": self.constraints_check,
            "raw_response": self.raw_response[:2000] if self.raw_response else "",
        }


class DigitalEngineerAgent(BaseHierarchicalAgent):
    """数字工程师：用数字、公式、量纲描述实施内容"""

    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"digital_eng_{uuid.uuid4().hex[:6]}",
            name="数字工程师",
            layer=LayerType.IMPLEMENTATION,
            role="digital_engineer",
            capabilities={
                AgentCapability.REASONING,
                AgentCapability.PLANNING,
                AgentCapability.IMPLEMENTATION,
                AgentCapability.COMMUNICATION,
            },
        )
        super().__init__(config, llm_adapter)

    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """数字工程师动作（第三层编排中由领域具像化智能体承担具体执行）"""
        yield f"[{self.name}] 就绪\n"

    def get_prompt(self, context: Dict[str, Any]) -> str:
        return context.get("prompt", "")

    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        return AgentAction.IMPLEMENT


class ConcretizationEngineerAgent(BaseHierarchicalAgent):
    """具像化工程师：用文字、实物/过程、模拟场景描述实施内容"""

    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"concretization_eng_{uuid.uuid4().hex[:6]}",
            name="具像化工程师",
            layer=LayerType.IMPLEMENTATION,
            role="concretization_engineer",
            capabilities={
                AgentCapability.REASONING,
                AgentCapability.PLANNING,
                AgentCapability.IMPLEMENTATION,
                AgentCapability.COMMUNICATION,
            },
        )
        super().__init__(config, llm_adapter)

    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """具像化工程师动作（第三层编排中由领域具像化智能体承担具体执行）"""
        yield f"[{self.name}] 就绪\n"

    def get_prompt(self, context: Dict[str, Any]) -> str:
        return context.get("prompt", "")

    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        return AgentAction.IMPLEMENT


class AbstractionEngineerAgent(BaseHierarchicalAgent):
    """抽象化工程师：提炼抽象模型与接口"""

    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"abstraction_eng_{uuid.uuid4().hex[:6]}",
            name="抽象化工程师",
            layer=LayerType.IMPLEMENTATION,
            role="abstraction_engineer",
            capabilities={
                AgentCapability.REASONING,
                AgentCapability.PLANNING,
                AgentCapability.STRATEGY_FORMULATION,
                AgentCapability.COMMUNICATION,
            },
        )
        super().__init__(config, llm_adapter)

    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """抽象化工程师动作（第三层编排中由领域具像化智能体承担具体执行）"""
        yield f"[{self.name}] 就绪\n"

    def get_prompt(self, context: Dict[str, Any]) -> str:
        return context.get("prompt", "")

    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        return AgentAction.ANALYZE


class DomainConcretizationAgent(BaseHierarchicalAgent):
    """
    领域具像化智能体
    
    针对某一实施步骤/领域，具备数字化+具像化能力：
    用数字、文字、模拟描述实施内容，并严格遵守第一性原理、物理守恒、
    材料属性约束、制造边界、环境适应、安全与冗余标准。
    
    具像化定义：通过文字和数字对任意对象进行详细描述的过程；
    若描述对象是事物，则该描述应足以将该事物复现出来。
    可使用网络工具查询细节步骤、描述不清时的理论或基础定义以补全描述。
    """

    def __init__(
        self,
        domain: str,
        step_name: str,
        step_description: str,
        llm_adapter=None,
        agent_id: str = None,
        web_search_fn: Optional[Callable[[str], str]] = None,
    ):
        self.domain = domain
        self.step_name = step_name
        self.step_description = step_description
        self.web_search_fn = web_search_fn
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"domain_conc_{domain}_{uuid.uuid4().hex[:6]}",
            name=f"领域具像化_{domain}",
            layer=LayerType.IMPLEMENTATION,
            role="domain_concretization",
            capabilities={
                AgentCapability.REASONING,
                AgentCapability.PLANNING,
                AgentCapability.IMPLEMENTATION,
                AgentCapability.COMMUNICATION,
            },
        )
        super().__init__(config, llm_adapter)
        self.last_output: Optional[ConcretizationOutput] = None

    def _fetch_network_refs(self) -> str:
        """
        使用网络工具查询细节步骤、定义或原理，供具像化描述参考。
        web_search_fn 为同步函数 (query: str) -> str，在异步上下文中通过 to_thread 调用。
        """
        if not self.web_search_fn:
            return ""
        parts = []
        desc_head = (self.step_description or "")[:80].strip()
        query1 = f"{self.step_name} {desc_head} 实施 细节步骤 操作".strip()
        query2 = f"{self.step_name} 定义 原理 基础 术语".strip()
        try:
            ref1 = self.web_search_fn(query1)
            if ref1 and ref1.strip():
                parts.append(f"【细节步骤/操作】\n{ref1.strip()}")
        except Exception as e:
            logger.debug(f"具像化网络查询(细节步骤)失败: {e}")
        try:
            ref2 = self.web_search_fn(query2)
            if ref2 and ref2.strip():
                parts.append(f"【定义/原理/基础】\n{ref2.strip()}")
        except Exception as e:
            logger.debug(f"具像化网络查询(定义原理)失败: {e}")
        return "\n\n".join(parts) if parts else ""

    async def run_concretization(self) -> AsyncGenerator[str, None]:
        """执行数字化+具像化，产出数字/文字/模拟描述，并遵守约束"""
        network_refs = ""
        if self.web_search_fn:
            try:
                network_refs = await asyncio.to_thread(self._fetch_network_refs)
            except Exception as e:
                logger.warning(f"具像化层网络检索失败: {e}")
        prompt = self._build_prompt(network_refs=network_refs.strip() or None)
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        full = "".join(response_parts)
        self.last_output = self._parse_response(full)
        # 解析失败且为回退结果时，用长文本模型从完整原文提取结构化字段（不截断）
        if self._is_fallback_parse(self.last_output) and self.last_output.textual_description:
            long_out = await self._extract_with_long_model(full)
            if long_out:
                self.last_output = long_out
                logger.info("具像化已通过长文本模型从原文提取结构化结果")

    def _is_fallback_parse(self, out: ConcretizationOutput) -> bool:
        """是否为解析失败后的回退结果（仅有原始文本，缺少结构化字段）"""
        return (
            not out.constraints_check
            and (not out.digital_description or not out.simulation_description)
        )

    async def _extract_with_long_model(self, full_raw: str) -> Optional[ConcretizationOutput]:
        """使用长文本模型从完整原始输出中提取 digital/textual/simulation/constraints_check，不截断。"""
        try:
            from Config.llm_config import get_chat_long
            llm_long = get_chat_long(temperature=0.2, streaming=False)
        except Exception as e:
            logger.debug(f"未启用长文本模型，跳过从原文提取: {e}")
            return None
        prompt = f"""以下是一段「领域具像化」的原始输出（可能因截断或格式问题未解析成 JSON）。请从中提取出四个字段，严格只输出一个 JSON 对象，放在 ```json 代码块中。

字段要求：
- digital_description: 数字化描述（数字、公式、量纲等）
- textual_description: 文字描述
- simulation_description: 模拟/场景描述
- constraints_check: 数组，已考虑的约束项列表

## 原始输出（完整，未截断）

{full_raw}

请直接输出上述四字段的 JSON（仅 ```json ... ``` 块）："""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if hasattr(llm_long, "ainvoke"):
                response = await llm_long.ainvoke(prompt)
            else:
                response = await loop.run_in_executor(None, lambda: llm_long.invoke(prompt))
            content = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.warning(f"长文本模型调用失败: {e}")
            return None
        m = re.search(r"```json\s*([\s\S]*?)\s*```", content)
        if not m:
            return None
        try:
            data = self._parse_json_with_fallback(m.group(1))
        except Exception:
            return None
        return ConcretizationOutput(
            domain=self.domain,
            step_name=self.step_name,
            step_description=self.step_description,
            digital_description=data.get("digital_description", ""),
            textual_description=data.get("textual_description", ""),
            simulation_description=data.get("simulation_description", ""),
            constraints_check=data.get("constraints_check", []) if isinstance(data.get("constraints_check"), list) else [],
            raw_response=full_raw,
        )

    def _build_prompt(self, network_refs: Optional[str] = None) -> str:
        constraints_block = get_constraint_prompt_for_domain(self.domain)
        ref_block = ""
        if network_refs:
            ref_block = f"""
## 网络检索参考（可补充细节步骤、定义与原理）

当步骤或理论描述不够清晰时，可参考以下检索结果补充细节步骤、基础定义或原理，使具像化描述足以复现事物。

{network_refs}
"""
        # 角色 prompt 参考 concretization_role_prompt_template，按领域略改
        role_prompt = build_concretization_role_prompt(
            self.domain,
            role_title_override=f"具象化评估智能体（{self.domain}领域）" if self.domain and self.domain != "通用" else None,
        )
        return f"""{role_prompt}

---
## 当前实施步骤（本领域: {self.domain}）

- **步骤名称**: {self.step_name}
- **步骤描述**: {self.step_description}
{ref_block}
## 任务要求

请从以下三方面描述该步骤的实施内容，并**严格遵守**下方约束与准则：

1. **数字化描述**：用数字、公式、量纲、参数范围、输入输出关系描述（便于仿真或计算验证）。
2. **文字描述**：用自然语言描述具体做什么、用什么材料/工具、在什么条件下、产出什么。
3. **模拟描述**：用场景、流程、状态变化或典型工况描述（便于模拟或测试）。

{constraints_block}

## 输出格式（JSON，放在 ```json 代码块中）

```json
{{
  "digital_description": "数字化描述内容",
  "textual_description": "文字描述内容",
  "simulation_description": "模拟/场景描述内容",
  "constraints_check": ["已考虑的约束1", "已考虑的约束2", ...]
}}
```

请直接输出你的分析结果（含 JSON 块）：
"""

    def _parse_json_with_fallback(self, json_str: str) -> dict:
        """
        解析 JSON，失败时尝试修复（去除控制字符、尾逗号、截断后补全括号、未闭合字符串补引号）后重试。
        """
        # 去除控制字符（保留 \n \r \t 以便定位，但换行可能导致字符串未闭合，后续修复）
        json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', ' ', json_str)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # 修复尾逗号 ,] ,}
            repaired = re.sub(r',\s*([}\]])', r'\1', json_str)
            if repaired != json_str:
                try:
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    pass
            pos = getattr(e, 'pos', None) or len(json_str)
            msg = getattr(e, 'msg', '') or str(e)
            # 未闭合字符串：在错误位置补闭合引号并补全括号
            if pos and pos > 0 and ("Unterminated string" in msg or "Unterminated" in str(e)):
                prefix = json_str[:pos]
                # 若末尾已是引号则可能是缺逗号或括号，否则补一个闭合引号
                prefix_stripped = prefix.rstrip()
                if prefix_stripped and prefix_stripped[-1] != '"':
                    repaired = prefix + '"'
                else:
                    repaired = prefix
                open_braces = repaired.count('{') - repaired.count('}')
                open_brackets = repaired.count('[') - repaired.count(']')
                repaired += ']' * max(0, open_brackets) + '}' * max(0, open_braces)
                try:
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    pass
            # 截断修复：在错误位置之前找到最后一个完整的 } 或 ]
            if pos and pos > 10:
                prefix = json_str[:pos]
                last_brace = prefix.rfind('}')
                last_bracket = prefix.rfind(']')
                cut = max(last_brace, last_bracket)
                if cut > 0:
                    open_braces = prefix[: cut + 1].count('{') - prefix[: cut + 1].count('}')
                    open_brackets = prefix[: cut + 1].count('[') - prefix[: cut + 1].count(']')
                    repaired = json_str[: cut + 1] + ']' * max(0, open_brackets) + '}' * max(0, open_braces)
                    try:
                        return json.loads(repaired)
                    except json.JSONDecodeError:
                        pass
                # 若没有完整括号，尝试在 pos 处补引号再补括号（通用截断）
                repaired = json_str[:pos].rstrip()
                if repaired and repaired[-1] == '"':
                    pass
                elif repaired and repaired[-1] not in '}]':
                    repaired += '"'
                open_braces = repaired.count('{') - repaired.count('}')
                open_brackets = repaired.count('[') - repaired.count(']')
                repaired += ']' * max(0, open_brackets) + '}' * max(0, open_braces)
                try:
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    pass
            raise

    def _parse_response(self, response: str) -> ConcretizationOutput:
        out = ConcretizationOutput(
            domain=self.domain,
            step_name=self.step_name,
            step_description=self.step_description,
            raw_response=response,
        )
        try:
            m = re.search(r"```json\s*([\s\S]*?)\s*```", response)
            if m:
                data = self._parse_json_with_fallback(m.group(1))
                out.digital_description = data.get("digital_description", "")
                out.textual_description = data.get("textual_description", "")
                out.simulation_description = data.get("simulation_description", "")
                raw_check = data.get("constraints_check", [])
                out.constraints_check = raw_check if isinstance(raw_check, list) else []
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"解析领域具像化输出失败: {e}")
            # 解析失败时，不截断：将完整原始响应放入 textual_description，后续可由长文本模型再提取
            if response.strip():
                out.textual_description = response.strip()
        return out

    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """执行领域具像化（数字化+具像化）"""
        async for chunk in self.run_concretization():
            yield chunk

    def get_prompt(self, context: Dict[str, Any]) -> str:
        return self._build_prompt()

    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        return AgentAction.IMPLEMENT


# ============================================================================
# 工具集成具象化智能体
# ============================================================================

@dataclass
class ToolExecutionResult:
    """工具执行结果"""
    tool_name: str
    success: bool
    output: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    execution_time: float = 0.0
    output_file_path: str = ""  # 输出文件路径

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "execution_time": self.execution_time,
            "output_file_path": self.output_file_path,
        }


class ToolIntegratedConcretizationAgent(BaseHierarchicalAgent):
    """
    工具集成具象化智能体
    
    为第三层具象化层提供软硬件实现工具：
    - 写代码工具智能体（CodeWriterTool）：实现软件功能、算法功能
    - 3D打印工具智能体（ThreeDPrintTool）：实现硬件形态设计
    
    根据具象化描述自动判断需要调用哪个工具，并生成对应的实现代码或3D设计方案。
    """

    def __init__(
        self,
        domain: str = "通用",
        llm_adapter=None,
        agent_id: str = None,
    ):
        self.domain = domain
        
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"tool_integrated_conc_{uuid.uuid4().hex[:6]}",
            name=f"工具集成具象化智能体_{domain}",
            layer=LayerType.IMPLEMENTATION,
            role="tool_integrated_concretization",
            capabilities={
                AgentCapability.REASONING,
                AgentCapability.PLANNING,
                AgentCapability.IMPLEMENTATION,
                AgentCapability.COMMUNICATION,
            },
        )
        super().__init__(config, llm_adapter)
        
        # 初始化工具
        self.code_writer_tool = None
        self.three_d_print_tool = None
        
        if CodeWriterTool is not None:
            self.code_writer_tool = CodeWriterTool(
                tool_id=f"code_writer_{domain}_{uuid.uuid4().hex[:4]}",
                llm_adapter=llm_adapter,
            )
            logger.info(f"写代码工具已初始化: {domain}")
        
        if ThreeDPrintTool is not None:
            self.three_d_print_tool = ThreeDPrintTool(
                tool_id=f"3d_print_{domain}_{uuid.uuid4().hex[:4]}",
                llm_adapter=llm_adapter,
            )
            logger.info(f"3D打印工具已初始化: {domain}")
        
        # 工具执行历史
        self.tool_execution_history: List[ToolExecutionResult] = []

    def has_tools(self) -> bool:
        """检查是否有可用工具"""
        return self.code_writer_tool is not None or self.three_d_print_tool is not None

    def get_available_tools(self) -> List[str]:
        """获取可用工具列表"""
        tools = []
        if self.code_writer_tool is not None:
            tools.append("code_writer")
        if self.three_d_print_tool is not None:
            tools.append("three_d_print")
        return tools

    async def execute_code_generation(
        self,
        task_description: str,
        language: str = "python",
        code_type: str = "function",
        context: str = "",
        constraints: List[str] = None,
    ) -> ToolExecutionResult:
        """
        执行代码生成工具
        
        Args:
            task_description: 任务描述
            language: 编程语言
            code_type: 代码类型
            context: 上下文信息（如具象化描述）
            constraints: 约束条件
        
        Returns:
            ToolExecutionResult
        """
        import time
        start_time = time.time()
        
        if self.code_writer_tool is None:
            return ToolExecutionResult(
                tool_name="code_writer",
                success=False,
                error="写代码工具未初始化",
            )
        
        try:
            result = await self.code_writer_tool.execute_async({
                "task_description": task_description,
                "language": language,
                "code_type": code_type,
                "context": context,
                "constraints": constraints or [],
            })
            
            execution_time = time.time() - start_time
            exec_result = ToolExecutionResult(
                tool_name="code_writer",
                success=result.success,
                output=result.data if result.success else {},
                error=result.error or "",
                execution_time=execution_time,
            )
            self.tool_execution_history.append(exec_result)
            return exec_result
            
        except Exception as e:
            logger.exception(f"代码生成工具执行失败: {e}")
            execution_time = time.time() - start_time
            exec_result = ToolExecutionResult(
                tool_name="code_writer",
                success=False,
                error=str(e),
                execution_time=execution_time,
            )
            self.tool_execution_history.append(exec_result)
            return exec_result

    async def execute_3d_design(
        self,
        task_description: str,
        design_type: str = "structural",
        material: str = "PLA",
        technology: str = "FDM",
        context: str = "",
        constraints: List[str] = None,
        generate_openscad: bool = True,
    ) -> ToolExecutionResult:
        """
        执行3D打印设计工具
        
        Args:
            task_description: 设计任务描述
            design_type: 设计类型
            material: 打印材料
            technology: 打印技术
            context: 上下文信息（如具象化描述）
            constraints: 设计约束
            generate_openscad: 是否生成OpenSCAD代码
        
        Returns:
            ToolExecutionResult
        """
        import time
        start_time = time.time()
        
        if self.three_d_print_tool is None:
            return ToolExecutionResult(
                tool_name="three_d_print",
                success=False,
                error="3D打印工具未初始化",
            )
        
        try:
            result = await self.three_d_print_tool.execute_async({
                "task_description": task_description,
                "design_type": design_type,
                "material": material,
                "technology": technology,
                "context": context,
                "constraints": constraints or [],
                "generate_openscad": generate_openscad,
            })
            
            execution_time = time.time() - start_time
            exec_result = ToolExecutionResult(
                tool_name="three_d_print",
                success=result.success,
                output=result.data if result.success else {},
                error=result.error or "",
                execution_time=execution_time,
            )
            self.tool_execution_history.append(exec_result)
            return exec_result
            
        except Exception as e:
            logger.exception(f"3D打印工具执行失败: {e}")
            execution_time = time.time() - start_time
            exec_result = ToolExecutionResult(
                tool_name="three_d_print",
                success=False,
                error=str(e),
                execution_time=execution_time,
            )
            self.tool_execution_history.append(exec_result)
            return exec_result

    async def analyze_and_execute_tools(
        self,
        concretization_content: str,
        category_name: str = "",
        output_base_dir: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        分析具象化内容，自动判断并执行相应工具，将结果保存到指定目录
        
        Args:
            concretization_content: 具象化内容
            category_name: 团体名称
            output_base_dir: 输出基础目录（discussion/discussion_id）
        
        Yields:
            执行过程信息
        """
        import os
        from datetime import datetime
        
        if not self.has_tools():
            yield "[工具集成] 无可用工具\n"
            return
        
        yield f"\n[工具集成] 分析具象化内容，判断需要调用的工具...\n"
        
        # 创建输出目录
        code_dir = ""
        pro_dir = ""
        if output_base_dir:
            code_dir = os.path.join(output_base_dir, "code")
            pro_dir = os.path.join(output_base_dir, "pro")
            os.makedirs(code_dir, exist_ok=True)
            os.makedirs(pro_dir, exist_ok=True)
        
        # 简单关键词匹配判断需要哪个工具
        content_lower = concretization_content.lower()
        
        # 检查是否需要代码生成
        code_keywords = [
            "代码", "算法", "软件", "程序", "函数", "接口", "api",
            "python", "java", "javascript", "脚本", "模块", "类",
            "code", "algorithm", "software", "function", "script",
        ]
        need_code = any(kw in content_lower for kw in code_keywords)
        
        # 检查是否需要3D设计
        hardware_keywords = [
            "3d", "打印", "硬件", "结构", "外壳", "支架",
            "齿轮", "轴承", "机械", "外形", "尺寸", "材料",
            "hardware", "enclosure", "bracket", "mechanical", "structural",
            "fdm", "sla", "pla", "abs", "petg",
        ]
        need_3d = any(kw in content_lower for kw in hardware_keywords)
        
        # 执行代码生成
        if need_code and self.code_writer_tool is not None:
            yield f"[工具集成] 检测到软件/算法需求，调用写代码工具...\n"
            
            # 提取任务描述（取前500字符作为任务描述）
            task_desc = concretization_content[:500].strip()
            if category_name:
                task_desc = f"团体[{category_name}]的实施任务: {task_desc}"
            
            result = await self.execute_code_generation(
                task_description=task_desc,
                language="python",
                code_type="function",
                context=concretization_content[:2000],
            )
            
            if result.success:
                yield f"  ✓ 代码生成成功，耗时: {result.execution_time:.2f}s\n"
                code_output = result.output
                code_content = code_output.get("code", "")
                
                # 保存代码到code目录
                if code_content and code_dir:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_category = "".join(c if c.isalnum() or c in "._-" else "_" for c in category_name)[:20] if category_name else "general"
                    filename = code_output.get("filename", f"code_{safe_category}_{ts}.py")
                    # 确保文件名安全
                    filename = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
                    if not filename.endswith(('.py', '.js', '.java', '.cpp', '.c', '.rs', '.go', '.sh', '.sql')):
                        filename = f"{filename}.py"
                    
                    code_file_path = os.path.join(code_dir, filename)
                    try:
                        with open(code_file_path, "w", encoding="utf-8") as f:
                            f.write(f"# 自动生成代码 - {category_name or '通用'}\n")
                            f.write(f"# 生成时间: {ts}\n")
                            f.write(f"# 描述: {code_output.get('description', '')}\n\n")
                            f.write(code_content)
                            if code_output.get("usage_example"):
                                f.write(f"\n\n# 使用示例:\n# {code_output.get('usage_example', '')}\n")
                        result.output_file_path = code_file_path
                        yield f"  ✓ 代码已保存: {os.path.basename(code_file_path)}\n"
                    except Exception as e:
                        yield f"  × 保存代码失败: {e}\n"
                
                if code_content:
                    yield f"  代码片段预览:\n```\n{code_content[:300]}...\n```\n"
            else:
                yield f"  × 代码生成失败: {result.error}\n"
        
        # 执行3D设计
        if need_3d and self.three_d_print_tool is not None:
            yield f"[工具集成] 检测到硬件/结构需求，调用3D打印工具...\n"
            
            # 提取任务描述
            task_desc = concretization_content[:500].strip()
            if category_name:
                task_desc = f"团体[{category_name}]的硬件设计任务: {task_desc}"
            
            result = await self.execute_3d_design(
                task_description=task_desc,
                design_type="structural",
                material="PLA",
                technology="FDM",
                context=concretization_content[:2000],
            )
            
            if result.success:
                yield f"  ✓ 3D设计生成成功，耗时: {result.execution_time:.2f}s\n"
                design_output = result.output
                
                # 保存3D打印参数到pro目录
                if pro_dir:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_category = "".join(c if c.isalnum() or c in "._-" else "_" for c in category_name)[:20] if category_name else "general"
                    
                    # 保存设计参数文件（JSON格式）
                    param_filename = f"3d_params_{safe_category}_{ts}.json"
                    param_file_path = os.path.join(pro_dir, param_filename)
                    try:
                        import json
                        param_data = {
                            "category": category_name,
                            "generated_at": ts,
                            "design_type": design_output.get("design_type", "structural"),
                            "material": design_output.get("material", "PLA"),
                            "technology": design_output.get("technology", "FDM"),
                            "dimensions": design_output.get("dimensions", {}),
                            "wall_thickness": design_output.get("wall_thickness", 0),
                            "infill_percentage": design_output.get("infill_percentage", 0),
                            "print_parameters": design_output.get("print_parameters", {}),
                            "design_description": design_output.get("design_description", ""),
                            "structural_features": design_output.get("structural_features", []),
                            "post_processing": design_output.get("post_processing", []),
                            "estimated_print_time": design_output.get("estimated_print_time", ""),
                            "estimated_material_cost": design_output.get("estimated_material_cost", ""),
                            "design_notes": design_output.get("design_notes", []),
                        }
                        with open(param_file_path, "w", encoding="utf-8") as f:
                            json.dump(param_data, f, ensure_ascii=False, indent=2)
                        yield f"  ✓ 3D打印参数已保存: {param_filename}\n"
                    except Exception as e:
                        yield f"  × 保存3D参数失败: {e}\n"
                    
                    # 保存OpenSCAD代码（如果有）
                    openscad_code = design_output.get("openscad_code", "")
                    if openscad_code:
                        scad_filename = f"model_{safe_category}_{ts}.scad"
                        scad_file_path = os.path.join(pro_dir, scad_filename)
                        try:
                            with open(scad_file_path, "w", encoding="utf-8") as f:
                                f.write(f"// 自动生成OpenSCAD模型 - {category_name or '通用'}\n")
                                f.write(f"// 生成时间: {ts}\n")
                                f.write(f"// 设计说明: {design_output.get('design_description', '')[:100]}\n\n")
                                f.write(openscad_code)
                            result.output_file_path = scad_file_path
                            yield f"  ✓ OpenSCAD模型已保存: {scad_filename}\n"
                        except Exception as e:
                            yield f"  × 保存OpenSCAD文件失败: {e}\n"
                    
                    # 保存CAD建模指导（Markdown格式）
                    cad_instructions = design_output.get("cad_instructions", "")
                    if cad_instructions:
                        cad_filename = f"cad_guide_{safe_category}_{ts}.md"
                        cad_file_path = os.path.join(pro_dir, cad_filename)
                        try:
                            with open(cad_file_path, "w", encoding="utf-8") as f:
                                f.write(f"# CAD建模指导 - {category_name or '通用'}\n\n")
                                f.write(f"**生成时间**: {ts}\n\n")
                                f.write(f"## 设计说明\n\n{design_output.get('design_description', '')}\n\n")
                                f.write(f"## 建模步骤\n\n{cad_instructions}\n")
                            yield f"  ✓ CAD建模指导已保存: {cad_filename}\n"
                        except Exception as e:
                            yield f"  × 保存CAD指导失败: {e}\n"
                
                if design_output.get("design_description"):
                    yield f"  设计说明: {design_output.get('design_description', '')[:200]}\n"
            else:
                yield f"  × 3D设计生成失败: {result.error}\n"
        
        if not need_code and not need_3d:
            yield "[工具集成] 未检测到需要工具辅助的内容\n"

    def get_tool_execution_history(self) -> List[Dict[str, Any]]:
        """获取工具执行历史"""
        return [r.to_dict() for r in self.tool_execution_history]

    def clear_tool_history(self):
        """清空工具执行历史"""
        self.tool_execution_history.clear()
        if self.code_writer_tool is not None:
            self.code_writer_tool.clear_history()
        if self.three_d_print_tool is not None:
            self.three_d_print_tool.clear_history()

    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """执行工具集成具象化"""
        content = context.get("concretization_content", "")
        category = context.get("category_name", "")
        output_dir = context.get("output_base_dir", "")
        async for chunk in self.analyze_and_execute_tools(content, category, output_dir):
            yield chunk

    def get_prompt(self, context: Dict[str, Any]) -> str:
        return context.get("prompt", "")

    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        return AgentAction.IMPLEMENT
