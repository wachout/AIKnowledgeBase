# -*- coding:utf-8 -*-
"""
数据库元数据查询智能体
识别用户是否在查询数据库本身的元数据（如表数量、列数量、表描述、列注释等）
"""

import json
import re
from typing import Dict, Any, List, Optional
from langchain_community.chat_models.tongyi import ChatTongyi
from Agent.AgenticSqlAgent.tools.database_tools import (
    query_tables_by_sql_id,
    query_table_by_name,
    query_columns_by_table_id,
    query_column_by_name
)
from Config.llm_config import get_chat_tongyi


class DatabaseMetadataAgent:
    """数据库元数据查询智能体：识别并处理数据库元数据查询"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)
    
    def check_metadata_query(self, query: str) -> Dict[str, Any]:
        """
        检查用户查询是否是数据库元数据查询
        
        Args:
            query: 用户查询问题
            
        Returns:
            检查结果，包含：
            - is_metadata_query: 是否是元数据查询
            - query_type: 查询类型（如"table_count", "column_count", "table_description", "column_comment"等）
            - table_name: 表名（如果涉及特定表）
            - column_name: 列名（如果涉及特定列）
            - confidence: 置信度
        """
        try:
            system_prompt = """你是一个数据库专家，专门识别用户是否在查询数据库本身的元数据信息。

数据库元数据查询包括：
1. **表数量查询**：如"有多少表"、"有几个表"、"表的总数"等
2. **列数量查询**：如"某表有多少列"、"某表有几个字段"、"某表的列数"等
3. **表描述查询**：如"某表的描述"、"某表是做什么的"、"某表的说明"等
4. **列注释查询**：如"某列的注释"、"某列的含义"、"某列的说明"、"某列的comment"等
5. **表列表查询**：如"有哪些表"、"列出所有表"、"显示所有表名"等
6. **列列表查询**：如"某表有哪些列"、"某表的字段列表"、"列出某表的所有列"等

**重要原则**：
- 如果用户查询的是数据库本身的元数据信息（表数量、列数量、表描述、列注释等），则认为是元数据查询
- 如果用户查询的是表中的业务数据（如"查询用户表的数据"、"统计订单数量"等），则不是元数据查询
- 元数据查询关注的是数据库结构本身，而不是表中的数据内容

请分析用户查询，判断是否是数据库元数据查询，并以JSON格式返回分析结果。"""

            user_prompt = f"""用户查询：{query}

请判断这个查询是否是数据库元数据查询，以JSON格式返回：
{{
    "is_metadata_query": true/false,
    "query_type": "查询类型（如果是元数据查询，可能是：table_count、column_count、table_description、column_comment、table_list、column_list等）",
    "table_name": "表名（如果涉及特定表，从查询中提取表名，否则为空字符串）",
    "column_name": "列名（如果涉及特定列，从查询中提取列名，否则为空字符串）",
    "confidence": 0.9,
    "explanation": "判断说明"
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
                    "is_metadata_query": result.get("is_metadata_query", False),
                    "query_type": result.get("query_type", ""),
                    "table_name": result.get("table_name", ""),
                    "column_name": result.get("column_name", ""),
                    "confidence": result.get("confidence", 0.0),
                    "explanation": result.get("explanation", ""),
                    "raw_response": result
                }
            else:
                return {
                    "success": False,
                    "is_metadata_query": False,
                    "error": "无法解析大模型返回的JSON",
                    "raw_response": content
                }
                
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "is_metadata_query": False,
                "error": f"JSON解析失败: {e}",
                "raw_response": content if 'content' in locals() else ""
            }
        except Exception as e:
            return {
                "success": False,
                "is_metadata_query": False,
                "error": f"元数据查询检查失败: {str(e)}"
            }
    
    def execute_metadata_query(self, sql_id: str, query_type: str, 
                               table_name: str = "", column_name: str = "") -> Dict[str, Any]:
        """
        执行数据库元数据查询
        
        Args:
            sql_id: 数据库连接ID
            query_type: 查询类型（table_count、column_count、table_description、column_comment、table_list、column_list）
            table_name: 表名（如果涉及特定表）
            column_name: 列名（如果涉及特定列）
            
        Returns:
            查询结果
        """
        try:
            result = {
                "success": False,
                "query_type": query_type,
                "data": None,
                "error": None
            }
            
            if query_type == "table_count":
                # 统计数据库有多少表
                tables = query_tables_by_sql_id(sql_id)
                result["success"] = True
                result["data"] = {
                    "count": len(tables),
                    "message": f"数据库中共有 {len(tables)} 个表"
                }
                
            elif query_type == "table_list":
                # 列出所有表
                tables = query_tables_by_sql_id(sql_id)
                table_list = []
                for table in tables:
                    table_list.append({
                        "table_name": table.get("table_name", ""),
                        "table_description": table.get("table_description", ""),
                        "table_id": table.get("table_id", "")
                    })
                result["success"] = True
                result["data"] = {
                    "tables": table_list,
                    "count": len(table_list),
                    "message": f"数据库中共有 {len(table_list)} 个表"
                }
                
            elif query_type == "column_count":
                # 统计指定表有多少列
                if not table_name:
                    result["error"] = "查询列数量需要指定表名"
                    # 返回所有可用的表名
                    all_tables = query_tables_by_sql_id(sql_id)
                    available_tables = [t.get("table_name", "") for t in all_tables if t.get("table_name")]
                    result["available_tables"] = available_tables
                    result["error_message"] = f"查询列数量需要指定表名。\n可用的表名列表：{', '.join(available_tables[:20])}" + (f"\n... 还有 {len(available_tables) - 20} 个表" if len(available_tables) > 20 else "")
                    return result
                
                table_info = query_table_by_name(sql_id, table_name)
                if not table_info:
                    # 表名不存在，返回所有可用的表名
                    all_tables = query_tables_by_sql_id(sql_id)
                    available_tables = [t.get("table_name", "") for t in all_tables if t.get("table_name")]
                    result["error"] = f"未找到表: {table_name}"
                    result["available_tables"] = available_tables
                    result["error_message"] = f"未找到表 '{table_name}'。\n可用的表名列表：{', '.join(available_tables[:20])}" + (f"\n... 还有 {len(available_tables) - 20} 个表" if len(available_tables) > 20 else "")
                    return result
                
                table_id = table_info.get("table_id", "")
                columns = query_columns_by_table_id(table_id)
                result["success"] = True
                result["data"] = {
                    "table_name": table_name,
                    "count": len(columns),
                    "message": f"表 {table_name} 中共有 {len(columns)} 个列"
                }
                
            elif query_type == "column_list":
                # 列出指定表的所有列
                if not table_name:
                    result["error"] = "查询列列表需要指定表名"
                    # 返回所有可用的表名
                    all_tables = query_tables_by_sql_id(sql_id)
                    available_tables = [t.get("table_name", "") for t in all_tables if t.get("table_name")]
                    result["available_tables"] = available_tables
                    result["error_message"] = f"查询列列表需要指定表名。\n可用的表名列表：{', '.join(available_tables[:20])}" + (f"\n... 还有 {len(available_tables) - 20} 个表" if len(available_tables) > 20 else "")
                    return result
                
                table_info = query_table_by_name(sql_id, table_name)
                if not table_info:
                    # 表名不存在，返回所有可用的表名
                    all_tables = query_tables_by_sql_id(sql_id)
                    available_tables = [t.get("table_name", "") for t in all_tables if t.get("table_name")]
                    result["error"] = f"未找到表: {table_name}"
                    result["available_tables"] = available_tables
                    result["error_message"] = f"未找到表 '{table_name}'。\n可用的表名列表：{', '.join(available_tables[:20])}" + (f"\n... 还有 {len(available_tables) - 20} 个表" if len(available_tables) > 20 else "")
                    return result
                
                table_id = table_info.get("table_id", "")
                columns = query_columns_by_table_id(table_id)
                column_list = []
                for col in columns:
                    col_info = col.get("col_info", {})
                    if isinstance(col_info, str):
                        try:
                            col_info = json.loads(col_info)
                        except:
                            col_info = {}
                    
                    col_comment = col_info.get("comment", "") if isinstance(col_info, dict) else ""
                    column_list.append({
                        "column_name": col.get("col_name", ""),
                        "column_type": col.get("col_type", ""),
                        "column_comment": col_comment
                    })
                
                result["success"] = True
                result["data"] = {
                    "table_name": table_name,
                    "columns": column_list,
                    "count": len(column_list),
                    "message": f"表 {table_name} 中共有 {len(column_list)} 个列"
                }
                
            elif query_type == "table_description":
                # 查询指定表的描述
                if not table_name:
                    result["error"] = "查询表描述需要指定表名"
                    # 返回所有可用的表名
                    all_tables = query_tables_by_sql_id(sql_id)
                    available_tables = [t.get("table_name", "") for t in all_tables if t.get("table_name")]
                    result["available_tables"] = available_tables
                    result["error_message"] = f"查询表描述需要指定表名。\n可用的表名列表：{', '.join(available_tables[:20])}" + (f"\n... 还有 {len(available_tables) - 20} 个表" if len(available_tables) > 20 else "")
                    return result
                
                table_info = query_table_by_name(sql_id, table_name)
                if not table_info:
                    # 表名不存在，返回所有可用的表名
                    all_tables = query_tables_by_sql_id(sql_id)
                    available_tables = [t.get("table_name", "") for t in all_tables if t.get("table_name")]
                    result["error"] = f"未找到表: {table_name}"
                    result["available_tables"] = available_tables
                    result["error_message"] = f"未找到表 '{table_name}'。\n可用的表名列表：{', '.join(available_tables[:20])}" + (f"\n... 还有 {len(available_tables) - 20} 个表" if len(available_tables) > 20 else "")
                    return result
                
                table_description = table_info.get("table_description", "")
                result["success"] = True
                result["data"] = {
                    "table_name": table_name,
                    "table_description": table_description if table_description else "该表没有描述信息",
                    "message": f"表 {table_name} 的描述: {table_description if table_description else '该表没有描述信息'}"
                }
                
            elif query_type == "column_comment":
                # 查询指定列的注释
                if not table_name:
                    result["error"] = "查询列注释需要指定表名"
                    # 返回所有可用的表名
                    all_tables = query_tables_by_sql_id(sql_id)
                    available_tables = [t.get("table_name", "") for t in all_tables if t.get("table_name")]
                    result["available_tables"] = available_tables
                    result["error_message"] = f"查询列注释需要指定表名。\n可用的表名列表：{', '.join(available_tables[:20])}" + (f"\n... 还有 {len(available_tables) - 20} 个表" if len(available_tables) > 20 else "")
                    return result
                if not column_name:
                    result["error"] = "查询列注释需要指定列名"
                    # 返回指定表的所有可用列名
                    table_info = query_table_by_name(sql_id, table_name)
                    if table_info:
                        table_id = table_info.get("table_id", "")
                        columns = query_columns_by_table_id(table_id)
                        available_columns = [c.get("col_name", "") for c in columns if c.get("col_name")]
                        result["available_columns"] = available_columns
                        result["error_message"] = f"查询列注释需要指定列名。\n表 '{table_name}' 的可用列名列表：{', '.join(available_columns[:30])}" + (f"\n... 还有 {len(available_columns) - 30} 个列" if len(available_columns) > 30 else "")
                    else:
                        # 表名也不存在
                        all_tables = query_tables_by_sql_id(sql_id)
                        available_tables = [t.get("table_name", "") for t in all_tables if t.get("table_name")]
                        result["available_tables"] = available_tables
                        result["error_message"] = f"查询列注释需要指定列名，且表 '{table_name}' 不存在。\n可用的表名列表：{', '.join(available_tables[:20])}" + (f"\n... 还有 {len(available_tables) - 20} 个表" if len(available_tables) > 20 else "")
                    return result
                
                table_info = query_table_by_name(sql_id, table_name)
                if not table_info:
                    # 表名不存在，返回所有可用的表名
                    all_tables = query_tables_by_sql_id(sql_id)
                    available_tables = [t.get("table_name", "") for t in all_tables if t.get("table_name")]
                    result["error"] = f"未找到表: {table_name}"
                    result["available_tables"] = available_tables
                    result["error_message"] = f"未找到表 '{table_name}'。\n可用的表名列表：{', '.join(available_tables[:20])}" + (f"\n... 还有 {len(available_tables) - 20} 个表" if len(available_tables) > 20 else "")
                    return result
                
                table_id = table_info.get("table_id", "")
                col_info = query_column_by_name(table_id, column_name)
                if not col_info:
                    # 列名不存在，返回该表的所有可用列名
                    columns = query_columns_by_table_id(table_id)
                    available_columns = [c.get("col_name", "") for c in columns if c.get("col_name")]
                    result["error"] = f"未找到列: {table_name}.{column_name}"
                    result["available_columns"] = available_columns
                    result["error_message"] = f"未找到列 '{table_name}.{column_name}'。\n表 '{table_name}' 的可用列名列表：{', '.join(available_columns[:30])}" + (f"\n... 还有 {len(available_columns) - 30} 个列" if len(available_columns) > 30 else "")
                    return result
                
                col_info_data = col_info.get("col_info", {})
                if isinstance(col_info_data, str):
                    try:
                        col_info_data = json.loads(col_info_data)
                    except:
                        col_info_data = {}
                
                col_comment = col_info_data.get("comment", "") if isinstance(col_info_data, dict) else ""
                result["success"] = True
                result["data"] = {
                    "table_name": table_name,
                    "column_name": column_name,
                    "column_type": col_info.get("col_type", ""),
                    "column_comment": col_comment if col_comment else "该列没有注释信息",
                    "message": f"列 {table_name}.{column_name} 的注释: {col_comment if col_comment else '该列没有注释信息'}"
                }
                
            else:
                result["error"] = f"不支持的查询类型: {query_type}"
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "query_type": query_type,
                "error": f"执行元数据查询失败: {str(e)}"
            }
    
    def process_metadata_query(self, sql_id: str, query: str) -> Dict[str, Any]:
        """
        处理数据库元数据查询（完整流程）
        
        Args:
            sql_id: 数据库连接ID
            query: 用户查询问题
            
        Returns:
            处理结果，包含：
            - is_metadata_query: 是否是元数据查询
            - metadata_result: 元数据查询结果（如果是元数据查询）
            - should_continue: 是否应该继续后续的SQL生成流程
        """
        try:
            # 步骤1: 检查是否是元数据查询
            check_result = self.check_metadata_query(query)
            
            if not check_result.get("success"):
                return {
                    "success": False,
                    "is_metadata_query": False,
                    "error": check_result.get("error", "元数据查询检查失败"),
                    "should_continue": True  # 检查失败时继续后续流程
                }
            
            is_metadata_query = check_result.get("is_metadata_query", False)
            
            if not is_metadata_query:
                # 不是元数据查询，继续后续流程
                return {
                    "success": True,
                    "is_metadata_query": False,
                    "should_continue": True
                }
            
            # 步骤2: 执行元数据查询
            query_type = check_result.get("query_type", "")
            table_name = check_result.get("table_name", "")
            column_name = check_result.get("column_name", "")
            
            metadata_result = self.execute_metadata_query(
                sql_id=sql_id,
                query_type=query_type,
                table_name=table_name,
                column_name=column_name
            )
            
            return {
                "success": True,
                "is_metadata_query": True,
                "metadata_result": metadata_result,
                "query_type": query_type,
                "table_name": table_name,
                "column_name": column_name,
                "should_continue": False  # 元数据查询完成，不需要继续后续流程
            }
            
        except Exception as e:
            return {
                "success": False,
                "is_metadata_query": False,
                "error": f"处理元数据查询失败: {str(e)}",
                "should_continue": True  # 出错时继续后续流程
            }
