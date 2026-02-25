"""
科学家/学者智能体

分析第一层输出的任务分解，决定实施该项目需要哪些领域的专家。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator
import asyncio
import uuid
import json
import re
import logging

from .base_hierarchical_agent import (
    BaseHierarchicalAgent, HierarchicalAgentConfig, AgentCapability
)
from ..types import LayerType, AgentAction


logger = logging.getLogger(__name__)


@dataclass
class ExpertRequirement:
    """专家需求"""
    role: str                      # 角色标识 (如 software_architect)
    name: str                      # 显示名称 (如 软件架构师)
    domain: str                    # 专业领域 (如 软件架构设计)
    reason: str                    # 需要该专家的原因
    expertise: List[str] = field(default_factory=list)  # 具体专长
    priority: int = 1              # 优先级 1-5


@dataclass
class ScholarAnalysisResult:
    """科学家分析结果"""
    task_analysis: str                          # 任务分析摘要
    project_type: str                           # 项目类型
    required_experts: List[ExpertRequirement]   # 所需专家列表
    key_challenges: List[str]                   # 关键挑战
    estimated_complexity: str                   # 估计复杂度 (低/中/高)
    analysis_timestamp: datetime = field(default_factory=datetime.now)


class ScholarAgent(BaseHierarchicalAgent):
    """
    科学家/学者智能体
    
    职责：
    1. 阅读用户需求和第一层圆桌讨论输出的任务分解
    2. 分析项目需要哪些领域的专家
    3. 输出专家需求列表，供动态智能体工厂创建专家
    """
    
    def __init__(self, llm_adapter=None, agent_id: str = None):
        config = HierarchicalAgentConfig(
            agent_id=agent_id or f"scholar_{uuid.uuid4().hex[:6]}",
            name="科学家",
            layer=LayerType.IMPLEMENTATION,
            role="scholar",
            capabilities={
                AgentCapability.REASONING,
                AgentCapability.PLANNING,
                AgentCapability.STRATEGY_FORMULATION,
                AgentCapability.COMMUNICATION
            }
        )
        super().__init__(config, llm_adapter)
        self.last_analysis: Optional[ScholarAnalysisResult] = None
    
    async def act(self, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """执行分析动作"""
        yield f"[{self.name}] 正在分析任务需求...\n"
        
        prompt = self.get_prompt(context)
        response_parts = []
        
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        full_response = "".join(response_parts)
        self.last_result = {"action": "analyze", "response": full_response}
    
    async def analyze_required_experts(
        self,
        task_list: List[Dict[str, Any]],
        first_layer_output: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        分析第一层输出，确定需要哪些专家
        
        Args:
            task_list: 第一层输出的任务列表
            first_layer_output: 第一层完整输出（包含共识、洞察等）
        
        Yields:
            分析过程的输出
        """
        yield "\n┌─────────────────────────────────────────┐\n"
        yield "│       科学家分析阶段                      │\n"
        yield "└─────────────────────────────────────────┘\n\n"
        
        # 构建分析上下文
        context = {
            "task_list": task_list,
            "first_layer_output": first_layer_output
        }
        
        yield "[科学家] 正在阅读第一层讨论结果...\n"
        yield f"[科学家] 发现 {len(task_list)} 个待实施任务\n\n"
        
        # 调用LLM进行分析
        prompt = self._build_analysis_prompt(task_list, first_layer_output)
        
        yield "[科学家] 正在分析项目需要的专家团队...\n\n"
        
        response_parts = []
        async for chunk in self.call_llm(prompt):
            yield chunk
            response_parts.append(chunk)
        
        full_response = "".join(response_parts)
        
        # 解析结果
        yield "\n\n[科学家] 正在整理专家需求...\n"
        analysis_result = self._parse_analysis_result(full_response)
        self.last_analysis = analysis_result
        
        yield f"\n[科学家] 分析完成，需要 {len(analysis_result.required_experts)} 位专家\n"
        
        # 输出专家列表
        yield "\n需要的专家团队:\n"
        for i, expert in enumerate(analysis_result.required_experts, 1):
            yield f"  {i}. {expert.name} ({expert.domain})\n"
            yield f"     原因: {expert.reason}\n"
    
    def get_analysis_result(self) -> Optional[ScholarAnalysisResult]:
        """获取最近一次分析结果"""
        return self.last_analysis
    
    def get_required_experts_specs(self) -> List[Dict[str, Any]]:
        """
        获取专家需求规格列表，用于动态智能体工厂
        
        Returns:
            专家规格列表，每个元素包含 role, name, domain, expertise
        """
        if not self.last_analysis:
            return []
        
        specs = []
        for expert in self.last_analysis.required_experts:
            specs.append({
                "role": expert.role,
                "name": expert.name,
                "domain": expert.domain,
                "expertise": expert.expertise,
                "reason": expert.reason,
                "priority": expert.priority
            })
        return specs
    
    def _build_analysis_prompt(
        self,
        task_list: List[Dict[str, Any]],
        first_layer_output: Dict[str, Any]
    ) -> str:
        """构建分析提示词"""
        # 格式化任务列表
        tasks_text = ""
        for i, task in enumerate(task_list, 1):
            name = task.get('name', f'任务{i}')
            desc = task.get('description', '')
            tasks_text += f"{i}. {name}\n   {desc}\n\n"
        
        # 提取第一层关键信息
        consensus = first_layer_output.get('consensus_data', {})
        key_points = consensus.get('key_points', [])
        insights = first_layer_output.get('key_insights', [])
        
        key_points_text = "\n".join([f"- {p}" for p in key_points[:5]]) if key_points else "无"
        insights_text = "\n".join([f"- {i}" for i in insights[:5]]) if insights else "无"
        
        return f"""你是一位资深科学家/学者，负责分析项目需求并确定所需的专家团队。第二层实施步骤细化层将与第一层讨论层的领域专家一一对应；若第一层已有领域专家名单，将优先按该名单创建第二层智能体。请明确用户目标，推荐可落地实施的领域专家。

## 用户需求和第一层讨论结果

### 待实施任务
{tasks_text}

### 第一层讨论共识
{key_points_text}

### 关键洞察
{insights_text}

## 你的任务

请分析以上内容，确定实施这个项目需要哪些领域的专家。推荐专家时须紧扣用户目标，便于第二层给出可实施、可验证的详细步骤。

请按以下格式输出（使用JSON格式）：

```json
{{
  "task_analysis": "对任务的整体分析摘要",
  "project_type": "项目类型（如：软件开发、硬件设计、科研项目、综合工程等）",
  "estimated_complexity": "复杂度评估（低/中/高）",
  "key_challenges": ["挑战1", "挑战2", "..."],
  "required_experts": [
    {{
      "role": "expert_role_id",
      "name": "专家名称（中文）",
      "domain": "专业领域",
      "reason": "需要该专家的原因",
      "expertise": ["具体专长1", "具体专长2"],
      "priority": 1
    }}
  ]
}}
```

## 可选的专家类型（可根据需要自定义）

**软件领域**: software_architect(软件架构师), frontend_engineer(前端工程师), backend_engineer(后端工程师), database_expert(数据库专家), devops_engineer(运维工程师), ai_engineer(AI工程师), security_expert(安全专家)

**硬件领域**: hardware_engineer(硬件工程师), embedded_engineer(嵌入式工程师), circuit_designer(电路设计师), pcb_engineer(PCB工程师)

**科学领域**: materials_scientist(材料学家), chemist(化学家), physicist(物理学家), biologist(生物学家), data_scientist(数据科学家)

**管理与规划**: project_planner(项目规划师), cost_estimator(成本估算师), quality_manager(质量管理师), risk_analyst(风险分析师)

**其他**: 可根据项目需要自定义专家类型

请根据项目实际需求选择3-6位最关键的专家。
"""
    
    def _parse_analysis_result(self, response: str) -> ScholarAnalysisResult:
        """解析LLM返回的分析结果"""
        try:
            # 尝试提取JSON
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    return self._create_default_result(response)
            
            data = json.loads(json_str)
            
            # 解析专家列表
            required_experts = []
            for exp in data.get('required_experts', []):
                expert = ExpertRequirement(
                    role=exp.get('role', 'custom'),
                    name=exp.get('name', '领域专家'),
                    domain=exp.get('domain', '通用'),
                    reason=exp.get('reason', '项目需要'),
                    expertise=exp.get('expertise', []),
                    priority=exp.get('priority', 1)
                )
                required_experts.append(expert)
            
            return ScholarAnalysisResult(
                task_analysis=data.get('task_analysis', ''),
                project_type=data.get('project_type', '综合项目'),
                required_experts=required_experts,
                key_challenges=data.get('key_challenges', []),
                estimated_complexity=data.get('estimated_complexity', '中')
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"解析科学家分析结果失败: {e}")
            return self._create_default_result(response)
    
    def _create_default_result(self, response: str) -> ScholarAnalysisResult:
        """创建默认分析结果（解析失败时使用）"""
        return ScholarAnalysisResult(
            task_analysis=response[:500] if response else "无法解析",
            project_type="综合项目",
            required_experts=[
                ExpertRequirement(
                    role="project_planner",
                    name="项目规划师",
                    domain="项目规划",
                    reason="统筹项目实施",
                    expertise=["项目管理", "资源调度"],
                    priority=1
                ),
                ExpertRequirement(
                    role="technical_expert",
                    name="技术专家",
                    domain="技术实施",
                    reason="提供技术方案",
                    expertise=["技术分析", "方案设计"],
                    priority=2
                ),
                ExpertRequirement(
                    role="quality_manager",
                    name="质量管理师",
                    domain="质量控制",
                    reason="确保实施质量",
                    expertise=["质量标准", "验收检查"],
                    priority=3
                )
            ],
            key_challenges=["需要进一步分析"],
            estimated_complexity="中"
        )
    
    def get_prompt(self, context: Dict[str, Any]) -> str:
        """获取通用提示词"""
        task_list = context.get('task_list', [])
        first_layer_output = context.get('first_layer_output', {})
        return self._build_analysis_prompt(task_list, first_layer_output)
    
    def select_action(self, state: Dict[str, Any]) -> AgentAction:
        """选择动作"""
        return AgentAction.ANALYZE
