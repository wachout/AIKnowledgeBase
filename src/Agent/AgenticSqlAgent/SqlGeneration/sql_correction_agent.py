# -*- coding:utf-8 -*-
"""
SQL纠错智能体
根据检测到的错误，修正SQL语句
"""

import json
import re
from typing import Dict, Any, List
from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi


class SqlCorrectionAgent:
    """SQL纠错智能体：根据检测到的错误修正SQL语句"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)
        
    
    def correct_sql(self, sql: str, query: str, sql_type: str,
                   errors: List[str], warnings: List[str],
                   tables_info: List[Dict[str, Any]],
                   execution_error: str = None,
                   execution_result: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        修正SQL语句
        
        Args:
            sql: 原始SQL语句
            query: 用户原始查询
            sql_type: 数据库类型
            errors: 错误列表
            warnings: 警告列表
            tables_info: 表结构信息
            execution_error: 执行错误信息（如果有）
            
        Returns:
            修正结果
        """
        try:
            system_prompt = f"""你是一个SQL语句修正专家。你的任务是根据检测到的错误和警告，修正SQL语句。

数据库类型：{sql_type}

请修正SQL语句：
1. 修复所有语法错误
2. 修复所有逻辑错误
3. 确保符合{sql_type}数据库的语法规范
4. 确保表名和列名正确
5. 确保能够正确回答用户的问题
6. **重要：不要使用聚合函数**（如COUNT、COUNT DISTINCT、SUM、AVG、MAX、MIN等）
7. **重要：不要使用GROUP BY子句**，直接返回原始数据记录
8. **重要：对于文本类型字段的查询条件优化**：
   - 如果SQL执行后返回0行数据，且WHERE条件中包含文本类型（VARCHAR、TEXT、CHAR等）字段的等号（=）比较
   - 考虑将等号（=）改为LIKE操作符进行模糊匹配
   - 因为用户输入时可能会使用简称、部分名称、别名等，精确匹配可能查询不到数据
   - MySQL使用：`column_name LIKE '%value%'` 或 `column_name LIKE '%value%'`
   - PostgreSQL使用：`column_name LIKE '%value%'` 或 `column_name ILIKE '%value%'`（不区分大小写）
   - 优先使用LIKE '%value%'进行包含匹配，这样可以匹配到包含该值的所有记录"""

            tables_str = "\n".join([
                f"- {t.get('table_name', '')}: {', '.join([c.get('col_name', '') for c in t.get('columns', [])])}"
                for t in tables_info
            ])
            
            errors_str = "\n".join([f"- {e}" for e in errors]) if errors else "无错误"
            warnings_str = "\n".join([f"- {w}" for w in warnings]) if warnings else "无警告"
            exec_error_str = f"\n执行错误：{execution_error}" if execution_error else ""
            
            user_prompt = f"""用户查询：{query}

原始SQL语句：
{sql}

检测到的错误：
{errors_str}

检测到的警告：
{warnings_str}
{exec_error_str}
{execution_info}

表结构：
{tables_str}

请修正SQL语句，以JSON格式返回：
{{
    "corrected_sql": "修正后的SQL语句",
    "corrections": ["修正说明列表"],
    "explanation": "修正说明"
}}

重要要求：
- **不要使用聚合函数**（如COUNT、COUNT DISTINCT、SUM、AVG、MAX、MIN等）
- **不要使用GROUP BY子句**
- **直接查询并返回原始数据行**
- **文本类型字段查询优化**：
  - 如果执行结果为空（0行数据），且WHERE条件中包含文本类型字段的等号（=）比较
  - 考虑将等号改为LIKE操作符进行模糊匹配
  - MySQL：`column_name LIKE '%value%'` 或 `column_name LIKE 'value%'`
  - PostgreSQL：`column_name LIKE '%value%'` 或 `column_name ILIKE '%value%'`（不区分大小写）
  - 优先使用LIKE '%value%'进行包含匹配，以匹配用户可能使用的简称、部分名称等

请确保返回有效的JSON格式，SQL语句不要包含换行符和多余的空格。"""

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
                
                corrected_sql = result.get("corrected_sql", sql).strip()
                
                return {
                    "success": True,
                    "corrected_sql": corrected_sql,
                    "corrections": result.get("corrections", []),
                    "explanation": result.get("explanation", ""),
                    "raw_response": result
                }
            else:
                return {
                    "success": False,
                    "error": "无法解析大模型返回的JSON",
                    "raw_response": content,
                    "corrected_sql": sql  # 返回原始SQL
                }
                
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON解析失败: {e}",
                "raw_response": content if 'content' in locals() else "",
                "corrected_sql": sql  # 返回原始SQL
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"SQL纠错失败: {str(e)}",
                "corrected_sql": sql  # 返回原始SQL
            }
