# -*- coding: utf-8 -*-
"""
主持人智能体
控制议程、引导讨论、议程管理、共识追踪
"""

import json
import logging
from typing import Dict, Any, List
from .base_agent import BaseAgent, WorkingStyle

logger = logging.getLogger(__name__)


class Moderator(BaseAgent):
    """主持人智能体：控制议程、引导讨论"""

    def __init__(self, llm_instance=None):
        super().__init__(
            name="主持人",
            role_definition="圆桌讨论会议主持人，负责控制讨论议程、引导讨论方向、管理时间和追踪共识",
            professional_skills=[
                "议程管理",
                "讨论引导",
                "冲突调解",
                "共识识别",
                "时间控制",
                "总结提炼"
            ],
            working_style=WorkingStyle.PROFESSIONAL_OBJECTIVE,
            behavior_guidelines=[
                "保持讨论秩序和效率",
                "确保所有声音都被听到",
                "客观公正地引导讨论",
                "及时识别和记录共识",
                "适时干预偏离主题的讨论",
                "为讨论设定清晰的目标"
            ],
            output_format="""
**主持人发言：**

**当前阶段**: [讨论阶段]

**议程更新**:
- ✅ 已完成: [已完成的议题]
- 🔄 正在进行: [当前议题]
- ⏳ 计划: [后续议题]

**关键共识点**:
1. [共识点1]
2. [共识点2]

**主要分歧点**:
1. [分歧点1] - [涉及专家]

**下一步行动**:
[对讨论方向的建议]
""",
            llm_instance=llm_instance
        )

        # 主持人特有属性
        self.discussion_agenda = []
        self.consensus_points = []
        self.divergence_points = []
        self.participation_tracking = {}

    def open_meeting(self, topic: str, participants: List[Dict[str, Any]]) -> str:
        """
        开场介绍

        Args:
            topic: 讨论主题
            participants: 参与者列表

        Returns:
            开场致辞
        """
        opening_prompt = self._build_opening_prompt(topic, participants)

        try:
            response = self.llm.invoke(opening_prompt)
            opening_speech = self._extract_response_content(response)

            # 初始化参与追踪
            for participant in participants:
                self.participation_tracking[participant['name']] = {
                    'speeches': 0,
                    'agreements': 0,
                    'disagreements': 0,
                    'questions_asked': 0
                }

            logger.info(f"✅ 主持人完成开场介绍，共有 {len(participants)} 位参与者")
            return opening_speech

        except Exception as e:
            logger.error(f"❌ 主持人开场介绍失败: {e}")
            return self._create_fallback_opening(topic, participants)

    def _build_opening_prompt(self, topic: str, participants: List[Dict[str, Any]]) -> str:
        """构建开场介绍提示"""
        participants_text = "\n".join([
            f"- **{p['name']}** ({p['role']}): {', '.join(p.get('skills', []))}"
            for p in participants
        ])

        prompt = f"""你是一位专业的圆桌讨论会议主持人。请为以下讨论会议制作开场介绍。

**讨论主题：**
{topic}

**参会专家：**
{participants_text}

**开场介绍要求：**

1. **欢迎致辞** - 欢迎所有参与者
2. **主题介绍** - 清晰阐述讨论主题和目标
3. **专家介绍** - 简要介绍每位专家的背景和专长
4. **讨论规则** - 说明讨论的基本规则和流程
5. **期望成果** - 明确本次讨论期望达成的目标

**讨论规则说明：**
- 每位专家依次发言
- 发言后会有对应的质疑者提出质疑
- 鼓励建设性批评和深入讨论
- 主持人会记录共识和分歧点
- 讨论将进行多轮，直到达成共识或识别关键分歧

**主持人职责：**
- 控制讨论节奏和时间
- 确保讨论不偏离主题
- 记录重要共识点和分歧点
- 在需要时引导讨论方向

请用专业、热情的语气制作开场介绍。"""

        return prompt

    def _create_fallback_opening(self, topic: str, participants: List[Dict[str, Any]]) -> str:
        """创建后备开场介绍"""
        participants_names = [p['name'] for p in participants]

        return f"""尊敬的各位专家：

欢迎参加本次"{topic}"主题的圆桌讨论会议。

**参会专家：**
{chr(10).join(f"- {name}" for name in participants_names)}

本次讨论将遵循以下规则：
1. 每位专家依次发言，分享专业观点
2. 质疑者会对发言进行建设性质疑
3. 主持人记录共识点和分歧点
4. 讨论将进行多轮，直到达成共识

让我们开始这场深入而富有建设性的讨论！"""

    def guide_discussion(self, current_round: int, discussion_history: List[Dict[str, Any]],
                        consensus_tracker: Any) -> Dict[str, Any]:
        """
        引导讨论过程

        Args:
            current_round: 当前轮次
            discussion_history: 讨论历史
            consensus_tracker: 共识追踪器

        Returns:
            引导指令
        """
        guide_prompt = self._build_guide_prompt(current_round, discussion_history, consensus_tracker)

        try:
            response = self.llm.invoke(guide_prompt)
            response_text = self._extract_response_content(response)

            guide_result = self._parse_guide_response(response_text, current_round)

            # 更新议程
            self._update_agenda(guide_result)

            return guide_result

        except Exception as e:
            logger.error(f"❌ 主持人引导讨论失败: {e}")
            return self._create_fallback_guide(current_round)

    def _build_guide_prompt(self, current_round: int, discussion_history: List[Dict[str, Any]],
                           consensus_tracker: Any) -> str:
        """构建讨论引导提示"""
        recent_history = discussion_history[-10:]  # 最近10条发言

        history_text = "\n".join([
            f"**{speech.get('agent_name', 'Unknown')}**: {speech.get('content', '')[:150]}..."
            for speech in recent_history
        ])

        consensus_status = consensus_tracker.get_status() if consensus_tracker else "暂无共识数据"

        prompt = f"""你是一位经验丰富的圆桌讨论主持人。请基于当前讨论状态提供引导建议。

**当前状态：**
- 讨论轮次：第{current_round}轮
- 发言数量：{len(discussion_history)}条

**最近讨论内容：**
{history_text}

**共识状态：**
{consensus_status}

**引导要求：**

### 1. 议程管理
- 评估当前讨论进度
- 确定下一阶段的重点
- 调整讨论节奏和深度

### 2. 参与度评估
- 识别活跃和沉默的参与者
- 鼓励更多参与
- 平衡不同观点的表达

### 3. 共识识别
- 识别已达成的共识点
- 突出主要分歧点
- 评估达成共识的可能性

### 4. 方向引导
- 确定讨论是否需要深入某个主题
- 建议是否需要引入新视角
- 判断是否可以进入总结阶段

### 5. 干预建议
- 是否需要澄清某个观点
- 是否需要调解分歧
- 是否需要引入外部资源

**输出格式：**

请以结构化方式提供引导建议：

**当前评估：**
[对讨论进展的评估]

**共识状态：**
[共识点和分歧点的总结]

**下一步建议：**
[具体的引导建议和行动计划]

**预期成果：**
[本轮讨论期望达成的目标]
"""

        return prompt

    def _parse_guide_response(self, response_text: str, current_round: int) -> Dict[str, Any]:
        """解析引导响应"""
        return {
            'round': current_round,
            'assessment': self._extract_section(response_text, '当前评估', '共识状态'),
            'consensus_status': self._extract_section(response_text, '共识状态', '下一步建议'),
            'next_suggestions': self._extract_section(response_text, '下一步建议', '预期成果'),
            'expected_outcomes': self._extract_section(response_text, '预期成果', ''),
            'raw_response': response_text
        }

    def _create_fallback_guide(self, current_round: int) -> Dict[str, Any]:
        """创建后备引导"""
        return {
            'round': current_round,
            'assessment': f"第{current_round}轮讨论正在进行中",
            'consensus_status': "正在收集各方意见",
            'next_suggestions': "继续进行专家发言和质疑环节",
            'expected_outcomes': "深化讨论，识别关键共识点",
            'raw_response': f"后备引导：第{current_round}轮继续讨论"
        }

    def _update_agenda(self, guide_result: Dict[str, Any]):
        """更新议程"""
        self.discussion_agenda.append({
            'round': guide_result.get('round'),
            'assessment': guide_result.get('assessment'),
            'timestamp': self._get_timestamp()
        })

    def close_meeting(self, discussion_history: List[Dict[str, Any]],
                     consensus_tracker: Any) -> str:
        """
        结束会议总结

        Args:
            discussion_history: 讨论历史
            consensus_tracker: 共识追踪器

        Returns:
            结束致辞
        """
        summary_prompt = self._build_summary_prompt(discussion_history, consensus_tracker)

        try:
            response = self.llm.invoke(summary_prompt)
            closing_speech = self._extract_response_content(response)

            logger.info("✅ 主持人完成会议总结")
            return closing_speech

        except Exception as e:
            logger.error(f"❌ 主持人会议总结失败: {e}")
            return self._create_fallback_closing(discussion_history)

    def _build_summary_prompt(self, discussion_history: List[Dict[str, Any]],
                             consensus_tracker: Any) -> str:
        """构建总结提示"""
        total_speeches = len(discussion_history)

        # 统计参与情况
        speaker_stats = {}
        for speech in discussion_history:
            speaker = speech.get('agent_name', 'Unknown')
            speaker_stats[speaker] = speaker_stats.get(speaker, 0) + 1

        speaker_summary = "\n".join([f"- {speaker}: {count}次发言" for speaker, count in speaker_stats.items()])

        consensus_summary = consensus_tracker.get_final_summary() if consensus_tracker else "讨论过程完整，收集了各方观点"

        prompt = f"""你是一位专业的主持人。请为本次圆桌讨论会议制作总结致辞。

**会议统计：**
- 总发言数：{total_speeches}
- 参与专家：{len(speaker_stats)}

**发言统计：**
{speaker_summary}

**共识总结：**
{consensus_summary}

**总结致辞要求：**

1. **感谢参与** - 感谢所有专家的贡献
2. **总结成果** - 回顾达成的共识和重要洞察
3. **指出分歧** - 客观说明仍存在的分歧点
4. **后续建议** - 提出下一步行动建议
5. **结束语** - 专业而温暖的结束语

请制作一段简洁而全面的总结致辞。"""

        return prompt

    def _create_fallback_closing(self, discussion_history: List[Dict[str, Any]]) -> str:
        """创建后备结束致辞"""
        return f"""尊敬的各位专家：

感谢大家参与本次深入而富有建设性的讨论！

本次会议收集了{len(discussion_history)}条重要观点，涵盖了多个专业领域。

希望本次讨论能为解决问题提供有价值的参考和方向。

谢谢各位！"""

    def get_agenda_status(self) -> Dict[str, Any]:
        """获取议程状态"""
        return {
            'total_rounds': len(self.discussion_agenda),
            'current_assessment': self.discussion_agenda[-1] if self.discussion_agenda else None,
            'consensus_points': self.consensus_points,
            'divergence_points': self.divergence_points,
            'participation_tracking': self.participation_tracking
        }