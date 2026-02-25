"""
风险管理者智能体 - Risk Manager Agent
负责风险评估、风险识别、提供缓解建议，确保风险覆盖度和可行性。
"""

from typing import Dict, Any, List
from .base_agent import BaseAgent


class RiskManager(BaseAgent):
    """
    风险管理者智能体
    主要职责：
    - 风险评估
    - 风险识别
    - 提供缓解建议
    - 确保风险覆盖度和可行性
    """

    def __init__(self, llm_instance=None):
        from .base_agent import WorkingStyle
        super().__init__(
            name="风险管理者",
            role_definition="风险评估与管理专家",
            professional_skills=[
                "风险识别",
                "风险评估",
                "风险缓解策略",
                "应急计划制定",
                "概率分析",
                "影响评估"
            ],
            working_style=WorkingStyle.STEADY_CONSERVATIVE,
            behavior_guidelines=[
                "优先考虑潜在风险",
                "基于证据评估风险概率",
                "提供可操作的风险缓解措施",
                "关注长期风险而非短期利益",
                "建议建立风险监控机制",
                "保持风险意识但不过度悲观"
            ],
            output_format="""
请以以下格式输出：
## 风险识别
[识别出的主要风险点]

## 风险评估
[各风险的概率和影响程度分析]

## 风险优先级
[按优先级排序的风险列表]

## 缓解策略
[针对各风险的具体缓解措施]

## 应急计划
[应对风险发生时的应急方案]

## 监控建议
[持续监控和预警机制建议]
            """,
            llm_instance=llm_instance
        )

    def assess_risks(self, discussion_topic: str,
                    proposed_solutions: List[Dict[str, Any]],
                    discussion_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估讨论主题和解决方案相关的风险

        Args:
            discussion_topic: 讨论主题
            proposed_solutions: 提出的解决方案
            discussion_context: 讨论上下文

        Returns:
            风险评估结果
        """
        assessment_prompt = f"""
你作为风险管理者，需要全面评估讨论主题和解决方案相关的风险。

## 讨论主题
{discussion_topic}

## 提出的解决方案
{self._format_solutions(proposed_solutions)}

## 讨论上下文
{chr(10).join(f"- {k}: {v}" for k, v in discussion_context.items())}

## 你的任务
请进行全面的风险评估，包括：
1. 识别潜在风险点
2. 评估风险概率和影响
3. 分析风险间的相互关系
4. 确定风险优先级
5. 评估整体风险水平

请基于客观分析提供风险评估结果。
        """

        response = self.llm.invoke(assessment_prompt)
        response_text = self._extract_response_content(response)

        risk_assessment = self._parse_structured_response(response_text, "assessment_report")

        return {
            "risk_manager": self.name,
            "risk_assessment": risk_assessment,
            "timestamp": self._get_timestamp()
        }

    def develop_mitigation_strategies(self, identified_risks: List[Dict[str, Any]],
                                    discussion_topic: str) -> Dict[str, Any]:
        """
        制定风险缓解策略

        Args:
            identified_risks: 已识别的风险
            discussion_topic: 讨论主题

        Returns:
            缓解策略
        """
        mitigation_prompt = f"""
你作为风险管理者，需要为已识别的风险制定缓解策略。

## 讨论主题
{discussion_topic}

## 已识别风险
{self._format_risks(identified_risks)}

## 你的任务
请制定全面的风险缓解策略，包括：
1. 预防措施
2. 监测机制
3. 应急响应计划
4. 风险转移方案
5. 资源分配建议
6. 时间安排规划

确保缓解策略具有可操作性和成本效益。
        """

        response = self.llm.invoke(mitigation_prompt)
        response_text = self._extract_response_content(response)

        mitigation_strategies = self._parse_structured_response(response_text, "mitigation_report")

        return {
            "strategy_developer": self.name,
            "mitigation_strategies": mitigation_strategies,
            "timestamp": self._get_timestamp()
        }

    def monitor_risks(self, discussion_progress: Dict[str, Any],
                     previous_assessments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        监控讨论过程中的风险变化

        Args:
            discussion_progress: 讨论进展
            previous_assessments: 之前的风险评估

        Returns:
            风险监控结果
        """
        monitoring_prompt = f"""
你作为风险管理者，需要监控讨论过程中的风险变化。

## 当前讨论进展
{discussion_progress.get('current_status', '进行中')}

## 最新讨论内容
{discussion_progress.get('recent_discussions', '暂无')}

## 之前的风险评估
{self._summarize_previous_assessments(previous_assessments)}

## 你的任务
请监控风险变化情况，包括：
1. 新出现或变化的风险
2. 现有风险的缓解情况
3. 风险优先级的调整
4. 新的缓解措施需求
5. 整体风险水平的评估

请提供及时的风险监控报告。
        """

        response = self.llm.invoke(monitoring_prompt)
        response_text = self._extract_response_content(response)

        monitoring_result = self._parse_structured_response(response_text, "monitoring_report")

        return {
            "risk_monitor": self.name,
            "monitoring_report": monitoring_result,
            "timestamp": self._get_timestamp()
        }

    def create_contingency_plans(self, high_priority_risks: List[Dict[str, Any]],
                                discussion_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建应急预案

        Args:
            high_priority_risks: 高优先级风险
            discussion_context: 讨论上下文

        Returns:
            应急预案
        """
        contingency_prompt = f"""
你作为风险管理者，需要为高优先级风险创建应急预案。

## 讨论上下文
{chr(10).join(f"- {k}: {v}" for k, v in discussion_context.items())}

## 高优先级风险
{self._format_risks(high_priority_risks)}

## 你的任务
请创建详细的应急预案，包括：
1. 风险触发条件
2. 应急响应步骤
3. 所需资源和人员
4. 沟通协调机制
5. 恢复和改进措施
6. 预案测试建议

确保预案具有实用性和可执行性。
        """

        response = self.llm.invoke(contingency_prompt)
        response_text = self._extract_response_content(response)

        contingency_plans = self._parse_structured_response(response_text, "contingency_report")

        return {
            "emergency_planner": self.name,
            "contingency_plans": contingency_plans,
            "timestamp": self._get_timestamp()
        }

    def evaluate_feasibility(self, proposed_actions: List[str],
                           available_resources: Dict[str, Any],
                           time_constraints: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估行动方案的可行性

        Args:
            proposed_actions: 提出的行动方案
            available_resources: 可用资源
            time_constraints: 时间约束

        Returns:
            可行性评估结果
        """
        feasibility_prompt = f"""
你作为风险管理者，需要评估行动方案的可行性。

## 提出的行动方案
{chr(10).join(f"- {action}" for action in proposed_actions)}

## 可用资源
{chr(10).join(f"- {k}: {v}" for k, v in available_resources.items())}

## 时间约束
{chr(10).join(f"- {k}: {v}" for k, v in time_constraints.items())}

## 你的任务
请评估各方案的可行性，包括：
1. 资源充足性分析
2. 时间可行性评估
3. 技术难度分析
4. 风险可控性评估
5. 成功概率预测
6. 建议的优化方案

请提供客观的可行性评估。
        """

        response = self.llm.invoke(feasibility_prompt)
        response_text = self._extract_response_content(response)

        feasibility_assessment = self._parse_structured_response(response_text, "feasibility_report")

        return {
            "feasibility_analyst": self.name,
            "feasibility_assessment": feasibility_assessment,
            "timestamp": self._get_timestamp()
        }

    def _format_solutions(self, solutions: List[Dict[str, Any]]) -> str:
        """格式化解决方案"""
        formatted_parts = []
        for i, solution in enumerate(solutions, 1):
            formatted_parts.append(f"### 方案 {i}")
            for key, value in solution.items():
                formatted_parts.append(f"- {key}: {value}")

        return chr(10).join(formatted_parts)

    def _format_risks(self, risks: List[Dict[str, Any]]) -> str:
        """格式化风险"""
        formatted_parts = []
        for risk in risks:
            formatted_parts.append(f"- **{risk.get('name', '未命名风险')}**: {risk.get('description', '无描述')}")
            formatted_parts.append(f"  - 概率: {risk.get('probability', '未知')}")
            formatted_parts.append(f"  - 影响: {risk.get('impact', '未知')}")

        return chr(10).join(formatted_parts)

    def _summarize_previous_assessments(self, assessments: List[Dict[str, Any]]) -> str:
        """总结之前的风险评估"""
        if not assessments:
            return "暂无之前的风险评估记录。"

        summary_parts = []
        for assessment in assessments[-3:]:  # 只总结最近3次评估
            summary_parts.append(f"- {assessment.get('timestamp', '未知时间')}: {assessment.get('key_findings', '无关键发现')}")

        return chr(10).join(summary_parts)

    # 注意: 解析方法已移至基类 BaseAgent._parse_structured_response()
    # 以下方法已废弃，保留以确保向后兼容
    
    def _parse_risk_assessment(self, response: str) -> Dict[str, Any]:
        """解析风险评估响应（已废弃，请使用 _parse_structured_response）"""
        return self._parse_structured_response(response, "assessment_report")

    def _parse_mitigation_response(self, response: str) -> Dict[str, Any]:
        """解析缓解策略响应（已废弃，请使用 _parse_structured_response）"""
        return self._parse_structured_response(response, "mitigation_report")

    def _parse_monitoring_response(self, response: str) -> Dict[str, Any]:
        """解析监控响应（已废弃，请使用 _parse_structured_response）"""
        return self._parse_structured_response(response, "monitoring_report")

    def _parse_contingency_response(self, response: str) -> Dict[str, Any]:
        """解析应急预案响应（已废弃，请使用 _parse_structured_response）"""
        return self._parse_structured_response(response, "contingency_report")

    def _parse_feasibility_response(self, response: str) -> Dict[str, Any]:
        """解析可行性评估响应（已废弃，请使用 _parse_structured_response）"""
        return self._parse_structured_response(response, "feasibility_report")