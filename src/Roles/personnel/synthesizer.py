# -*- coding: utf-8 -*-
"""
综合者智能体
整合各方观点，生成综合方案
"""

import json
import logging
from typing import Dict, Any, List
from .base_agent import BaseAgent, WorkingStyle

logger = logging.getLogger(__name__)


class Synthesizer(BaseAgent):
    """综合者智能体：整合各方观点，生成综合方案"""

    def __init__(self, llm_instance=None):
        super().__init__(
            name="综合者",
            role_definition="系统思维专家，擅长整合多方观点，识别共识点，生成综合解决方案",
            professional_skills=[
                "系统思维",
                "方案比较",
                "共识识别",
                "综合分析",
                "决策优化",
                "跨领域整合"
            ],
            working_style=WorkingStyle.COLLABORATIVE_WINWIN,
            behavior_guidelines=[
                "客观公正地整合各方观点",
                "识别共识点而非仅仅分歧",
                "寻找平衡和共赢的解决方案",
                "考虑系统的整体最优",
                "提供可操作的综合方案",
                "促进跨领域协作"
            ],
            output_format="""
**综合分析结果：**

**共识点总结：**
1. [共识点1] - [涉及专家]
2. [共识点2] - [涉及专家]

**分歧点分析：**
1. [分歧点1]: [专家A观点] vs [专家B观点]
2. [分歧点2]: [专家A观点] vs [专家B观点]

**综合方案建议：**
### 方案一：[方案名称]
**优点：**
- [优点1]
- [优点2]

**缺点：**
- [缺点1]
- [缺点2]

**实施建议：**
[具体实施步骤]

### 方案二：[方案名称]
[类似结构]

**最终推荐方案：**
[推荐理由和选择标准]

**风险缓解策略：**
[针对主要风险的应对措施]
""",
            llm_instance=llm_instance
        )

        # 综合者特有属性
        self.synthesis_quality = 0.0
        self.consensus_identified = []
        self.solutions_generated = []

    def synthesize_opinions(self, discussion_history: List[Dict[str, Any]],
                           consensus_tracker: Any) -> Dict[str, Any]:
        """
        综合各方意见

        Args:
            discussion_history: 讨论历史
            consensus_tracker: 共识追踪器

        Returns:
            综合分析结果
        """
        synthesis_prompt = self._build_synthesis_prompt(discussion_history, consensus_tracker)

        try:
            response = self.llm.invoke(synthesis_prompt)
            response_text = self._extract_response_content(response)

            synthesis_result = self._parse_synthesis_response(response_text)

            # 更新综合质量评分
            self.synthesis_quality += 0.1

            # 记录生成的方案
            self.solutions_generated.append({
                'timestamp': self._get_timestamp(),
                'result': synthesis_result
            })

            return synthesis_result

        except Exception as e:
            logger.error(f"❌ 综合者分析失败: {e}")
            return self._create_fallback_synthesis(discussion_history)

    def _build_synthesis_prompt(self, discussion_history: List[Dict[str, Any]],
                               consensus_tracker: Any) -> str:
        """构建综合分析提示"""
        # 整理讨论历史，按专家分组
        expert_opinions = {}
        for speech in discussion_history:
            expert_name = speech.get('agent_name', 'Unknown')
            if expert_name not in expert_opinions:
                expert_opinions[expert_name] = []
            expert_opinions[expert_name].append(speech)

        # 生成专家观点总结
        opinions_summary = ""
        for expert_name, speeches in expert_opinions.items():
            opinions_summary += f"\n**{expert_name}** ({len(speeches)}次发言):\n"
            for speech in speeches[-3:]:  # 最近3次发言
                content = speech.get('content', '')[:200] + "..." if len(speech.get('content', '')) > 200 else speech.get('content', '')
                opinions_summary += f"- {content}\n"

        # 获取共识状态
        consensus_status = consensus_tracker.get_status() if consensus_tracker else "暂无共识数据"

        prompt = f"""你是一位系统思维专家，负责整合多方观点，生成综合解决方案。

**讨论参与专家及观点：**
{opinions_summary}

**当前共识状态：**
{consensus_status}

**综合分析任务：**

### 1. 共识点识别
- 识别各方观点中的共同点
- 总结达成共识的核心问题
- 记录共识的强度和范围

### 2. 分歧点分析
- 识别主要的观点分歧
- 分析分歧的根本原因
- 评估分歧对决策的影响

### 3. 方案整合
基于各方观点，生成综合解决方案：

**方案生成原则：**
- 吸收各方的优点
- 平衡不同利益诉求
- 考虑实施可行性
- 优化整体系统效果

**方案评估维度：**
- 技术可行性
- 经济合理性
- 业务价值
- 风险可控性
- 用户接受度

### 4. 决策建议
- 推荐最优方案
- 说明选择理由
- 提供实施路径

### 5. 风险管理
- 识别主要风险
- 提出缓解策略
- 制定应急预案

{self.output_format}

请提供客观、全面、建设性的综合分析。"""

        return prompt

    def _parse_synthesis_response(self, response_text: str) -> Dict[str, Any]:
        """解析综合分析响应"""
        return {
            'synthesizer_name': self.name,
            'content': response_text,
            'timestamp': self._get_timestamp(),
            'synthesis_type': 'comprehensive_analysis'
        }

    def _create_fallback_synthesis(self, discussion_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """创建后备综合分析"""
        total_speeches = len(discussion_history)

        return {
            'synthesizer_name': self.name,
            'content': f"本次讨论共收集{total_speeches}条意见。建议继续深化讨论，重点关注技术可行性和业务价值平衡。",
            'timestamp': self._get_timestamp(),
            'synthesis_type': 'fallback_analysis'
        }

    def compare_solutions(self, solutions: List[Dict[str, Any]],
                         criteria: List[str]) -> Dict[str, Any]:
        """
        比较不同解决方案

        Args:
            solutions: 解决方案列表
            criteria: 比较标准

        Returns:
            比较结果
        """
        comparison_prompt = f"""请比较以下解决方案：

**比较标准：**
{chr(10).join(f"- {criterion}" for criterion in criteria)}

**解决方案列表：**
{chr(10).join(f"{i+1}. {sol.get('title', f'方案{i+1}')}：{sol.get('description', '')}" for i, sol in enumerate(solutions))}

请从多个维度进行比较，并给出推荐方案。"""

        try:
            response = self.llm.invoke(comparison_prompt)
            comparison_text = self._extract_response_content(response)

            return {
                'comparison_result': comparison_text,
                'criteria_used': criteria,
                'solutions_compared': len(solutions)
            }

        except Exception as e:
            logger.error(f"❌ 综合者方案比较失败: {e}")
            return {
                'comparison_result': f"方案比较过程出错，建议人工评估{len(solutions)}个方案",
                'criteria_used': criteria,
                'solutions_compared': len(solutions)
            }

    def identify_best_practices(self, discussion_history: List[Dict[str, Any]]) -> List[str]:
        """
        从讨论中识别最佳实践

        Args:
            discussion_history: 讨论历史

        Returns:
            最佳实践列表
        """
        practices_prompt = f"""基于本次讨论，识别出值得借鉴的最佳实践：

**讨论内容摘要：**
{chr(10).join([f"- {speech.get('agent_name')}: {speech.get('content', '')[:100]}..." for speech in discussion_history[-10:]])}

请识别出讨论中体现的最佳实践，包括：
- 方法论和分析框架
- 技术选型和架构决策
- 风险管理策略
- 协作和沟通模式

列出3-5个最重要的最佳实践。"""

        try:
            response = self.llm.invoke(practices_prompt)
            practices_text = self._extract_response_content(response)

            # 简单解析为列表
            practices = [line.strip('- •').strip() for line in practices_text.split('\n') if line.strip() and (line.startswith('-') or line.startswith('•'))]

            return practices[:5]  # 最多5个

        except Exception as e:
            logger.error(f"❌ 综合者识别最佳实践失败: {e}")
            return ["建议建立跨部门协作机制", "重视数据驱动决策", "关注用户体验和反馈"]