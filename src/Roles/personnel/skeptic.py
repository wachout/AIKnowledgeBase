# -*- coding: utf-8 -*-
"""
质疑者智能体
提出反面意见和风险识别
"""

import json
import logging
import os
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
            role_definition=f"{target_expert.domain}领域质疑者，专门对{target_expert.name}的观点进行批判性分析和风险识别；引导被质疑者在专业领域内突破思维以更好完成任务，并提醒其勿随意突破本领域边界。",
            professional_skills=[
                "批判性思维",
                "风险识别",
                "逻辑推理",
                "证据评估",
                "替代方案生成",
                "思维突破性引导（鼓励领域内创新与突破定式）",
                "知识领域边界意识（提醒在领域内可突破、勿越界）",
                f"{target_expert.domain}领域知识"
            ],
            working_style=WorkingStyle.AGGRESSIVE_INNOVATIVE,  # 质疑者通常更激进
            behavior_guidelines=[
                "保持建设性批评态度",
                "基于证据提出质疑",
                "识别潜在风险和盲点",
                "提供替代观点和解决方案",
                "促进深入讨论和思考",
                "避免个人攻击，聚焦问题本身",
                "思维突破性：提醒被质疑者可在本领域内突破思维定式、创新完成目标",
                "领域边界：提醒被质疑者在自身领域内可大胆突破，但不要随意越界到其他专业，保持专业边界"
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
        对专家意见进行质疑。可使用 web_search_tool 进行网络/论文检索，并结合 discussion/discussion_id/files 中的本地论文进行质疑。
        """
        # 若有工具管理器，先做一次与专家观点相关的网络/学术检索，结果并入 context 供构建质疑使用
        tool_mgr = getattr(self, "_tool_manager", None)
        layer = context.get("skeptic_layer") or context.get("revision_round") or 1
        if tool_mgr and expert_opinion.get("content"):
            try:
                base_content = (expert_opinion.get("content") or "")[:150].strip() or context.get("topic", "research")
                # 第二层：额外用「实施 参数 指标 数据」类查询，便于查到可反馈给发言者的具体数据
                if layer == 2:
                    query_params = f"{base_content} 实施 参数 指标 数据 具体数值"
                else:
                    query_params = base_content
                query = query_params
                for tool_name in ("academic_paper_search", "web_search"):
                    tool = tool_mgr.get_tool(tool_name) if hasattr(tool_mgr, "get_tool") else None
                    if not tool:
                        continue
                    try:
                        discussion_id = context.get("discussion_id", "")
                        params = {"query": query, "limit": 5}
                        if tool_name == "academic_paper_search" and discussion_id:
                            params["save_path"] = os.path.join("discussion", discussion_id, "files")
                        result = tool_mgr.execute_tool(tool_name, params) if hasattr(tool_mgr, "execute_tool") else None
                        if result and getattr(result, "success", False) and getattr(result, "data", None):
                            context = dict(context)
                            context["network_search_results"] = context.get("network_search_results", [])
                            if tool_name == "academic_paper_search":
                                papers = (result.data.get("latest_10_papers") or result.data.get("papers") or [])[:5]
                                context["network_search_results"].extend([{"source": "academic", "title": p.get("title"), "abstract": (p.get("abstract") or "")[:400]} for p in papers])
                            else:
                                res_list = (result.data.get("results") or [])[:5]
                                context["network_search_results"].extend([{"source": "web", "title": r.get("title"), "snippet": r.get("snippet", "")} for r in res_list])
                            break
                    except Exception as e:
                        logger.warning(f"质疑者检索/下载失败 ({tool_name})，继续下一工具或仅用上下文质疑: {e}")
            except Exception as e:
                logger.warning(f"质疑者检索辅助失败，继续执行质疑: {e}")

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
        """构建质疑提示。第二层（revision_round=2）时侧重实施参数/指标/数据查询并反馈给发言者，并提醒可行性、步骤详细度、不要空理论。"""
        layer = context.get("skeptic_layer") or context.get("revision_round") or 1
        local_block = ""
        if context.get("local_papers_summary"):
            papers_dir = context.get("local_papers_dir") or context.get("papers_downloaded_to") or os.path.join("discussion", (context.get("discussion_id") or "discussion_id"), "files")
            local_block = f"""
**可参考的本地论文（来自 {papers_dir}，可结合以下摘要支撑或反驳专家观点/查询实施参数与数据）：**
{context.get('local_papers_summary', '')}
"""
        network_block = ""
        if context.get("network_search_results"):
            network_block = "\n**网络/学术检索结果（可引用以支撑质疑或提取参数/指标/数据）：**\n" + "\n".join(
                f"- [{r.get('source', '')}] {r.get('title', '')}: {(r.get('abstract') or r.get('snippet') or '')[:200]}"
                for r in context["network_search_results"][:8]
            )

        if layer == 2:
            # 第二层：查询实施所需参数/指标/暂无法确定的信息，明确反馈给发言者，并提醒可行性、步骤详细度、不要空理论；同时体现思维突破性与领域边界
            prompt = f"""你是一位{self.target_expert.domain}领域的质疑者，本轮为**第二层**。你的职责包括**思维突破性**（鼓励被质疑者在本领域内突破思维、更好完成任务）与**知识领域边界**（提醒其在领域内可突破，但勿随意越界到其他专业）。请使用网络检索与 discussion/discussion_id/files 中的论文，**查询实施所需的参数、指标、暂无法确定的信息、需明确的数据**，将查到的**具体数据、参数、指标**在下方明确反馈给{self.target_expert.name}；并**明确提醒**发言者：在专业领域不违背第一性原理、逻辑可推理、可实施执行的前提下，请注重**实施的可行性、步骤的详细度，不要空理论**。

**你可以使用：** (1) 上下文中的「本地论文摘要」 (2) 「网络/学术检索结果」，从中提取或归纳出与实施相关的**参数、指标、数值、标准、时间节点**等需明确的信息，**逐条列出并反馈给发言者**。

**目标专家信息：**
- 姓名：{self.target_expert.name}
- 领域：{self.target_expert.domain}
- 专长：{self.target_expert.expertise_area}

**专家当前发言（请针对其实施方案查找并反馈缺失或待定的参数/指标/数据）：**
{expert_opinion.get('content', '')}
{local_block}
{network_block}

**第二层任务：**
1. **数据与参数反馈**：从上述本地论文与检索结果中，找出与专家方案实施相关的**参数、指标、阈值、标准、典型数值、时间范围**等；若检索中无直接数据，则列出「尚需明确的数据项」并建议如何获取。
2. **明确反馈**：将上述信息清晰、逐条地反馈给{self.target_expert.name}，便于其在修订稿中吸纳。
3. **对发言者的提醒**：在结尾明确提醒：在专业领域不违背第一性原理、逻辑可推理、可实施执行的前提下，请特别注重**实施的可行性、步骤的详细度，避免空理论**；若质疑者已提供具体参数或数据，请在修订稿中体现。
4. **思维与边界**：提醒{self.target_expert.name}——可在**本领域内**突破思维、创新完成任务；但在角色**领域内**不要随意突破边界，勿越界到其他专业。

请保持专业、建设性，输出可直接交给发言者使用的「数据反馈 + 提醒」内容。"""

            return prompt

        # 第一层：具像化与可执行性质疑
        prompt = f"""你是一位{self.target_expert.domain}领域的质疑者，专门对{self.target_expert.name}的观点进行批判性分析。你的职责包括：**思维突破性**（鼓励被质疑者在本领域内突破思维定式、更好完成任务）与**知识领域边界**（提醒其在自身领域内可大胆突破，但不要随意越界到其他专业）。

**你可以使用：** (1) 上下文中的「本地论文摘要」（来自 discussion/discussion_id/files 的论文）与 (2) 若已提供则「网络/学术检索结果」，结合这些材料对专家观点进行有理有据的质疑。

**重要原则：质疑必须偏向「具像化的计划与实施」，不要停留在虚理论。** 多问「怎么落地、谁来做、何时验收、产出是什么」，少问抽象概念。

**目标专家信息：**
- 姓名：{self.target_expert.name}
- 领域：{self.target_expert.domain}
- 专长：{self.target_expert.expertise_area}
- 工作风格：{self.target_expert.working_style.value}

**专家观点：**
{expert_opinion.get('content', '')}
{local_block}
{network_block}

**讨论上下文（含 discussion_id、近期发言等）：**
{json.dumps({k: v for k, v in context.items() if k not in ("local_papers_summary", "network_search_results")}, ensure_ascii=False, indent=2)}

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

**思维与边界提醒（请在质疑中或结尾自然体现）：**
- **思维突破性**：鼓励{self.target_expert.name}在**本领域内**突破思维定式、创新完成目标，可提醒其「可在专业内大胆突破以更好完成任务」。
- **知识领域边界**：提醒被质疑者——在自身**角色领域内**可突破思维，但**不要随意突破领域边界**，勿越界到其他专业，保持专业边界。

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