# -*- coding:utf-8 -*-
"""
监督智能体
核对每一步实施的准确性和合理性，确保前后智能体工作能好好协调
"""

import json
import logging
from typing import Dict, Any, List, Optional
from Config.llm_config import get_chat_tongyi
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)


class SupervisionAgent:
    """监督智能体：核对每一步的准确性和合理性，确保智能体协调工作"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, enable_thinking=False)
        
        self.supervision_prompt = ChatPromptTemplate.from_template(
            """你是一个专业的智能体工作流监督专家，负责检查每个步骤的准确性和合理性，确保前后智能体能够协调工作。

当前步骤: {current_step}
步骤名称: {step_name}
步骤结果: {step_result}

前置步骤信息:
{previous_steps_info}

任务上下文:
{task_context}

请从以下维度进行评估：

1. **准确性检查**:
   - 步骤结果是否符合预期格式？
   - 步骤结果是否包含必要的数据？
   - 步骤执行是否成功完成？
   - 是否有明显的错误或异常？

2. **合理性检查**:
   - 步骤结果是否与前置步骤的结果一致？
   - 步骤结果是否与任务目标相符？
   - 步骤之间的数据传递是否合理？
   - 是否有数据丢失或不匹配的情况？

3. **协调性检查**:
   - 当前步骤的输出是否满足后续步骤的输入要求？
   - 数据格式是否与后续步骤的期望格式一致？
   - 是否有必要的数据字段缺失？
   - 前后步骤之间的依赖关系是否合理？

4. **质量评估**:
   - 步骤结果的质量如何？
   - 是否有需要改进的地方？
   - 是否有潜在的问题或风险？

请以JSON格式返回评估结果：
{{
    "accuracy": {{
        "score": 0.0-1.0,
        "is_valid": true/false,
        "issues": ["问题1", "问题2"],
        "details": "详细说明"
    }},
    "reasonableness": {{
        "score": 0.0-1.0,
        "is_reasonable": true/false,
        "issues": ["问题1", "问题2"],
        "details": "详细说明"
    }},
    "coordination": {{
        "score": 0.0-1.0,
        "is_coordinated": true/false,
        "issues": ["问题1", "问题2"],
        "details": "详细说明",
        "next_step_requirements": {{
            "required_fields": ["字段1", "字段2"],
            "data_format": "格式说明",
            "is_ready": true/false
        }}
    }},
    "quality": {{
        "score": 0.0-1.0,
        "assessment": "质量评估",
        "recommendations": ["建议1", "建议2"]
    }},
    "overall": {{
        "score": 0.0-1.0,
        "status": "pass/warning/fail",
        "summary": "总体评估摘要",
        "action_required": true/false,
        "action_items": ["需要采取的行动1", "需要采取的行动2"]
    }}
}}

请严格返回JSON格式，不要包含其他文本。
"""
        )
    
    def supervise_step(self, 
                      step_name: str,
                      step_result: Dict[str, Any],
                      previous_steps: List[Dict[str, Any]],
                      task_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        监督单个步骤的准确性和合理性
        
        Args:
            step_name: 步骤名称
            step_result: 步骤结果
            previous_steps: 前置步骤结果列表
            task_context: 任务上下文（文件信息、用户查询等）
            
        Returns:
            监督评估结果
        """
        try:
            # 准备前置步骤信息
            previous_steps_info = self._format_previous_steps(previous_steps)
            
            # 准备任务上下文
            task_context_str = json.dumps(task_context, ensure_ascii=False, default=str, indent=2)
            
            # 准备步骤结果（限制大小）
            step_result_str = json.dumps(step_result, ensure_ascii=False, default=str, indent=2)
            if len(step_result_str) > 5000:  # 限制大小
                step_result_str = step_result_str[:5000] + "... (数据已截断)"
            
            # 调用LLM进行评估
            prompt = self.supervision_prompt.format(
                current_step=f"步骤 {len(previous_steps) + 1}",
                step_name=step_name,
                step_result=step_result_str,
                previous_steps_info=previous_steps_info,
                task_context=task_context_str
            )
            
            response = self.llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 解析JSON响应
            try:
                # 提取JSON部分
                json_start = response_text.find('{')
                json_end = response_text.rfind('}')
                if json_start != -1 and json_end != -1:
                    json_str = response_text[json_start:json_end+1]
                    evaluation = json.loads(json_str)
                else:
                    raise ValueError("无法找到JSON格式的响应")
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ 监督评估响应解析失败: {e}")
                # 返回默认评估结果
                evaluation = self._default_evaluation(step_name, step_result)
            
            # 添加基础检查
            evaluation = self._add_basic_checks(evaluation, step_name, step_result, previous_steps)
            
            logger.info(f"✅ 步骤 {step_name} 监督完成，总体评分: {evaluation.get('overall', {}).get('score', 0):.2f}")
            return evaluation
            
        except Exception as e:
            logger.error(f"❌ 监督评估失败: {e}", exc_info=True)
            return self._default_evaluation(step_name, step_result, error=str(e))
    
    def _format_previous_steps(self, previous_steps: List[Dict[str, Any]]) -> str:
        """格式化前置步骤信息"""
        if not previous_steps:
            return "无前置步骤"
        
        formatted = []
        for i, step in enumerate(previous_steps, 1):
            step_name = step.get("step", f"步骤{i}")
            success = step.get("success", False)
            status = "✅ 成功" if success else "❌ 失败"
            formatted.append(f"{i}. {step_name}: {status}")
            
            # 如果有错误，添加错误信息
            if not success and step.get("error"):
                formatted.append(f"   错误: {step.get('error')}")
        
        return "\n".join(formatted)
    
    def _add_basic_checks(self, evaluation: Dict[str, Any],
                         step_name: str,
                         step_result: Dict[str, Any],
                         previous_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """添加基础检查"""
        issues = []
        
        # 检查步骤结果是否为空
        if not step_result:
            issues.append("步骤结果为空")
        
        # 检查是否有错误字段
        if isinstance(step_result, dict) and "error" in step_result:
            issues.append(f"步骤执行出错: {step_result.get('error')}")
        
        # 检查关键字段是否存在（根据步骤名称）
        if step_name == "statistics_calculation":
            if "calculations" not in step_result:
                issues.append("缺少 'calculations' 字段")
            elif not step_result.get("calculations"):
                issues.append("'calculations' 字段为空")
        
        elif step_name == "correlation_analysis":
            if "strong_correlations" not in step_result:
                issues.append("缺少 'strong_correlations' 字段")
        
        elif step_name == "semantic_analysis":
            if "semantic_analysis" not in step_result:
                issues.append("缺少 'semantic_analysis' 字段")
        
        elif step_name == "summary_analysis":
            if "analysis_summary" not in step_result:
                issues.append("缺少 'analysis_summary' 字段")
            elif not step_result.get("analysis_summary"):
                issues.append("'analysis_summary' 字段为空")
            if "chart_recommendations" not in step_result:
                issues.append("缺少 'chart_recommendations' 字段")
            elif not step_result.get("chart_recommendations"):
                issues.append("'chart_recommendations' 字段为空")
        
        elif step_name == "echarts_generation":
            if "charts" not in step_result:
                issues.append("缺少 'charts' 字段")
            elif not step_result.get("charts"):
                issues.append("'charts' 字段为空或没有生成图表")
        
        # 更新评估结果
        if issues:
            if "accuracy" not in evaluation:
                evaluation["accuracy"] = {}
            if "issues" not in evaluation["accuracy"]:
                evaluation["accuracy"]["issues"] = []
            evaluation["accuracy"]["issues"].extend(issues)
            evaluation["accuracy"]["is_valid"] = False
            evaluation["accuracy"]["score"] = max(0.0, evaluation.get("accuracy", {}).get("score", 1.0) - len(issues) * 0.2)
        
        return evaluation
    
    def _default_evaluation(self, step_name: str, step_result: Dict[str, Any], error: str = None) -> Dict[str, Any]:
        """返回默认评估结果"""
        return {
            "accuracy": {
                "score": 0.5,
                "is_valid": False,
                "issues": [error] if error else ["无法完成评估"],
                "details": error or "评估过程出错"
            },
            "reasonableness": {
                "score": 0.5,
                "is_reasonable": False,
                "issues": [],
                "details": "无法完成合理性评估"
            },
            "coordination": {
                "score": 0.5,
                "is_coordinated": False,
                "issues": [],
                "details": "无法完成协调性评估",
                "next_step_requirements": {
                    "required_fields": [],
                    "data_format": "未知",
                    "is_ready": False
                }
            },
            "quality": {
                "score": 0.5,
                "assessment": "无法完成质量评估",
                "recommendations": ["请检查步骤执行情况"]
            },
            "overall": {
                "score": 0.5,
                "status": "warning",
                "summary": "评估过程出错，无法完成完整评估",
                "action_required": True,
                "action_items": ["检查步骤执行情况", "查看错误日志"]
            }
        }
    
    def check_coordination(self,
                          current_step_result: Dict[str, Any],
                          next_step_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查当前步骤结果是否满足下一步骤的要求
        
        Args:
            current_step_result: 当前步骤结果
            next_step_requirements: 下一步骤的要求
            
        Returns:
            协调性检查结果
        """
        try:
            issues = []
            missing_fields = []
            
            # 检查必需字段
            required_fields = next_step_requirements.get("required_fields", [])
            for field in required_fields:
                if field not in current_step_result:
                    missing_fields.append(field)
                    issues.append(f"缺少必需字段: {field}")
            
            # 检查数据格式
            expected_format = next_step_requirements.get("data_format", "")
            if expected_format and not self._check_data_format(current_step_result, expected_format):
                issues.append(f"数据格式不符合要求: {expected_format}")
            
            # 检查数据是否为空
            if not current_step_result:
                issues.append("步骤结果为空")
            
            is_ready = len(missing_fields) == 0 and len(issues) == 0
            
            return {
                "is_ready": is_ready,
                "missing_fields": missing_fields,
                "issues": issues,
                "score": 1.0 if is_ready else max(0.0, 1.0 - len(issues) * 0.2)
            }
            
        except Exception as e:
            logger.error(f"❌ 协调性检查失败: {e}")
            return {
                "is_ready": False,
                "missing_fields": [],
                "issues": [f"检查过程出错: {str(e)}"],
                "score": 0.0
            }
    
    def _check_data_format(self, data: Any, expected_format: str) -> bool:
        """检查数据格式是否符合要求"""
        # 简单的格式检查逻辑
        if expected_format == "dict":
            return isinstance(data, dict)
        elif expected_format == "list":
            return isinstance(data, list)
        elif expected_format == "non_empty_dict":
            return isinstance(data, dict) and len(data) > 0
        elif expected_format == "non_empty_list":
            return isinstance(data, list) and len(data) > 0
        else:
            return True  # 如果不明确，返回True
