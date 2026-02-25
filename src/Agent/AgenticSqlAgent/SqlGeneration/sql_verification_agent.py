# -*- coding:utf-8 -*-
"""
SQL核对输出智能体
核对SQL执行结果是否满足用户查询需求
"""

import json
import re
from typing import Dict, Any, List
from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi


class SqlVerificationAgent:
    """SQL核对输出智能体：核对SQL执行结果是否满足用户查询需求"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)
        
    
    def verify_output(self, sql: str, query: str, execution_result: Dict[str, Any],
                     intent_analysis: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        核对SQL执行结果
        
        Args:
            sql: SQL语句
            query: 用户原始查询
            execution_result: SQL执行结果
            intent_analysis: 意图分析结果（用于核对）
            
        Returns:
            核对结果
        """
        try:
            system_prompt = """你是一个SQL结果核对专家。你的任务是核对SQL执行结果是否满足用户查询需求。

请核对：
1. SQL执行结果是否回答了用户的问题
2. 返回的数据是否符合用户查询的意图
3. 数据是否完整（是否有遗漏）
4. 数据是否准确（是否符合预期）
5. 如果结果不符合预期，说明原因"""

            # 构建执行结果摘要
            execution_summary = ""
            if execution_result and execution_result.get("executed"):
                row_count = execution_result.get("row_count", 0)
                data = execution_result.get("data", [])
                execution_summary = f"执行成功，返回 {row_count} 行数据"
                if data and len(data) > 0:
                    # 显示前几行数据作为示例
                    sample_data = data[:3]
                    execution_summary += f"\n示例数据（前3行）：\n{json.dumps(sample_data, ensure_ascii=False, indent=2)}"
            else:
                execution_summary = f"执行失败：{execution_result.get('error', '未知错误')}" if execution_result else "未执行"
            
            intent_summary = ""
            if intent_analysis:
                intent_summary = f"\n意图分析结果：\n"
                intent_summary += f"- 本源实体：{', '.join([e.get('entity_name', '') for e in intent_analysis.get('primary_entities', [])])}\n"
                intent_summary += f"- 实体属性：{', '.join([a.get('attribute_name', '') for a in intent_analysis.get('entity_attributes', [])])}\n"
                intent_summary += f"- 实体指标：{', '.join([m.get('metric_name', '') for m in intent_analysis.get('entity_metrics', [])])}\n"
            
            user_prompt = f"""用户查询：{query}

SQL语句：
{sql}

执行结果：
{execution_summary}
{intent_summary}

请核对SQL执行结果是否满足用户查询需求，以JSON格式返回：
{{
    "is_satisfied": true/false,
    "satisfaction_score": 0.9,
    "verification_reason": "核对说明",
    "missing_info": ["缺失的信息"],
    "unexpected_info": ["不符合预期的信息"],
    "suggestions": ["改进建议"]
}}

请确保返回有效的JSON格式。"""

            response = self.llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ])
            
            content = response.content.strip()
            
            # 提取JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                return {
                    "success": True,
                    "is_satisfied": result.get("is_satisfied", True),
                    "satisfaction_score": result.get("satisfaction_score", 1.0),
                    "verification_reason": result.get("verification_reason", ""),
                    "missing_info": result.get("missing_info", []),
                    "unexpected_info": result.get("unexpected_info", []),
                    "suggestions": result.get("suggestions", []),
                    "raw_response": result
                }
            else:
                return {
                    "success": False,
                    "error": "无法解析大模型返回的JSON",
                    "raw_response": content,
                    "is_satisfied": True,  # 默认认为满足
                    "satisfaction_score": 1.0
                }
                
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON解析失败: {e}",
                "raw_response": content if 'content' in locals() else "",
                "is_satisfied": True,  # 默认认为满足
                "satisfaction_score": 1.0
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"SQL核对输出失败: {str(e)}",
                "is_satisfied": True,  # 默认认为满足
                "satisfaction_score": 1.0
            }
