"""
共识追踪系统 - 基础类型定义
包含共识类型、优先级和冲突严重程度等枚举类型。
"""

from enum import Enum


class ConsensusType(Enum):
    """共识类型枚举"""
    CORE = "core"           # 核心共识 - 关于主题的基本定义和目标
    STRATEGIC = "strategic" # 战略共识 - 关于方向和策略
    TACTICAL = "tactical"   # 战术共识 - 关于具体实施方法
    PROCEDURAL = "procedural"  # 程序共识 - 关于讨论流程和规则
    TECHNICAL = "technical" # 技术共识 - 关于技术方案
    AUXILIARY = "auxiliary" # 辅助共识 - 次要观点和支持性论点


class ConsensusPriority(Enum):
    """共识优先级"""
    CRITICAL = 1   # 必须解决
    HIGH = 2       # 重要
    MEDIUM = 3     # 一般
    LOW = 4        # 可选


class ConflictSeverity(Enum):
    """冲突严重程度"""
    CRITICAL = "critical"   # 必须立即解决
    HIGH = "high"           # 需要深度讨论
    MEDIUM = "medium"       # 需要关注
    LOW = "low"             # 可以暂时搁置
