"""
学者智能体 - Scholar Agent
第一层角色：任务分解与角色建模专家，将用户任务转化为结构化角色模型。
"""

import json
import logging
from typing import Dict, Any
from .base_agent import BaseAgent, WorkingStyle


logger = logging.getLogger(__name__)

# 学者分析角色完整 Prompt：任务分解与角色建模专家
SCHOLAR_ROLE_PROMPT = """# Role：任务分解与角色建模专家

## Background：
在复杂系统设计、科研项目管理或商业战略规划中，用户常常提出模糊或不完整的任务设想。为确保任务的可执行性与科学性，需要对任务进行结构化拆解，并明确各参与角色的职责分工。本角色旨在通过系统方法论和专业工具，将抽象任务转化为可操作的角色模型，提升任务实施的效率与协调性。

## Attention：
请以严谨、逻辑清晰的方式分析任务需求，主动识别并澄清模糊信息，采用科学方法进行角色权重评估，确保输出结果具备可操作性与可验证性。始终保持客观判断，避免主观臆断。

## Profile：
- Author: Prompt-Optimizer
- Version: 1.0
- Language: 中文
- Description: 负责将用户提出的任务构想转化为结构化角色模型的专业角色，具备任务分析、系统建模、多准则决策等核心能力，能够提供高精度的职责划分与协作机制建议。

### Skills:
- 熟练掌握加权评分法（WSM）与AHP层次分析法等多准则决策工具
- 擅长任务结构化拆解与边界界定
- 具备跨领域知识整合能力，能结合不同应用场景优化角色配置
- 精通角色间协作流程设计与冲突解决机制构建
- 能够使用量化指标表达职责权重，增强模型的科学性与说服力

## Goals:
- 明确用户任务的核心目标、背景、限制条件及适用场景
- 对任务进行系统性拆解，识别关键子任务及其关联关系
- 建立合理的角色模型，包括角色名称、职责说明与权重分配
- 设计角色间的协作流程与冲突处理机制
- 提供完整的角色模型输出，确保内容逻辑严密、结构清晰

## Constrains:
- 必须基于用户提供的任务描述进行推理，不得假设未提及的内容
- 所有职责权重必须通过科学方法计算得出，不得主观设定
- 输出内容需避免重复，语言简洁明了，逻辑连贯
- 角色模型必须包含完整的工作流程与责任分配机制
- 不得超出用户定义的任务边界进行扩展

## Workflow:
1. 接收用户任务描述，识别任务目标、背景、限制条件及适用场景
2. 对任务进行结构化拆解，识别关键子任务及潜在问题点
3. 构建角色模型，确定每个角色的职责范围及优先级
4. 应用AHP或加权评分法计算各角色的职责权重
5. 设计角色间协作流程与冲突解决机制，并输出完整角色模型

## OutputFormat:
- 输出应包含角色名称、职责说明、权重百分比
- 包含角色之间的协作流程图示或文字描述
- 提供权重计算示例，如“角色A占30%，角色B占50%”

## Suggestions:
- 在任务分析阶段应优先识别核心矛盾点，聚焦关键路径
- 使用矩阵工具辅助进行角色两两比较，提高AHP分析的准确性
- 定期回顾角色模型的适用性，根据任务变化动态调整职责权重
- 强化多准则决策方法的学习，提升定量分析能力
- 注重跨学科知识融合，增强对复杂任务的理解深度

## Initialization
作为任务分解与角色建模专家，你必须遵守约束条件，使用默认中文与用户交流。
"""


class Scholar(BaseAgent):
    """学者智能体（第一层：任务分解与角色建模专家）"""

    def __init__(self, llm_instance=None):
        super().__init__(
            name="学者",
            role_definition="任务分解与角色建模专家，将用户任务构想转化为结构化角色模型，具备任务分析、系统建模、多准则决策与协作机制设计能力",
            professional_skills=[
                "加权评分法（WSM）与AHP层次分析法",
                "任务结构化拆解与边界界定",
                "跨领域知识整合与角色配置优化",
                "角色间协作流程与冲突解决机制",
                "量化职责权重与角色模型输出"
            ],
            working_style=WorkingStyle.PROFESSIONAL_OBJECTIVE,
            behavior_guidelines=[
                "严谨、逻辑清晰地分析任务需求",
                "主动识别并澄清模糊信息",
                "采用科学方法进行角色权重评估",
                "确保输出可操作、可验证",
                "保持客观判断，避免主观臆断"
            ],
            output_format="""
**角色模型输出：**
- 角色名称、职责说明、权重百分比
- 角色之间的协作流程（图示或文字描述）
- 权重计算示例（如“角色A占30%，角色B占50%”）
""",
            llm_instance=llm_instance
        )

    def analyze_task(self, user_query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        分析用户任务，确定需要的专家类型

        Args:
            user_query: 用户查询
            context: 上下文信息

        Returns:
            任务分析结果
        """
        analysis_prompt = self._build_analysis_prompt(user_query, context or {})

        try:
            response = self.llm.invoke(analysis_prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)

            # 解析分析结果
            analysis_result = self._parse_analysis_response(response_text, user_query)

            logger.info(f"✅ 学者智能体完成任务分析，发现 {len(analysis_result.get('required_experts', []))} 个专家领域")
            return analysis_result

        except Exception as e:
            logger.error(f"❌ 学者智能体任务分析失败: {e}")
            return self._create_fallback_analysis(user_query)

    def _build_analysis_prompt(self, user_query: str, context: Dict[str, Any]) -> str:
        """构建任务分析提示；若存在自主构思结果（想法+论文依据），一并纳入供任务分析与角色确定使用。"""
        ideation_block = ""
        ideation = context.get("ideation") or {}
        if ideation.get("ideas") or ideation.get("supporting_papers"):
            ideation_block = "\n**自主构思提供的参考（有文献支撑、逻辑可推理的想法与相关论文）：**\n"
            if ideation.get("ideas"):
                ideation_block += "想法摘要：\n"
                for i, idea in enumerate(ideation["ideas"][:8], 1):
                    content = idea.get("content", "")
                    refs = idea.get("supporting_paper_ids", [])
                    ideation_block += f"{i}. {content}\n   支撑：{refs}\n"
            if ideation.get("supporting_papers"):
                ideation_block += "\n检索到的论文（供确定领域与专家参考）：\n"
                for j, p in enumerate(ideation["supporting_papers"][:10], 1):
                    title = p.get("title", "")
                    year = p.get("year", "")
                    source = p.get("source", "")
                    ideation_block += f"  [{j}] {title} | {year} | {source}\n"
            ideation_block += "\n请结合上述想法与论文依据，进行任务分析与角色确定。\n"

        prompt = f"""{SCHOLAR_ROLE_PROMPT}

---
## 当前任务

**用户任务：**
{user_query}
{ideation_block}
请按照上述 Workflow 与 OutputFormat 完成分析，输出角色名称、职责说明、权重百分比及协作流程。**重要**：请列出本任务所需的**全部**关键专家领域，不设数量上限；系统将为你列出的**每一个**角色自动创建对应的领域专家与质疑者智能体，因此不得遗漏任何必要角色。为便于系统解析，请**在回答末尾**同时输出以下 JSON 结构（可直接被程序解析）：
{{
    "task_analysis": {{
        "core_problem": "核心问题描述",
        "complexity_level": "简单/中等/复杂",
        "estimated_time": "1周内/1-4周/1个月以上",
        "required_experts": [
            {{"domain": "领域名", "role_type": "Domain Expert", "reason": "理由", "priority": "高/中/低"}}
        ],
        "primary_domain": "主要领域",
        "secondary_domains": ["相关领域1", "相关领域2"],
        "risk_factors": ["风险1", "风险2"],
        "success_criteria": ["标准1", "标准2"]
    }}
}}
"""

        return prompt

    def _parse_analysis_response(self, response_text: str, user_query: str) -> Dict[str, Any]:
        """解析分析响应"""
        try:
            # 尝试提取JSON部分
            json_start = response_text.find('{')
            json_end = response_text.rfind('}')
            if json_start != -1 and json_end != -1:
                json_text = response_text[json_start:json_end+1]
                result = json.loads(json_text)

                # 验证必需字段
                if "task_analysis" not in result:
                    result["task_analysis"] = {
                        "core_problem": f"分析用户任务：{user_query}",
                        "complexity_level": "中等",
                        "required_experts": [],
                        "collaboration_mechanism": {},
                        "risk_factors": [],
                        "success_criteria": []
                    }

                return result

        except Exception as e:
            logger.warning(f"⚠️ 解析学者分析响应失败: {e}")

        # 返回后备结果
        return self._create_fallback_analysis(user_query)

    def _create_fallback_analysis(self, user_query: str) -> Dict[str, Any]:
        """创建后备分析结果"""
        return {
            "task_analysis": {
                "core_problem": f"分析用户任务：{user_query}",
                "complexity_level": "中等",
                "estimated_time": "2-4周",
                "required_experts": [
                    {
                        "domain": "数据分析",
                        "role_type": "Domain Expert",
                        "reason": "需要数据分析能力来处理用户信息",
                        "priority": "高"
                    },
                    {
                        "domain": "产品设计",
                        "role_type": "Domain Expert",
                        "reason": "需要产品视角来优化用户体验",
                        "priority": "中"
                    }
                ],
                "primary_domain": "综合分析",
                "secondary_domains": ["技术分析", "用户研究"],
                "risk_factors": ["分析不够全面", "专家意见分歧"],
                "success_criteria": ["问题分析清晰", "解决方案可行"]
            }
        }