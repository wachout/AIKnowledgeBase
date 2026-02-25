# -*- coding: utf-8 -*-
"""
智能体人员模块
"""

# 基础类
from .base_agent import BaseAgent

# 响应解析工具
from .response_parser import (
    ResponseParser,
    LLMResponseAdapter,
    StructuredResponseBuilder
)

# 智能体配置
from .agent_config import (
    AgentConfig,
    WorkingStyle,
    ConfigRegistry,
    # 预定义配置
    MODERATOR_CONFIG,
    FACILITATOR_CONFIG,
    SYNTHESIZER_CONFIG,
    DATA_ANALYST_CONFIG,
    RISK_MANAGER_CONFIG,
    SKEPTIC_CONFIG,
    TECHNOLOGY_EXPERT_CONFIG,
    BUSINESS_EXPERT_CONFIG,
    LEGAL_EXPERT_CONFIG,
    create_domain_expert_config,
)

# 智能体角色
from .moderator import Moderator
from .facilitator import Facilitator
from .synthesizer import Synthesizer
from .data_analyst import DataAnalyst
from .risk_manager import RiskManager
from .skeptic import Skeptic
from .domain_expert import DomainExpert
from .scholar import Scholar

__all__ = [
    # 基础类
    'BaseAgent',
    
    # 响应解析工具
    'ResponseParser',
    'LLMResponseAdapter',
    'StructuredResponseBuilder',
    
    # 配置
    'AgentConfig',
    'WorkingStyle',
    'ConfigRegistry',
    'MODERATOR_CONFIG',
    'FACILITATOR_CONFIG',
    'SYNTHESIZER_CONFIG',
    'DATA_ANALYST_CONFIG',
    'RISK_MANAGER_CONFIG',
    'SKEPTIC_CONFIG',
    'TECHNOLOGY_EXPERT_CONFIG',
    'BUSINESS_EXPERT_CONFIG',
    'LEGAL_EXPERT_CONFIG',
    'create_domain_expert_config',
    
    # 智能体角色
    'Moderator',
    'Facilitator',
    'Synthesizer',
    'DataAnalyst',
    'RiskManager',
    'Skeptic',
    'DomainExpert',
    'Scholar',
]