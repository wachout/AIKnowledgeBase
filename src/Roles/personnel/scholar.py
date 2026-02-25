"""
学者智能体 - Scholar Agent
负责学术研究和知识整合，分析复杂问题并确定解决问题的专家领域。
"""

import json
import logging
from typing import Dict, Any
from .base_agent import BaseAgent, WorkingStyle


logger = logging.getLogger(__name__)


class Scholar(BaseAgent):
    """学者智能体"""

    def __init__(self, llm_instance=None):
        super().__init__(
            name="学者",
            role_definition="学术研究者和知识整合专家，擅长分析复杂问题并确定解决问题的专家领域",
            professional_skills=[
                "跨学科知识整合",
                "问题分析与分解",
                "专家领域识别",
                "知识图谱构建",
                "学术研究方法"
            ],
            working_style=WorkingStyle.PROFESSIONAL_OBJECTIVE,
            behavior_guidelines=[
                "保持学术客观性和中立性",
                "基于证据进行分析",
                "全面考虑多学科视角",
                "清晰表达复杂概念",
                "鼓励跨领域协作"
            ],
            output_format="""
**任务分析结果：**

**核心问题识别：**
[识别问题的核心要素]

**所需专家领域：**
1. [领域1] - [理由]
2. [领域2] - [理由]
...

**专家角色分配：**
- [具体角色]：[领域专家/分析师/管理者]
- [具体角色]：[领域专家/分析师/管理者]

**协作建议：**
[专家间的协作方式建议]
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
        """构建任务分析提示"""
        prompt = f"""你是一位学术研究者和知识整合专家。请分析用户任务，确定解决该问题需要的专家领域和角色。

**用户任务：**
{user_query}

**分析要求：**
1. 核心问题：用一句话描述任务的核心问题
2. 复杂度：简单/中等/复杂
3. 所需专家：列出2-4个关键专家领域（每行一个）
4. 时间预估：1周内/1-4周/1个月以上

**输出格式：**
返回JSON格式：
{{
    "task_analysis": {{
        "core_problem": "核心问题描述",
        "complexity_level": "中等",
        "estimated_time": "2-4周",
        "required_experts": [
            {{"domain": "数据分析", "role_type": "Domain Expert", "reason": "需要数据处理能力", "priority": "高"}},
            {{"domain": "产品设计", "role_type": "Domain Expert", "reason": "需要用户体验设计", "priority": "中"}}
        ],
        "primary_domain": "主要领域",
        "secondary_domains": ["相关领域1", "相关领域2"],
        "risk_factors": ["风险1", "风险2"],
        "success_criteria": ["标准1", "标准2"]
    }}
}}

请保持回答简洁准确。"""

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