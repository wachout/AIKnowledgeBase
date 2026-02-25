# -*- coding: utf-8 -*-
"""
质疑者智能体
提出反面意见和风险识别
"""

import json
import logging
from typing import Dict, Any, List
from .base_agent import BaseAgent, WorkingStyle

logger = logging.getLogger(__name__)


class Skeptic(BaseAgent):
    """质疑者智能体：提出反面意见和风险识别"""

    def __init__(self, target_expert: 'DomainExpert', llm_instance=None):
        """
        初始化质疑者

        Args:
            target_expert: 对应的领域专家
            llm_instance: LLM实例
        """
        self.target_expert = target_expert

        super().__init__(
            name=f"{target_expert.name}质疑者",
            role_definition=f"{target_expert.domain}领域质疑者，专门对{target_expert.name}的观点进行批判性分析和风险识别",
            professional_skills=[
                "批判性思维",
                "风险识别",
                "逻辑推理",
                "证据评估",
                "替代方案生成",
                f"{target_expert.domain}领域知识"
            ],
            working_style=WorkingStyle.AGGRESSIVE_INNOVATIVE,  # 质疑者通常更激进
            behavior_guidelines=[
                "保持建设性批评态度",
                "基于证据提出质疑",
                "识别潜在风险和盲点",
                "提供替代观点和解决方案",
                "促进深入讨论和思考",
                "避免个人攻击，聚焦问题本身"
            ],
            output_format="""
**质疑分析结果：**

**质疑点识别：**
1. [质疑点1] - [具体理由]
2. [质疑点2] - [具体理由]

**风险评估：**
- **技术风险**: [技术层面的潜在问题]
- **实施风险**: [实施过程中的挑战]
- **业务风险**: [对业务目标的影响]

**替代方案建议：**
1. [方案1]: [详细描述]
2. [方案2]: [详细描述]

**改进建议：**
[对原方案的具体改进建议]

**进一步验证建议：**
[需要进一步验证或研究的方面]
""",
            llm_instance=llm_instance
        )

        # 质疑者特有属性
        self.questioning_score = 0.0  # 质疑质量评分
        self.construction_score = 0.0  # 建设性评分

    @classmethod
    def create_from_config(cls, config: Dict[str, Any], target_expert: 'DomainExpert', llm_instance=None) -> 'Skeptic':
        """
        从 roles 保存的配置重建质疑者（重启任务时，需先加载对应的领域专家）
        """
        return cls(target_expert=target_expert, llm_instance=llm_instance)

    @classmethod
    def create_for_expert(cls, expert: 'DomainExpert', llm_instance=None) -> 'Skeptic':
        """
        为领域专家创建对应的质疑者

        Args:
            expert: 领域专家实例
            llm_instance: LLM实例

        Returns:
            创建的质疑者实例
        """
        return cls(target_expert=expert, llm_instance=llm_instance)

    def question_expert(self, expert_opinion: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        对专家意见进行质疑

        Args:
            expert_opinion: 专家的意见
            context: 讨论上下文

        Returns:
            质疑结果
        """
        question_prompt = self._build_question_prompt(expert_opinion, context)

        try:
            response = self.llm.invoke(question_prompt)
            response_text = self._extract_response_content(response)

            question_result = self._parse_question_response(response_text)

            # 更新质疑评分
            self.questioning_score += 0.1
            self.construction_score += 0.05

            return question_result

        except Exception as e:
            logger.error(f"❌ {self.name} 质疑失败: {e}")
            return self._create_fallback_question(expert_opinion)

    def _build_question_prompt(self, expert_opinion: Dict[str, Any], context: Dict[str, Any]) -> str:
        """构建质疑提示（质疑偏向具像化、计划与实施，避免停留在虚理论）"""
        prompt = f"""你是一位{self.target_expert.domain}领域的质疑者，专门对{self.target_expert.name}的观点进行批判性分析。

**重要原则：你的质疑必须偏向「具像化的计划与实施」，不要停留在虚理论。** 多问「怎么落地、谁来做、何时验收、产出是什么」，少问抽象概念。

**目标专家信息：**
- 姓名：{self.target_expert.name}
- 领域：{self.target_expert.domain}
- 专长：{self.target_expert.expertise_area}
- 工作风格：{self.target_expert.working_style.value}

**专家观点：**
{expert_opinion.get('content', '')}

**讨论上下文：**
{json.dumps(context, ensure_ascii=False, indent=2)}

**质疑任务（优先具像化与可执行性）：**

### 1. 具像化与可执行性（必问）
- 观点如何转化为具体步骤或计划？缺少哪些可执行动作？
- 谁负责、何时完成、交付物或验收标准是什么？
- 是否有时间线、里程碑、可量化的指标？

### 2. 实施与落地
- 技术/业务方案在实施上有无缺失？资源、依赖、约束是否说清？
- 实施难度和成本是否被低估？有无替代的更易落地方案？

### 3. 逻辑与证据（在具像化前提下可问）
- 推理与前提是否支撑「可落地」的结论？证据是否足以支撑实施决策？

### 4. 风险与验证
- 落地过程中有哪些具体风险？如何验证每一步是否达标？

**请避免**：只讨论抽象概念、纯理论或空泛的「应该加强」「需要重视」；**务必**把质疑落在具体计划、步骤、责任与验收上。

{self.output_format}

请保持专业、建设性的质疑态度，旨在把讨论推向可执行的方案优化。"""

        return prompt

    def _parse_question_response(self, response_text: str) -> Dict[str, Any]:
        """解析质疑响应"""
        return {
            'skeptic_name': self.name,
            'target_expert': self.target_expert.name,
            'content': response_text,
            'timestamp': self._get_timestamp(),
            'questioning_type': 'constructive_criticism'
        }

    def _create_fallback_question(self, expert_opinion: Dict[str, Any]) -> Dict[str, Any]:
        """创建后备质疑"""
        return {
            'skeptic_name': self.name,
            'target_expert': self.target_expert.name,
            'content': f"我注意到{self.target_expert.name}的观点值得进一步验证和讨论。建议考虑更多数据支持和风险评估。",
            'timestamp': self._get_timestamp(),
            'questioning_type': 'general_questioning'
        }

    def evaluate_expert_response(self, expert_response: Dict[str, Any],
                                original_questioning: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估专家对质疑的回应

        Args:
            expert_response: 专家的回应
            original_questioning: 原始质疑

        Returns:
            评估结果
        """
        evaluation_prompt = f"""请评估专家对质疑的回应质量。

**原始质疑：**
{original_questioning.get('content', '')}

**专家回应：**
{expert_response.get('content', '')}

请从以下方面评估：
1. 回应是否充分解决了质疑点？
2. 是否提供了新的证据或解释？
3. 观点是否有调整或改进？
4. 是否显示出开放和协作的态度？

请给出综合评估。"""

        try:
            response = self.llm.invoke(evaluation_prompt)
            evaluation_text = self._extract_response_content(response)

            return {
                'evaluation': evaluation_text,
                'response_quality': 'good',  # 可以根据内容分析质量
                'collaboration_level': 'high'  # 协作程度评估
            }

        except Exception as e:
            logger.error(f"❌ 质疑者评估专家回应失败: {e}")
            return {
                'evaluation': '评估过程出错，请人工判断回应质量',
                'response_quality': 'unknown',
                'collaboration_level': 'unknown'
            }

    def generate_alternative_solution(self, original_problem: str,
                                    expert_solution: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成替代解决方案

        Args:
            original_problem: 原始问题
            expert_solution: 专家的解决方案

        Returns:
            替代解决方案
        """
        alternative_prompt = f"""基于对{self.target_expert.name}解决方案的质疑，请提出替代方案。

**原始问题：**
{original_problem}

**专家解决方案：**
{expert_solution.get('content', '')}

请提出1-2个替代性的解决方案，并说明其优缺点。"""

        try:
            response = self.llm.invoke(alternative_prompt)
            alternative_text = self._extract_response_content(response)

            return {
                'alternative_solutions': alternative_text,
                'generated_by': self.name,
                'target_domain': self.target_expert.domain
            }

        except Exception as e:
            logger.error(f"❌ 质疑者生成替代方案失败: {e}")
            return {
                'alternative_solutions': f'建议进一步研究{self.target_expert.domain}领域的替代方案',
                'generated_by': self.name,
                'target_domain': self.target_expert.domain
            }

    def _handle_questioning_message(self, message):
        """处理质疑消息"""
        try:
            questioning_content = message.content.get('questioning_content', '')
            target_expert = message.content.get('target_expert', '')

            logger.info(f"{self.name} 收到质疑消息，目标专家: {target_expert}")

            # 如果是质疑自己的专家，进行质疑分析
            if target_expert == self.target_expert.name:
                # 生成质疑回应
                response = self.question_expert(
                    expert_opinion={
                        "content": questioning_content,
                        "speaker": target_expert
                    },
                    context={"round_number": message.round_number or 1}
                )

                # 创建回应消息
                if self.communication_protocol and self.message_bus:
                    response_message = self.communication_protocol.create_response_message(
                        sender=self.name,
                        receiver=target_expert,
                        response_content=response.get('content', ''),
                        parent_message_id=message.message_id,
                        round_number=message.round_number or 1,
                        conversation_id=message.conversation_id
                    )

                    # 发送回应消息
                    self.message_bus.send_message(response_message)
                    logger.info(f"{self.name} 发送质疑回应给 {target_expert}")

        except Exception as e:
            logger.error(f"{self.name} 处理质疑消息失败: {e}")