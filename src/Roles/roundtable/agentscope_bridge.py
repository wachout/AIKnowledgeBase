# -*- coding: utf-8 -*-
"""
AgentScope 桥接模块：用 AgentScope 统一圆桌会议三层智能体的消息格式与执行

- 第一层：讨论层（领域专家、质疑者等）
- 第二层：实施层（科学家、领域实施专家、综合者）
- 第三层：具像化层（数字化/具像化工程师等）

使用方式：
1. 消息统一为 AgentScope Msg（name/role/content/metadata），便于跨层传递与记忆。
2. 将现有 BaseAgent 包装为 AgentScope AgentBase，通过 reply() 委托 think/speak，支持异步与记忆。
3. 可选：通过环境变量 USE_AGENTSCOPE=1 或配置启用，由 control_discussion 使用本桥接执行智能体。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..personnel.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# 可选依赖：AgentScope 未安装时桥接不生效
try:
    from agentscope.message import Msg
    from agentscope.agent import AgentBase
    from agentscope.memory import InMemoryMemory
    _AGENTSCOPE_AVAILABLE = True
except ImportError:
    Msg = None  # type: ignore
    AgentBase = object  # type: ignore
    InMemoryMemory = None  # type: ignore
    _AGENTSCOPE_AVAILABLE = False


def is_agentscope_available() -> bool:
    """是否已安装并可用 AgentScope。"""
    return _AGENTSCOPE_AVAILABLE


def to_agentscope_msg(
    name: str,
    content: Any,
    role: str = "user",
    metadata: Optional[Dict[str, Any]] = None,
) -> "Msg":
    """
    将圆桌内部数据转为 AgentScope Msg，便于跨层统一传递与记忆。
    AgentScope 要求 content 为 str 或 content blocks 列表，dict 会序列化为 JSON 字符串。
    """
    if not _AGENTSCOPE_AVAILABLE:
        raise RuntimeError("AgentScope 未安装，请执行: pip install agentscope")
    if isinstance(content, dict):
        content = json.dumps(content, ensure_ascii=False)
    elif not isinstance(content, str) and content is not None:
        content = str(content)
    return Msg(name=name, content=content or "", role=role, metadata=metadata or {})


def from_agentscope_msg(msg: "Msg") -> Dict[str, Any]:
    """
    从 AgentScope Msg 解析出圆桌可用的结构：
    - content: 发言内容或结构化 dict
    - name: 发送者
    - metadata: 扩展信息（如 round_number, layer）
    """
    if not _AGENTSCOPE_AVAILABLE or msg is None:
        return {}
    out = {"name": getattr(msg, "name", None), "content": getattr(msg, "content", None)}
    if hasattr(msg, "metadata") and msg.metadata:
        out["metadata"] = dict(msg.metadata)
    return out


def build_roundtable_input_msg(
    topic: str,
    context: Dict[str, Any],
    previous_speeches: List[Dict[str, Any]],
    sender: str = "coordinator",
) -> "Msg":
    """
    构建发给某一圆桌智能体的输入 Msg，content 为结构化 dict，
    供 RoundtableAgentScopeAdapter.reply() 解析并调用 think/speak。
    """
    payload = {
        "topic": topic,
        "context": context,
        "previous_speeches": previous_speeches,
    }
    return to_agentscope_msg(
        name=sender,
        content=payload,
        role="user",
        metadata={"type": "roundtable_input"},
    )


class RoundtableAgentScopeAdapter(AgentBase if _AGENTSCOPE_AVAILABLE else object):
    """
    将现有 BaseAgent（如 DomainExpert、Skeptic）包装为 AgentScope AgentBase，
    通过 reply() 接收 Msg，解析 topic/context/previous_speeches 后调用
    agent.think() 与 agent.speak()，再以 Msg 返回发言结果。
    支持 AgentScope 的 memory（若传入）统一存储讨论消息。
    """

    def __init__(
        self,
        name: str,
        agent: "BaseAgent",
        memory: Optional["InMemoryMemory"] = None,
    ):
        if not _AGENTSCOPE_AVAILABLE:
            raise RuntimeError("AgentScope 未安装，请执行: pip install agentscope")
        try:
            super().__init__(name=name)
        except TypeError:
            super().__init__()
        self.name = name
        self._agent = agent
        self._memory = memory or InMemoryMemory()

    async def reply(self, msg: Optional["Msg"] = None) -> "Msg":
        """
        处理圆桌输入 Msg：content 为 dict 含 topic/context/previous_speeches，
        调用底层 agent.think + agent.speak，返回包含 thinking 与 speech 的 Msg。
        """
        await self._memory.add(msg)
        content = getattr(msg, "content", None) if msg else None
        if isinstance(content, str) and content.strip().startswith("{"):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                content = {"topic": content, "context": {}, "previous_speeches": []}
        if isinstance(content, dict):
            topic = content.get("topic", "")
            context = content.get("context", {})
            previous_speeches = content.get("previous_speeches", [])
        else:
            topic = str(content) if content else ""
            context = {}
            previous_speeches = []

        loop = asyncio.get_event_loop()
        thinking_result = await loop.run_in_executor(
            None,
            lambda: self._agent.think(topic, context),
        )
        speech_result = await loop.run_in_executor(
            None,
            lambda: self._agent.speak(context, previous_speeches),
        )

        response_content = {
            "thinking": thinking_result,
            "speech": speech_result,
        }
        # AgentScope Msg 要求 content 为 str 或 content blocks，故序列化为 JSON
        response_msg = Msg(
            name=self.name,
            role="assistant",
            content=json.dumps(response_content, ensure_ascii=False),
            metadata={"type": "roundtable_speech"},
        )
        await self._memory.add(response_msg)
        return response_msg

    async def observe(self, msg: Optional["Msg"] = None) -> None:
        """仅将消息写入记忆，不生成回复。"""
        if msg:
            await self._memory.add(msg)


def create_roundtable_agents_agentscope(
    agents_dict: Dict[str, "BaseAgent"],
    use_memory: bool = True,
) -> Dict[str, "RoundtableAgentScopeAdapter"]:
    """
    为圆桌第一层（或第二层）的 agents 字典创建 AgentScope 包装，
    返回 name -> RoundtableAgentScopeAdapter。
    若未安装 AgentScope，返回空字典。
    """
    if not _AGENTSCOPE_AVAILABLE:
        logger.warning("AgentScope 未安装，create_roundtable_agents_agentscope 返回空字典")
        return {}

    memory = InMemoryMemory() if use_memory else None
    out = {}
    for agent_name, agent in agents_dict.items():
        try:
            out[agent_name] = RoundtableAgentScopeAdapter(
                name=agent_name,
                agent=agent,
                memory=memory,
            )
        except Exception as e:
            logger.warning(f"为智能体 {agent_name} 创建 AgentScope 包装失败: {e}")
    return out


def get_agentscope_enabled() -> bool:
    """是否启用 AgentScope 执行圆桌智能体（可通过环境变量 USE_AGENTSCOPE=1 开启）。"""
    return os.environ.get("USE_AGENTSCOPE", "").strip() in ("1", "true", "True", "yes")


def run_agent_reply_sync(
    adapter: "RoundtableAgentScopeAdapter",
    topic: str,
    context: Dict[str, Any],
    previous_speeches: List[Dict[str, Any]],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    在同步上下文中运行某一圆桌智能体的 reply（think + speak），
    返回 (thinking_result, speech_result)。
    若未安装 AgentScope 或 adapter 非 AgentScope 包装，调用方应回退到直接调用 agent.think/speak。
    """
    if not _AGENTSCOPE_AVAILABLE or not isinstance(adapter, RoundtableAgentScopeAdapter):
        return {}, {}
    msg = build_roundtable_input_msg(topic, context, previous_speeches)
    try:
        # 本函数常在无事件循环的线程中被调用，不能用 get_event_loop()；用 get_running_loop() 判断是否已有运行中的循环
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            future = asyncio.run_coroutine_threadsafe(adapter.reply(msg), loop)
            response_msg = future.result(timeout=120)
        else:
            response_msg = asyncio.run(adapter.reply(msg))
    except Exception as e:
        logger.warning(f"AgentScope adapter.reply 执行失败: {e}", exc_info=True)
        return {}, {}
    content = getattr(response_msg, "content", None)
    if isinstance(content, str) and content.strip().startswith("{"):
        try:
            content = json.loads(content)
        except json.JSONDecodeError:
            content = None
    if isinstance(content, dict):
        return content.get("thinking", {}), content.get("speech", {})
    return {}, {}
