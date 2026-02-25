"""
协调者智能体 - Facilitator Agent
负责促进和谐讨论、沟通协调、冲突解决，确保协作氛围和参与度。
"""

import logging
from typing import Dict, Any, List
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class Facilitator(BaseAgent):
    """
    协调者智能体
    主要职责：
    - 促进和谐讨论
    - 沟通协调和冲突解决
    - 确保协作氛围和参与度
    - 协调发言顺序和讨论流程
    """

    def __init__(self, llm_instance=None):
        from .base_agent import WorkingStyle
        super().__init__(
            name="协调者",
            role_definition="讨论协调与冲突化解专家",
            professional_skills=[
                "沟通协调",
                "冲突解决",
                "会议主持",
                "情绪管理",
                "参与度评估",
                "群体动力学"
            ],
            working_style=WorkingStyle.COLLABORATIVE_WINWIN,
            behavior_guidelines=[
                "始终保持中立客观的态度",
                "积极倾听各方观点",
                "及时识别和化解冲突",
                "鼓励沉默成员参与",
                "维护积极的讨论氛围",
                "确保讨论有序进行"
            ],
            output_format="""
请以以下格式输出：
## 协调总结
[当前讨论轮次的总结]

## 发言安排
[下一轮的发言顺序建议]

## 冲突化解
[如果有冲突，提供化解建议]

## 参与评估
[各成员参与度评估]
            """,
            llm_instance=llm_instance
        )

    def coordinate_round(self, discussion_context: Dict[str, Any],
                        previous_speeches: List[Dict[str, Any]],
                        consensus_points: List[str],
                        divergence_points: List[str]) -> Dict[str, Any]:
        """
        协调一轮讨论发言

        Args:
            discussion_context: 讨论上下文
            previous_speeches: 上一轮发言内容
            consensus_points: 共识点
            divergence_points: 分歧点

        Returns:
            协调结果，包含发言顺序、冲突化解建议等
        """
        coordination_prompt = f"""
你作为协调者，需要为这一轮讨论做出协调安排。

## 讨论主题
{discussion_context.get('topic', '未指定')}

## 上一轮发言总结
{self._summarize_previous_round(previous_speeches)}

## 当前共识点
{chr(10).join(f"- {point}" for point in consensus_points)}

## 当前分歧点
{chr(10).join(f"- {point}" for point in divergence_points)}

## 你的任务
1. 评估当前讨论氛围和参与度
2. 识别潜在冲突或紧张关系
3. 安排下一轮的合理发言顺序
4. 提出冲突化解建议（如需要）
5. 确保所有重要观点都能被充分讨论

请提供具体的协调方案，包括：
- 发言顺序建议
- 重点关注的问题
- 冲突化解措施
- 参与度提升建议
        """

        response = self.llm.invoke(coordination_prompt)
        response_text = self._extract_response_content(response)

        coordination_result = self._parse_structured_response(response_text, "coordination_plan")

        return {
            "coordinator": self.name,
            "coordination_result": coordination_result,
            "timestamp": self._get_timestamp()
        }

    def resolve_conflict(self, conflict_description: str,
                        involved_parties: List[str],
                        discussion_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        化解讨论中的冲突

        Args:
            conflict_description: 冲突描述
            involved_parties: 涉及的各方
            discussion_context: 讨论上下文

        Returns:
            冲突化解方案
        """
        conflict_prompt = f"""
你作为协调者，需要化解讨论中的冲突。

## 冲突描述
{conflict_description}

## 涉及各方
{chr(10).join(f"- {party}" for party in involved_parties)}

## 讨论上下文
{discussion_context.get('topic', '未指定')}

## 你的任务
请提供冲突化解方案，包括：
1. 冲突根源分析
2. 各方立场理解
3. 化解策略建议
4. 调解步骤
5. 预防措施

保持中立客观，积极促进各方达成共识。
        """

        response = self.llm.invoke(conflict_prompt)
        response_text = self._extract_response_content(response)

        resolution = self._parse_structured_response(response_text, "resolution_plan")

        return {
            "mediator": self.name,
            "conflict_resolution": resolution,
            "timestamp": self._get_timestamp()
        }

    def assess_participation(self, all_speeches: List[Dict[str, Any]],
                           participants: List[str]) -> Dict[str, Any]:
        """
        评估各参与者的参与度

        Args:
            all_speeches: 所有发言记录
            participants: 参与者列表

        Returns:
            参与度评估结果
        """
        participation_prompt = f"""
你作为协调者，需要评估各参与者的讨论参与度。

## 参与者列表
{chr(10).join(f"- {participant}" for participant in participants)}

## 发言统计
{self._analyze_participation_stats(all_speeches, participants)}

## 你的任务
请评估每个参与者的参与度，包括：
1. 发言频率和质量
2. 倾听和回应情况
3. 建设性贡献程度
4. 协作精神表现
5. 建议提升措施

请给出客观公正的评估。
        """

        response = self.llm.invoke(participation_prompt)
        response_text = self._extract_response_content(response)

        assessment = self._parse_structured_response(response_text, "assessment_report")

        return {
            "assessor": self.name,
            "participation_assessment": assessment,
            "timestamp": self._get_timestamp()
        }

    def _summarize_previous_round(self, previous_speeches: List[Dict[str, Any]]) -> str:
        """总结上一轮发言"""
        if not previous_speeches:
            return "这是第一轮讨论，还没有之前的发言记录。"

        summary_parts = []
        for speech in previous_speeches[-5:]:  # 只总结最近5条发言
            speaker = speech.get('speaker', '未知')
            content_preview = speech.get('content', '')[:200] + "..." if len(speech.get('content', '')) > 200 else speech.get('content', '')
            summary_parts.append(f"{speaker}: {content_preview}")

        return chr(10).join(summary_parts)

    def _analyze_participation_stats(self, all_speeches: List[Dict[str, Any]],
                                   participants: List[str]) -> str:
        """分析参与统计"""
        stats = {}
        for participant in participants:
            participant_speeches = [s for s in all_speeches if s.get('speaker') == participant]
            stats[participant] = {
                'speech_count': len(participant_speeches),
                'total_words': sum(len(s.get('content', '')) for s in participant_speeches),
                'avg_length': sum(len(s.get('content', '')) for s in participant_speeches) / max(len(participant_speeches), 1)
            }

        stats_text = []
        for participant, stat in stats.items():
            stats_text.append(f"{participant}: 发言次数{stat['speech_count']}, 总字数{stat['total_words']}, 平均长度{stat['avg_length']:.1f}")

        return chr(10).join(stats_text)

    # 注意: 解析方法已移至基类 BaseAgent._parse_structured_response()
    # 以下方法已废弃，保留以确保向后兼容
    
    def _parse_coordination_response(self, response: str) -> Dict[str, Any]:
        """解析协调响应（已废弃，请使用 _parse_structured_response）"""
        return self._parse_structured_response(response, "coordination_plan")

    def _parse_conflict_resolution(self, response: str) -> Dict[str, Any]:
        """解析冲突化解响应（已废弃，请使用 _parse_structured_response）"""
        return self._parse_structured_response(response, "resolution_plan")

    def _parse_participation_assessment(self, response: str) -> Dict[str, Any]:
        """解析参与度评估响应（已废弃，请使用 _parse_structured_response）"""
        return self._parse_structured_response(response, "assessment_report")

    def initiate_depth_discussion(self, expert_list: List[str], discussion_context: Dict[str, Any],
                                previous_round: Any) -> str:
        """
        发起深度讨论阶段

        Args:
            expert_list: 参与专家列表
            discussion_context: 讨论上下文
            previous_round: 上一轮讨论对象

        Returns:
            深度讨论邀请内容
        """
        try:
            prompt = f"""作为讨论协调者，现在是深度讨论阶段的开始。

参与专家：{', '.join(expert_list)}

讨论主题：{discussion_context.get('topic', '未指定')}

上一轮讨论情况：
- 发言专家数量：{len(previous_round.speeches) if hasattr(previous_round, 'speeches') else '未知'}
- 主要话题：{discussion_context.get('current_topic', '综合讨论')}

请以协调者的身份发出邀请，鼓励专家们进行直接对话和观点交锋：

## 深度讨论阶段邀请

[邀请内容]

要求：
1. 说明深度讨论的目的：促进专家间直接交流，深化理解
2. 提醒专家们可以回应彼此的观点
3. 鼓励建设性的意见交换
4. 保持专业和尊重的态度
5. 说明这个阶段的时间安排

请用自然、鼓励的语气撰写邀请内容。"""

            response = self.llm.invoke(prompt)
            invitation = self._extract_response_content(response)

            return invitation

        except Exception as e:
            logger.error(f"发起深度讨论失败: {str(e)}")
            return f"""## 深度讨论阶段邀请

亲爱的专家们：

现在进入深度讨论阶段。在这个阶段，各位专家可以直接回应彼此的观点，进行更深入的交流和观点交锋。

请大家：
- 积极参与讨论
- 尊重不同观点
- 寻求共识和共同理解
- 共同推动解决方案的完善

让我们开始深入的交流！"""

    def summarize_depth_discussion(self, interactions: List[Dict[str, Any]],
                                 discussion_context: Dict[str, Any]) -> str:
        """
        总结深度讨论阶段

        Args:
            interactions: 讨论交互记录
            discussion_context: 讨论上下文

        Returns:
            深度讨论总结
        """
        try:
            interaction_summary = "\n".join([
                f"- {interaction.get('speaker', '未知')}: {interaction.get('content', '')[:100]}..."
                for interaction in interactions[-5:]  # 最近5次交互
            ]) if interactions else "无交互记录"

            prompt = f"""作为讨论协调者，请总结刚刚结束的深度讨论阶段。

讨论主题：{discussion_context.get('topic', '未指定')}

交互记录摘要：
{interaction_summary}

请提供深度讨论阶段的总结，包括：

## 深度讨论总结

[总结内容]

总结要点：
1. 专家间的主要共识点
2. 仍然存在的分歧
3. 新发现的见解或解决方案
4. 对后续讨论的建议
5. 整体讨论氛围评估

请客观、全面地总结讨论成果。"""

            response = self.llm.invoke(prompt)
            summary = self._extract_response_content(response)

            return summary

        except Exception as e:
            logger.error(f"总结深度讨论失败: {str(e)}")
            return f"""## 深度讨论总结

深度讨论阶段已经完成。在这个阶段，专家们进行了直接的观点交流和交锋。

主要成果：
- 促进了专家间的相互理解
- 发现了新的讨论角度
- 为后续的综合分析奠定了基础

讨论将继续进行，请专家们为下一阶段做好准备。"""