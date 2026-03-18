"""
话题画像系统 - Topic Profiler
负责任务分析模块，对用户任务进行深度分析和画像。
"""

from typing import Dict, Any, List
from datetime import datetime
import json


class TaskAnalysis:
    """任务分析类"""

    def __init__(self, task_description: str, requester: str = "unknown"):
        self.task_description = task_description
        self.requester = requester
        self.analyzed_at = datetime.now().isoformat()

        # 分析结果
        self.core_problem = ""
        self.sub_problems = []
        self.required_expertise = []
        self.complexity_level = "medium"  # low, medium, high
        self.time_estimate = ""  # 预估时间
        self.resource_requirements = []
        self.potential_challenges = []
        self.success_criteria = []

        # 领域分析
        self.primary_domain = ""
        self.secondary_domains = []
        self.cross_domain_aspects = []

        # 参与者分析
        self.recommended_roles = []
        self.participant_count = 0
        self.collaboration_patterns = []

        # 风险分析
        self.risk_factors = []
        self.mitigation_strategies = []

        # 自主构思：研究假设（科学意义且可检验，经进化策略平衡新颖性与可行性）
        self.research_hypotheses = []

    def set_core_analysis(self, core_problem: str, sub_problems: List[str],
                         complexity: str, time_estimate: str):
        """设置核心问题分析"""
        self.core_problem = core_problem
        self.sub_problems = sub_problems.copy()
        self.complexity_level = complexity
        self.time_estimate = time_estimate

    def set_domain_analysis(self, primary_domain: str, secondary_domains: List[str],
                           cross_domain_aspects: List[str]):
        """设置领域分析"""
        self.primary_domain = primary_domain
        self.secondary_domains = secondary_domains.copy()
        self.cross_domain_aspects = cross_domain_aspects.copy()

    def set_participant_analysis(self, recommended_roles: List[Dict[str, Any]],
                                participant_count: int, collaboration_patterns: List[str]):
        """设置参与者分析"""
        self.recommended_roles = recommended_roles.copy()
        self.participant_count = participant_count
        self.collaboration_patterns = collaboration_patterns.copy()

    def set_requirements(self, resources: List[str], success_criteria: List[str]):
        """设置需求和成功标准"""
        self.resource_requirements = resources.copy()
        self.success_criteria = success_criteria.copy()

    def set_risks(self, risk_factors: List[str], mitigation_strategies: List[str]):
        """设置风险分析"""
        self.risk_factors = risk_factors.copy()
        self.mitigation_strategies = mitigation_strategies.copy()

    def set_research_hypotheses(self, hypotheses: List[Dict[str, Any]]):
        """设置自主构思产出的研究假设列表（每项含 text, novelty_score, feasibility_score, testability_criteria 等）"""
        self.research_hypotheses = [dict(h) for h in hypotheses]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_description": self.task_description,
            "requester": self.requester,
            "analyzed_at": self.analyzed_at,
            "core_analysis": {
                "core_problem": self.core_problem,
                "sub_problems": self.sub_problems,
                "complexity_level": self.complexity_level,
                "time_estimate": self.time_estimate
            },
            "domain_analysis": {
                "primary_domain": self.primary_domain,
                "secondary_domains": self.secondary_domains,
                "cross_domain_aspects": self.cross_domain_aspects
            },
            "participant_analysis": {
                "recommended_roles": self.recommended_roles,
                "participant_count": self.participant_count,
                "collaboration_patterns": self.collaboration_patterns
            },
            "requirements": {
                "resource_requirements": self.resource_requirements,
                "success_criteria": self.success_criteria
            },
            "risk_analysis": {
                "risk_factors": self.risk_factors,
                "mitigation_strategies": self.mitigation_strategies
            },
            "research_hypotheses": self.research_hypotheses,
            "ideation_ideas": getattr(self, "ideation_ideas", []),
            "ideation_papers": getattr(self, "ideation_papers", []),
            "papers_downloaded_to": getattr(self, "papers_downloaded_to", None),
        }


class TopicProfile:
    """话题画像类"""

    def __init__(self, topic_name: str, task_analysis: TaskAnalysis):
        self.topic_name = topic_name
        self.task_analysis = task_analysis
        self.created_at = datetime.now().isoformat()

        # 画像特征
        self.topic_characteristics = {
            "scope": "",  # broad, narrow, specialized
            "urgency": "",  # low, medium, high, critical
            "impact": "",  # local, regional, global
            "controversy_level": "",  # low, medium, high
            "expertise_requirement": "",  # general, specialized, expert
            "time_sensitivity": "",  # flexible, moderate, strict
            "resource_intensity": ""  # low, medium, high
        }

        # 讨论策略建议
        self.discussion_strategy = {
            "recommended_format": "",  # roundtable, debate, workshop, etc.
            "optimal_participant_mix": [],
            "suggested_agenda": [],
            "communication_guidelines": [],
            "decision_making_approach": ""
        }

        # 进度追踪
        self.progress_indicators = []
        self.milestones = []

    def set_characteristics(self, characteristics: Dict[str, str]):
        """设置话题特征"""
        self.topic_characteristics.update(characteristics)

    def set_discussion_strategy(self, strategy: Dict[str, Any]):
        """设置讨论策略"""
        self.discussion_strategy.update(strategy)

    def add_progress_indicator(self, indicator: str):
        """添加进度指标"""
        if indicator not in self.progress_indicators:
            self.progress_indicators.append(indicator)

    def add_milestone(self, milestone: str, target_date: str = None):
        """添加里程碑"""
        milestone_data = {
            "description": milestone,
            "target_date": target_date or "TBD",
            "status": "pending"
        }
        self.milestones.append(milestone_data)

    def update_milestone_status(self, milestone_index: int, status: str):
        """更新里程碑状态"""
        if 0 <= milestone_index < len(self.milestones):
            self.milestones[milestone_index]["status"] = status
            self.milestones[milestone_index]["updated_at"] = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "topic_name": self.topic_name,
            "created_at": self.created_at,
            "task_analysis": self.task_analysis.to_dict(),
            "topic_characteristics": self.topic_characteristics,
            "discussion_strategy": self.discussion_strategy,
            "progress_indicators": self.progress_indicators,
            "milestones": self.milestones
        }


class TopicProfiler:
    """
    话题画像系统
    主要功能：
    - 任务分析模块
    - 话题画像生成
    - 讨论策略建议
    """

    def __init__(self, llm_instance=None):
        self.llm_instance = llm_instance
        self.analyzed_topics: Dict[str, TopicProfile] = {}

    def create_topic_profile(self, topic_name: str, task_analysis: TaskAnalysis):
        """
        创建话题画像（流式返回）

        Args:
            topic_name: 话题名称
            task_analysis: 任务分析结果

        Yields:
            创建过程中的各个步骤消息
        """
        if not self.llm_instance:
            # 如果没有 LLM 实例，直接使用默认配置
            yield {
                "step": "profile_error_fallback",
                "message": "⚠️ 没有提供 LLM 实例，使用默认配置...",
                "progress": "使用默认配置"
            }
            
            topic_profile = self._create_default_topic_profile(topic_name, task_analysis)
            self.analyzed_topics[topic_name] = topic_profile
            
            yield {
                "step": "profile_complete",
                "message": "✅ 话题画像创建完成（默认配置）",
                "topic_profile": topic_profile.to_dict(),
                "progress": "画像完成"
            }
            return

        try:
            # 步骤1: 准备画像分析
            yield {
                "step": "profile_analysis_start",
                "message": "🔍 正在分析话题特征...",
                "progress": "特征分析中"
            }

            # 简化任务分析数据，避免传递过多信息导致LLM响应慢
            simplified_analysis = {
                "core_problem": task_analysis.core_problem,
                "complexity_level": task_analysis.complexity_level,
                "primary_domain": task_analysis.primary_domain,
                "participant_count": task_analysis.participant_count,
                "risk_count": len(task_analysis.risk_factors)
            }

            profile_prompt = f"""
基于以下简化任务分析，快速创建一个话题画像：

## 简化任务信息
{json.dumps(simplified_analysis, ensure_ascii=False, indent=2)}

## 画像创建要求
请快速从以下维度创建话题画像：

### 话题特征 (用一行回答)
scope: broad/narrow/specialized | urgency: low/medium/high/critical | impact: local/regional/global | controversy_level: low/medium/high | expertise_requirement: general/specialized/expert | time_sensitivity: flexible/moderate/strict | resource_intensity: low/medium/high

### 讨论策略 (用一行回答)
recommended_format: roundtable/debate/workshop/presentation | optimal_participant_mix: 专家,协调者,记录员 | suggested_agenda: 开场介绍,问题分析,方案讨论,共识形成,总结行动 | communication_guidelines: 尊重发言,建设性批评,基于事实 | decision_making_approach: 共识决策

请保持回答简洁直接，不要过多解释。
            """

            # 步骤2: LLM分析特征
            yield {
                "step": "llm_analysis",
                "message": "🧠 正在生成画像策略...",
                "progress": "AI分析中"
            }

            # 使用 invoke 方法调用 LLM（LangChain 标准用法）
            response = self.llm_instance.invoke(profile_prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)

            # 步骤3: 解析和创建画像
            yield {
                "step": "profile_parsing",
                "message": "📋 正在整理画像结果...",
                "progress": "结果整理中"
            }

            topic_profile = self._parse_topic_profile_quick(response_text, topic_name, task_analysis)

            # 存储画像
            self.analyzed_topics[topic_name] = topic_profile

            yield {
                "step": "profile_complete",
                "message": "✅ 话题画像创建完成",
                "topic_profile": topic_profile.to_dict(),
                "progress": "画像完成"
            }

        except Exception as e:
            # 如果出错，使用快速默认创建
            print(f"Warning: Topic profile creation failed: {str(e)}")
            yield {
                "step": "profile_error_fallback",
                "message": "⚠️ 画像创建遇到问题，使用默认配置...",
                "progress": "使用默认配置"
            }

            topic_profile = self._create_default_topic_profile(topic_name, task_analysis)
            self.analyzed_topics[topic_name] = topic_profile

            yield {
                "step": "profile_complete",
                "message": "✅ 话题画像创建完成（默认配置）",
                "topic_profile": topic_profile.to_dict(),
                "progress": "画像完成"
            }

    def _parse_topic_profile_quick(self, response: str, topic_name: str, task_analysis: TaskAnalysis) -> TopicProfile:
        """快速解析话题画像响应"""
        topic_profile = TopicProfile(topic_name, task_analysis)

        try:
            # 快速解析简化响应
            lines = response.strip().split('\n')

            characteristics = {}
            strategy = {}

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # 解析特征
                if 'scope:' in line and 'urgency:' in line:
                    # 这是特征行，快速解析
                    parts = line.split('|')
                    for part in parts:
                        if ':' in part:
                            key, value = part.split(':', 1)
                            key = key.strip()
                            value = value.strip()
                            characteristics[key] = value

                # 解析策略
                elif 'recommended_format:' in line and 'optimal_participant_mix:' in line:
                    # 这是策略行，快速解析
                    parts = line.split('|')
                    for part in parts:
                        if ':' in part:
                            key, value = part.split(':', 1)
                            key = key.strip()
                            value = value.strip()
                            if key == 'optimal_participant_mix':
                                strategy[key] = [v.strip() for v in value.split(',')]
                            elif key == 'suggested_agenda':
                                strategy[key] = [v.strip() for v in value.split(',')]
                            elif key == 'communication_guidelines':
                                strategy[key] = [v.strip() for v in value.split(',')]
                            else:
                                strategy[key] = value

            # 设置默认值如果解析失败
            if not characteristics:
                characteristics = {
                    "scope": "narrow",
                    "urgency": "medium",
                    "impact": "regional",
                    "controversy_level": "medium",
                    "expertise_requirement": "specialized",
                    "time_sensitivity": "moderate",
                    "resource_intensity": "medium"
                }

            if not strategy:
                strategy = {
                    "recommended_format": "roundtable",
                    "optimal_participant_mix": ["专家", "协调者", "记录员"],
                    "suggested_agenda": ["开场介绍", "问题分析", "方案讨论", "共识形成", "总结行动"],
                    "communication_guidelines": ["尊重发言", "建设性批评", "基于事实"],
                    "decision_making_approach": "共识决策"
                }

            topic_profile.set_characteristics(characteristics)
            topic_profile.set_discussion_strategy(strategy)

            # 添加默认进度指标和里程碑
            topic_profile.add_progress_indicator("问题分析完成")
            topic_profile.add_progress_indicator("专家意见收集")
            topic_profile.add_progress_indicator("共识形成")
            topic_profile.add_progress_indicator("行动计划制定")

            topic_profile.add_milestone("初始分析完成")
            topic_profile.add_milestone("深度讨论阶段")
            topic_profile.add_milestone("解决方案形成")
            topic_profile.add_milestone("行动计划制定")

        except Exception as e:
            print(f"Warning: Failed to parse quick topic profile response: {str(e)}")
            # 使用默认值
            return self._create_default_topic_profile(topic_name, task_analysis)

        return topic_profile

    def _create_default_topic_profile(self, topic_name: str, task_analysis: TaskAnalysis) -> TopicProfile:
        """创建默认话题画像"""
        topic_profile = TopicProfile(topic_name, task_analysis)

        # 使用基于任务分析的智能默认值
        complexity = task_analysis.complexity_level

        # 根据复杂度设置特征
        if complexity == "high":
            characteristics = {
                "scope": "broad",
                "urgency": "high",
                "impact": "global",
                "controversy_level": "high",
                "expertise_requirement": "expert",
                "time_sensitivity": "strict",
                "resource_intensity": "high"
            }
        elif complexity == "low":
            characteristics = {
                "scope": "narrow",
                "urgency": "low",
                "impact": "local",
                "controversy_level": "low",
                "expertise_requirement": "general",
                "time_sensitivity": "flexible",
                "resource_intensity": "low"
            }
        else:  # medium
            characteristics = {
                "scope": "narrow",
                "urgency": "medium",
                "impact": "regional",
                "controversy_level": "medium",
                "expertise_requirement": "specialized",
                "time_sensitivity": "moderate",
                "resource_intensity": "medium"
            }

        strategy = {
            "recommended_format": "roundtable",
            "optimal_participant_mix": ["专家", "协调者", "记录员"],
            "suggested_agenda": ["开场介绍", "问题分析", "方案讨论", "共识形成", "总结行动"],
            "communication_guidelines": ["尊重发言", "建设性批评", "基于事实"],
            "decision_making_approach": "共识决策"
        }

        topic_profile.set_characteristics(characteristics)
        topic_profile.set_discussion_strategy(strategy)

        # 添加进度指标
        topic_profile.add_progress_indicator("问题分析完成")
        topic_profile.add_progress_indicator("专家意见收集")
        topic_profile.add_progress_indicator("共识形成")
        topic_profile.add_progress_indicator("行动计划制定")

        topic_profile.add_milestone("初始分析完成")
        topic_profile.add_milestone("深度讨论阶段")
        topic_profile.add_milestone("解决方案形成")
        topic_profile.add_milestone("行动计划制定")

        return topic_profile

    def get_topic_profile(self, topic_name: str) -> TopicProfile:
        """
        获取话题画像

        Args:
            topic_name: 话题名称

        Returns:
            话题画像
        """
        return self.analyzed_topics.get(topic_name)

    def list_topics(self) -> List[str]:
        """
        列出所有已分析的话题

        Returns:
            话题名称列表
        """
        return list(self.analyzed_topics.keys())

    def update_topic_progress(self, topic_name: str, progress_update: Dict[str, Any]):
        """
        更新话题进度

        Args:
            topic_name: 话题名称
            progress_update: 进度更新信息
        """
        if topic_name not in self.analyzed_topics:
            return

        profile = self.analyzed_topics[topic_name]

        # 更新进度指标
        if "progress_indicators" in progress_update:
            for indicator in progress_update["progress_indicators"]:
                profile.add_progress_indicator(indicator)

        # 更新里程碑
        if "milestone_updates" in progress_update:
            for update in progress_update["milestone_updates"]:
                milestone_index = update.get("index")
                status = update.get("status")
                if milestone_index is not None and status:
                    profile.update_milestone_status(milestone_index, status)

    def generate_discussion_guide(self, topic_profile: TopicProfile) -> Dict[str, Any]:
        """
        生成讨论指南

        Args:
            topic_profile: 话题画像

        Returns:
            讨论指南
        """
        guide = {
            "topic_overview": {
                "name": topic_profile.topic_name,
                "core_problem": topic_profile.task_analysis.core_problem,
                "complexity": topic_profile.task_analysis.complexity_level,
                "estimated_time": topic_profile.task_analysis.time_estimate
            },
            "participant_guidance": {
                "recommended_roles": topic_profile.task_analysis.recommended_roles,
                "participant_count": topic_profile.task_analysis.participant_count,
                "collaboration_patterns": topic_profile.task_analysis.collaboration_patterns
            },
            "discussion_strategy": topic_profile.discussion_strategy,
            "success_criteria": topic_profile.task_analysis.success_criteria,
            "risk_mitigation": topic_profile.task_analysis.mitigation_strategies,
            "progress_tracking": {
                "indicators": topic_profile.progress_indicators,
                "milestones": topic_profile.milestones
            }
        }

        return guide

    def export_profiles(self) -> str:
        """
        导出所有画像数据

        Returns:
            JSON格式的数据
        """
        data = {
            "exported_at": datetime.now().isoformat(),
            "profiles": {
                name: profile.to_dict() for name, profile in self.analyzed_topics.items()
            }
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def import_profiles(self, json_data: str):
        """
        导入画像数据

        Args:
            json_data: JSON格式的数据
        """
        try:
            data = json.loads(json_data)
            profiles_data = data.get("profiles", {})

            for name, profile_data in profiles_data.items():
                # 重建TaskAnalysis
                task_data = profile_data["task_analysis"]
                task_analysis = TaskAnalysis(
                    task_data["task_description"],
                    task_data["requester"]
                )

                # 恢复分析结果
                core_analysis = task_data["core_analysis"]
                task_analysis.set_core_analysis(
                    core_analysis["core_problem"],
                    core_analysis["sub_problems"],
                    core_analysis["complexity_level"],
                    core_analysis["time_estimate"]
                )

                domain_analysis = task_data["domain_analysis"]
                task_analysis.set_domain_analysis(
                    domain_analysis["primary_domain"],
                    domain_analysis["secondary_domains"],
                    domain_analysis["cross_domain_aspects"]
                )

                participant_analysis = task_data["participant_analysis"]
                task_analysis.set_participant_analysis(
                    participant_analysis["recommended_roles"],
                    participant_analysis["participant_count"],
                    participant_analysis["collaboration_patterns"]
                )

                requirements = task_data["requirements"]
                task_analysis.set_requirements(
                    requirements["resource_requirements"],
                    requirements["success_criteria"]
                )

                risk_analysis = task_data["risk_analysis"]
                task_analysis.set_risks(
                    risk_analysis["risk_factors"],
                    risk_analysis["mitigation_strategies"]
                )

                # 重建TopicProfile
                topic_profile = TopicProfile(name, task_analysis)
                topic_profile.set_characteristics(profile_data["topic_characteristics"])
                topic_profile.set_discussion_strategy(profile_data["discussion_strategy"])
                topic_profile.progress_indicators = profile_data.get("progress_indicators", [])
                topic_profile.milestones = profile_data.get("milestones", [])

                self.analyzed_topics[name] = topic_profile

        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Invalid data format: {str(e)}")

    def _extract_sections(self, text: str) -> Dict[str, str]:
        """提取文本中的章节"""
        sections = {}
        current_section = ""
        current_content = []

        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('##') or line.startswith('###'):
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content)
                current_section = line.replace('#', '').strip()
                current_content = []
            elif current_section:
                current_content.append(line)

        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def _extract_section_content(self, sections: Dict[str, str], keywords: List[str]) -> str:
        """提取章节内容"""
        for keyword in keywords:
            for section_name, content in sections.items():
                if keyword in section_name:
                    return content.strip()
        return ""

    def _extract_list_items(self, sections: Dict[str, str], keywords: List[str]) -> List[str]:
        """提取列表项"""
        content = self._extract_section_content(sections, keywords)
        if not content:
            return []

        items = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('- ') or line.startswith('• '):
                items.append(line[2:].strip())

        return items