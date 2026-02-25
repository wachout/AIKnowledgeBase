"""
数据分析师智能体 - Data Analyst Agent
负责数据支撑分析、数据可视化，提供数据洞察和说服力。
"""

from typing import Dict, Any, List
from .base_agent import BaseAgent
from .base_agent import WorkingStyle

class DataAnalyst(BaseAgent):
    """
    数据分析师智能体
    主要职责：
    - 数据支撑分析
    - 数据可视化
    - 提供数据洞察
    - 增强观点说服力
    """

    def __init__(self, llm_instance=None):
        
        super().__init__(
            name="数据分析师",
            role_definition="数据分析与可视化专家",
            professional_skills=[
                "数据分析",
                "统计建模",
                "数据可视化",
                "趋势分析",
                "相关性分析",
                "预测分析"
            ],
            working_style=WorkingStyle.PROFESSIONAL_OBJECTIVE,
            behavior_guidelines=[
                "基于数据和事实说话",
                "使用适当的统计方法",
                "提供清晰的数据可视化",
                "解释数据背后的含义",
                "质疑不准确的数据使用",
                "建议数据收集改进"
            ],
            output_format="""
请以以下格式输出：
## 数据分析结果
[具体的分析发现]

## 关键指标
[重要的数据指标和统计结果]

## 数据可视化建议
[图表类型和展示方式]

## 数据洞察
[基于数据的深刻见解]

## 数据质量评估
[数据可靠性和完整性评估]
            """,
            llm_instance=llm_instance
        )

    def analyze_data(self, discussion_topic: str,
                    available_data: Dict[str, Any],
                    research_questions: List[str]) -> Dict[str, Any]:
        """
        基于讨论主题进行数据分析

        Args:
            discussion_topic: 讨论主题
            available_data: 可用的数据
            research_questions: 研究问题

        Returns:
            数据分析结果
        """
        analysis_prompt = f"""
你作为数据分析师，需要为讨论主题提供数据支撑分析。

## 讨论主题
{discussion_topic}

## 可用数据概览
{self._summarize_available_data(available_data)}

## 研究问题
{chr(10).join(f"- {question}" for question in research_questions)}

## 你的任务
请进行全面的数据分析，包括：
1. 数据质量评估
2. 描述性统计分析
3. 相关性和趋势分析
4. 数据可视化建议
5. 关键发现和洞察
6. 数据局限性和建议

请基于数据提供客观、准确的分析结果。
        """

        response = self.llm.invoke(analysis_prompt)
        response_text = self._extract_response_content(response)

        analysis_result = self._parse_structured_response(response_text, "analysis_report")

        return {
            "analyst": self.name,
            "data_analysis": analysis_result,
            "timestamp": self._get_timestamp()
        }

    def create_visualization(self, data_insights: Dict[str, Any],
                           discussion_context: str) -> Dict[str, Any]:
        """
        创建数据可视化方案

        Args:
            data_insights: 数据洞察
            discussion_context: 讨论上下文

        Returns:
            可视化方案
        """
        visualization_prompt = f"""
你作为数据分析师，需要为数据洞察设计可视化方案。

## 讨论上下文
{discussion_context}

## 数据洞察
{self._format_insights(data_insights)}

## 你的任务
请设计合适的数据可视化方案，包括：
1. 图表类型选择（柱状图、折线图、饼图、散点图等）
2. 数据映射方案（x轴、y轴、颜色、大小等）
3. 视觉元素设计（颜色、标签、图例等）
4. 交互功能建议
5. 图表布局安排

确保可视化方案能够有效传达数据洞察。
        """

        response = self.llm.invoke(visualization_prompt)
        response_text = self._extract_response_content(response)

        visualization_plan = self._parse_structured_response(response_text, "visualization_plan")

        return {
            "visualizer": self.name,
            "visualization_plan": visualization_plan,
            "timestamp": self._get_timestamp()
        }

    def validate_claims(self, claims: List[str],
                       available_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证其他参与者基于数据的声明

        Args:
            claims: 需要验证的声明
            available_data: 可用的数据

        Returns:
            声明验证结果
        """
        validation_prompt = f"""
你作为数据分析师，需要验证其他参与者的数据相关声明。

## 待验证声明
{chr(10).join(f"- {claim}" for claim in claims)}

## 可用数据
{self._summarize_available_data(available_data)}

## 你的任务
请验证每个声明的数据基础：
1. 声明是否基于准确数据
2. 数据解读是否正确
3. 是否存在数据偏差或误导
4. 建议更准确的数据表述
5. 指出需要补充的数据

请保持客观公正的验证态度。
        """

        response = self.llm.invoke(validation_prompt)
        response_text = self._extract_response_content(response)

        validation_result = self._parse_structured_response(response_text, "validation_report")

        return {
            "validator": self.name,
            "claims_validation": validation_result,
            "timestamp": self._get_timestamp()
        }

    def suggest_data_collection(self, discussion_topic: str,
                              current_data_gaps: List[str]) -> Dict[str, Any]:
        """
        建议数据收集改进方案

        Args:
            discussion_topic: 讨论主题
            current_data_gaps: 当前数据缺失

        Returns:
            数据收集建议
        """
        suggestion_prompt = f"""
你作为数据分析师，需要建议数据收集改进方案。

## 讨论主题
{discussion_topic}

## 当前数据缺失
{chr(10).join(f"- {gap}" for gap in current_data_gaps)}

## 你的任务
请建议数据收集改进方案，包括：
1. 优先收集的数据类型
2. 数据收集方法
3. 样本量和时间跨度建议
4. 数据质量控制措施
5. 成本效益分析
6. 时间安排建议

确保建议具有可操作性和实际价值。
        """

        response = self.llm.invoke(suggestion_prompt)
        response_text = self._extract_response_content(response)

        suggestions = self._parse_structured_response(response_text, "suggestions")

        return {
            "data_expert": self.name,
            "data_collection_suggestions": suggestions,
            "timestamp": self._get_timestamp()
        }

    def _summarize_available_data(self, data: Dict[str, Any]) -> str:
        """总结可用数据"""
        if not data:
            return "当前没有可用数据。"

        summary_parts = []
        for key, value in data.items():
            if isinstance(value, (list, dict)):
                summary_parts.append(f"{key}: {type(value).__name__} 类型，包含 {len(value)} 项")
            else:
                summary_parts.append(f"{key}: {value}")

        return chr(10).join(summary_parts)

    def _format_insights(self, insights: Dict[str, Any]) -> str:
        """格式化数据洞察"""
        formatted_parts = []
        for key, value in insights.items():
            formatted_parts.append(f"### {key}")
            if isinstance(value, list):
                formatted_parts.extend(f"- {item}" for item in value)
            else:
                formatted_parts.append(str(value))

        return chr(10).join(formatted_parts)

    # 注意: 解析方法已移至基类 BaseAgent._parse_structured_response()
    # 以下方法已废弃，保留以确保向后兼容
    
    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """解析分析响应（已废弃，请使用 _parse_structured_response）"""
        return self._parse_structured_response(response, "analysis_report")

    def _parse_visualization_response(self, response: str) -> Dict[str, Any]:
        """解析可视化响应（已废弃，请使用 _parse_structured_response）"""
        return self._parse_structured_response(response, "visualization_plan")

    def _parse_validation_response(self, response: str) -> Dict[str, Any]:
        """解析验证响应（已废弃，请使用 _parse_structured_response）"""
        return self._parse_structured_response(response, "validation_report")

    def _parse_suggestion_response(self, response: str) -> Dict[str, Any]:
        """解析建议响应（已废弃，请使用 _parse_structured_response）"""
        return self._parse_structured_response(response, "suggestions")