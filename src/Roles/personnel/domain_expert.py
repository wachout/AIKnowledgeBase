# -*- coding: utf-8 -*-
"""
领域专家智能体
提供专业观点和技术方案
"""

import json
import logging
from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent, WorkingStyle

logger = logging.getLogger(__name__)


class DomainExpert(BaseAgent):
    """领域专家智能体：提供专业观点和技术方案"""

    def __init__(self,
                 domain: str,
                 expertise_area: str,
                 working_style: WorkingStyle = WorkingStyle.PROFESSIONAL_OBJECTIVE,
                 llm_instance=None):
        """
        初始化领域专家

        Args:
            domain: 专家领域
            expertise_area: 具体专长领域
            working_style: 工作风格
            llm_instance: LLM实例
        """

        # 根据领域确定专业技能
        professional_skills = self._get_skills_for_domain(domain, expertise_area)

        # 根据领域确定角色定义
        role_definition = f"{domain}领域专家，专注于{expertise_area}，提供专业技术方案和深入分析"

        # 根据领域确定行为准则
        behavior_guidelines = self._get_guidelines_for_domain(domain)

        # 根据领域确定输出格式
        output_format = self._get_output_format_for_domain(domain)

        super().__init__(
            name=f"{domain}专家",
            role_definition=role_definition,
            professional_skills=professional_skills,
            working_style=working_style,
            behavior_guidelines=behavior_guidelines,
            output_format=output_format,
            llm_instance=llm_instance
        )

        # 专家特有属性
        self.domain = domain
        self.expertise_area = expertise_area
        self.expertise_score = 0.0  # 专业性评分
        self.collaboration_score = 0.0  # 协作评分

    @classmethod
    def create_from_config(cls, config: Dict[str, Any], llm_instance=None) -> 'DomainExpert':
        """
        从 roles 保存的配置重建领域专家（重启任务时使用）
        """
        domain = config.get('domain', '通用')
        expertise_area = config.get('expertise_area', domain)
        target = config.get('target_expert', {})
        if isinstance(target, dict) and target.get('expertise_area'):
            expertise_area = target['expertise_area']
        ws = config.get('working_style', '专业客观')
        if isinstance(ws, str):
            style_map = {'专业客观': WorkingStyle.PROFESSIONAL_OBJECTIVE, '激进创新': WorkingStyle.AGGRESSIVE_INNOVATIVE,
                         '稳健保守': WorkingStyle.STEADY_CONSERVATIVE, '合作共赢': WorkingStyle.COLLABORATIVE_WINWIN,
                         '结果导向': WorkingStyle.RESULT_ORIENTED}
            working_style = style_map.get(ws, WorkingStyle.PROFESSIONAL_OBJECTIVE)
        else:
            working_style = WorkingStyle.PROFESSIONAL_OBJECTIVE
        return cls(domain=domain, expertise_area=expertise_area, working_style=working_style, llm_instance=llm_instance)

    @classmethod
    def create_from_analysis(cls, expert_analysis: Dict[str, Any], llm_instance=None) -> 'DomainExpert':
        """
        根据学者分析结果创建领域专家

        Args:
            expert_analysis: 学者分析结果中的专家信息
            llm_instance: LLM实例

        Returns:
            创建的领域专家实例
        """
        domain = expert_analysis.get('domain', '通用')
        expertise_area = expert_analysis.get('expertise_area', domain)

        # 根据优先级确定工作风格
        priority = expert_analysis.get('priority', '中')
        working_style = cls._get_style_from_priority(priority)

        return cls(
            domain=domain,
            expertise_area=expertise_area,
            working_style=working_style,
            llm_instance=llm_instance
        )

    @staticmethod
    def _get_style_from_priority(priority: str) -> WorkingStyle:
        """根据优先级确定工作风格"""
        style_map = {
            '高': WorkingStyle.PROFESSIONAL_OBJECTIVE,
            '中': WorkingStyle.COLLABORATIVE_WINWIN,
            '低': WorkingStyle.STEADY_CONSERVATIVE
        }
        return style_map.get(priority, WorkingStyle.PROFESSIONAL_OBJECTIVE)

    @staticmethod
    def _get_skills_for_domain(domain: str, expertise_area: str) -> List[str]:
        """根据领域获取专业技能"""
        skill_map = {
            '数据科学': [
                '机器学习算法',
                '统计建模',
                '数据可视化',
                '特征工程',
                '模型评估'
            ],
            '软件工程': [
                '系统架构设计',
                'API设计开发',
                '性能优化',
                '代码重构',
                '技术选型'
            ],
            '产品设计': [
                '用户研究',
                '产品策略',
                '交互设计',
                '用户体验优化',
                '需求分析'
            ],
            '安全专家': [
                '网络安全',
                '数据隐私保护',
                '风险评估',
                '安全架构设计',
                '合规性检查'
            ],
            '业务分析': [
                '流程优化',
                '需求分析',
                '数据分析',
                '商业智能',
                'KPI设计'
            ],
            '市场分析': [
                '市场趋势分析',
                '竞争分析',
                '用户行为研究',
                '市场定位策略',
                '营销策略'
            ],
            '项目管理': [
                '项目规划',
                '风险管理',
                '资源分配',
                '进度控制',
                '团队协调'
            ],
            '法律专家': [
                '合同审查',
                '知识产权保护',
                '合规性分析',
                '法律风险评估',
                '隐私政策制定'
            ]
        }

        # 返回对应领域的技能，如果没有找到则返回通用技能
        return skill_map.get(domain, [
            f'{domain}专业知识',
            f'{expertise_area}技能',
            '问题分析',
            '解决方案设计',
            '风险评估'
        ])

    @staticmethod
    def _get_guidelines_for_domain(domain: str) -> List[str]:
        """根据领域获取行为准则"""
        guideline_map = {
            '数据科学': [
                '基于数据和证据进行分析',
                '使用适当的统计方法',
                '确保模型的可解释性',
                '考虑数据质量和偏差',
                '提供可复现的结果'
            ],
            '软件工程': [
                '遵循软件工程最佳实践',
                '考虑系统可扩展性和维护性',
                '注重代码质量和测试覆盖',
                '评估技术风险和依赖',
                '提供清晰的技术文档'
            ],
            '产品设计': [
                '以用户为中心的设计理念',
                '考虑用户体验和可用性',
                '平衡技术和业务需求',
                '进行用户研究和验证',
                '关注产品的市场竞争力和独特性'
            ],
            '安全专家': [
                '采用防御性安全策略',
                '考虑多层次安全防护',
                '评估隐私和合规风险',
                '保持对最新威胁的关注',
                '提供可操作的安全建议'
            ]
        }

        # 返回对应领域的准则，如果没有找到则返回通用准则
        return guideline_map.get(domain, [
            '保持专业性和客观性',
            '基于领域知识提供建议',
            '考虑实际可行性和约束',
            '与其他专家积极协作',
            '提供建设性意见和建议'
        ])

    @staticmethod
    def _get_output_format_for_domain(domain: str) -> str:
        """根据领域获取输出格式"""
        format_map = {
            '数据科学': """
**数据分析结果：**

**关键指标：**
- [指标1]: [数值] ([解读])
- [指标2]: [数值] ([解读])

**模型建议：**
[推荐的算法或模型]

**数据洞察：**
[从数据中发现的规律]

**技术建议：**
[实现建议和技术方案]
""",
            '软件工程': """
**技术方案分析：**

**架构建议：**
[系统架构设计方案]

**技术栈选择：**
[推荐的技术栈和工具]

**实现计划：**
[分阶段的实现计划]

**风险评估：**
[技术风险和应对策略]
""",
            '产品设计': """
**产品设计方案：**

**用户需求分析：**
[用户痛点和需求识别]

**功能设计：**
[核心功能和特性设计]

**用户体验优化：**
[交互流程和界面优化]

**验证计划：**
[用户测试和验证计划]
"""
        }

        # 返回对应领域的格式，如果没有找到则返回通用格式
        return format_map.get(domain, """
**专业分析结果：**

**核心观点：**
[主要观点和立场]

**详细分析：**
[深入的专业分析]

**建议方案：**
[具体可行的建议]

**风险考虑：**
[潜在风险和应对措施]
""")

    def provide_expertise(self, topic: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        提供专业意见

        Args:
            topic: 讨论主题
            context: 讨论上下文

        Returns:
            专业意见结果
        """
        expertise_prompt = self._build_expertise_prompt(topic, context)

        try:
            response = self.llm.invoke(expertise_prompt)
            response_text = self._extract_response_content(response)

            expertise_result = self._parse_expertise_response(response_text)

            # 更新专业性评分
            self.expertise_score += 0.1

            return expertise_result

        except Exception as e:
            logger.error(f"❌ {self.name} 提供专业意见失败: {e}")
            return self._create_fallback_expertise(topic, context)

    def _build_expertise_prompt(self, topic: str, context: Dict[str, Any]) -> str:
        """构建专业意见提示"""
        prompt = f"""你是一位{self.domain}领域的{self.expertise_area}专家。请基于你的专业知识提供深入分析和建议。

**讨论主题：**
{topic}

**当前上下文：**
{json.dumps(context, ensure_ascii=False, indent=2)}

**你的专业背景：**
领域：{self.domain}
专长：{self.expertise_area}
工作风格：{self.working_style.value}

**专业技能：**
{chr(10).join(f"- {skill}" for skill in self.professional_skills)}

**分析要求：**

### 1. 专业视角分析
基于你的{self.domain}专业背景，分析该主题的核心问题。

### 2. 技术深度
提供技术层面的深入见解和分析。

### 3. 实际可行性
考虑实际约束和技术可行性。

### 4. 创新建议
提出创新性的解决方案或思路。

### 5. 风险评估
识别潜在的技术风险和挑战。

{self.output_format}

请提供专业、深入、有价值的分析和建议。"""

        return prompt

    def _parse_expertise_response(self, response_text: str) -> Dict[str, Any]:
        """解析专业意见响应"""
        return {
            'expert_name': self.name,
            'domain': self.domain,
            'expertise_area': self.expertise_area,
            'content': response_text,
            'timestamp': self._get_timestamp(),
            'working_style': self.working_style.value
        }

    def _create_fallback_expertise(self, topic: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """创建后备专业意见"""
        return {
            'expert_name': self.name,
            'domain': self.domain,
            'expertise_area': self.expertise_area,
            'content': f"基于{self.domain}专业知识，我认为{topic}需要进一步的技术分析和方案设计。",
            'timestamp': self._get_timestamp(),
            'working_style': self.working_style.value
        }

    def evaluate_collaboration(self, other_experts_opinions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        评估与其他专家的协作

        Args:
            other_experts_opinions: 其他专家的意见

        Returns:
            协作评估结果
        """
        # 简单的协作评分逻辑
        collaboration_score = 0.5  # 基础分数

        # 根据意见数量和互动情况调整评分
        if len(other_experts_opinions) > 0:
            collaboration_score += 0.1

        self.collaboration_score = collaboration_score

        return {
            'collaboration_score': collaboration_score,
            'feedback_count': len(other_experts_opinions),
            'assessment': '积极参与协作讨论' if collaboration_score > 0.6 else '正常参与讨论'
        }

    def _handle_response_message(self, message):
        """处理回应消息（通常是质疑者的回应）"""
        try:
            response_content = message.content.get('response_content', '')
            sender = message.sender

            logger.info(f"{self.name} 收到来自 {sender} 的回应消息")

            # 如果是质疑者的回应，进行回应评估
            if sender.startswith('skeptic_'):
                evaluation = self.evaluate_skeptic_response(
                    skeptic_response={"content": response_content, "sender": sender},
                    original_opinion={"content": "需要从消息历史中获取", "speaker": self.name}
                )

                logger.info(f"{self.name} 评估质疑者回应完成: {evaluation.get('evaluation', 'N/A')}")

        except Exception as e:
            logger.error(f"{self.name} 处理回应消息失败: {e}")

    def revise_speech_after_skeptic(
        self,
        current_speech: str,
        skeptic_challenge: str,
        context: Dict[str, Any],
        revision_round: int = 1,
    ) -> Dict[str, Any]:
        """
        根据质疑者的言论完善修改自己的发言（质疑→修订循环中由专家调用）。
        
        Args:
            current_speech: 当前版本发言内容（初次为初始发言，后续为上一轮修订稿）
            skeptic_challenge: 质疑者本轮提出的质疑/建议
            context: 讨论上下文
            revision_round: 第几轮修订（1 或 2）
            
        Returns:
            与 speak() 同结构的发言结果字典（content 为修订后的完整发言）
        """
        prompt = f"""你是{self.role_definition}，具备以下专业技能：
{chr(10).join(f"- {s}" for s in self.professional_skills)}

**你当前的发言内容：**
{current_speech}

**质疑者对你提出的质疑/建议（请认真对待并据此完善）：**
{skeptic_challenge}

**任务：** 请根据质疑者的意见，对上述发言进行完善和修改。要求：
1. 保留你仍坚持的合理观点，对质疑中合理的部分进行补充、修正或澄清。
2. 对质疑中的误解予以简要澄清，对建设性建议予以吸纳。
3. 输出为一份完整、连贯的修订后发言（不要只写修改片段），可直接作为你在本轮讨论中的正式发言。
4. 保持专业、客观，篇幅适中。

请直接输出修订后的完整发言内容，不要加「修订版」「回应如下」等前缀。"""

        try:
            response = self.llm.invoke(prompt)
            revised_text = self._extract_response_content(response)
            if not revised_text or not revised_text.strip():
                revised_text = current_speech
            return {
                "agent_name": self.name,
                "role": self.role_definition,
                "content": revised_text.strip(),
                "timestamp": self._get_timestamp(),
                "working_style": self.working_style.value,
                "professional_skills": self.professional_skills,
                "success": True,
                "is_revision": True,
                "revision_round": revision_round,
            }
        except Exception as e:
            logger.warning(f"{self.name} 根据质疑修订发言失败 (第{revision_round}轮): {e}")
            return {
                "agent_name": self.name,
                "role": self.role_definition,
                "content": current_speech,
                "timestamp": self._get_timestamp(),
                "working_style": self.working_style.value,
                "professional_skills": self.professional_skills,
                "success": False,
                "is_revision": True,
                "revision_round": revision_round,
                "error": str(e),
            }

    def evaluate_skeptic_response(self, skeptic_response: Dict[str, Any], original_opinion: Dict[str, Any]) -> Dict[str, Any]:
        """评估质疑者的回应"""
        evaluation_prompt = f"""请评估质疑者对您观点的质疑质量和建设性。

**您的原始观点：**
{original_opinion.get('content', '')}

**质疑者的回应：**
{skeptic_response.get('content', '')}

请从以下方面进行评估：
1. 质疑是否基于事实和逻辑？
2. 是否提出了建设性的改进建议？
3. 是否显示出对{self.domain}领域的理解？
4. 是否有助于完善技术方案？

请给出综合评估。"""

        try:
            response = self.llm.invoke(evaluation_prompt)
            evaluation_text = self._extract_response_content(response)

            return {
                'evaluation': evaluation_text,
                'skeptic_name': skeptic_response.get('sender', ''),
                'original_expert': self.name,
                'evaluation_quality': 'good'  # 可以进一步分析
            }

        except Exception as e:
            logger.error(f"{self.name} 评估质疑者回应失败: {e}")
            return {
                'evaluation': '评估过程出错，请人工判断质疑质量',
                'skeptic_name': skeptic_response.get('sender', ''),
                'original_expert': self.name,
                'evaluation_quality': 'error'
            }

    def _handle_direct_discussion_message(self, message):
        """处理直接讨论消息"""
        try:
            discussion_type = message.content.get('discussion_type', 'general')
            discussion_content = message.content.get('discussion_content', '')
            sender = message.sender

            logger.info(f"{self.name} 收到来自 {sender} 的直接讨论消息 (类型: {discussion_type})")

            # 根据讨论类型生成回应
            if discussion_type == 'response':
                # 这是对其他专家观点的回应
                response = self._generate_discussion_response(discussion_content, sender)
            elif discussion_type == 'clarification':
                # 这是澄清请求
                response = self._generate_clarification_response(discussion_content, sender)
            elif discussion_type == 'debate':
                # 这是辩论观点
                response = self._generate_debate_response(discussion_content, sender)
            else:
                # 一般性讨论
                response = self._generate_general_discussion_response(discussion_content, sender)

            # 如果有回应内容，通过通信协议发送回应
            if response and self.communication_protocol and self.message_bus:
                response_message = self.communication_protocol.create_direct_discussion_message(
                    sender=self.name,
                    receiver=sender,  # 回应给发送者
                    discussion_content=response,
                    discussion_type="response",
                    round_number=message.round_number or 1,
                    conversation_id=message.conversation_id
                )

                self.message_bus.send_message(response_message)
                logger.info(f"{self.name} 发送讨论回应给 {sender}")

        except Exception as e:
            logger.error(f"{self.name} 处理直接讨论消息失败: {e}")

    def _generate_discussion_response(self, original_content: str, sender: str) -> str:
        """生成对其他专家观点的回应"""
        try:
            prompt = f"""作为{self.role_definition}，请对{self.domain}领域的同事{sender}的观点进行回应：

{sender}的观点：
{original_content}

请从您的专业角度：
1. 表达您对这个观点的理解
2. 指出您同意或不同意的部分，并解释原因
3. 分享您的相关经验或见解
4. 提出建设性的建议

请保持专业、尊重和建设性的态度。"""

            response = self.llm.invoke(prompt)
            return self._extract_response_content(response)

        except Exception as e:
            logger.error(f"生成讨论回应失败: {str(e)}")
            return f"感谢{sender}分享的观点。我会认真考虑这些建议，并在后续讨论中继续交流。"

    def _generate_clarification_response(self, clarification_request: str, sender: str) -> str:
        """生成澄清回应"""
        try:
            prompt = f"""作为{self.role_definition}，请澄清您对以下问题的观点：

{sender}的问题/澄清请求：
{clarification_request}

请提供清晰、具体的解释，帮助{sender}更好地理解您的观点。"""

            response = self.llm.invoke(prompt)
            return self._extract_response_content(response)

        except Exception as e:
            logger.error(f"生成澄清回应失败: {str(e)}")
            return f"感谢{sender}的提问。我的观点是基于{self.domain}领域的最佳实践，希望这个澄清能帮助您更好地理解。"

    def _generate_debate_response(self, debate_point: str, sender: str) -> str:
        """生成辩论回应"""
        try:
            prompt = f"""作为{self.role_definition}，请对{sender}的辩论观点进行回应：

{sender}的辩论观点：
{debate_point}

请：
1. 客观分析对方观点的合理性
2. 基于事实和专业知识提出您的反驳或补充
3. 寻求可能的共识点
4. 保持建设性和专业性

辩论目的是为了找到更好的解决方案。"""

            response = self.llm.invoke(prompt)
            return self._extract_response_content(response)

        except Exception as e:
            logger.error(f"生成辩论回应失败: {str(e)}")
            return f"感谢{sender}提出的不同观点。这种辩论有助于我们更全面地考虑问题。我会重新审视这个观点。"

    def _generate_general_discussion_response(self, discussion_content: str, sender: str) -> str:
        """生成一般性讨论回应"""
        try:
            prompt = f"""作为{self.role_definition}，请参与关于以下内容的讨论：

讨论内容：
{discussion_content}

请分享您的专业观点和建议。"""

            response = self.llm.invoke(prompt)
            return self._extract_response_content(response)

        except Exception as e:
            logger.error(f"生成一般讨论回应失败: {str(e)}")
            return f"感谢大家的分享。我会继续关注这个讨论，并贡献我的专业观点。"
    
    # =========================================================================
    # 专家主动交互能力 - 支持专家间直接对话
    # =========================================================================
    
    def request_clarification(self, target_expert: str, question: str, 
                             context: str = "", round_number: int = 0) -> Optional[str]:
        """
        向其他专家请求澄清
        
        Args:
            target_expert: 目标专家名称
            question: 澄清问题
            context: 问题上下文
            round_number: 所属轮次
            
        Returns:
            消息 ID 或 None
        """
        content = {
            "clarification_topic": question,
            "specific_questions": [question],
            "context": context or f"关于 {self.domain} 领域的问题",
            "requester_domain": self.domain,
            "requester_expertise": self.expertise_area
        }
        
        return self.initiate_interaction(
            target=target_expert,
            interaction_type="clarification",
            content=content,
            round_number=round_number
        )
    
    def challenge_viewpoint(self, target_expert: str, claim: str, 
                           counter_argument: str, evidence: str = "",
                           round_number: int = 0) -> Optional[str]:
        """
        挑战其他专家的观点
        
        Args:
            target_expert: 目标专家名称
            claim: 被质疑的观点
            counter_argument: 反驳论点
            evidence: 支持证据
            round_number: 所属轮次
            
        Returns:
            消息 ID 或 None
        """
        content = {
            "target_expert": target_expert,
            "questioning_content": counter_argument,
            "questioning_type": "viewpoint_challenge",
            "target_claim": claim,
            "evidence": evidence,
            "challenger_domain": self.domain
        }
        
        return self.initiate_interaction(
            target=target_expert,
            interaction_type="challenge",
            content=content,
            round_number=round_number
        )
    
    def propose_collaboration(self, target_experts: List[str], proposal: str,
                             collaboration_goal: str = "", 
                             round_number: int = 0) -> List[Optional[str]]:
        """
        向其他专家提议协作
        
        Args:
            target_experts: 目标专家列表
            proposal: 协作提案
            collaboration_goal: 协作目标
            round_number: 所属轮次
            
        Returns:
            消息 ID 列表
        """
        results = []
        
        for target in target_experts:
            content = {
                "proposal_content": proposal,
                "collaboration_goal": collaboration_goal or f"共同解决 {self.domain} 相关问题",
                "expected_contribution": f"结合 {self.expertise_area} 与 {target} 的专业知识",
                "proposer_domain": self.domain,
                "proposer_expertise": self.expertise_area
            }
            
            message_id = self.initiate_interaction(
                target=target,
                interaction_type="collaboration",
                content=content,
                round_number=round_number
            )
            results.append(message_id)
        
        return results
    
    def respond_to_open_question(self, question_content: str, question_id: str = "",
                                perspective_type: str = "expert",
                                round_number: int = 0) -> Dict[str, Any]:
        """
        回应开放问题
        
        Args:
            question_content: 问题内容
            question_id: 问题 ID
            perspective_type: 观点类型
            round_number: 所属轮次
            
        Returns:
            回应结果
        """
        try:
            # 使用 LLM 生成回应
            prompt = f"""作为{self.role_definition}，请回应以下开放性问题：

问题：{question_content}

请从{self.domain}领域的角度提供专业观点，包括：
1. 主要观点
2. 支持证据或理由
3. 可能的局限性或注意事项
4. 后续建议"""
            
            response = self.llm.invoke(prompt)
            response_content = self._extract_response_content(response)
            
            return {
                "success": True,
                "question_id": question_id,
                "responder": self.name,
                "responder_domain": self.domain,
                "response_content": response_content,
                "perspective_type": perspective_type,
                "confidence": "high",
                "round_number": round_number
            }
            
        except Exception as e:
            logger.error(f"{self.name} 回应开放问题失败: {e}")
            return {
                "success": False,
                "question_id": question_id,
                "responder": self.name,
                "error": str(e)
            }
    
    def initiate_debate(self, target_expert: str, debate_topic: str,
                       initial_position: str, supporting_evidence: List[str] = None,
                       round_number: int = 0) -> Optional[str]:
        """
        发起与其他专家的辩论
        
        Args:
            target_expert: 目标专家
            debate_topic: 辩论主题
            initial_position: 初始立场
            supporting_evidence: 支持证据列表
            round_number: 所属轮次
            
        Returns:
            消息 ID 或 None
        """
        content = {
            "debate_position": initial_position,
            "supporting_evidence": supporting_evidence or [],
            "target_claim": debate_topic,
            "debate_initiator": self.name,
            "debate_domain": self.domain
        }
        
        return self.initiate_interaction(
            target=target_expert,
            interaction_type="debate",
            content=content,
            round_number=round_number
        )
    
    def express_support(self, target_expert: str, supported_viewpoint: str,
                       additional_insights: str = "",
                       round_number: int = 0) -> Optional[str]:
        """
        表达对其他专家观点的支持
        
        Args:
            target_expert: 目标专家
            supported_viewpoint: 支持的观点
            additional_insights: 额外的见解
            round_number: 所属轮次
            
        Returns:
            消息 ID 或 None
        """
        content = {
            "response_content": f"我支持 {target_expert} 的观点: {supported_viewpoint}. {additional_insights}",
            "response_type": "support",
            "addresses_points": [supported_viewpoint],
            "supporter_domain": self.domain,
            "confidence_level": "high"
        }
        
        return self.initiate_interaction(
            target=target_expert,
            interaction_type="support",
            content=content,
            round_number=round_number
        )