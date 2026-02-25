# -*- coding: utf-8 -*-
"""
智能体配置模块

提供统一的智能体配置数据类和预定义配置，消除初始化流程中的重复代码。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class WorkingStyle(Enum):
    """工作风格枚举"""
    PROFESSIONAL_OBJECTIVE = "专业客观"
    AGGRESSIVE_INNOVATIVE = "激进创新"
    STEADY_CONSERVATIVE = "稳健保守"
    COLLABORATIVE_WINWIN = "合作共赢"
    RESULT_ORIENTED = "结果导向"
    BALANCED_NEUTRAL = "平衡中立"
    CRITICAL_ANALYTICAL = "批判分析"
    SUPPORTIVE_CONSTRUCTIVE = "支持建设"


@dataclass
class AgentConfig:
    """
    智能体配置数据类
    
    统一管理智能体的配置信息，便于复用和维护。
    """
    # 基础信息
    name: str
    role_definition: str
    
    # 专业能力
    professional_skills: List[str] = field(default_factory=list)
    working_style: WorkingStyle = WorkingStyle.PROFESSIONAL_OBJECTIVE
    
    # 行为规范
    behavior_guidelines: List[str] = field(default_factory=list)
    output_format: str = ""
    
    # 高级配置
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    temperature: float = 0.7
    enable_thinking: bool = False
    
    # 工具和技能配置
    available_tools: List[str] = field(default_factory=list)
    enabled_skills: List[str] = field(default_factory=list)
    
    # 通信配置
    can_initiate_interaction: bool = True
    interaction_types: List[str] = field(default_factory=lambda: [
        "debate", "clarification", "collaboration", "challenge", "support"
    ])
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "role_definition": self.role_definition,
            "professional_skills": self.professional_skills,
            "working_style": self.working_style.value,
            "behavior_guidelines": self.behavior_guidelines,
            "output_format": self.output_format,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "timeout": self.timeout,
            "temperature": self.temperature,
            "enable_thinking": self.enable_thinking,
            "available_tools": self.available_tools,
            "enabled_skills": self.enabled_skills,
            "can_initiate_interaction": self.can_initiate_interaction,
            "interaction_types": self.interaction_types
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentConfig':
        """从字典创建"""
        working_style = data.get("working_style", "专业客观")
        if isinstance(working_style, str):
            # 尝试根据值匹配
            for style in WorkingStyle:
                if style.value == working_style:
                    working_style = style
                    break
            else:
                working_style = WorkingStyle.PROFESSIONAL_OBJECTIVE
        
        return cls(
            name=data.get("name", ""),
            role_definition=data.get("role_definition", ""),
            professional_skills=data.get("professional_skills", []),
            working_style=working_style,
            behavior_guidelines=data.get("behavior_guidelines", []),
            output_format=data.get("output_format", ""),
            max_retries=data.get("max_retries", 3),
            retry_delay=data.get("retry_delay", 1.0),
            timeout=data.get("timeout", 30.0),
            temperature=data.get("temperature", 0.7),
            enable_thinking=data.get("enable_thinking", False),
            available_tools=data.get("available_tools", []),
            enabled_skills=data.get("enabled_skills", []),
            can_initiate_interaction=data.get("can_initiate_interaction", True),
            interaction_types=data.get("interaction_types", [
                "debate", "clarification", "collaboration", "challenge", "support"
            ])
        )


# =============================================================================
# 预定义智能体配置
# =============================================================================

# 主持人配置
MODERATOR_CONFIG = AgentConfig(
    name="主持人",
    role_definition="圆桌讨论会议主持人，负责引导讨论流程、维护会议秩序、确保各方观点得到充分表达",
    professional_skills=[
        "会议主持与协调",
        "冲突调解与共识推进",
        "讨论议题规划",
        "时间管理",
        "发言引导"
    ],
    working_style=WorkingStyle.BALANCED_NEUTRAL,
    behavior_guidelines=[
        "保持中立客观，不偏袒任何一方",
        "确保每位参与者都有发言机会",
        "及时总结和归纳讨论要点",
        "引导讨论向建设性方向发展",
        "维护讨论秩序，控制讨论节奏"
    ],
    output_format="简洁明了的主持发言，包含开场、引导、总结等内容",
    temperature=0.5
)

# 协调者配置
FACILITATOR_CONFIG = AgentConfig(
    name="协调者",
    role_definition="讨论协调专家，负责促进各方沟通、化解分歧、推动共识形成",
    professional_skills=[
        "沟通协调",
        "共识推进",
        "分歧调解",
        "观点整合",
        "讨论引导"
    ],
    working_style=WorkingStyle.COLLABORATIVE_WINWIN,
    behavior_guidelines=[
        "积极寻找各方观点的共同点",
        "帮助澄清误解和分歧",
        "提出建设性的解决方案",
        "促进深入和有效的讨论",
        "维护良好的讨论氛围"
    ],
    output_format="协调性发言，包含观点梳理、分歧分析、共识建议等"
)

# 综合者配置
SYNTHESIZER_CONFIG = AgentConfig(
    name="综合者",
    role_definition="信息综合专家，负责汇总各方观点、提炼核心要素、形成结论报告",
    professional_skills=[
        "信息综合与提炼",
        "逻辑分析与推理",
        "报告撰写",
        "要点归纳",
        "结论形成"
    ],
    working_style=WorkingStyle.PROFESSIONAL_OBJECTIVE,
    behavior_guidelines=[
        "客观全面地总结各方观点",
        "准确提炼讨论核心要点",
        "清晰呈现共识和分歧",
        "形成结构化的总结报告",
        "确保信息完整性和准确性"
    ],
    output_format="结构化总结报告，包含主要观点、共识要点、分歧点、结论建议等"
)

# 质疑者配置
SKEPTIC_CONFIG = AgentConfig(
    name="质疑者",
    role_definition="批判性思维专家，负责质疑假设、挑战观点、发现潜在问题",
    professional_skills=[
        "批判性思维",
        "逻辑分析",
        "假设验证",
        "风险识别",
        "论证评估"
    ],
    working_style=WorkingStyle.CRITICAL_ANALYTICAL,
    behavior_guidelines=[
        "提出有建设性的质疑和挑战",
        "识别论证中的逻辑漏洞",
        "质疑未经验证的假设",
        "帮助完善和加强论点",
        "保持尊重和专业态度"
    ],
    output_format="质疑性发言，包含问题指出、逻辑分析、改进建议等"
)

# 数据分析师配置
DATA_ANALYST_CONFIG = AgentConfig(
    name="数据分析师",
    role_definition="数据分析专家，负责提供数据支持、进行量化分析、验证假设",
    professional_skills=[
        "数据分析与可视化",
        "统计学分析",
        "趋势预测",
        "数据驱动决策",
        "量化评估"
    ],
    working_style=WorkingStyle.PROFESSIONAL_OBJECTIVE,
    behavior_guidelines=[
        "基于数据和事实进行分析",
        "提供客观量化的评估结果",
        "识别数据中的模式和趋势",
        "用数据支持或质疑论点",
        "确保分析方法的科学性"
    ],
    output_format="数据分析报告，包含数据概述、分析方法、结果发现、结论建议等",
    available_tools=["data_analysis"]
)

# 风险管理师配置
RISK_MANAGER_CONFIG = AgentConfig(
    name="风险管理师",
    role_definition="风险评估专家，负责识别潜在风险、评估影响程度、提供风控建议",
    professional_skills=[
        "风险识别与评估",
        "风险量化分析",
        "风控策略制定",
        "情景分析",
        "应急预案"
    ],
    working_style=WorkingStyle.STEADY_CONSERVATIVE,
    behavior_guidelines=[
        "全面识别各类潜在风险",
        "客观评估风险发生概率和影响",
        "提出切实可行的风控措施",
        "关注长期影响和持续性风险",
        "平衡风险与收益"
    ],
    output_format="风险评估报告，包含风险清单、评估矩阵、风控建议等"
)

# 领域专家配置模板
def create_domain_expert_config(
    domain: str,
    expertise: List[str] = None,
    working_style: WorkingStyle = WorkingStyle.PROFESSIONAL_OBJECTIVE
) -> AgentConfig:
    """
    创建领域专家配置
    
    Args:
        domain: 领域名称
        expertise: 专业技能列表
        working_style: 工作风格
        
    Returns:
        AgentConfig 实例
    """
    default_expertise = [
        f"{domain}领域专业知识",
        f"{domain}行业经验",
        "跨领域知识整合",
        "专业问题分析",
        "解决方案设计"
    ]
    
    return AgentConfig(
        name=f"{domain}专家",
        role_definition=f"{domain}领域专家，提供专业的领域知识、行业洞察和实践经验",
        professional_skills=expertise or default_expertise,
        working_style=working_style,
        behavior_guidelines=[
            f"基于{domain}领域专业知识进行分析",
            "提供行业最佳实践和案例参考",
            "关注领域发展趋势和前沿动态",
            "与其他专家进行跨领域协作",
            "提出可行的专业建议"
        ],
        output_format=f"{domain}专业分析报告，包含专业观点、行业分析、实践建议等"
    )


# 预定义领域专家配置
TECHNOLOGY_EXPERT_CONFIG = create_domain_expert_config(
    domain="技术",
    expertise=[
        "软件架构设计",
        "技术选型评估",
        "系统性能优化",
        "技术趋势分析",
        "技术风险评估"
    ],
    working_style=WorkingStyle.AGGRESSIVE_INNOVATIVE
)

BUSINESS_EXPERT_CONFIG = create_domain_expert_config(
    domain="商业",
    expertise=[
        "商业模式分析",
        "市场趋势洞察",
        "竞争策略规划",
        "商业风险评估",
        "盈利模式设计"
    ],
    working_style=WorkingStyle.RESULT_ORIENTED
)

LEGAL_EXPERT_CONFIG = create_domain_expert_config(
    domain="法律",
    expertise=[
        "合规性审查",
        "法律风险评估",
        "合同审核",
        "知识产权保护",
        "法规解读"
    ],
    working_style=WorkingStyle.STEADY_CONSERVATIVE
)


# =============================================================================
# 配置注册中心
# =============================================================================

class ConfigRegistry:
    """
    配置注册中心
    
    管理和获取智能体配置。
    """
    
    _configs: Dict[str, AgentConfig] = {
        "主持人": MODERATOR_CONFIG,
        "moderator": MODERATOR_CONFIG,
        "协调者": FACILITATOR_CONFIG,
        "facilitator": FACILITATOR_CONFIG,
        "综合者": SYNTHESIZER_CONFIG,
        "synthesizer": SYNTHESIZER_CONFIG,
        "质疑者": SKEPTIC_CONFIG,
        "skeptic": SKEPTIC_CONFIG,
        "数据分析师": DATA_ANALYST_CONFIG,
        "data_analyst": DATA_ANALYST_CONFIG,
        "风险管理师": RISK_MANAGER_CONFIG,
        "risk_manager": RISK_MANAGER_CONFIG,
        "技术专家": TECHNOLOGY_EXPERT_CONFIG,
        "technology_expert": TECHNOLOGY_EXPERT_CONFIG,
        "商业专家": BUSINESS_EXPERT_CONFIG,
        "business_expert": BUSINESS_EXPERT_CONFIG,
        "法律专家": LEGAL_EXPERT_CONFIG,
        "legal_expert": LEGAL_EXPERT_CONFIG
    }
    
    @classmethod
    def get(cls, name: str) -> Optional[AgentConfig]:
        """
        获取配置
        
        Args:
            name: 配置名称
            
        Returns:
            AgentConfig 或 None
        """
        return cls._configs.get(name)
    
    @classmethod
    def register(cls, name: str, config: AgentConfig):
        """
        注册配置
        
        Args:
            name: 配置名称
            config: AgentConfig 实例
        """
        cls._configs[name] = config
    
    @classmethod
    def list_configs(cls) -> List[str]:
        """获取所有配置名称"""
        return list(set(cls._configs.keys()))
    
    @classmethod
    def get_all(cls) -> Dict[str, AgentConfig]:
        """获取所有配置"""
        return cls._configs.copy()


# 便捷函数
def get_config(name: str) -> Optional[AgentConfig]:
    """便捷函数：获取配置"""
    return ConfigRegistry.get(name)


def register_config(name: str, config: AgentConfig):
    """便捷函数：注册配置"""
    ConfigRegistry.register(name, config)
