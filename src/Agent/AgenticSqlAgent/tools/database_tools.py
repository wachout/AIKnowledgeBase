# -*- coding:utf-8 -*-
"""
数据库查询工具
提供给智能体使用的数据库查询工具
"""

from typing import Dict, Any, List, Optional
from Db.sqlite_db import cSingleSqlite
from Control.control_sql import CControl


def query_database_info(sql_id: str) -> Dict[str, Any]:
    """
    查询数据库连接信息
    
    Args:
        sql_id: 数据库连接ID
        
    Returns:
        数据库连接信息字典
    """
    try:
        return cSingleSqlite.query_base_sql_by_sql_id(sql_id) or {}
    except Exception as e:
        print(f"查询数据库信息失败: {e}")
        return {}


def query_tables_by_sql_id(sql_id: str) -> List[Dict[str, Any]]:
    """
    根据sql_id查询所有表信息
    
    Args:
        sql_id: 数据库连接ID
        
    Returns:
        表信息列表
    """
    try:
        return cSingleSqlite.query_table_sql_by_sql_id(sql_id) or []
    except Exception as e:
        print(f"查询表信息失败: {e}")
        return []


def query_table_by_name(sql_id: str, table_name: str) -> Optional[Dict[str, Any]]:
    """
    根据表名查询表信息
    
    Args:
        sql_id: 数据库连接ID
        table_name: 表名
        
    Returns:
        表信息字典，如果不存在返回None
    """
    try:
        return cSingleSqlite.query_table_sql_by_sql_id_and_name(sql_id, table_name)
    except Exception as e:
        print(f"查询表信息失败: {e}")
        return None


def query_columns_by_table_id(table_id: str) -> List[Dict[str, Any]]:
    """
    根据table_id查询所有列信息
    
    Args:
        table_id: 表ID
        
    Returns:
        列信息列表
    """
    try:
        return cSingleSqlite.query_col_sql_by_table_id(table_id) or []
    except Exception as e:
        print(f"查询列信息失败: {e}")
        return []


def query_column_by_name(table_id: str, col_name: str) -> Optional[Dict[str, Any]]:
    """
    根据列名查询列信息
    
    Args:
        table_id: 表ID
        col_name: 列名
        
    Returns:
        列信息字典，如果不存在返回None
    """
    try:
        return cSingleSqlite.query_col_sql_by_table_id_and_name(table_id, col_name)
    except Exception as e:
        print(f"查询列信息失败: {e}")
        return None


def execute_sql(sql_id: str, sql: str) -> Dict[str, Any]:
    """
    执行SQL语句
    
    Args:
        sql_id: 数据库连接ID
        sql: SQL语句
        
    Returns:
        执行结果字典，包含：
        - success: 是否成功
        - row_count: 返回行数
        - columns: 列名列表
        - data: 数据列表（最多返回前100行）
        - error: 错误信息（如果有）
    """
    result = {
        "success": False,
        "row_count": 0,
        "columns": [],
        "data": [],
        "error": None
    }
    
    try:
        # 获取数据库连接信息
        database_info = query_database_info(sql_id)
        if not database_info:
            result["error"] = "未找到数据库连接信息"
            return result
        
        # 使用CControl执行SQL
        sql_control = CControl()
        conn, db_type = sql_control.connect_database(
            ip=database_info.get("ip", ""),
            port=database_info.get("port", ""),
            sql_type=database_info.get("sql_type", "mysql"),
            sql_name=database_info.get("sql_name", ""),
            sql_user_name=database_info.get("sql_user_name", ""),
            sql_user_password=database_info.get("sql_user_password", "")
        )
        
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            
            # 获取列名
            if cursor.description:
                result["columns"] = [desc[0] for desc in cursor.description]
            
            # 获取数据（限制行数，避免返回过多数据）
            rows = cursor.fetchall()
            result["row_count"] = len(rows)
            
            # 转换为字典列表（最多返回前100行）
            if rows:
                if db_type == 'postgresql':
                    # PostgreSQL使用RealDictCursor，已经是字典格式
                    result["data"] = rows[:10]
                else:
                    # MySQL需要手动转换为字典
                    result["data"] = [
                        {result["columns"][i]: row[i] for i in range(len(result["columns"]))}
                        for row in rows[:10]
                    ]
            
            result["success"] = True
            
        finally:
            conn.close()
            
    except Exception as e:
        result["error"] = str(e)
        print(f"⚠️ SQL执行失败: {e}")
    
    return result
