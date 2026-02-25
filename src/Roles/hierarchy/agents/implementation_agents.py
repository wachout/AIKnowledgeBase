"""
多层强化学习智能体系统 - 实施层智能体
负责具体实施工作的专用智能体
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Generator, Set, AsyncGenerator
import asyncio
import uuid

from .base_hierarchical_agent import (
    BaseHierarchicalAgent, HierarchicalAgentConfig, AgentCapability
)
from ..types import LayerType, AgentAction, ImplementationRole


class ArchitectAgent(BaseHierarchicalAgent):
    """架构师智能体 - 负责技术架构设计"""
    
    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"architect_{uuid.uuid4().hex[:6]}",
            name="架构师",
            layer=LayerType.IMPLEMENTATION,
            role="architect",
            capabilities={
                AgentCapability.DESIGN,
                AgentCapability.PLANNING,
                AgentCapability.REASONING,
                AgentCapability.COMMUNICATION
            }
        )
        super().__init__(config, llm_adapter)
    
    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Note: 结果存储在 self.last_result 属性中"""
        yield f"[{self.name}] 正在设计架构...\n"
        action = self.select_action(context)
        prompt = self.get_prompt(context)
        
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        self.last_result = {"action": action.value, "response": "".join(response_parts)}
    
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        return AgentAction.DESIGN
    
    def get_prompt(self, context: Dict[str, Any]) -> str:
        task = context.get("task", {})
        phase_name = context.get("phase_name", "架构设计")
        previous_speeches = context.get("previous_speeches", [])
        
        # 构建之前发言的摘要
        prev_summary = ""
        if previous_speeches:
            prev_summary = "\n".join([f"- {s[:100]}..." if len(str(s)) > 100 else f"- {s}" for s in previous_speeches[-3:]])
        
        # 提取任务描述的关键信息（去除代码）
        task_desc = task.get('description', '')
        if len(task_desc) > 200:
            task_desc = task_desc[:200] + "..."
        
        return f"""【重要】这是一个圆桌讨论会议，你需要用口语化的方式发言，禁止输出任何代码、类定义或函数实现。

你是一位资深技术架构师，正在参与关于"{task.get('name', '未知任务')}"的实施讨论。

## 当前阶段：{phase_name}

## 讨论话题
{task_desc}

## 之前的讨论
{prev_summary if prev_summary else '这是第一个发言'}

## 你的发言要求
请用自然语言口语化地阐述你的架构设计思路：
- 你认为应该如何划分模块？
- 核心组件之间如何协作？
- 你推荐什么技术方案？
- 有哪些需要注意的风险？

请直接开始你的发言（不要输出代码）：
"""


class DeveloperAgent(BaseHierarchicalAgent):
    """开发者智能体 - 负责具体实现逻辑"""
    
    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"developer_{uuid.uuid4().hex[:6]}",
            name="开发者",
            layer=LayerType.IMPLEMENTATION,
            role="developer",
            capabilities={
                AgentCapability.IMPLEMENTATION,
                AgentCapability.REASONING,
                AgentCapability.COMMUNICATION
            }
        )
        super().__init__(config, llm_adapter)
    
    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Note: 结果存储在 self.last_result 属性中"""
        yield f"[{self.name}] 正在实现功能...\n"
        action = self.select_action(context)
        prompt = self.get_prompt(context)
        
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        self.last_result = {"action": action.value, "response": "".join(response_parts)}
    
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        return AgentAction.IMPLEMENT
    
    def get_prompt(self, context: Dict[str, Any]) -> str:
        task = context.get("task", {})
        design = context.get("design", "")
        phase_name = context.get("phase_name", "功能实现")
        previous_speeches = context.get("previous_speeches", [])
        
        prev_summary = ""
        if previous_speeches:
            prev_summary = "\n".join([f"- {s[:100]}..." if len(str(s)) > 100 else f"- {s}" for s in previous_speeches[-3:]])
        
        task_desc = task.get('description', '')
        if len(task_desc) > 200:
            task_desc = task_desc[:200] + "..."
        
        return f"""【重要】这是一个圆桌讨论会议，你需要用口语化的方式发言，禁止输出任何代码、类定义或函数实现。

你是一位专业开发者，正在参与关于"{task.get('name', '未知任务')}"的实施讨论。

## 当前阶段：{phase_name}

## 讨论话题
{task_desc}

## 之前的讨论
{prev_summary if prev_summary else '这是第一个发言'}

## 你的发言要求
请用自然语言口语化地阐述你对实现可行性的评估：
- 这个任务的主要技术难点是什么？
- 你打算如何实现？大致思路是什么？
- 可能会遇到哪些风险和挑战？
- 预计需要多少时间和资源？

请直接开始你的发言（不要输出代码）：
"""


class TesterAgent(BaseHierarchicalAgent):
    """测试员智能体 - 负责测试用例设计"""
    
    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"tester_{uuid.uuid4().hex[:6]}",
            name="测试员",
            layer=LayerType.IMPLEMENTATION,
            role="tester",
            capabilities={
                AgentCapability.TESTING,
                AgentCapability.REASONING,
                AgentCapability.COMMUNICATION
            }
        )
        super().__init__(config, llm_adapter)
    
    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Note: 结果存储在 self.last_result 属性中"""
        yield f"[{self.name}] 正在设计测试用例...\n"
        action = self.select_action(context)
        prompt = self.get_prompt(context)
        
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        self.last_result = {"action": action.value, "response": "".join(response_parts)}
    
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        return AgentAction.TEST
    
    def get_prompt(self, context: Dict[str, Any]) -> str:
        task = context.get("task", {})
        implementation = context.get("implementation", "")
        phase_name = context.get("phase_name", "测试评估")
        previous_speeches = context.get("previous_speeches", [])
        
        prev_summary = ""
        if previous_speeches:
            prev_summary = "\n".join([f"- {s[:100]}..." if len(str(s)) > 100 else f"- {s}" for s in previous_speeches[-3:]])
        
        task_desc = task.get('description', '')
        if len(task_desc) > 200:
            task_desc = task_desc[:200] + "..."
        
        return f"""【重要】这是一个圆桌讨论会议，你需要用口语化的方式发言，禁止输出任何代码、类定义或测试用例实现。

你是一位专业测试工程师，正在参与关于"{task.get('name', '未知功能')}"的实施讨论。

## 当前阶段：{phase_name}

## 讨论话题
{task_desc}

## 之前的讨论
{prev_summary if prev_summary else '这是第一个发言'}

## 你的发言要求
请用自然语言口语化地阐述你的测试策略观点：
- 这个功能需要哪些类型的测试？
- 有哪些关键的边界条件需要覆盖？
- 你认为哪些地方最容易出问题？
- 测试的优先级应该如何排列？

请直接开始你的发言（不要输出代码）：
"""


class DocumenterAgent(BaseHierarchicalAgent):
    """文档员智能体 - 负责文档和规范编写"""
    
    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"documenter_{uuid.uuid4().hex[:6]}",
            name="文档员",
            layer=LayerType.IMPLEMENTATION,
            role="documenter",
            capabilities={
                AgentCapability.DOCUMENTATION,
                AgentCapability.COMMUNICATION
            }
        )
        super().__init__(config, llm_adapter)
    
    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Note: 结果存储在 self.last_result 属性中"""
        yield f"[{self.name}] 正在编写文档...\n"
        action = self.select_action(context)
        prompt = self.get_prompt(context)
        
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        self.last_result = {"action": action.value, "response": "".join(response_parts)}
    
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        return AgentAction.DOCUMENT
    
    def get_prompt(self, context: Dict[str, Any]) -> str:
        task = context.get("task", {})
        artifacts = context.get("artifacts", [])
        return f"""你是一位技术文档专家。请为以下内容编写文档。

## 功能/模块
{task.get('name', '未知')}

## 产出物
{str(artifacts)[:300] if artifacts else '无'}

## 要求
1. 编写使用说明
2. 记录API接口
3. 添加示例代码
4. 说明注意事项

请提供文档内容。
"""


class CoordinatorAgent(BaseHierarchicalAgent):
    """协调员智能体 - 负责进度协调"""
    
    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"coordinator_{uuid.uuid4().hex[:6]}",
            name="协调员",
            layer=LayerType.IMPLEMENTATION,
            role="coordinator",
            capabilities={
                AgentCapability.COORDINATION,
                AgentCapability.PLANNING,
                AgentCapability.COMMUNICATION
            }
        )
        super().__init__(config, llm_adapter)
    
    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Note: 结果存储在 self.last_result 属性中"""
        yield f"[{self.name}] 正在协调进度...\n"
        action = self.select_action(context)
        prompt = self.get_prompt(context)
        
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        self.last_result = {"action": action.value, "response": "".join(response_parts)}
    
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        return AgentAction.COORDINATE
    
    def get_prompt(self, context: Dict[str, Any]) -> str:
        task = context.get("task", {})
        tasks = context.get("tasks", [])
        progress = context.get("progress", {})
        phase_name = context.get("phase_name", "进度协调")
        previous_speeches = context.get("previous_speeches", [])
        consensus_summary = context.get("consensus_summary", "")
        
        prev_summary = ""
        if previous_speeches:
            prev_summary = "\n".join([f"- {s[:100]}..." if len(str(s)) > 100 else f"- {s}" for s in previous_speeches[-3:]])
        
        task_desc = task.get('description', '')
        if len(task_desc) > 150:
            task_desc = task_desc[:150] + "..."
        
        return f"""【重要】这是一个圆桌讨论会议，你需要用口语化的方式发言，禁止输出任何代码、类定义或函数实现。

你是一位项目协调员，正在参与关于"{task.get('name', '当前任务')}"的实施讨论。

## 当前阶段：{phase_name}

## 讨论话题
{task_desc}

## 之前的讨论
{prev_summary if prev_summary else '这是第一个发言'}

## 共识情况
{consensus_summary[:150] if consensus_summary else '暂无共识数据'}

## 你的发言要求
请用自然语言口语化地做一个协调总结：
- 目前大家的观点有哪些共识？
- 还有哪些分歧需要进一步讨论？
- 有没有什么阻塞问题需要解决？
- 下一步应该怎么做？

请直接开始你的发言（不要输出代码）：
"""


def create_implementation_agent(
    role: str,
    llm_adapter=None,
    agent_id: str = None
) -> BaseHierarchicalAgent:
    """创建实施层智能体工厂函数"""
    role_mapping = {
        "architect": ArchitectAgent,
        "developer": DeveloperAgent,
        "tester": TesterAgent,
        "documenter": DocumenterAgent,
        "coordinator": CoordinatorAgent
    }
    agent_class = role_mapping.get(role.lower(), DeveloperAgent)
    return agent_class(llm_adapter=llm_adapter, agent_id=agent_id)
