"""
多层强化学习智能体系统 - 决策层智能体
负责高层战略决策的专用智能体
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Generator, Set, AsyncGenerator
import asyncio
import uuid

from .base_hierarchical_agent import (
    BaseHierarchicalAgent, HierarchicalAgentConfig, AgentCapability
)
from ..types import LayerType, AgentAction


# ==================== 策略师智能体 ====================

class StrategistAgent(BaseHierarchicalAgent):
    """
    策略师智能体
    负责提出和制定战略方案
    """
    
    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"strategist_{uuid.uuid4().hex[:6]}",
            name="策略师",
            layer=LayerType.DECISION,
            role="strategist",
            capabilities={
                AgentCapability.REASONING,
                AgentCapability.PLANNING,
                AgentCapability.STRATEGY_FORMULATION,
                AgentCapability.COMMUNICATION
            }
        )
        super().__init__(config, llm_adapter)
    
    async def act(
        self,
        context: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """执行策略制定动作
        
        Note:
            结果存储在 self.last_result 属性中
        """
        query = context.get("query", "")
        yield f"[{self.name}] 正在分析问题...\n"
        
        # 选择动作
        action = self.select_action(context)
        self.update_state({"last_action": action})
        
        yield f"[{self.name}] 执行动作: {action.value}\n"
        
        # 生成提示词并调用 LLM
        prompt = self.get_prompt(context)
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        full_response = "".join(response_parts)
        
        # 解析响应
        result = self.parse_llm_response(full_response)
        result["action"] = action.value
        
        # 记录经验
        self.record_experience(
            state=self.get_state_features(),
            action=action,
            reward=0.0,  # 稍后由验证层更新
            next_state={},
            done=False
        )
        
        self.last_result = result  # 存储结果
    
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        """选择策略制定相关动作"""
        # 根据上下文选择动作
        if "previous_strategy" in state:
            return AgentAction.EVALUATE_PROPOSAL
        return AgentAction.PROPOSE_STRATEGY
    
    def get_prompt(self, context: Dict[str, Any]) -> str:
        """生成策略师提示词"""
        query = context.get("query", "")
        history = context.get("discussion_history", [])
        
        history_text = ""
        if history:
            history_text = "\n".join([
                f"- {h.get('speaker', '未知')}: {h.get('content', '')[:100]}..."
                for h in history[-5:]
            ])
        
        return f"""你是一位资深的战略策划专家。请针对以下问题提出战略方案。

## 问题
{query}

## 历史讨论（如有）
{history_text if history_text else "无"}

## 要求
1. 分析问题的核心需求
2. 提出清晰的战略目标
3. 规划可行的实施路径
4. 考虑潜在风险和约束

请提供结构化的战略方案。
"""


# ==================== 分析师智能体 ====================

class AnalystAgent(BaseHierarchicalAgent):
    """
    分析师智能体
    负责深入分析和评估方案
    """
    
    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"analyst_{uuid.uuid4().hex[:6]}",
            name="分析师",
            layer=LayerType.DECISION,
            role="analyst",
            capabilities={
                AgentCapability.REASONING,
                AgentCapability.RISK_ASSESSMENT,
                AgentCapability.COMMUNICATION
            }
        )
        super().__init__(config, llm_adapter)
    
    async def act(
        self,
        context: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """执行分析动作
        
        Note:
            结果存储在 self.last_result 属性中
        """
        yield f"[{self.name}] 正在进行深度分析...\n"
        
        action = self.select_action(context)
        self.update_state({"last_action": action})
        
        prompt = self.get_prompt(context)
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        full_response = "".join(response_parts)
        result = self.parse_llm_response(full_response)
        result["action"] = action.value
        
        self.last_result = result  # 存储结果
    
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        """选择分析相关动作"""
        return AgentAction.EVALUATE_PROPOSAL
    
    def get_prompt(self, context: Dict[str, Any]) -> str:
        """生成分析师提示词"""
        query = context.get("query", "")
        proposals = context.get("proposals", [])
        
        proposals_text = ""
        if proposals:
            proposals_text = "\n".join([
                f"方案 {i+1}: {p.get('summary', str(p)[:200])}"
                for i, p in enumerate(proposals)
            ])
        
        return f"""你是一位专业的商业分析师。请对以下内容进行深入分析。

## 原始问题
{query}

## 提出的方案
{proposals_text if proposals_text else "暂无具体方案"}

## 分析要求
1. 评估方案的可行性
2. 识别潜在风险点
3. 分析资源需求
4. 预测可能的结果

请提供详细的分析报告。
"""


# ==================== 批评家智能体 ====================

class CriticAgent(BaseHierarchicalAgent):
    """
    批评家智能体
    负责质疑和挑战方案，确保决策质量
    """
    
    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"critic_{uuid.uuid4().hex[:6]}",
            name="批评家",
            layer=LayerType.DECISION,
            role="critic",
            capabilities={
                AgentCapability.REASONING,
                AgentCapability.RISK_ASSESSMENT,
                AgentCapability.COMMUNICATION
            }
        )
        super().__init__(config, llm_adapter)
    
    async def act(
        self,
        context: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """执行批评动作
        
        Note:
            结果存储在 self.last_result 属性中
        """
        yield f"[{self.name}] 正在审视方案...\n"
        
        action = self.select_action(context)
        self.update_state({"last_action": action})
        
        prompt = self.get_prompt(context)
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        full_response = "".join(response_parts)
        result = self.parse_llm_response(full_response)
        result["action"] = action.value
        
        self.last_result = result  # 存储结果
    
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        """选择批评相关动作"""
        return AgentAction.CHALLENGE
    
    def get_prompt(self, context: Dict[str, Any]) -> str:
        """生成批评家提示词"""
        query = context.get("query", "")
        proposals = context.get("proposals", [])
        analysis = context.get("analysis", "")
        
        return f"""你是一位严谨的批评家，负责发现方案中的问题和漏洞。

## 原始问题
{query}

## 当前方案摘要
{str(proposals)[:500] if proposals else "暂无"}

## 分析结果
{analysis[:500] if analysis else "暂无"}

## 批评要求
1. 指出方案中的逻辑漏洞
2. 识别被忽视的风险
3. 质疑假设的合理性
4. 提出需要进一步考虑的问题

请提供建设性的批评意见。
"""


# ==================== 工厂函数 ====================

def create_decision_agent(
    role: str,
    llm_adapter=None,
    agent_id: str = None
) -> BaseHierarchicalAgent:
    """
    创建决策层智能体
    
    Args:
        role: 角色类型 (strategist/analyst/critic)
        llm_adapter: LLM 适配器
        agent_id: 智能体ID
        
    Returns:
        决策层智能体实例
    """
    role_mapping = {
        "strategist": StrategistAgent,
        "analyst": AnalystAgent,
        "critic": CriticAgent
    }
    
    agent_class = role_mapping.get(role.lower(), StrategistAgent)
    return agent_class(llm_adapter=llm_adapter, agent_id=agent_id)
