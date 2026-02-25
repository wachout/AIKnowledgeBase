# -*- coding:utf-8 -*-
"""
SQL生成智能体
根据相关的表和列，生成SQL查询语句
"""

import json
import re
from typing import Dict, Any, List
from langchain_community.chat_models.tongyi import ChatTongyi
from Agent.AgenticSqlAgent.tools.database_tools import query_columns_by_table_id
from Config.llm_config import get_chat_tongyi


class SqlGenerationAgent:
    """SQL生成智能体：根据相关表和列生成SQL查询语句"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)
    
    def generate_sql(self, query: str, intent_analysis: Dict[str, Any],
                    relevant_tables: List[Dict[str, Any]], sql_id: str,
                    database_info: Dict[str, Any], table_check_result: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        生成SQL查询语句
        
        Args:
            query: 用户查询问题
            intent_analysis: 意图分析结果
            relevant_tables: 相关表列表（包含table_id和table_name，以及匹配的列信息）
            sql_id: 数据库ID
            database_info: 数据库信息（包含sql_type等）
            table_check_result: 表核对结果（包含匹配的实体、属性、指标、时间字段信息）
            
        Returns:
            SQL生成结果，包含生成的SQL语句
        """
        try:
            sql_type = database_info.get("sql_type", "mysql").lower()
            
            # 从relevant_tables中提取匹配的列信息（无论是否有table_check_result）
            matched_columns_by_table = {}
            for table_info in relevant_tables:
                table_name = table_info.get("table_name", "")
                # 收集该表匹配的所有列
                matched_cols = []
                if table_info.get("matched_attributes"):
                    matched_cols.extend(table_info.get("matched_attributes", []))
                if table_info.get("matched_metrics"):
                    matched_cols.extend(table_info.get("matched_metrics", []))
                if table_info.get("matched_time_fields"):
                    matched_cols.extend(table_info.get("matched_time_fields", []))
                if matched_cols:
                    matched_columns_by_table[table_name] = matched_cols
            
            # 获取每个表的详细信息
            tables_info = []
            for table_info in relevant_tables:
                table_id = table_info.get("table_id", "")
                table_name = table_info.get("table_name", "")
                
                # 获取表的列信息
                columns = query_columns_by_table_id(table_id)
                columns_detail = []
                
                # 如果该表有匹配的列，优先显示匹配的列
                matched_cols = matched_columns_by_table.get(table_name, [])
                
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
                    
                    # 标记是否为匹配的列
                    is_matched = col_name in matched_cols if matched_cols else False
                    
                    columns_detail.append({
                        "col_name": col_name,
                        "col_type": col_type,
                        "col_comment": col_comment,
                        "is_primary": is_primary,
                        "is_unique": is_unique,
                        "is_matched": is_matched  # 标记是否为用户需要的列
                    })
                
                # 如果有匹配的列，优先排序
                if matched_cols:
                    columns_detail.sort(key=lambda x: (not x.get("is_matched", False), x.get("col_name", "")))
                
                tables_info.append({
                    "table_name": table_name,
                    "table_id": table_id,
                    "columns": columns_detail,
                    "matched_entities": table_info.get("matched_entities", []),
                    "matched_attributes": table_info.get("matched_attributes", []),
                    "matched_metrics": table_info.get("matched_metrics", []),
                    "matched_time_fields": table_info.get("matched_time_fields", [])
                })
            
            # 构建数据库特定的语法提示
            sql_syntax_guide = ""
            if sql_type == "mysql":
                sql_syntax_guide = """
MySQL语法规范：
1. **字符串引号**：使用单引号 'text' 或双引号 "text"（推荐单引号）
2. **标识符引用**：使用反引号 `table_name` 或 `column_name`（当名称包含特殊字符时）
3. **字符串连接**：使用 CONCAT(str1, str2) 函数
4. **日期格式化**：使用 DATE_FORMAT(date, '%Y-%m-%d') 函数
5. **LIMIT语法**：使用 LIMIT n 或 LIMIT offset, n
6. **布尔值**：使用 0/1 或 TRUE/FALSE
7. **字符串比较**：默认不区分大小写（可使用 BINARY 关键字强制区分）
8. **正则表达式**：使用 REGEXP 或 RLIKE 操作符
9. **日期函数**：NOW(), CURDATE(), DATE_ADD(), DATEDIFF() 等
10. **窗口函数**：MySQL 8.0+ 支持窗口函数，语法：ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)
"""
            elif sql_type == "postgresql":
                sql_syntax_guide = """
PostgreSQL语法规范：
1. **字符串引号**：使用单引号 'text'（双引号用于标识符）
2. **标识符引用**：使用双引号 "table_name" 或 "column_name"（当名称包含特殊字符或大小写敏感时）
3. **字符串连接**：使用 || 操作符，如 'text1' || 'text2'
4. **日期格式化**：使用 TO_CHAR(date, 'YYYY-MM-DD') 函数
5. **LIMIT语法**：使用 LIMIT n OFFSET offset
6. **布尔值**：使用 TRUE/FALSE/BOOLEAN 类型
7. **字符串比较**：默认区分大小写（可使用 ILIKE 进行不区分大小写匹配）
8. **正则表达式**：使用 ~ 操作符（区分大小写）或 ~*（不区分大小写），或 SIMILAR TO
9. **日期函数**：NOW(), CURRENT_DATE, DATE_TRUNC(), AGE() 等
10. **窗口函数**：完整支持，语法：ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)
11. **类型转换**：使用 :: 操作符，如 '123'::INTEGER 或 CAST('123' AS INTEGER)
"""
            else:
                sql_syntax_guide = f"""
{sql_type}数据库语法规范：
请确保生成的SQL符合 {sql_type} 数据库的语法规范。
"""
            
            # 构建提示词
            system_prompt = f"""你是一个专业的SQL查询生成专家。你的任务是根据用户查询和相关的表结构，生成正确的SQL查询语句。

数据库类型：{sql_type}
{sql_syntax_guide}
重要提示：
1. 优先使用标记为[匹配]的列，这些列是用户查询中明确需要的字段
2. 匹配的实体、属性、指标、时间字段列已经在表信息中明确标注
3. 请确保生成的SQL语句能够正确回答用户的问题
4. **严格按照上述{sql_type}语法规范生成SQL语句**

请确保生成的SQL语句：
1. 语法正确，严格符合{sql_type}数据库的语法规范
2. 使用正确的引号、标识符引用、字符串连接、日期函数等
3. 能够正确回答用户的问题
4. 优先使用匹配的列（标记为[匹配]的列）
5. 包含必要的JOIN、WHERE、ORDER BY等子句
6. **重要：不要使用聚合函数（如COUNT、COUNT DISTINCT、SUM、AVG、MAX、MIN等），要查询原始数据行**
7. **重要：不要使用GROUP BY子句，直接返回原始数据记录**
8. 如果用户需要统计数据，也应该返回原始数据，让用户自己进行统计
9. **重要：对于文本类型（VARCHAR、TEXT、CHAR等）字段的WHERE条件查询**：
   - 优先使用LIKE操作符进行模糊匹配，而不是使用等号（=）进行精确匹配
   - 因为用户输入时可能会使用简称、部分名称、别名等，精确匹配可能查询不到数据
   - MySQL使用：`column_name LIKE '%value%'` 或 `column_name LIKE 'value%'`
   - PostgreSQL使用：`column_name LIKE '%value%'` 或 `column_name ILIKE '%value%'`（不区分大小写）
   - 如果确实需要精确匹配，可以使用等号，但优先考虑LIKE查询"""

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
    "columns_used": [
        {{
            "table_name": "表名",
            "col_name": "列名",
            "col_description": "列描述（从表结构中的comment获取）"
        }}
    ]
}}

重要要求：
- **不要使用聚合函数**（如COUNT、COUNT DISTINCT、SUM、AVG、MAX、MIN等）
- **不要使用GROUP BY子句**
- **直接查询并返回原始数据行**，而不是统计数据
- 如果用户需要统计信息，也应该返回所有相关的原始数据记录
- **严格按照{sql_type}数据库的语法规范**：
  - 字符串使用正确的引号格式
  - 使用正确的字符串连接方式
  - 使用正确的日期函数和格式化
  - 使用正确的LIMIT语法
  - 使用正确的标识符引用方式
- **重要：文本类型字段的查询条件**：
  - 对于VARCHAR、TEXT、CHAR等文本类型字段，在WHERE条件中优先使用LIKE操作符进行模糊匹配
  - 因为用户输入时可能会使用简称、部分名称、别名等，精确匹配（=）可能查询不到数据
  - MySQL示例：`WHERE column_name LIKE '%用户输入值%'` 或 `WHERE column_name LIKE '用户输入值%'`
  - PostgreSQL示例：`WHERE column_name LIKE '%用户输入值%'` 或 `WHERE column_name ILIKE '%用户输入值%'`（不区分大小写）
  - 只有在确实需要精确匹配时才使用等号（=）
- **重要**：在 columns_used 中，必须为每个使用的列提供 table_name、col_name 和 col_description（从表结构信息中获取）

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
                columns_used = result.get("columns_used", [])
                
                # 处理 columns_used，确保格式正确
                columns_with_info = []
                for col_info in columns_used:
                    if isinstance(col_info, dict):
                        # 已经是字典格式
                        columns_with_info.append({
                            "table_name": col_info.get("table_name", ""),
                            "col_name": col_info.get("col_name", ""),
                            "col_description": col_info.get("col_description", col_info.get("col_name", ""))
                        })
                    elif isinstance(col_info, str):
                        # 如果是字符串，尝试从表信息中查找
                        # 格式可能是 "table.col" 或 "col"
                        if "." in col_info:
                            table_name, col_name = col_info.split(".", 1)
                        else:
                            col_name = col_info
                            table_name = ""
                        
                        # 从tables_info中查找列的描述
                        col_description = col_name
                        for table_info in tables_info:
                            if table_name and table_info.get("table_name", "") != table_name:
                                continue
                            for col_detail in table_info.get("columns", []):
                                if col_detail.get("col_name", "") == col_name:
                                    col_description = col_detail.get("col_comment", col_name)
                                    if not table_name:
                                        table_name = table_info.get("table_name", "")
                                    break
                            if col_description != col_name:
                                break
                        
                        columns_with_info.append({
                            "table_name": table_name,
                            "col_name": col_name,
                            "col_description": col_description
                        })
                
                return {
                    "success": True,
                    "sql": sql,
                    "sql_type": result.get("sql_type", sql_type),
                    "explanation": result.get("explanation", ""),
                    "tables_used": result.get("tables_used", []),
                    "columns_used": columns_with_info,  # 包含表名和列描述的列表
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
