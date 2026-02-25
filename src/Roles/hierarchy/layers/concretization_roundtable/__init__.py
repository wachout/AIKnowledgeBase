# -*- coding: utf-8 -*-
"""
第三层具像化层

- 数字工程师、具像化工程师、抽象化工程师
- 领域具像化智能体（按实施步骤/领域自动创建）
- 阅读 implement/ 中的实施步骤，产出数字化+具像化描述，保存到 concretization/
"""

from .constraints import (
    CONCRETIZATION_CONSTRAINTS,
    DOMAIN_CONSTRAINT_HINTS,
    get_constraint_prompt_for_domain,
)
from .concretization_agents import (
    DigitalEngineerAgent,
    ConcretizationEngineerAgent,
    AbstractionEngineerAgent,
    DomainConcretizationAgent,
    ConcretizationOutput,
)
from .concretization_discussion import (
    ConcretizationDiscussion,
    ConcretizationResult,
    _collect_implementation_steps,
)

__all__ = [
    "CONCRETIZATION_CONSTRAINTS",
    "DOMAIN_CONSTRAINT_HINTS",
    "get_constraint_prompt_for_domain",
    "DigitalEngineerAgent",
    "ConcretizationEngineerAgent",
    "AbstractionEngineerAgent",
    "DomainConcretizationAgent",
    "ConcretizationOutput",
    "ConcretizationDiscussion",
    "ConcretizationResult",
    "_collect_implementation_steps",
]
