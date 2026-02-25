# -*- coding:utf-8 -*-
"""
SQL优化智能体
优化SQL语句的性能和可读性
"""

import json
import re
from typing import Dict, Any, List
from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi


class SqlOptimizationAgent:
    """SQL优化智能体：优化SQL语句的性能和可读性"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)
        
    
    def optimize_sql(self, sql: str, query: str, sql_type: str,
                    tables_info: List[Dict[str, Any]],
                    execution_result: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        优化SQL语句
        
        Args:
            sql: SQL语句
            query: 用户原始查询
            sql_type: 数据库类型
            tables_info: 表结构信息
            execution_result: SQL执行结果（用于性能分析）
            
        Returns:
            优化结果
        """
        try:
            system_prompt = f"""你是一个SQL优化专家。你的任务是优化SQL语句的性能和可读性。

数据库类型：{sql_type}

请优化SQL语句：
1. 提高查询性能（如添加索引提示、优化JOIN顺序等）
2. 提高可读性（如格式化、添加注释等）
3. 确保优化后的SQL能够正确回答用户的问题
4. 确保符合{sql_type}数据库的最佳实践
5. **重要：不要添加聚合函数**（如COUNT、COUNT DISTINCT、SUM、AVG、MAX、MIN等）
6. **重要：不要添加GROUP BY子句**，保持返回原始数据记录"""

            tables_str = "\n".join([
                f"- {t.get('table_name', '')}: {', '.join([c.get('col_name', '') for c in t.get('columns', [])])}"
                for t in tables_info
            ])
            
            execution_info = ""
            if execution_result:
                if execution_result.get("executed"):
                    execution_info = f"\n执行结果：成功执行，返回 {execution_result.get('row_count', 0)} 行数据"
                else:
                    execution_info = f"\n执行错误：{execution_result.get('error', '')}"
            
            user_prompt = f"""用户查询：{query}

SQL语句：
{sql}
{execution_info}

表结构：
{tables_str}

请优化SQL语句，以JSON格式返回：
{{
    "optimized_sql": "优化后的SQL语句",
    "optimizations": ["优化说明列表"],
    "performance_improvements": "性能改进说明",
    "explanation": "优化说明"
}}

重要要求：
- **不要添加聚合函数**（如COUNT、COUNT DISTINCT、SUM、AVG、MAX、MIN等）
- **不要添加GROUP BY子句**
- **保持返回原始数据记录**，只优化查询性能，不改变返回的数据结构

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
                
                optimized_sql = result.get("optimized_sql", sql).strip()
                
                return {
                    "success": True,
                    "optimized_sql": optimized_sql,
                    "optimizations": result.get("optimizations", []),
                    "performance_improvements": result.get("performance_improvements", ""),
                    "explanation": result.get("explanation", ""),
                    "raw_response": result
                }
            else:
                return {
                    "success": False,
                    "error": "无法解析大模型返回的JSON",
                    "raw_response": content,
                    "optimized_sql": sql  # 返回原始SQL
                }
                
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON解析失败: {e}",
                "raw_response": content if 'content' in locals() else "",
                "optimized_sql": sql  # 返回原始SQL
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"SQL优化失败: {str(e)}",
                "optimized_sql": sql  # 返回原始SQL
            }
