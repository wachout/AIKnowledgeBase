"""
多层强化学习智能体系统 - 检验层智能体
负责质量验证和反馈的专用智能体
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Generator, Set, AsyncGenerator
import asyncio
import uuid

from .base_hierarchical_agent import (
    BaseHierarchicalAgent, HierarchicalAgentConfig, AgentCapability
)
from ..types import LayerType, AgentAction, ValidationRole


class QualityInspectorAgent(BaseHierarchicalAgent):
    """质量检验员智能体 - 检查产出物质量"""
    
    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"quality_{uuid.uuid4().hex[:6]}",
            name="质量检验员",
            layer=LayerType.VALIDATION,
            role="quality_inspector",
            capabilities={
                AgentCapability.QUALITY_INSPECTION,
                AgentCapability.REASONING,
                AgentCapability.COMMUNICATION
            }
        )
        super().__init__(config, llm_adapter)
    
    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Note: 结果存储在 self.last_result 属性中"""
        yield f"[{self.name}] 正在检查质量...\n"
        action = self.select_action(context)
        prompt = self.get_prompt(context)
        
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        self.last_result = {"action": action.value, "response": "".join(response_parts)}
    
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        return AgentAction.INSPECT
    
    def get_prompt(self, context: Dict[str, Any]) -> str:
        artifacts = context.get("artifacts", [])
        criteria = context.get("criteria", [])
        return f"""你是一位质量检验专家。请检查以下产出物的质量。

## 产出物
{str(artifacts)[:500] if artifacts else '无'}

## 质量标准
{str(criteria)[:200] if criteria else '完整性、一致性、可用性'}

## 检查要点
1. 检查完整性
2. 验证一致性
3. 评估可用性
4. 记录问题

请提供质量检查报告。
"""


class LogicValidatorAgent(BaseHierarchicalAgent):
    """逻辑验证员智能体 - 验证逻辑正确性"""
    
    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"logic_{uuid.uuid4().hex[:6]}",
            name="逻辑验证员",
            layer=LayerType.VALIDATION,
            role="logic_validator",
            capabilities={
                AgentCapability.LOGIC_VALIDATION,
                AgentCapability.REASONING,
                AgentCapability.COMMUNICATION
            }
        )
        super().__init__(config, llm_adapter)
    
    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Note: 结果存储在 self.last_result 属性中"""
        yield f"[{self.name}] 正在验证逻辑...\n"
        action = self.select_action(context)
        prompt = self.get_prompt(context)
        
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        self.last_result = {"action": action.value, "response": "".join(response_parts)}
    
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        return AgentAction.VALIDATE
    
    def get_prompt(self, context: Dict[str, Any]) -> str:
        implementation = context.get("implementation", "")
        requirements = context.get("requirements", [])
        return f"""你是一位逻辑验证专家。请验证实现的逻辑正确性。

## 实现内容
{str(implementation)[:500] if implementation else '无'}

## 需求
{str(requirements)[:200] if requirements else '无'}

## 验证要点
1. 检查逻辑完整性
2. 验证边界条件
3. 检测潜在错误
4. 确认需求满足

请提供逻辑验证报告。
"""


class PerformanceAnalystAgent(BaseHierarchicalAgent):
    """性能分析员智能体 - 分析性能指标"""
    
    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"performance_{uuid.uuid4().hex[:6]}",
            name="性能分析员",
            layer=LayerType.VALIDATION,
            role="performance_analyst",
            capabilities={
                AgentCapability.PERFORMANCE_ANALYSIS,
                AgentCapability.REASONING,
                AgentCapability.COMMUNICATION
            }
        )
        super().__init__(config, llm_adapter)
    
    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Note: 结果存储在 self.last_result 属性中"""
        yield f"[{self.name}] 正在分析性能...\n"
        action = self.select_action(context)
        prompt = self.get_prompt(context)
        
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        self.last_result = {"action": action.value, "response": "".join(response_parts)}
    
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        return AgentAction.VALIDATE
    
    def get_prompt(self, context: Dict[str, Any]) -> str:
        metrics = context.get("metrics", {})
        implementation = context.get("implementation", "")
        return f"""你是一位性能分析专家。请分析以下实现的性能。

## 性能指标
{str(metrics)[:300] if metrics else '无'}

## 实现摘要
{str(implementation)[:300] if implementation else '无'}

## 分析要点
1. 评估时间复杂度
2. 分析空间复杂度
3. 识别性能瓶颈
4. 提出优化建议

请提供性能分析报告。
"""


class SecurityAuditorAgent(BaseHierarchicalAgent):
    """安全审计员智能体 - 安全性检查"""
    
    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"security_{uuid.uuid4().hex[:6]}",
            name="安全审计员",
            layer=LayerType.VALIDATION,
            role="security_auditor",
            capabilities={
                AgentCapability.SECURITY_AUDIT,
                AgentCapability.REASONING,
                AgentCapability.COMMUNICATION
            }
        )
        super().__init__(config, llm_adapter)
    
    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Note: 结果存储在 self.last_result 属性中"""
        yield f"[{self.name}] 正在审计安全性...\n"
        action = self.select_action(context)
        prompt = self.get_prompt(context)
        
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        self.last_result = {"action": action.value, "response": "".join(response_parts)}
    
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        return AgentAction.VALIDATE
    
    def get_prompt(self, context: Dict[str, Any]) -> str:
        implementation = context.get("implementation", "")
        return f"""你是一位安全审计专家。请检查以下实现的安全性。

## 实现内容
{str(implementation)[:500] if implementation else '无'}

## 审计要点
1. 检查输入验证
2. 识别安全漏洞
3. 验证权限控制
4. 检测敏感信息泄露

请提供安全审计报告。
"""


class ComplianceCheckerAgent(BaseHierarchicalAgent):
    """合规检查员智能体 - 规范合规检查"""
    
    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"compliance_{uuid.uuid4().hex[:6]}",
            name="合规检查员",
            layer=LayerType.VALIDATION,
            role="compliance_checker",
            capabilities={
                AgentCapability.COMPLIANCE_CHECK,
                AgentCapability.REASONING,
                AgentCapability.COMMUNICATION
            }
        )
        super().__init__(config, llm_adapter)
    
    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Note: 结果存储在 self.last_result 属性中"""
        yield f"[{self.name}] 正在检查合规性...\n"
        action = self.select_action(context)
        prompt = self.get_prompt(context)
        
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        self.last_result = {"action": action.value, "response": "".join(response_parts)}
    
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        return AgentAction.VALIDATE
    
    def get_prompt(self, context: Dict[str, Any]) -> str:
        artifacts = context.get("artifacts", [])
        standards = context.get("standards", [])
        return f"""你是一位合规检查专家。请检查以下内容的合规性。

## 产出物
{str(artifacts)[:400] if artifacts else '无'}

## 标准规范
{str(standards)[:200] if standards else '行业最佳实践'}

## 检查要点
1. 检查编码规范
2. 验证文档完整
3. 确认流程合规
4. 检查最佳实践

请提供合规检查报告。
"""


def create_validation_agent(
    role: str,
    llm_adapter=None,
    agent_id: str = None
) -> BaseHierarchicalAgent:
    """创建检验层智能体工厂函数"""
    role_mapping = {
        "quality_inspector": QualityInspectorAgent,
        "logic_validator": LogicValidatorAgent,
        "performance_analyst": PerformanceAnalystAgent,
        "security_auditor": SecurityAuditorAgent,
        "compliance_checker": ComplianceCheckerAgent
    }
    agent_class = role_mapping.get(role.lower(), QualityInspectorAgent)
    return agent_class(llm_adapter=llm_adapter, agent_id=agent_id)
