# -*- coding:utf-8 -*-
"""
SQL检查智能体
检查生成的SQL语句是否正确，并进行验证
"""

import json
import re
# from typing import Dict, Any
from typing import Dict, Any, Optional, List
from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi


class SqlCheckAgent:
    """SQL检查智能体：检查SQL语句的语法和逻辑正确性"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)
        
    
    def check_sql(self, sql: str, query: str, sql_type: str,
                 tables_info: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        检查SQL语句
        
        Args:
            sql: 待检查的SQL语句
            query: 用户原始查询
            sql_type: 数据库类型
            tables_info: 表结构信息
            
        Returns:
            检查结果
        """
        try:
            system_prompt = f"""你是一个SQL语句检查专家。你的任务是检查SQL语句的语法和逻辑正确性。

数据库类型：{sql_type}

请检查SQL语句：
1. 语法是否正确
2. 是否符合{sql_type}数据库的语法规范
3. 表名和列名是否正确
4. 是否能够正确回答用户的问题
5. 是否有潜在的安全问题（如SQL注入）"""

            tables_str = "\n".join([
                f"- {t.get('table_name', '')}: {', '.join([c.get('col_name', '') for c in t.get('columns', [])])}"
                for t in tables_info
            ])
            
            user_prompt = f"""用户查询：{query}

SQL语句：
{sql}

表结构：
{tables_str}

请检查SQL语句，以JSON格式返回：
{{
    "is_valid": true/false,
    "is_safe": true/false,
    "errors": ["错误列表"],
    "warnings": ["警告列表"],
    "corrected_sql": "修正后的SQL语句（如果有错误）",
    "explanation": "检查说明"
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
                    "is_valid": result.get("is_valid", False),
                    "is_safe": result.get("is_safe", True),
                    "errors": result.get("errors", []),
                    "warnings": result.get("warnings", []),
                    "corrected_sql": result.get("corrected_sql", sql),
                    "explanation": result.get("explanation", ""),
                    "raw_response": result
                }
            else:
                return {
                    "success": False,
                    "error": "无法解析大模型返回的JSON",
                    "raw_response": content,
                    "is_valid": False,
                    "is_safe": True
                }
                
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON解析失败: {e}",
                "raw_response": content if 'content' in locals() else "",
                "is_valid": False,
                "is_safe": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"SQL检查失败: {str(e)}",
                "is_valid": False,
                "is_safe": True
            }
