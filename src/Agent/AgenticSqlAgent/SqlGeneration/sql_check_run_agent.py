# -*- coding:utf-8 -*-
"""
SQL检测运行智能体
检测SQL语句的语法和逻辑，并尝试运行SQL
"""

import json
import re
from typing import Dict, Any, List
from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi
from Agent.AgenticSqlAgent.tools.database_tools import execute_sql


class SqlCheckRunAgent:
    """SQL检测运行智能体：检测SQL语法和逻辑，并尝试运行SQL"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)
        
    
    def check_and_run_sql(self, sql: str, query: str, sql_id: str, 
                         sql_type: str, tables_info: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        检测并运行SQL语句
        
        Args:
            sql: 待检测的SQL语句
            query: 用户原始查询
            sql_id: 数据库ID
            sql_type: 数据库类型
            tables_info: 表结构信息
            
        Returns:
            检测和运行结果
        """
        try:
            # 构建数据库特定的语法检查规则
            syntax_check_rules = ""
            if sql_type == "mysql":
                syntax_check_rules = """
MySQL语法检查规则：
1. **字符串引号**：应使用单引号 'text' 或双引号 "text"
2. **标识符引用**：使用反引号 `table_name` 或 `column_name`（当名称包含特殊字符时）
3. **字符串连接**：应使用 CONCAT(str1, str2) 函数，不是 || 操作符
4. **日期格式化**：应使用 DATE_FORMAT(date, '%Y-%m-%d') 函数
5. **LIMIT语法**：应使用 LIMIT n 或 LIMIT offset, n，不是 LIMIT n OFFSET offset
6. **布尔值**：使用 0/1 或 TRUE/FALSE
7. **正则表达式**：使用 REGEXP 或 RLIKE 操作符
8. **日期函数**：NOW(), CURDATE(), DATE_ADD(), DATEDIFF() 等
"""
            elif sql_type == "postgresql":
                syntax_check_rules = """
PostgreSQL语法检查规则：
1. **字符串引号**：应使用单引号 'text'（双引号用于标识符）
2. **标识符引用**：使用双引号 "table_name" 或 "column_name"（当名称包含特殊字符或大小写敏感时）
3. **字符串连接**：应使用 || 操作符，不是 CONCAT() 函数
4. **日期格式化**：应使用 TO_CHAR(date, 'YYYY-MM-DD') 函数
5. **LIMIT语法**：应使用 LIMIT n OFFSET offset，不是 LIMIT offset, n
6. **布尔值**：使用 TRUE/FALSE/BOOLEAN 类型
7. **正则表达式**：使用 ~ 操作符（区分大小写）或 ~*（不区分大小写）
8. **类型转换**：使用 :: 操作符，如 '123'::INTEGER
9. **日期函数**：NOW(), CURRENT_DATE, DATE_TRUNC(), AGE() 等
"""
            else:
                syntax_check_rules = f"""
{sql_type}数据库语法检查规则：
请检查SQL是否符合 {sql_type} 数据库的语法规范。
"""
            
            # 1. 先进行语法检查（主要关注MySQL和PostgreSQL的语法差异）
            system_prompt = f"""你是一个专业的数据库专家和SQL语句检查专家。你的任务是检查SQL语句的语法正确性和安全性，并核对表结构信息。

数据库类型：{sql_type}
{syntax_check_rules}

请检查SQL语句：
1. **语法是否正确**：是否符合{sql_type}数据库的语法规范
2. **语法元素是否正确**：引号、标识符引用、字符串连接、日期函数、LIMIT语法等是否符合{sql_type}规范
3. **表名和列名核对**（重要）：
   - **必须核对给定的表结构信息**，验证SQL中使用的表名是否在表结构信息中存在
   - **必须核对给定的表结构信息**，验证SQL中使用的列名是否在对应表的列信息中存在
   - **只有在表名或列名确实不在给定的表结构信息中时，才报告错误**
   - **不要猜测或推断表名和列名是否存在**，必须基于给定的表结构信息进行核对
   - 如果表名或列名在给定的表结构信息中存在，即使看起来不常见，也应该认为正确
4. **是否有潜在的安全问题**：如SQL注入风险

**重要说明**：
- 作为数据库专家，必须严格核对给定的表结构信息
- 主要检查语法正确性，不检查逻辑计算是否正确
- 对于需要逻辑计算才能达到用户要求的查询，暂时不做检查
- 只要SQL语法正确、表名和列名在给定的表结构信息中存在，且能执行，就认为检查通过
- **不要因为表名或列名看起来不常见就误报错误，必须基于给定的表结构信息进行核对**"""

            # 构建详细的表结构信息，包括表名和所有列名
            tables_str = "\n".join([
                f"表名：{t.get('table_name', '')}\n" +
                f"列名列表：{', '.join([c.get('col_name', '') for c in t.get('columns', [])])}\n" +
                f"列详细信息：\n" +
                "\n".join([
                    f"  - {c.get('col_name', '')} ({c.get('col_type', 'unknown')})" +
                    (f" - {c.get('col_comment', '')}" if c.get('col_comment') else "")
                    for c in t.get('columns', [])
                ])
                for t in tables_info
            ])
            
            user_prompt = f"""用户查询：{query}

SQL语句：
{sql}

表结构：
{tables_str}

请检查SQL语句的语法是否正确（主要关注是否符合{sql_type}数据库的语法规范），并核对表结构信息，以JSON格式返回：
{{
    "is_valid": true/false,
    "is_safe": true/false,
    "errors": ["语法错误列表（如引号使用错误、函数名错误、LIMIT语法错误、表名或列名在给定的表结构信息中不存在等）"],
    "warnings": ["警告列表（如潜在的性能问题、安全性警告等）"],
    "explanation": "检查说明（重点说明是否符合{sql_type}语法规范，以及表名和列名的核对结果）"
}}

**重要检查要求**：
- **必须核对给定的表结构信息**：验证SQL中使用的表名和列名是否在给定的表结构信息中存在
- **只有在表名或列名确实不在给定的表结构信息中时，才报告错误**
- **不要猜测或推断**：必须基于给定的表结构信息进行核对
- 如果表名或列名在给定的表结构信息中存在，即使看起来不常见，也应该认为正确
- 主要检查语法正确性，不检查逻辑计算是否正确
- 如果SQL语法正确、表名和列名在给定的表结构信息中存在，即使需要逻辑计算才能达到用户要求，也认为is_valid为true
- 重点关注是否符合{sql_type}数据库的语法规范，以及表名和列名是否在给定的表结构信息中存在

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
                check_result = json.loads(json_str)
            else:
                check_result = {
                    "is_valid": True,
                    "is_safe": True,
                    "errors": [],
                    "warnings": ["无法解析检查结果"],
                    "explanation": ""
                }
            
            # 2. 通过execute_sql运行检查运行结果（主要检查语法和执行结果）
            execution_result = None
            execution_error = None
            
            # 无论LLM检查结果如何，都尝试执行SQL，通过实际执行结果来判断
            try:
                # 尝试执行SQL，这是最可靠的语法检查方式
                execution_result = execute_sql(sql_id, sql)
                
                if execution_result and execution_result.get("success"):
                    execution_result["executed"] = True
                    # 如果执行成功，说明语法基本正确，更新检查结果
                    if not check_result.get("is_valid", False):
                        check_result["is_valid"] = True
                        check_result["warnings"] = check_result.get("warnings", [])
                        check_result["warnings"].append("LLM检查认为有错误，但实际执行成功")
                else:
                    execution_error = execution_result.get("error", "SQL执行失败") if execution_result else "SQL执行失败"
                    execution_result = {
                        "executed": False,
                        "error": execution_error
                    }
                    # 如果执行失败，更新检查结果
                    if check_result.get("is_valid", False):
                        check_result["is_valid"] = False
                        if "errors" not in check_result:
                            check_result["errors"] = []
                        check_result["errors"].append(f"执行错误: {execution_error}")
            except Exception as e:
                execution_error = str(e)
                execution_result = {
                    "executed": False,
                    "error": execution_error
                }
                # 如果执行异常，更新检查结果
                if check_result.get("is_valid", False):
                    check_result["is_valid"] = False
                    if "errors" not in check_result:
                        check_result["errors"] = []
                    check_result["errors"].append(f"执行异常: {execution_error}")
            
            return {
                "success": True,
                "is_valid": check_result.get("is_valid", False),
                "is_safe": check_result.get("is_safe", True),
                "errors": check_result.get("errors", []),
                "warnings": check_result.get("warnings", []),
                "explanation": check_result.get("explanation", ""),
                "execution_result": execution_result,
                "raw_check_response": check_result
            }
                
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON解析失败: {e}",
                "raw_response": content if 'content' in locals() else "",
                "is_valid": False,
                "is_safe": True,
                "execution_result": {"executed": False, "error": "检查过程出错"}
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"SQL检测运行失败: {str(e)}",
                "is_valid": False,
                "is_safe": True,
                "execution_result": {"executed": False, "error": str(e)}
            }
