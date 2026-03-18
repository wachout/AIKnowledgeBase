# -*- coding: utf-8 -*-
"""
智能体基类
定义所有智能体的共同接口和功能
"""

import json
import logging
import sys
import os
import time
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
import requests
from dataclasses import dataclass, field

# Add the project root to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from Config.llm_config import get_chat_tongyi

# 导入工具系统
try:
    from ..tools.tool_manager import ToolManager, ToolExecutionStats
    from ..tools.skill_registry import SkillRegistry, AgentSkillSet, SkillContext, SkillResult
    from ..tools.base_tool import BaseTool, ToolResult
except ImportError:
    ToolManager = None
    ToolExecutionStats = None
    SkillRegistry = None
    AgentSkillSet = None
    SkillContext = None
    SkillResult = None
    BaseTool = None
    ToolResult = None

# 导入通信协议类
try:
    from .roundtable_discussion import MessageType, MessagePriority, AgentMessage
except ImportError:
    # 如果导入失败，定义简化的版本
    class MessageType(Enum):
        QUESTIONING = "questioning"
        RESPONSE = "response"
        COLLABORATION = "collaboration"
        CONSENSUS_UPDATE = "consensus_update"

    class MessagePriority(Enum):
        LOW = "low"
        NORMAL = "normal"
        HIGH = "high"
        CRITICAL = "critical"

    @dataclass
    class AgentMessage:
        sender: str = ""
        receiver: str = ""
        message_type: MessageType = MessageType.QUESTIONING
        priority: MessagePriority = MessagePriority.NORMAL
        content: Dict[str, Any] = field(default_factory=dict)


class AgentError(Exception):
    """智能体基础异常类"""
    pass


class LLMTimeoutError(AgentError):
    """LLM调用超时异常"""
    pass


class LLMNetworkError(AgentError):
    """LLM网络连接异常"""
    pass


class LLMContentError(AgentError):
    """LLM内容审核异常"""
    pass


class LLMFormatError(AgentError):
    """LLM响应格式异常"""
    pass


class LLMRateLimitError(AgentError):
    """LLM请求频率限制异常"""
    pass

logger = logging.getLogger(__name__)


class WorkingStyle(Enum):
    """工作风格枚举"""
    PROFESSIONAL_OBJECTIVE = "专业客观"
    AGGRESSIVE_INNOVATIVE = "激进创新"
    STEADY_CONSERVATIVE = "稳健保守"
    COLLABORATIVE_WINWIN = "合作共赢"
    RESULT_ORIENTED = "结果导向"


class BaseAgent:
    """智能体基类"""

    def __init__(self,
                 name: str,
                 role_definition: str,
                 professional_skills: List[str],
                 working_style: WorkingStyle,
                 behavior_guidelines: List[str],
                 output_format: str,
                 llm_instance=None):
        """
        初始化智能体

        Args:
            name: 智能体名称
            role_definition: 角色定义
            professional_skills: 专业技能列表
            working_style: 工作风格
            behavior_guidelines: 行为准则
            output_format: 输出格式规范
            llm_instance: LLM实例，如果为None则使用默认配置
        """
        self.name = name
        self.role_definition = role_definition
        self.professional_skills = professional_skills
        self.working_style = working_style
        self.behavior_guidelines = behavior_guidelines
        self.output_format = output_format

        # 初始化LLM
        if llm_instance is None:
            self.llm = get_chat_tongyi(temperature=0.7, enable_thinking=False)
        else:
            self.llm = llm_instance

        # 智能体状态
        self.conversation_history = []
        self.thinking_process = []
        self.collaboration_score = 0.0

        # 工具系统 - 增强版
        self.available_tools = []
        self.tool_usage_history = []
        self._tool_manager: Optional['ToolManager'] = None
        self._skill_registry: Optional['SkillRegistry'] = None
        self._skill_set: Optional['AgentSkillSet'] = None

        # 重试配置
        self.max_retries = 3
        self.retry_delay = 1.0  # 基础延迟时间（秒）
        self.timeout = 30.0  # LLM调用超时时间（秒）

        # 错误统计
        self.error_count = 0
        self.last_error_time = None
        self.success_count = 0
        self.consecutive_failures = 0
        self.health_status = "healthy"  # healthy, degraded, critical

        # 通信系统
        self.message_bus = None
        self.communication_protocol = None

    def think(self, topic: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        深度思考过程

        Args:
            topic: 讨论主题
            context: 讨论上下文

        Returns:
            思考结果字典
        """
        thinking_prompt = self._build_thinking_prompt(topic, context)
        thinking_result = None
        last_error = None

        try:
            # 使用重试机制调用LLM
            response_text = self._invoke_llm_with_retry(thinking_prompt, "深度思考")

            # 解析思考结果
            thinking_result = self._parse_thinking_response(response_text)

            # 记录思考过程
            self.thinking_process.append({
                'topic': topic,
                'context': context,
                'result': thinking_result,
                'timestamp': self._get_timestamp(),
                'success': True
            })

            logger.info(f"✅ {self.name} 深度思考完成")
            return thinking_result

        except LLMTimeoutError as e:
            last_error = e
            logger.error(f"⏰ {self.name} 思考超时: {e}")
            thinking_result = self._create_fallback_thinking(topic, context)
            thinking_result['error_type'] = 'timeout'
            return thinking_result

        except LLMNetworkError as e:
            last_error = e
            logger.error(f"🌐 {self.name} 思考网络错误: {e}")
            thinking_result = self._create_fallback_thinking(topic, context)
            thinking_result['error_type'] = 'network'
            return thinking_result

        except LLMContentError as e:
            last_error = e
            logger.error(f"🚫 {self.name} 思考内容审核失败: {e}")
            thinking_result = self._create_fallback_thinking(topic, context)
            thinking_result['error_type'] = 'content_filter'
            return thinking_result

        except LLMFormatError as e:
            last_error = e
            logger.error(f"📝 {self.name} 思考响应格式错误: {e}")
            thinking_result = self._create_fallback_thinking(topic, context)
            thinking_result['error_type'] = 'format_error'
            return thinking_result

        except LLMRateLimitError as e:
            last_error = e
            logger.error(f"🚦 {self.name} 思考频率限制: {e}")
            thinking_result = self._create_fallback_thinking(topic, context)
            thinking_result['error_type'] = 'rate_limit'
            return thinking_result

        except AgentError as e:
            last_error = e
            logger.error(f"❌ {self.name} 思考失败: {e}")
            thinking_result = self._create_fallback_thinking(topic, context)
            thinking_result['error_type'] = 'unknown'
            return thinking_result

        except Exception as e:
            last_error = e
            logger.error(f"💥 {self.name} 思考出现未预期的错误: {e}")
            thinking_result = self._create_fallback_thinking(topic, context)
            thinking_result['error_type'] = 'unexpected'
            return thinking_result

        finally:
            # 记录思考过程（如果之前没有记录成功的）
            if thinking_result is None:
                self.thinking_process.append({
                    'topic': topic,
                    'context': context,
                    'result': None,
                    'timestamp': self._get_timestamp(),
                    'success': False,
                    'error': str(last_error) if last_error else 'Unknown error'
                })

    def _build_thinking_prompt(self, topic: str, context: Dict[str, Any]) -> str:
        """构建思考提示"""
        # ⭐ 新增：提取针对我的质疑
        my_challenges = context.get('my_challenges', [])
        challenges_text = ""
        if my_challenges:
            challenges_text = "\n\n## ⚠️ 待回应的质疑\n"
            challenges_text += "上一轮讨论中，有人对你的观点提出了以下质疑，请在本轮讨论中优先回应：\n\n"
            for i, challenge in enumerate(my_challenges, 1):
                skeptic = challenge.get('skeptic', '质疑者')
                content = challenge.get('content', '')
                challenges_text += f"**质疑{i}** - 来自 {skeptic}:\n{content}\n\n"
        
        # 过滤掉不需要在prompt中显示的字段
        filtered_context = {k: v for k, v in context.items() 
                           if k not in ['my_challenges', 'has_pending_challenges']}
        
        prompt = f"""你是一位{self.role_definition}，具备以下专业技能：
{chr(10).join(f"- {skill}" for skill in self.professional_skills)}

你的工作风格是：{self.working_style.value}

行为准则：
{chr(10).join(f"- {guideline}" for guideline in self.behavior_guidelines)}
{challenges_text}
## 深度思考分析框架

**讨论主题：**
{topic}

**当前上下文：**
{json.dumps(filtered_context, ensure_ascii=False, indent=2)}

### 1. 核心思考序列 (Core Thinking Sequence)
请按照以下步骤进行深度思考：

**关注 (Attention)**:
- 识别讨论的核心问题和关键要素
- 明确讨论目标和期望结果

**需要 (Needs)**:
- 分析解决该问题需要哪些资源、信息和能力
- 识别潜在的挑战和障碍

**多种假设生成 (Multiple Hypotheses)**:
- 生成3-5种不同的解决方案或观点
- 考虑各种可能性和替代方案

**系统性验证 (Systematic Verification)**:
- 对每个假设进行验证和评估
- 使用逻辑推理、数据分析和专业知识进行验证

### 2. 多角度思考 (Multi-perspective Thinking)
请从以下维度分析问题：

**短期 vs 长期影响**:
- 短期内可能产生的影响
- 长期发展可能带来的变化

**微观 vs 宏观层面**:
- 个体/具体层面的影响
- 系统/整体层面的影响

**内部 vs 外部视角**:
- 组织内部的观点和利益
- 外部环境和社会影响

**理论与实践差距**:
- 理论上的最佳方案
- 实践中可行的解决方案

### 3. 证据支撑 (Evidence-based)
请提供以下证据支持：

**数据支持**:
- 相关统计数据和量化指标

**案例研究**:
- 类似问题的成功案例或失败教训

**行业报告**:
- 相关领域的研究报告和行业标准

**推理逻辑**:
- 清晰的推理过程和逻辑链条

### 4. 批判性思维 (Critical Thinking)
请进行以下批判性分析：

**识别假设**:
- 明确所有假设前提

**评估可靠性**:
- 评估信息的可靠性和准确性

**考虑替代解释**:
- 考虑其他可能的解释和观点

**识别潜在风险**:
- 识别潜在的风险和不确定性

### 5. 协作精神 (Collaboration)
作为讨论参与者，请：
- 积极回应其他专家的观点
- 寻找共识和共同点
- 提供建设性批评
- 促进讨论向深入发展

### 6. 专业与创新 (First Principles & Innovation)
**请务必遵守：** 在专业领域内不违背第一性原理，结论需逻辑可推理、可实施执行。
**同时请：** 在满足上述约束下，适当突破固有思维，增加创新思路，提出有建设性的新视角或方案。

## 输出格式
请按照以下格式输出你的思考结果：

**核心观点 (Core Opinion)**:
[你的主要观点和立场]

**详细分析 (Detailed Analysis)**:
[你的深度分析过程]

**证据支撑 (Evidence Support)**:
[数据、案例等证据]

**潜在风险 (Potential Risks)**:
[识别的风险和挑战]

**建议方案 (Recommended Solutions)**:
[具体的建议和解决方案]

**协作建议 (Collaboration Suggestions)**:
[对其他专家的建议和期望]

请保持专业、客观、建设性的讨论态度。
"""

        return prompt

    def _parse_thinking_response(self, response_text: str) -> Dict[str, Any]:
        """解析思考响应"""
        try:
            # 尝试提取结构化内容
            result = {
                'core_opinion': self._extract_section(response_text, '核心观点', '详细分析'),
                'detailed_analysis': self._extract_section(response_text, '详细分析', '证据支撑'),
                'evidence_support': self._extract_section(response_text, '证据支撑', '潜在风险'),
                'potential_risks': self._extract_section(response_text, '潜在风险', '建议方案'),
                'recommended_solutions': self._extract_section(response_text, '建议方案', '协作建议'),
                'collaboration_suggestions': self._extract_section(response_text, '协作建议', ''),
                'raw_response': response_text
            }
            return result
        except Exception as e:
            logger.warning(f"⚠️ 解析思考响应失败: {e}")
            return {
                'core_opinion': response_text[:200] + '...',
                'detailed_analysis': response_text,
                'raw_response': response_text
            }

    def _extract_section(self, text: str, start_marker: str, end_marker: str) -> str:
        """从文本中提取指定部分"""
        try:
            start_idx = text.find(start_marker)
            if start_idx == -1:
                return ""

            start_content = text.find(':', start_idx)
            if start_content == -1:
                start_content = start_idx + len(start_marker)

            if end_marker:
                end_idx = text.find(end_marker, start_content)
                if end_idx != -1:
                    return text[start_content:end_idx].strip()
                else:
                    return text[start_content:].strip()
            else:
                return text[start_content:].strip()

        except Exception as e:
            logger.warning(f"⚠️ 提取文本部分失败: {e}")
            return ""

    # =========================================================================
    # 通用响应处理方法 - 消除子类重复代码
    # =========================================================================

    def _extract_response_content(self, response) -> str:
        """
        统一提取 LLM 响应内容
        
        Args:
            response: LLM 响应对象（可能是字符串、具有 content 属性的对象等）
            
        Returns:
            响应文本内容
        """
        if response is None:
            return ""
        if hasattr(response, 'content'):
            return response.content
        if isinstance(response, str):
            return response
        return str(response)

    def _extract_sections(self, text: str) -> Dict[str, str]:
        """
        提取 Markdown 章节内容
        
        从文本中提取以 ## 或 ### 开头的章节标题和内容。
        
        Args:
            text: 包含 Markdown 章节的文本
            
        Returns:
            章节字典，键为章节标题，值为章节内容
        """
        sections = {}
        current_section = ""
        current_content = []

        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('##') or line.startswith('###'):
                # 保存之前的章节
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content)
                # 开始新章节
                current_section = line.replace('#', '').strip()
                current_content = []
            elif current_section:
                current_content.append(line)

        # 保存最后一个章节
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def _parse_structured_response(self, response: str, key_name: str, 
                                   additional_fields: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        通用的结构化响应解析
        
        将响应文本解析为标准结构，包含原始响应、解析的章节和时间戳。
        
        Args:
            response: 响应文本
            key_name: 主键名称（如 'analysis_report', 'facilitation_summary'）
            additional_fields: 额外字段（可选）
            
        Returns:
            结构化响应字典
        """
        result = {
            key_name: response,
            "parsed_sections": self._extract_sections(response),
            "timestamp": self._get_timestamp()
        }
        
        # 添加额外字段
        if additional_fields:
            result.update(additional_fields)
        
        return result

    def _parse_json_response(self, text: str, fallback: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        尝试解析 JSON 格式的响应
        
        Args:
            text: 响应文本
            fallback: 解析失败时的后备值
            
        Returns:
            解析后的字典或后备值
        """
        try:
            # 尝试直接解析
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 JSON 块
        try:
            import re
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
            if json_match:
                return json.loads(json_match.group(1))
        except (json.JSONDecodeError, Exception):
            pass
        
        return fallback if fallback is not None else {"raw_text": text}

    def _extract_list_items(self, text: str, marker: str = "-") -> List[str]:
        """
        从文本中提取列表项
        
        Args:
            text: 包含列表的文本
            marker: 列表标记（默认为 '-'）
            
        Returns:
            列表项列表
        """
        items = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith(marker):
                item = line[len(marker):].strip()
                if item:
                    items.append(item)
        return items

    def _extract_numbered_items(self, text: str) -> List[str]:
        """
        从文本中提取编号列表项
        
        Args:
            text: 包含编号列表的文本
            
        Returns:
            编号项内容列表（不含编号）
        """
        import re
        items = []
        pattern = r'^\s*\d+[\.\)]\s*(.+)$'
        for line in text.split('\n'):
            match = re.match(pattern, line)
            if match:
                item = match.group(1).strip()
                if item:
                    items.append(item)
        return items

    def _invoke_llm_with_retry(self, prompt: str, operation_name: str = "LLM调用") -> str:
        """
        带重试机制的LLM调用

        Args:
            prompt: 提示文本
            operation_name: 操作名称，用于日志记录

        Returns:
            LLM响应文本

        Raises:
            AgentError: 当所有重试都失败时抛出
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"🤖 {self.name} {operation_name} - 尝试 {attempt + 1}/{self.max_retries}")

                # 设置超时
                start_time = time.time()

                # 调用LLM
                response = self.llm.invoke(prompt)

                # 检查响应格式
                if not hasattr(response, 'content') and not isinstance(response, str):
                    raise LLMFormatError(f"LLM响应格式异常: {type(response)}")

                response_text = response.content if hasattr(response, 'content') else str(response)

                # 检查响应内容是否为空
                if not response_text or response_text.strip() == "":
                    raise LLMFormatError("LLM返回空响应")

                elapsed_time = time.time() - start_time
                logger.debug(f"✅ {self.name} {operation_name} 成功 (耗时: {elapsed_time:.2f}s)")

                # 更新成功统计
                self.success_count += 1
                self.consecutive_failures = 0
                self._update_health_status()

                return response_text

            except TimeoutError as e:
                last_exception = LLMTimeoutError(f"LLM调用超时: {e}")
                logger.warning(f"⏰ {self.name} {operation_name} 超时 (尝试 {attempt + 1}/{self.max_retries}): {e}")

            except requests.exceptions.RequestException as e:
                last_exception = LLMNetworkError(f"网络连接错误: {e}")
                logger.warning(f"🌐 {self.name} {operation_name} 网络错误 (尝试 {attempt + 1}/{self.max_retries}): {e}")

            except Exception as e:
                error_str = str(e).lower()

                # 识别不同类型的错误
                if any(keyword in error_str for keyword in ['rate limit', 'quota', '429']):
                    last_exception = LLMRateLimitError(f"请求频率限制: {e}")
                    logger.warning(f"🚦 {self.name} {operation_name} 频率限制 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                elif any(keyword in error_str for keyword in ['content', 'audit', 'filter', 'sensitive']):
                    last_exception = LLMContentError(f"内容审核拦截: {e}")
                    logger.warning(f"🚫 {self.name} {operation_name} 内容审核 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                elif any(keyword in error_str for keyword in ['format', 'parse', 'json']):
                    last_exception = LLMFormatError(f"响应格式错误: {e}")
                    logger.warning(f"📝 {self.name} {operation_name} 格式错误 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                else:
                    last_exception = AgentError(f"未知LLM错误: {e}")
                    logger.warning(f"❓ {self.name} {operation_name} 未知错误 (尝试 {attempt + 1}/{self.max_retries}): {e}")

            # 如果不是最后一次尝试，则等待后重试
            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2 ** attempt)  # 指数退避
                logger.info(f"⏳ {self.name} {operation_name} 等待 {delay:.1f} 秒后重试...")
                time.sleep(delay)

        # 所有重试都失败
        self.error_count += 1
        self.last_error_time = time.time()
        self.consecutive_failures += 1
        self._update_health_status()

        logger.error(f"❌ {self.name} {operation_name} 在 {self.max_retries} 次尝试后仍然失败")
        raise last_exception

    def _create_fallback_thinking(self, topic: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """创建后备思考结果"""
        return {
            'core_opinion': f"关于{topic}的初步观点",
            'detailed_analysis': f"基于{self.role_definition}的专业角度分析{topic}",
            'evidence_support': "需要更多数据和信息进行分析",
            'potential_risks': "需要进一步评估风险",
            'recommended_solutions': f"建议从{self.professional_skills[0] if self.professional_skills else '专业领域'}角度深入研究",
            'collaboration_suggestions': "期待其他专家的观点和建议",
            'raw_response': f"后备思考结果：{topic}"
        }

    def speak(self, discussion_context: Dict[str, Any], previous_speeches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        生成发言内容

        Args:
            discussion_context: 讨论上下文
            previous_speeches: 之前的发言列表

        Returns:
            发言内容字典
        """
        speak_prompt = self._build_speak_prompt(discussion_context, previous_speeches)
        speech_result = None
        last_error = None

        try:
            # 使用重试机制调用LLM
            response_text = self._invoke_llm_with_retry(speak_prompt, "生成发言")

            speech_result = {
                'agent_name': self.name,
                'role': self.role_definition,
                'content': response_text,
                'timestamp': self._get_timestamp(),
                'working_style': self.working_style.value,
                'professional_skills': self.professional_skills,
                'success': True
            }

            # 记录对话历史
            self.conversation_history.append(speech_result)

            logger.info(f"✅ {self.name} 发言完成")
            return speech_result

        except LLMTimeoutError as e:
            last_error = e
            logger.error(f"⏰ {self.name} 发言超时: {e}")
            return self._create_fallback_speech(discussion_context, 'timeout')

        except LLMNetworkError as e:
            last_error = e
            logger.error(f"🌐 {self.name} 发言网络错误: {e}")
            return self._create_fallback_speech(discussion_context, 'network')

        except LLMContentError as e:
            last_error = e
            logger.error(f"🚫 {self.name} 发言内容审核失败: {e}")
            return self._create_fallback_speech(discussion_context, 'content_filter')

        except LLMFormatError as e:
            last_error = e
            logger.error(f"📝 {self.name} 发言响应格式错误: {e}")
            return self._create_fallback_speech(discussion_context, 'format_error')

        except LLMRateLimitError as e:
            last_error = e
            logger.error(f"🚦 {self.name} 发言频率限制: {e}")
            return self._create_fallback_speech(discussion_context, 'rate_limit')

        except AgentError as e:
            last_error = e
            logger.error(f"❌ {self.name} 发言失败: {e}")
            return self._create_fallback_speech(discussion_context, 'unknown')

        except Exception as e:
            last_error = e
            logger.error(f"💥 {self.name} 发言出现未预期的错误: {e}")
            return self._create_fallback_speech(discussion_context, 'unexpected')

        finally:
            # 确保所有发言都被记录到对话历史
            if speech_result is None:
                failed_speech = self._create_fallback_speech(discussion_context, 'final_fallback')
                failed_speech['success'] = False
                failed_speech['error'] = str(last_error) if last_error else 'Unknown error'
                self.conversation_history.append(failed_speech)

    def _update_health_status(self):
        """更新智能体健康状态"""
        total_operations = self.success_count + self.error_count

        if total_operations == 0:
            self.health_status = "healthy"
            return

        success_rate = self.success_count / total_operations

        if self.consecutive_failures >= 3:
            self.health_status = "critical"
        elif self.consecutive_failures >= 1 or success_rate < 0.5:
            self.health_status = "degraded"
        else:
            self.health_status = "healthy"

    def get_health_status(self) -> Dict[str, Any]:
        """获取智能体健康状态信息"""
        total_operations = self.success_count + self.error_count
        success_rate = (self.success_count / total_operations) if total_operations > 0 else 1.0

        return {
            "agent_name": self.name,
            "health_status": self.health_status,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": success_rate,
            "consecutive_failures": self.consecutive_failures,
            "last_error_time": self.last_error_time
        }

    def reset_error_stats(self):
        """重置错误统计（用于恢复后）"""
        self.error_count = 0
        self.consecutive_failures = 0
        self.last_error_time = None
        self._update_health_status()

    def set_communication_system(self, message_bus, communication_protocol):
        """设置通信系统"""
        self.message_bus = message_bus
        self.communication_protocol = communication_protocol

        # 订阅自己的消息
        if message_bus:
            message_bus.subscribe(self.name, self._handle_message)

    def _handle_message(self, message):
        """处理接收到的消息"""
        try:
            # 验证消息是否发给自己的
            if message.receiver != self.name and message.receiver != "":
                return

            # 根据消息类型处理
            if message.message_type.value == "questioning":
                self._handle_questioning_message(message)
            elif message.message_type.value == "response":
                self._handle_response_message(message)
            elif message.message_type.value == "collaboration":
                self._handle_collaboration_message(message)
            elif message.message_type.value == "consensus_update":
                self._handle_consensus_message(message)
            elif message.message_type.value == "direct_discussion":
                self._handle_direct_discussion_message(message)
            elif message.message_type.value == "inter_agent_dialogue":
                self._handle_inter_agent_dialogue_message(message)
            else:
                logger.debug(f"{self.name} 收到未处理的消息类型: {message.message_type.value}")

        except Exception as e:
            logger.error(f"{self.name} 处理消息失败: {e}")

    def _handle_questioning_message(self, message):
        """处理质疑消息"""
        # 默认实现，子类可以重写
        logger.info(f"{self.name} 收到质疑消息: {message.content.get('questioning_content', '')[:100]}...")

    def _handle_response_message(self, message):
        """处理回应消息"""
        # 默认实现，子类可以重写
        logger.info(f"{self.name} 收到回应消息: {message.content.get('response_content', '')[:100]}...")

    def _handle_collaboration_message(self, message):
        """处理协作消息"""
        # 默认实现，子类可以重写
        logger.info(f"{self.name} 收到协作消息: {message.content.get('collaboration_content', '')[:100]}...")

    def _handle_consensus_message(self, message):
        """处理共识消息"""
        # 默认实现，子类可以重写
        logger.info(f"{self.name} 收到共识更新: 水平 {message.content.get('consensus_level', 0.0)}")

    def _handle_direct_discussion_message(self, message):
        """处理直接讨论消息"""
        # 默认实现，子类可以重写
        discussion_type = message.content.get('discussion_type', 'unknown')
        discussion_content = message.content.get('discussion_content', '')[:100]
        logger.info(f"{self.name} 收到直接讨论消息 ({discussion_type}): {discussion_content}...")

    def _handle_inter_agent_dialogue_message(self, message):
        """处理智能体间对话消息"""
        # 默认实现，子类可以重写
        dialogue_content = message.content.get('dialogue_content', '')[:100]
        logger.info(f"{self.name} 收到智能体间对话: {dialogue_content}...")

    def send_message(self, receiver: str, message_type, content: Dict[str, Any],
                    priority="normal", conversation_id=None):
        """发送消息"""
        if not self.message_bus or not self.communication_protocol:
            logger.warning(f"{self.name} 的通信系统未初始化，无法发送消息")
            return None

        try:
            # 创建消息
            message = AgentMessage(
                sender=self.name,
                receiver=receiver,
                message_type=message_type,
                priority=MessagePriority(priority),
                content=content,
                conversation_id=conversation_id
            )

            # 发送消息
            success = self.message_bus.send_message(message)
            if success:
                logger.debug(f"{self.name} 发送消息成功: {message_type.value} -> {receiver}")
            else:
                logger.error(f"{self.name} 发送消息失败: {message_type.value} -> {receiver}")

            return message if success else None

        except Exception as e:
            logger.error(f"{self.name} 发送消息异常: {e}")
            return None
    
    # =========================================================================
    # 主动交互能力 - 支持专家间直接对话
    # =========================================================================
    
    def initiate_interaction(self, target: str, interaction_type: str, 
                            content: Dict[str, Any], round_number: int = 0) -> Optional[str]:
        """
        主动发起交互
        
        Args:
            target: 目标智能体名称
            interaction_type: 交互类型 (debate, clarification, collaboration, challenge)
            content: 交互内容
            round_number: 所属轮次
            
        Returns:
            消息 ID 或 None
        """
        if not self.communication_protocol or not self.message_bus:
            logger.warning(f"{self.name} 的通信系统未初始化，无法发起交互")
            return None
        
        try:
            # 根据交互类型选择契约
            contract_mapping = {
                "debate": "direct_debate",
                "clarification": "clarification_request",
                "collaboration": "collaboration_proposal",
                "challenge": "questioning",
                "support": "expert_response"
            }
            
            contract_name = contract_mapping.get(interaction_type, "open_question")
            
            # 使用契约创建消息
            message = self.communication_protocol.create_contracted_message(
                contract_name=contract_name,
                sender=self.name,
                receiver=target,
                content=content,
                round_number=round_number
            )
            
            if message:
                self.message_bus.send_message(message)
                logger.info(f"{self.name} 发起 {interaction_type} 交互与 {target}")
                return message.message_id
            
            return None
            
        except Exception as e:
            logger.error(f"{self.name} 发起交互失败: {e}")
            return None
    
    def respond_to_interaction(self, original_message_id: str, response_content: Dict[str, Any],
                              round_number: int = 0) -> bool:
        """
        响应交互请求
        
        Args:
            original_message_id: 原始消息 ID
            response_content: 响应内容
            round_number: 所属轮次
            
        Returns:
            是否成功
        """
        if not self.communication_protocol or not self.message_bus:
            return False
        
        try:
            # 创建响应消息
            message = self.communication_protocol.create_contracted_message(
                contract_name="expert_response",
                sender=self.name,
                receiver="",  # 响应通常发给原始发送者
                content=response_content,
                round_number=round_number,
                parent_message_id=original_message_id
            )
            
            if message:
                self.message_bus.send_message(message)
                self.communication_protocol.mark_response_received(original_message_id, message)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"{self.name} 响应交互失败: {e}")
            return False
    
    def can_interact_with(self, target: str, interaction_type: str) -> bool:
        """
        检查是否可以与目标进行指定类型的交互
        
        Args:
            target: 目标智能体名称
            interaction_type: 交互类型
            
        Returns:
            是否可以交互
        """
        # 不能与自己交互
        if target == self.name:
            return False
        
        # 检查通信系统是否已初始化
        if not self.communication_protocol:
            return False
        
        # 检查契约是否存在
        contract_mapping = {
            "debate": "direct_debate",
            "clarification": "clarification_request",
            "collaboration": "collaboration_proposal",
            "challenge": "questioning"
        }
        
        contract_name = contract_mapping.get(interaction_type)
        if contract_name and hasattr(self.communication_protocol, 'contract_registry'):
            return self.communication_protocol.contract_registry.has(contract_name)
        
        return True  # 默认允许
    
    def get_interaction_suggestions(self, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        获取建议的交互（基于当前上下文）
        
        Args:
            context: 当前讨论上下文
            
        Returns:
            交互建议列表
        """
        suggestions = []
        
        if not context:
            return suggestions
        
        # 分析最近的讨论内容
        recent_speeches = context.get('recent_speeches', [])
        divergence_points = context.get('divergence_points', [])
        
        # 基于分歧点建议辩论
        for divergence in divergence_points[:2]:
            involved = divergence.get('involved_agents', [])
            if self.name not in involved and involved:
                suggestions.append({
                    "target": involved[0],
                    "interaction_type": "debate",
                    "reason": f"关于 '{divergence.get('description', 'N/A')}' 的分歧",
                    "priority": 0.8
                })
        
        # 基于最近发言建议澄清或支持
        for speech in recent_speeches[-3:]:
            speaker = speech.get('agent_name', '')
            if speaker and speaker != self.name:
                # 可以请求澄清或表示支持
                suggestions.append({
                    "target": speaker,
                    "interaction_type": "clarification",
                    "reason": f"对 {speaker} 的观点请求澄清",
                    "priority": 0.5
                })
        
        return suggestions[:5]  # 最多返回 5 个建议

    def _build_speak_prompt(self, discussion_context: Dict[str, Any], previous_speeches: List[Dict[str, Any]]) -> str:
        """构建发言提示"""
        previous_speeches_text = ""
        if previous_speeches:
            speeches = []
            for speech in previous_speeches[-5:]:  # 只显示最近5条发言
                speeches.append(f"**{speech.get('agent_name', 'Unknown')}** ({speech.get('role', '')}): {speech.get('content', '')[:200]}...")
            previous_speeches_text = "\n".join(speeches)
        
        # ⭐ 新增：提取针对我的质疑
        my_challenges = discussion_context.get('my_challenges', [])
        challenges_section = ""
        if my_challenges:
            challenges_section = "\n## ⚠️ 待回应的质疑\n"
            challenges_section += "上一轮讨论中，以下质疑针对你的观点，请在发言中优先回应：\n\n"
            for i, challenge in enumerate(my_challenges, 1):
                skeptic = challenge.get('skeptic', '质疑者')
                content = challenge.get('content', '')
                round_num = challenge.get('round', '?')
                challenges_section += f"**质疑{i}** (第{round_num}轮, 来自{skeptic}):\n{content[:300]}\n\n"

        prompt = f"""你是一位{self.role_definition}，具备以下专业技能：
{chr(10).join(f"- {skill}" for skill in self.professional_skills)}

你的工作风格是：{self.working_style.value}

## 当前讨论上下文

**讨论主题**: {discussion_context.get('topic', '')}
**当前轮次**: 第{discussion_context.get('round', 1)}轮
**讨论目标**: {discussion_context.get('objective', '')}

**讨论历史**:
{previous_speeches_text or "这是第一轮讨论"}
{challenges_section}
## 你的发言要求

请基于你的专业背景和工作风格，提供建设性的意见。发言应该：

1. **基于你的思考过程** - 参考你之前的深度分析
2. **回应其他专家** - 积极与他人观点进行互动
3. **回应质疑** - 如果有待回应的质疑，请优先针对性地回应
4. **提供具体建议** - 包含可操作的方案
5. **保持建设性** - 即使有不同意见也要尊重他人

请保持专业、客观、建设性的讨论态度。

你的发言："""

        return prompt

    def _create_fallback_speech(self, discussion_context: Dict[str, Any], error_type: str = None) -> Dict[str, Any]:
        """创建后备发言"""
        topic = discussion_context.get('topic', '该主题')

        # 根据错误类型生成不同的后备内容
        if error_type == 'timeout':
            content = f"由于系统响应超时，我暂时无法提供详细分析。但基于{self.professional_skills[0] if self.professional_skills else '专业经验'}，我认为{topic}是一个值得深入探讨的重要议题。"
        elif error_type == 'network':
            content = f"由于网络连接问题，我当前无法获取完整信息。但从{self.professional_skills[0] if self.professional_skills else '专业角度'}来看，{topic}需要我们共同关注和研究。"
        elif error_type == 'content_filter':
            content = f"由于内容审核机制的限制，我需要调整表达方式。但我坚持认为{topic}值得我们专业探讨和深入分析。"
        elif error_type == 'rate_limit':
            content = f"由于请求频率限制，我暂时无法提供完整分析。但我相信{topic}是一个值得我们继续讨论的重要话题。"
        else:
            content = f"基于{self.professional_skills[0] if self.professional_skills else '专业知识'}，我认为{topic}需要进一步讨论和深入分析。"

        return {
            'agent_name': self.name,
            'role': self.role_definition,
            'content': content,
            'timestamp': self._get_timestamp(),
            'working_style': self.working_style.value,
            'professional_skills': self.professional_skills,
            'is_fallback': True,
            'error_type': error_type
        }

    # =========================================================================
    # 工具系统集成 - 增强版
    # =========================================================================
    
    def set_tool_manager(self, tool_manager: 'ToolManager'):
        """
        设置工具管理器
        
        Args:
            tool_manager: ToolManager 实例
        """
        self._tool_manager = tool_manager
        logger.info(f"{self.name} 已绑定工具管理器")
    
    def set_skill_registry(self, skill_registry: 'SkillRegistry'):
        """
        设置技能注册中心
        
        Args:
            skill_registry: SkillRegistry 实例
        """
        self._skill_registry = skill_registry
        logger.info(f"{self.name} 已绑定技能注册中心")
    
    def set_skill_set(self, skill_set: 'AgentSkillSet'):
        """
        设置智能体技能集
        
        Args:
            skill_set: AgentSkillSet 实例
        """
        self._skill_set = skill_set
        logger.info(f"{self.name} 已绑定技能集: {len(skill_set.skills)} 个技能")
    
    def register_tool(self, tool: 'BaseTool'):
        """
        注册工具到智能体
        
        Args:
            tool: BaseTool 实例
        """
        if self._tool_manager:
            self._tool_manager.register_tool(tool)
            self.available_tools.append(tool.name)
            logger.info(f"{self.name} 注册工具: {tool.name}")
        else:
            logger.warning(f"{self.name} 工具管理器未设置，无法注册工具")
    
    def register_tools(self, tools: List['BaseTool']):
        """
        批量注册工具
        
        Args:
            tools: BaseTool 实例列表
        """
        for tool in tools:
            self.register_tool(tool)
    
    def enable_skill(self, skill_name: str):
        """
        为智能体启用技能
        
        Args:
            skill_name: 技能名称
        """
        if self._skill_set:
            self._skill_set.enable_skill(skill_name)
            logger.info(f"{self.name} 启用技能: {skill_name}")
        else:
            logger.warning(f"{self.name} 技能集未设置，无法启用技能")
    
    def disable_skill(self, skill_name: str):
        """
        为智能体禁用技能
        
        Args:
            skill_name: 技能名称
        """
        if self._skill_set:
            self._skill_set.disable_skill(skill_name)
            logger.info(f"{self.name} 禁用技能: {skill_name}")
    
    def get_available_tools(self) -> List[str]:
        """
        获取可用工具列表
        
        Returns:
            工具名称列表
        """
        if self._tool_manager:
            return self._tool_manager.list_tools()
        return self.available_tools
    
    def get_available_skills(self) -> List[str]:
        """
        获取可用技能列表
        
        Returns:
            技能名称列表
        """
        if self._skill_set:
            return list(self._skill_set.enabled_skills)
        return []
    
    def use_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用工具 - 增强版，通过 ToolManager 执行

        Args:
            tool_name: 工具名称
            parameters: 工具参数

        Returns:
            工具使用结果
        """
        timestamp = self._get_timestamp()
        
        # 如果有工具管理器，使用它来执行
        if self._tool_manager:
            try:
                tool_result = self._tool_manager.execute_tool(
                    tool_name=tool_name,
                    parameters=parameters,
                    context={"agent_name": self.name}
                )
                
                result = {
                    'tool_name': tool_name,
                    'parameters': parameters,
                    'success': tool_result.success,
                    'result': tool_result.data if tool_result.success else None,
                    'error': tool_result.error,
                    'execution_time': tool_result.execution_time,
                    'quality_assessment': tool_result.quality_assessment,
                    'timestamp': timestamp
                }
                
                self.tool_usage_history.append(result)
                
                if tool_result.success:
                    logger.info(f"{self.name} 成功使用工具: {tool_name}")
                else:
                    logger.warning(f"{self.name} 工具执行失败: {tool_name} - {tool_result.error}")
                
                return result
                
            except Exception as e:
                logger.error(f"{self.name} 工具调用异常: {tool_name} - {e}")
                result = {
                    'tool_name': tool_name,
                    'parameters': parameters,
                    'success': False,
                    'result': None,
                    'error': str(e),
                    'timestamp': timestamp
                }
                self.tool_usage_history.append(result)
                return result
        
        # 后备：模拟执行
        result = {
            'tool_name': tool_name,
            'parameters': parameters,
            'success': True,
            'result': f"工具 {tool_name} 执行完成（模拟）",
            'error': None,
            'timestamp': timestamp
        }
        self.tool_usage_history.append(result)
        return result
    
    def use_skill(self, skill_name: str, parameters: Dict[str, Any],
                  context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        使用技能
        
        Args:
            skill_name: 技能名称
            parameters: 技能参数
            context: 执行上下文
            
        Returns:
            技能执行结果
        """
        timestamp = self._get_timestamp()
        
        # 检查技能是否启用
        if self._skill_set and skill_name not in self._skill_set.enabled_skills:
            logger.warning(f"{self.name} 技能未启用: {skill_name}")
            return {
                'skill_name': skill_name,
                'success': False,
                'error': f"技能 {skill_name} 未启用",
                'timestamp': timestamp
            }
        
        # 通过技能注册中心执行
        if self._skill_registry:
            try:
                # 构建技能上下文
                skill_context = SkillContext(
                    agent_name=self.name,
                    agent_role=self.role_definition,
                    discussion_topic=context.get('topic', '') if context else '',
                    round_number=context.get('round', 0) if context else 0,
                    conversation_history=self.conversation_history[-5:],
                    tool_manager=self._tool_manager,
                    additional_context=context or {}
                ) if SkillContext else None
                
                # 执行技能
                skill_result = self._skill_registry.execute_skill(
                    skill_name=skill_name,
                    parameters=parameters,
                    context=skill_context
                )
                
                result = {
                    'skill_name': skill_name,
                    'parameters': parameters,
                    'success': skill_result.success,
                    'result': skill_result.data if skill_result.success else None,
                    'error': skill_result.error,
                    'execution_time': skill_result.execution_time,
                    'tools_used': skill_result.tools_used,
                    'quality_score': skill_result.quality_score,
                    'timestamp': timestamp
                }
                
                if skill_result.success:
                    logger.info(f"{self.name} 成功使用技能: {skill_name}")
                else:
                    logger.warning(f"{self.name} 技能执行失败: {skill_name} - {skill_result.error}")
                
                return result
                
            except Exception as e:
                logger.error(f"{self.name} 技能调用异常: {skill_name} - {e}")
                return {
                    'skill_name': skill_name,
                    'parameters': parameters,
                    'success': False,
                    'result': None,
                    'error': str(e),
                    'timestamp': timestamp
                }
        
        # 后备：模拟执行
        logger.warning(f"{self.name} 技能注册中心未设置，使用模拟执行")
        return {
            'skill_name': skill_name,
            'parameters': parameters,
            'success': True,
            'result': f"技能 {skill_name} 执行完成（模拟）",
            'error': None,
            'timestamp': timestamp
        }
    
    def execute_pipeline(self, pipeline_name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具流水线
        
        Args:
            pipeline_name: 流水线名称
            input_data: 输入数据
            
        Returns:
            流水线执行结果
        """
        timestamp = self._get_timestamp()
        
        if self._tool_manager:
            try:
                result = self._tool_manager.execute_pipeline(
                    pipeline_name=pipeline_name,
                    input_data=input_data,
                    context={"agent_name": self.name}
                )
                
                logger.info(f"{self.name} 执行流水线: {pipeline_name}")
                return {
                    'pipeline_name': pipeline_name,
                    'success': result.get('success', False),
                    'results': result.get('results', []),
                    'timestamp': timestamp
                }
                
            except Exception as e:
                logger.error(f"{self.name} 流水线执行异常: {pipeline_name} - {e}")
                return {
                    'pipeline_name': pipeline_name,
                    'success': False,
                    'error': str(e),
                    'timestamp': timestamp
                }
        
        logger.warning(f"{self.name} 工具管理器未设置，无法执行流水线")
        return {
            'pipeline_name': pipeline_name,
            'success': False,
            'error': "工具管理器未设置",
            'timestamp': timestamp
        }
    
    def get_tool_stats(self) -> Dict[str, Any]:
        """
        获取工具使用统计
        
        Returns:
            工具使用统计信息
        """
        if self._tool_manager:
            return self._tool_manager.get_execution_stats()
        
        # 从历史记录计算
        total = len(self.tool_usage_history)
        success = sum(1 for h in self.tool_usage_history if h.get('success', False))
        
        return {
            'total_executions': total,
            'successful_executions': success,
            'failed_executions': total - success,
            'success_rate': success / total if total > 0 else 0.0
        }

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()

    def get_status(self) -> Dict[str, Any]:
        """获取智能体状态"""
        return {
            'name': self.name,
            'role': self.role_definition,
            'working_style': self.working_style.value,
            'collaboration_score': self.collaboration_score,
            'conversation_count': len(self.conversation_history),
            'thinking_count': len(self.thinking_process),
            'tool_usage_count': len(self.tool_usage_history)
        }

    def get_system_prompt(self) -> str:
        """
        获取智能体的系统提示词
        
        Returns:
            智能体的完整系统提示词
        """
        skills_text = "\n".join(f"- {skill}" for skill in self.professional_skills)
        guidelines_text = "\n".join(f"- {guideline}" for guideline in self.behavior_guidelines)
        
        prompt = f"""你是一位{self.role_definition}，具备以下专业技能：
{skills_text}

你的工作风格是：{self.working_style.value}

行为准则：
{guidelines_text}

输出格式规范：
{self.output_format}

请保持专业、客观、建设性的讨论态度。"""
        
        return prompt

    def to_config_dict(self) -> Dict[str, Any]:
        """
        导出智能体的完整配置信息
        
        用于持久化保存智能体的配置，包含名称、角色定义、
        专业技能、工作风格、行为准则、系统提示词等。
        
        Returns:
            智能体配置字典
        """
        from datetime import datetime
        
        config = {
            "agent_id": getattr(self, 'agent_id', self.name),
            "agent_name": self.name,
            "role": getattr(self, 'role', 'base_agent'),
            "role_definition": self.role_definition,
            "professional_skills": self.professional_skills,
            "working_style": self.working_style.value,
            "behavior_guidelines": self.behavior_guidelines,
            "output_format": self.output_format,
            "system_prompt": self.get_system_prompt(),
            "health_status": self.health_status,
            "created_at": datetime.now().isoformat()
        }
        
        # 添加子类可能定义的额外属性
        if hasattr(self, 'domain'):
            config["domain"] = self.domain
        if hasattr(self, 'expertise'):
            config["expertise"] = self.expertise
        if hasattr(self, 'target_expert'):
            config["target_expert"] = getattr(self, 'target_expert', None)
        if hasattr(self, 'target_expert_domain'):
            config["target_expert_domain"] = getattr(self, 'target_expert_domain', None)
        
        return config