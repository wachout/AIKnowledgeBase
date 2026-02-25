# -*- coding:utf-8 -*-
"""
SQL生成智能体
根据相关的表和列，生成SQL查询语句
"""

import json
import re
from typing import Dict, Any, List
from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi
from Agent.AgenticSqlAgent.tools.database_tools import query_table_by_name, query_columns_by_table_id


class SqlGenerationAgent:
    """SQL生成智能体：根据相关表和列生成SQL查询语句"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)
        
    
    def generate_sql(self, query: str, intent_analysis: Dict[str, Any],
                    relevant_tables: List[Dict[str, Any]], sql_id: str,
                    database_info: Dict[str, Any], table_search_result: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        生成SQL查询语句
        
        Args:
            query: 用户查询问题
            intent_analysis: 意图分析结果
            relevant_tables: 相关表列表（包含table_id和table_name，以及匹配的列信息）
            sql_id: 数据库ID
            database_info: 数据库信息（包含sql_type等）
            table_search_result: 表搜索结果（包含匹配的实体、属性、指标、时间字段信息）
            
        Returns:
            SQL生成结果，包含生成的SQL语句
        """
        try:
            sql_type = database_info.get("sql_type", "mysql").lower()
            
            # 获取每个表的详细信息
            tables_info = []
            for table_info in relevant_tables:
                table_id = table_info.get("table_id", "")
                table_name = table_info.get("table_name", "")
                
                # 获取表的列信息
                columns = query_columns_by_table_id(table_id)
                columns_detail = []
                for col in columns:
                    col_name = col.get("col_name", "")
                    col_type = col.get("col_type", "")
                    col_info = col.get("col_info", {})
                    
                    if isinstance(col_info, str):
                        try:
                            col_info = json.loads(col_info)
                        except:
                            col_info = {}
                    
                    col_comment = col_info.get("comment", "") if isinstance(col_info, dict) else ""
                    is_primary = col_info.get("is_primary", False) if isinstance(col_info, dict) else False
                    is_unique = col_info.get("is_unique", False) if isinstance(col_info, dict) else False
                    
                    columns_detail.append({
                        "col_name": col_name,
                        "col_type": col_type,
                        "col_comment": col_comment,
                        "is_primary": is_primary,
                        "is_unique": is_unique
                    })
                
                tables_info.append({
                    "table_name": table_name,
                    "table_id": table_id,
                    "columns": columns_detail
                })
            
            # 构建提示词
            system_prompt = f"""你是一个专业的SQL查询生成专家。你的任务是根据用户查询和相关的表结构，生成正确的SQL查询语句。

数据库类型：{sql_type}

重要提示：
1. 优先使用标记为[匹配]的列，这些列是用户查询中明确需要的字段
2. 匹配的实体、属性、指标、时间字段列已经在表信息中明确标注
3. 请确保生成的SQL语句能够正确回答用户的问题

请确保生成的SQL语句：
1. 语法正确
2. 符合{sql_type}数据库的语法规范
3. 能够正确回答用户的问题
4. 优先使用匹配的列（标记为[匹配]的列）
5. 包含必要的JOIN、WHERE、GROUP BY、ORDER BY等子句
6. 对于聚合查询，使用正确的聚合函数（COUNT、SUM、AVG、MAX、MIN等）"""

            tables_str = "\n\n".join([
                f"表名：{t['table_name']}\n"
                + (f"匹配的实体：{', '.join(t.get('matched_entities', []))}\n" if t.get('matched_entities') else "")
                + (f"匹配的属性列：{', '.join(t.get('matched_attributes', []))}\n" if t.get('matched_attributes') else "")
                + (f"匹配的指标列：{', '.join(t.get('matched_metrics', []))}\n" if t.get('matched_metrics') else "")
                + (f"匹配的时间字段列：{', '.join(t.get('matched_time_fields', []))}\n" if t.get('matched_time_fields') else "")
                + f"列信息：\n" + "\n".join([
                    f"  - {c['col_name']} ({c['col_type']})"
                    f"{' [主键]' if c['is_primary'] else ''}"
                    f"{' [唯一]' if c['is_unique'] else ''}"
                    f"{' [匹配]' if c.get('is_matched', False) else ''}"
                    f"{' - ' + c['col_comment'] if c['col_comment'] else ''}"
                    for c in t['columns']
                ])
                for t in tables_info
            ])
            
            intent_str = json.dumps(intent_analysis, ensure_ascii=False, indent=2)
            
            user_prompt = f"""用户查询：{query}

意图分析结果：
{intent_str}

相关表结构：
{tables_str}

请生成SQL查询语句，以JSON格式返回：
{{
    "sql": "生成的SQL语句",
    "sql_type": "{sql_type}",
    "explanation": "SQL语句说明",
    "tables_used": ["使用的表名列表"],
    "columns_used": ["使用的列名列表"]
}}

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
                
                sql = result.get("sql", "").strip()
                
                return {
                    "success": True,
                    "sql": sql,
                    "sql_type": result.get("sql_type", sql_type),
                    "explanation": result.get("explanation", ""),
                    "tables_used": result.get("tables_used", []),
                    "columns_used": result.get("columns_used", []),
                    "raw_response": result
                }
            else:
                return {
                    "success": False,
                    "error": "无法解析大模型返回的JSON",
                    "raw_response": content,
                    "sql": ""
                }
                
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON解析失败: {e}",
                "raw_response": content if 'content' in locals() else "",
                "sql": ""
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"SQL生成失败: {str(e)}",
                "sql": ""
            }
