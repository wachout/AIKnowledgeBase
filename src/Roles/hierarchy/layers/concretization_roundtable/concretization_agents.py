# -*- coding: utf-8 -*-
"""
第三层具像化层 - 智能体

- 数字工程师：用数字、公式、量纲描述实施内容
- 具像化工程师：用文字、实物/过程描述、模拟场景描述实施内容
- 抽象化工程师：提炼抽象模型与接口
- 领域具像化智能体：按领域自动创建，具备数字化+具像化能力，遵守第一性原理等约束
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, AsyncGenerator
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
    """

    def __init__(
        self,
        domain: str,
        step_name: str,
        step_description: str,
        llm_adapter=None,
        agent_id: str = None,
    ):
        self.domain = domain
        self.step_name = step_name
        self.step_description = step_description
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

    async def run_concretization(self) -> AsyncGenerator[str, None]:
        """执行数字化+具像化，产出数字/文字/模拟描述，并遵守约束"""
        prompt = self._build_prompt()
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        full = "".join(response_parts)
        self.last_output = self._parse_response(full)

    def _build_prompt(self) -> str:
        constraints_block = get_constraint_prompt_for_domain(self.domain)
        return f"""你是「领域具像化」智能体，负责将实施步骤转化为可执行、可验证的数字化与具像化描述。

## 当前实施步骤（本领域: {self.domain}）

- **步骤名称**: {self.step_name}
- **步骤描述**: {self.step_description}

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
        解析 JSON，失败时尝试修复（去除控制字符、尾逗号、截断后补全括号）后重试。
        """
        # 去除控制字符
        json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
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
            # 截断修复：在错误位置之前找到最后一个 } 或 ]
            pos = getattr(e, 'pos', len(json_str))
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
            # 解析失败时，尝试从原始文本提取内容作为回退
            if response.strip():
                out.textual_description = response.strip()[:3000]
        return out

    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """执行领域具像化（数字化+具像化）"""
        async for chunk in self.run_concretization():
            yield chunk

    def get_prompt(self, context: Dict[str, Any]) -> str:
        return self._build_prompt()

    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        return AgentAction.IMPLEMENT
