# -*- coding:utf-8 -*-

'''
数据库连接控制模块
'''

import os
import re
import logging
import threading
import uuid
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set
import networkx as nx
# from typing import Dict, Any, List, Optional
try:
    import pymysql
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False

from Db.sqlite_db import cSingleSqlite
from Sql.schema_vector import SqlSchemaVectorAgent
# from Sql.vanna_manager import get_vanna_manager

from Control.control_elastic import CControl as ElasticSearchController
from Control.control_graph import CControl as GraphController

# from Agent import analysis_schema_run
from Agent.AgenticSqlAgent.AnalysisSql.database_analysis_agent import DatabaseAnalysisAgent
from Config.elasticsearch_config import is_elasticsearch_enabled

# from Agent.SqlIntelligentAgents.sql_intelligent_workflow import SqlIntelligentWorkflow
# from Agent.SqlIntelligentAgents.select_sql_agent import SelectSqlAgent
# 创建线程安全的logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 设置日志级别
logger_lock = threading.Lock()

def thread_safe_log(level_func, message, *args, **kwargs):
    """线程安全的日志记录函数"""
    with logger_lock:
        level_func(message, *args, **kwargs)

class CControl:
    
    def __init__(self):
        self.db_obj = cSingleSqlite
        self.elasticsearch_obj = ElasticSearchController()
        self.graph_obj = GraphController()
        self.vector_agent = SqlSchemaVectorAgent()
        # self.graph_id = "graphiti_sql_knowledge_graph"
    
    def generate_id(self, prefix=''):
        """生成唯一ID"""
        return f"{prefix}_{uuid.uuid4().hex[:16]}" if prefix else uuid.uuid4().hex[:16]
    
    def connect_database(self, ip, port, sql_type, sql_name, sql_user_name, sql_user_password):
        """连接数据库"""
        try:
            if sql_type == 'mysql':
                if not MYSQL_AVAILABLE:
                    raise Exception("PyMySQL未安装，无法连接MySQL数据库")
                conn = pymysql.connect(
                    host=ip,
                    port=int(port),
                    user=sql_user_name,
                    password=sql_user_password,
                    database=sql_name,
                    charset='utf8mb4'
                )
                return conn, 'mysql'
            elif sql_type == 'postgresql':
                if not POSTGRESQL_AVAILABLE:
                    raise Exception("psycopg2未安装，无法连接PostgreSQL数据库")
                conn = psycopg2.connect(
                    host=ip,
                    port=int(port),
                    user=sql_user_name,
                    password=sql_user_password,
                    database=sql_name
                )
                return conn, 'postgresql'
            else:
                raise Exception(f"不支持的数据库类型: {sql_type}")
        except Exception as e:
            logger.error(f"连接数据库失败: {e}")
            raise
    
    def get_tables(self, conn, db_type):
        """获取数据库中的所有表"""
        try:
            cursor = conn.cursor()
            if db_type == 'mysql':
                cursor.execute("SHOW TABLES")
                tables = [row[0] for row in cursor.fetchall()]
            elif db_type == 'postgresql':
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                tables = [row[0] for row in cursor.fetchall()]
            else:
                tables = []
            cursor.close()
            return tables
        except Exception as e:
            logger.error(f"获取表列表失败: {e}")
            raise
    
    def get_table_description(self, conn, db_type, table_name):
        """获取表的描述信息
        
        Args:
            conn: 数据库连接
            db_type: 数据库类型 ('mysql' 或 'postgresql')
            table_name: 表名
            
        Returns:
            str: 表的描述信息，如果没有则返回空字符串
        """
        try:
            cursor = conn.cursor()
            table_description = ""
            
            if db_type == 'mysql':
                # MySQL: 查询 information_schema.tables 获取 TABLE_COMMENT
                # 先获取当前数据库名称
                cursor.execute("SELECT DATABASE()")
                db_name_row = cursor.fetchone()
                db_name = db_name_row[0] if db_name_row and db_name_row[0] else None
                
                if db_name:
                    cursor.execute("""
                        SELECT TABLE_COMMENT 
                        FROM information_schema.TABLES 
                        WHERE TABLE_SCHEMA = %s 
                        AND TABLE_NAME = %s
                    """, (db_name, table_name))
                    row = cursor.fetchone()
                    if row and row[0]:
                        table_description = row[0]
            elif db_type == 'postgresql':
                # PostgreSQL: 查询 pg_catalog.pg_description 获取表的描述
                cursor.execute("""
                    SELECT obj_description(pc.oid, 'pg_class') AS table_comment
                    FROM pg_catalog.pg_class pc
                    LEFT JOIN pg_catalog.pg_namespace pn
                      ON pn.oid = pc.relnamespace
                    WHERE pc.relname = %s
                      AND pn.nspname = 'public'
                """, (table_name,))
                row = cursor.fetchone()
                if row and row[0]:
                    table_description = row[0]
            
            cursor.close()
            return table_description if table_description else ""
        except Exception as e:
            logger.warning(f"获取表描述信息失败: {e}")
            return ""
    
    def get_table_columns(self, conn, db_type, table_name):
        """获取表的列信息
        
        Args:
            conn: 数据库连接
            db_type: 数据库类型 ('mysql' 或 'postgresql')
            table_name: 表名
            
        Returns:
            dict: 包含 'columns' 和 'table_description' 的字典
                - columns: 列信息列表
                - table_description: 表的描述信息
        """
        try:
            cursor = conn.cursor()
            columns = []
            
            # 获取表描述信息
            table_description = self.get_table_description(conn, db_type, table_name)
            
            if db_type == 'mysql':
                cursor.execute(f"SHOW FULL COLUMNS FROM `{table_name}`")
                rows = cursor.fetchall()
                for row in rows:
                    # SHOW FULL COLUMNS 返回:
                    # Field, Type, Collation, Null, Key, Default, Extra, Privileges, Comment
                    col_info = {
                        'col_name': row[0],
                        'col_type': row[1],
                        'collation': row[2],
                        'is_null': row[3],
                        'key': row[4],
                        'default': row[5],
                        'extra': row[6],
                        'privileges': row[7],
                        'comment': row[8]
                    }
                    columns.append(col_info)
            elif db_type == 'postgresql':
                cursor.execute("""
                    SELECT 
                        c.column_name,
                        c.data_type,
                        c.is_nullable,
                        c.column_default,
                        pgd.description AS column_comment
                    FROM information_schema.columns c
                    LEFT JOIN pg_catalog.pg_class pc 
                      ON pc.relname = c.table_name
                    LEFT JOIN pg_catalog.pg_namespace pn
                      ON pn.nspname = c.table_schema 
                     AND pn.oid = pc.relnamespace
                    LEFT JOIN pg_catalog.pg_description pgd
                      ON pgd.objoid = pc.oid 
                     AND pgd.objsubid = c.ordinal_position
                    WHERE c.table_name = %s
                      AND c.table_schema = 'public'
                    ORDER BY c.ordinal_position
                """, (table_name,))
                rows = cursor.fetchall()
                for row in rows:
                    col_info = {
                        'col_name': row[0],
                        'col_type': row[1],
                        'is_nullable': row[2],
                        'column_default': row[3],
                        'comment': row[4]
                    }
                    columns.append(col_info)
            
            cursor.close()
            return {
                'columns': columns,
                'table_description': table_description
            }
        except Exception as e:
            logger.error(f"获取表列信息失败: {e}")
            raise

    def get_table_foreign_keys(self, conn, db_type, table_name):
        """获取表的外键信息"""
        try:
            cursor = conn.cursor()
            foreign_keys = []

            if db_type == 'mysql':
                cursor.execute("""
                    SELECT 
                        kcu.TABLE_NAME,
                        kcu.COLUMN_NAME,
                        kcu.REFERENCED_TABLE_NAME,
                        kcu.REFERENCED_COLUMN_NAME
                    FROM information_schema.KEY_COLUMN_USAGE kcu
                    WHERE kcu.TABLE_SCHEMA = DATABASE()
                      AND kcu.TABLE_NAME = %s
                      AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
                """, (table_name,))
                rows = cursor.fetchall()
                for row in rows:
                    foreign_keys.append({
                        'from_table': row[0],
                        'from_col': row[1],
                        'to_table': row[2],
                        'to_col': row[3]
                    })
            elif db_type == 'postgresql':
                cursor.execute("""
                    SELECT
                        tc.table_name AS from_table,
                        kcu.column_name AS from_column,
                        ccu.table_name AS to_table,
                        ccu.column_name AS to_column
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                     AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_name = %s
                      AND tc.table_schema = 'public'
                """, (table_name,))
                rows = cursor.fetchall()
                for row in rows:
                    foreign_keys.append({
                        'from_table': row[0],
                        'from_col': row[1],
                        'to_table': row[2],
                        'to_col': row[3]
                    })

            cursor.close()
            return foreign_keys
        except Exception as e:
            logger.error(f"获取外键信息失败: {e}")
            raise
    
    def get_relation(self, sql_id):
        all_foreign_keys_map = {}
        relations = cSingleSqlite.query_rel_sql_by_sql_id(sql_id)
        for rel in relations or []:
            from_table = rel.get("from_table", "")
            if from_table not in all_foreign_keys_map:
                all_foreign_keys_map[from_table] = []
        
            all_foreign_keys_map[from_table].append({
                "from_table": from_table,
                        "from_col": rel.get("from_col", ""),
                        "to_table": rel.get("to_table", ""),
                        "to_col": rel.get("to_col", "")
                    })
        return all_foreign_keys_map
    
    def analysis_schema(self, table):
        """
        基于规则的Schema分析（不使用智能体）
        
        Args:
            table: 表信息字典，包含：
                - table_name: 表名
                - table_description: 表描述
                - columns: 列信息列表，每个元素包含：
                    - col_name: 列名
                    - col_type: 列类型
                    - col_info: 列详细信息（字典，包含comment, is_nullable等）
        
        Returns:
            Dict: 分析结果，格式见注释
        """
        try:
            table_name = table.get("table_name", "")
            table_description = table.get("table_description", "")
            columns = table.get("columns", [])
            sql_id = table.get("sql_id", "")
            
            if not table_name:
                return {
                    "success": False,
                    "table_name": "",
                    "error": "表名为空"
                }
            
            # 1. 判断是否为测试表
            is_test_table = self._is_test_table(table_name, table_description)
            
            # 2. 判断命名规范程度
            naming_standard = self._check_naming_standard(table_name, columns)
            
            # 3. 确定主体（entity）
            entity_name, entity_description = self._extract_entity(table_name, table_description)
            
            # 4. 获取外键信息
            foreign_keys_list = []
            if sql_id:
                all_foreign_keys_map = self.get_relation(sql_id)
                foreign_keys_list = all_foreign_keys_map.get(table_name, [])
            
            # 5. 处理列信息
            attributes = []
            metrics = []
            unique_identifiers = []
            
            # 获取主键和唯一键信息（从列信息中推断）
            primary_keys = []
            unique_keys = []
            
            for col in columns:
                col_name = col.get("col_name", "")
                col_type = col.get("col_type", "").lower()
                
                # 获取列注释（优先从 col_comment，其次从 col_info）
                col_comment = col.get("col_comment", "")
                
                # 尝试从 col_info 获取更多信息
                col_info = col.get("col_info", {})
                if isinstance(col_info, str):
                    try:
                        col_info = json.loads(col_info)
                    except:
                        col_info = {}
                elif col_info is None:
                    col_info = {}
                
                # 如果 col_comment 为空，尝试从 col_info 获取
                if not col_comment and isinstance(col_info, dict):
                    col_comment = col_info.get("comment", "")
                
                # 判断主键和唯一键
                # 方法1：从 col_info 中获取（MySQL的key字段：PRI=主键，UNI=唯一键）
                is_primary = False
                is_unique = False
                
                if isinstance(col_info, dict):
                    key_type = col_info.get("key", "").upper()
                    if key_type == "PRI":
                        is_primary = True
                    elif key_type == "UNI":
                        is_unique = True
                    # 也检查其他可能的字段
                    if col_info.get("is_primary", False):
                        is_primary = True
                    if col_info.get("is_unique", False):
                        is_unique = True
                
                # 方法2：根据列名推断（常见命名规则）
                col_name_lower = col_name.lower()
                table_name_lower = table_name.lower()
                
                # 主键常见命名：id, table_id
                if not is_primary and (col_name_lower == 'id' or col_name_lower == f"{table_name_lower}_id"):
                    is_primary = True
                # 唯一键常见命名：code, no, number 等（且不是主键）
                elif not is_unique and not is_primary and col_name_lower in ['code', 'no', 'number', 'sn', 'serial_no']:
                    is_unique = True
                
                # 处理列名和注释
                col_display_name = self._parse_column_name(col_name)
                col_description = col_comment if col_comment else col_display_name
                
                # 判断列类型
                is_numeric = self._is_numeric_type(col_type)
                is_text = self._is_text_type(col_type)
                is_datetime = self._is_datetime_type(col_type)
                
                # 主键和唯一键（优先处理，因为它们不应该同时出现在属性和指标中）
                if is_primary:
                    primary_keys.append(col_name)
                    unique_identifiers.append({
                        "identifier_name": col_display_name,
                        "identifier_type": "primary_key",
                        "col_name": col_name,
                        "description": col_description
                    })
                    # 主键通常也是唯一标识符，跳过后续的属性/指标分类
                    continue
                elif is_unique:
                    unique_keys.append(col_name)
                    unique_identifiers.append({
                        "identifier_name": col_display_name,
                        "identifier_type": "unique_key",
                        "col_name": col_name,
                        "description": col_description
                    })
                    # 唯一键也跳过后续的属性/指标分类
                    continue
                
                # 时间类型列（作为属性）
                if is_datetime:
                    attributes.append({
                        "attr_name": col_display_name,
                        "attr_type": "datetime",
                        "attr_description": col_description,
                        "col_name": col_name
                    })
                # 数值类型列（作为指标）
                elif is_numeric:
                    metrics.append({
                        "metric_name": col_display_name,
                        "metric_type": "numeric",  # 可以是 count, sum, avg, max, min 等
                        "metric_description": col_description,
                        "col_name": col_name
                    })
                # 文本类型列（作为属性）
                elif is_text:
                    attributes.append({
                        "attr_name": col_display_name,
                        "attr_type": "text",
                        "attr_description": col_description,
                        "col_name": col_name
                    })
                else:
                    # 其他类型默认作为属性
                    attributes.append({
                        "attr_name": col_display_name,
                        "attr_type": "other",
                        "attr_description": col_description,
                        "col_name": col_name
                    })
            
            # 6. 处理外键信息
            foreign_keys_result = []
            for fk in foreign_keys_list:
                from_col = fk.get("from_col", "")
                to_table = fk.get("to_table", "")
                to_col = fk.get("to_col", "")
                
                # 推断关系类型（简化处理，默认为 one_to_many）
                relationship_type = "entity_to_entity"
                
                foreign_keys_result.append({
                    "fk_name": f"{table_name}_{from_col}_fk",
                    "from_col": from_col,
                    "to_table": to_table,
                    "to_col": to_col,
                    "relationship_type": relationship_type,
                    "description": f"关联到 {to_table} 表的 {to_col} 字段"
                })
            
            # 7. 生成分析理由
            analysis_reason = self._generate_analysis_reason(
                table_name, entity_name, len(attributes), len(metrics), 
                len(unique_identifiers), len(foreign_keys_result)
            )
            
            # 返回格式需要与 save_schema_analysis_graph_data 期望的格式一致
            return {
                "table_name": table_name,
                "table_id": table.get("table_id", ""),
                "analysis_result": {
                    "success": True,
                    "table_name": table_name,
                    "is_test_table": is_test_table,
                    "naming_standard": naming_standard,
                    "entity": {
                        "entity_name": entity_name,
                        "entity_description": entity_description
                    },
                    "attributes": attributes,
                    "metrics": metrics,
                    "unique_identifiers": unique_identifiers,
                    "foreign_keys": foreign_keys_result,
                    "analysis_reason": analysis_reason
                }
            }
            
        except Exception as e:
            traceback.print_exc()
            return {
                "table_name": table.get("table_name", ""),
                "table_id": table.get("table_id", ""),
                "analysis_result": {
                    "success": False,
                    "table_name": table.get("table_name", ""),
                    "error": str(e)
                }
            }
    
    def _is_test_table(self, table_name: str, table_description: str) -> bool:
        """判断是否为测试表"""
        test_keywords = ['test', 'demo', 'tmp', 'temp', 'sample', '测试', '示例', '临时', 'demo']
        table_name_lower = table_name.lower()
        desc_lower = (table_description or "").lower()
        
        # 检查表名
        if any(keyword in table_name_lower for keyword in test_keywords):
            return True
        
        # 检查表描述
        if table_description and any(keyword in desc_lower for keyword in test_keywords):
            return True
        
        return False
    
    def _check_naming_standard(self, table_name: str, columns: list) -> str:
        """检查命名规范程度"""
        # 检查表名：snake_case 或 camelCase 都算标准
        table_pattern = re.compile(r'^[a-z][a-z0-9_]*$|^[a-z][a-zA-Z0-9]*$')
        if not table_pattern.match(table_name.lower()):
            return "non_standard"
        
        # 检查列名：至少80%的列符合规范
        standard_count = 0
        total_count = 0
        
        for col in columns:
            col_name = col.get("col_name", "")
            if not col_name:
                continue
            
            total_count += 1
            col_pattern = re.compile(r'^[a-z][a-z0-9_]*$|^[a-z][a-zA-Z0-9]*$')
            if col_pattern.match(col_name.lower()):
                standard_count += 1
        
        if total_count == 0:
            return "standard"
        
        # 如果80%以上符合规范，认为是标准命名
        if standard_count / total_count >= 0.8:
            return "standard"
        else:
            return "non_standard"
    
    def _extract_entity(self, table_name: str, table_description: str) -> tuple:
        """提取主体信息"""
        # 如果有表描述，使用表描述作为主体描述
        entity_name = self._parse_table_name(table_name)
        if table_description:
            entity_description = table_description
        else:
            # 使用表名作为主体名称
            entity_description = entity_name
        
        return entity_name, entity_description
    
    def _parse_table_name(self, table_name: str) -> str:
        """解析表名（snake_case转成可读文本）"""
        # 移除表名前缀（如：t_, tbl_等）
        name = table_name.lower()
        prefixes = ['t_', 'tbl_', 'table_']
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        
        # 分割下划线
        parts = name.split('_')
        # 将每个部分首字母大写
        # parts = [part.capitalize() for part in parts if part]
        return " ".join(parts)
    
    def _parse_column_name(self, col_name: str) -> str:
        """解析列名（snake_case转成可读文本）"""
        # 移除列名后缀（如：_id, _name等）
        name = col_name.lower()
        
        # 分割下划线
        parts = name.split('_')
        # 将每个部分首字母大写
        # parts = [part.capitalize() for part in parts if part]
        return " ".join(parts)
    
    def _is_numeric_type(self, col_type: str) -> bool:
        """判断是否为数值类型"""
        numeric_types = ['int', 'integer', 'bigint', 'smallint', 'tinyint', 
                        'float', 'double', 'decimal', 'numeric', 'real', 
                        'number', 'money', 'smallmoney']
        return any(nt in col_type.lower() for nt in numeric_types)
    
    def _is_text_type(self, col_type: str) -> bool:
        """判断是否为文本类型"""
        text_types = ['varchar', 'char', 'text', 'string', 'nvarchar', 
                     'nchar', 'ntext', 'clob', 'blob']
        return any(tt in col_type.lower() for tt in text_types)
    
    def _is_datetime_type(self, col_type: str) -> bool:
        """判断是否为时间类型"""
        datetime_types = ['date', 'time', 'datetime', 'timestamp', 
                         'year', 'interval']
        return any(dt in col_type.lower() for dt in datetime_types)
    
    def _generate_analysis_reason(self, table_name: str, entity_name: str, 
                                  attr_count: int, metric_count: int,
                                  identifier_count: int, fk_count: int) -> str:
        """生成分析理由"""
        reasons = []
        reasons.append(f"表 {table_name} 代表业务实体：{entity_name}")
        
        if attr_count > 0:
            reasons.append(f"包含 {attr_count} 个属性字段")
        if metric_count > 0:
            reasons.append(f"包含 {metric_count} 个指标字段")
        if identifier_count > 0:
            reasons.append(f"包含 {identifier_count} 个唯一标识符")
        if fk_count > 0:
            reasons.append(f"包含 {fk_count} 个外键关联")
        
        return "；".join(reasons)
    
    def insert_sql_info(self, param):
        """插入数据库信息 - 连接数据库，获取表和列信息，保存到数据库"""
        try:
            user_id = param.get("user_id")
            ip = param.get("ip")
            port = param.get("port")
            sql_type = param.get("sql_type")
            sql_name = param.get("sql_name")
            sql_user_name = param.get("sql_user_name")
            sql_user_password = param.get("sql_user_password")
            sql_description = param.get("sql_description", "")
            
            if not all([user_id, ip, port, sql_type, sql_name, sql_user_name, sql_user_password]):
                return {"success": False, "message": "缺少必要参数"}
            
            # 生成sql_id
            if("sql_id" in param.keys()):
                sql_id = param.get("sql_id")
            else:
                sql_id = self.generate_id("sql")
            
            # 连接数据库测试
            conn = None
            try:
                conn, db_type = self.connect_database(
                    ip, port, sql_type, sql_name, sql_user_name, sql_user_password
                )
                
                # 获取所有表
                tables = self.get_tables(conn, db_type)
                logger.info(f"获取到{len(tables)}个表")
                # 保存base_sql信息
                base_sql_param = {
                    "sql_id": sql_id,
                    "user_id": user_id,
                    "ip": ip,
                    "port": port,
                    "sql_type": sql_type,
                    "sql_name": sql_name,
                    "sql_user_name": sql_user_name,
                    "sql_user_password": sql_user_password,
                    "sql_description": sql_description
                }
                
                if not self.db_obj.insert_base_sql(base_sql_param):
                    raise Exception("保存数据库连接信息失败")
                
                all_tables_analysis = []
                des_list = []
                for table_name in tables:
                    # 获取表的列信息和描述信息
                    table_info = self.get_table_columns(conn, db_type, table_name)
                    columns = table_info.get("columns", [])
                    table_description = table_info.get("table_description", "")
                    
                    # 保存表信息
                    table_id = self.generate_id("table")
                    table_sql_param = {
                        "table_id": table_id,
                        "sql_id": sql_id,
                        "table_name": table_name,
                        "table_description": table_description  # 使用获取到的表描述
                    }
                    self.db_obj.insert_table_sql(table_sql_param)
                    
                    columns_comments = []
                    # 保存列信息
                    for col in columns:
                        col_id = self.generate_id("col")
                        
                        # 判断列类型
                        col_typy_ana = ""
                        col_type = col.get("col_type", "")
                        is_numeric = self._is_numeric_type(col_type)
                        if(is_numeric):
                            col_typy_ana = "numeric"
                        is_text = self._is_text_type(col_type)
                        if(is_text):
                            col_typy_ana = "attribute"
                        is_datetime = self._is_datetime_type(col_type)
                        if(is_datetime):
                            col_typy_ana = "datetime"
                        
                        col["ana_type"] = col_typy_ana
                        col_sql_param = {
                            "col_id": col_id,
                            "table_id": table_id,
                            "col_name": col["col_name"],
                            "col_type": col.get("col_type", ""),
                            "col_info": col  # 保存完整的列信息JSON
                        }
                        
                        col_name = col["col_name"]
                        col_comment = col.get("comment", "")
                        if(col_comment):
                            columns_comments.append(col_comment)
                        else:
                            col_comment = self._parse_column_name(col_name)
                            columns_comments.append(col_comment)
                            
                        self.db_obj.insert_col_sql(col_sql_param)
                    
                    table_title = self._parse_table_name(table_name)
                    
                    if(table_description):
                        table_title = table_title + "\n" + table_description
                        
                    # 保存外键信息
                    foreign_keys = self.get_table_foreign_keys(conn, db_type, table_name)
                    for fk in foreign_keys:
                        rel_id = self.generate_id("rel")
                        rel_param = {
                            "rel_id": rel_id,
                            "sql_id": sql_id,
                            "from_table": fk.get("from_table"),
                            "from_col": fk.get("from_col"),
                            "to_table": fk.get("to_table"),
                            "to_col": fk.get("to_col")
                        }
                        self.db_obj.insert_rel_sql(rel_param)
                    
                    file_id = table_id
                    content_str = ";".join(columns_comments)
                    permission_level = "public"
                    # 保存到Elasticsearch（如果启用）
                    
                    if is_elasticsearch_enabled():
                        self.elasticsearch_obj.save_document_to_elastic(sql_id, file_id, 
                                                                        user_id, permission_level,
                                                                        table_title, content_str)
                    
                    des_list.append([table_id, table_title, content_str])

                    # 从数据库查询完整的列信息（包含 col_info）
                    full_columns = self.db_obj.query_col_sql_by_table_id(table_id)
                    
                    if(not table_description):
                        table_description = content_str
                    
                    # 构建完整的 table_info 用于分析
                    analysis_table_info = {
                        "table_id": table_id,
                        "sql_id": sql_id,
                        "table_name": table_name,
                        "table_description": table_description,
                        "columns": full_columns  # 使用完整的列信息，包含 col_info
                    }
                    
                    analysis_schema = self.analysis_schema(analysis_table_info)
                    all_tables_analysis.append(analysis_schema)
                    print("analysis_schema:", analysis_schema)
                    
                logger.info(f"📊 回调函数执行完成，共收集到 {len(all_tables_analysis)} 个表的结果")
                
                if(des_list):
                    try:
                        agent = DatabaseAnalysisAgent()
                        
                        logger.info(f"📊 开始分析数据库描述文本，共 {len(des_list)} 个表")
                        
                        # 直接调用智能体分析整个列表（des_list 格式: [["title", "content"], ...]）
                        # des_list = des_list[:10]
                        result = agent.analyze_database_descriptions(des_list, sql_id)
                        
                        if result.get("success"):
                            logger.info(f"✅ 数据库描述文本分析完成，共分析 {result.get('total_tables', 0)} 个表")
                            print("分析数据库描述文本结果:", result)
                        else:
                            error_msg = result.get("error", "分析失败")
                            logger.warning(f"⚠️ 数据库描述文本分析失败: {error_msg}")
                            return {"success": False, "message": f"分析数据库描述文本失败: {error_msg}"}
                    except Exception as e:
                        logger.error(f"分析数据库描述文本异常: {e}")
                        traceback.print_exc()
                        return {"success": False, "message": f"分析数据库描述文本失败: {str(e)}"}

                if all_tables_analysis:
                    try:
                        # 先保存到 SQLite（批量保存所有表的分析结果）
                        try:
                            # 统计测试表和标准命名表的数量
                            test_tables_count = sum(1 for ta in all_tables_analysis 
                                                  if ta.get("analysis_result", {}).get("is_test_table", False))
                            standard_naming_count = sum(1 for ta in all_tables_analysis 
                                                       if ta.get("analysis_result", {}).get("naming_standard") == "standard")
                            
                            # 批量保存所有表的分析结果到 SQLite
                            for table_analysis in all_tables_analysis:
                                table_id = table_analysis.get("table_id", "")
                                table_name = table_analysis.get("table_name", "")
                                analysis_result = table_analysis.get("analysis_result", {})
                                
                                if table_id and table_name and analysis_result:
                                    self.db_obj.insert_schema_analysis_result(
                                        sql_id=sql_id,
                                        table_id=table_id,
                                        table_name=table_name,
                                        analysis_result=analysis_result,
                                        total_tables=len(all_tables_analysis),
                                        test_tables_count=test_tables_count,
                                        standard_naming_count=standard_naming_count
                                    )
                            logger.info(f"✅ 保存 {len(all_tables_analysis)} 个表的分析结果到SQLite成功")
                        except Exception as e:
                            logger.warning(f"批量保存Schema分析结果到SQLite失败: {e}")
                            traceback.print_exc()
                        
                        logger.info(f"📊 准备保存 {len(all_tables_analysis)} 个表的分析结果到图数据库")
                        
                        # 构建完整的分析结果用于图数据库保存
                        # 注意：all_tables_analysis 中每个元素的结构为：
                        # {
                        #     "table_name": "...",
                        #     "table_id": "...",
                        #     "analysis_result": {
                        #         "entity": {...},
                        #         "attributes": [...],
                        #         "unique_identifiers": [...],
                        #         "foreign_keys": [...],
                        #         ...
                        #     }
                        # }
                        # 这个结构完全匹配 save_schema_analysis_graph_data 方法期望的格式
                        filtered_schema_result = {
                            "success": True,
                            "sql_id": sql_id,
                            "tables_analysis": all_tables_analysis,  # 已筛选，只包含核心业务表
                            "total_tables": len(all_tables_analysis),
                            "test_tables_count": 0,  # 已过滤，不包含测试表
                            "standard_naming_count": len(all_tables_analysis)  # 已过滤，只包含规范命名的表
                        }
                        
                        # self.graph_obj.save_schema_analysis_graph_data(
                        #     filtered_schema_result, 
                        #     sql_id, 
                        #     permission_level="public"
                        # )
                        logger.info(f"✅ 保存 {len(all_tables_analysis)} 个表的分析结果到图数据库成功")
                    except Exception as e:
                        logger.error(f"保存 Schema 分析图数据异常: {e}")
                        traceback.print_exc()
                        # 继续执行，不影响后续流程
                else:
                    logger.warning(f"⚠️ 没有收集到任何表分析结果，跳过图数据库保存")
                
                conn.close()
                return {"success": True, "message": "数据库信息添加成功", "sql_id": sql_id}
                
            except Exception as e:
                if conn:
                    conn.close()
                logger.error(f"插入数据库信息失败: {e}")
                return {"success": False, "message": f"添加数据库失败: {str(e)}"}
                
        except Exception as e:
            logger.error(f"插入数据库信息异常: {e}")
            return {"success": False, "message": f"添加数据库失败: {str(e)}"}
    
    def get_table_info(self, param):
        """获取表信息 - 生成列数据"""
        try:
            sql_id = param.get("sql_id")
            ip = param.get("ip")
            port = param.get("port")
            sql_type = param.get("sql_type")
            sql_name = param.get("sql_name")
            user_id = param.get("user_id")
            
            if not sql_id:
                # 如果没有sql_id，尝试根据其他参数查找
                base_sql_list = self.db_obj.query_base_sql_by_user_id(user_id)
                matched = None
                for db in base_sql_list:
                    if db["ip"] == ip and db["port"] == port and db["sql_type"] == sql_type and db["sql_name"] == sql_name:
                        matched = db
                        break
                if not matched:
                    return {"success": False, "message": "未找到对应的数据库信息"}
                sql_id = matched["sql_id"]
            
            # 查询表信息
            tables = self.db_obj.query_table_sql_by_sql_id(sql_id)
            
            # 组装表列表和列信息
            table_list = []
            for table in tables:
                table_id = table["table_id"]
                # 查询列信息
                columns = self.db_obj.query_col_sql_by_table_id(table_id)
                
                # 转换为ColumnInfo格式
                column_info_list = []
                for col in columns:
                    col_info = {
                        "col_id": col.get("col_id"),
                        "table_id": col.get("table_id"),
                        "col_name": col.get("col_name"),
                        "col_type": col.get("col_type"),
                        "col_info": col.get("col_info")
                    }
                    column_info_list.append(col_info)
                
                table_info = {
                    "table_id": table["table_id"],
                    "sql_id": table["sql_id"],
                    "table_name": table["table_name"],
                    "table_description": table.get("table_description", ""),
                    "columns": column_info_list
                }
                table_list.append(table_info)
            
            # 查询关联关系
            relations = self.db_obj.query_rel_sql_by_sql_id(sql_id)
            sql_des_list = self.db_obj.query_sql_des_by_sql_id(sql_id)
            sql_list = []
            for sql_des in sql_des_list:
                tmp_d = {}
                tmp_d["des"] = sql_des.get("sql_des", "")
                tmp_d["sql"] = sql_des.get("sql", "")
                sql_list.append(tmp_d)
            
            return {
                "success": True,
                "message": "获取表信息成功",
                "table_list": table_list,
                "relations": relations,
                "sql_list": sql_list
            }
            
        except Exception as e:
            logger.error(f"获取表信息失败: {e}")
            return {"success": False, "message": f"获取表信息失败: {str(e)}"}
        
    def delete_sql_rel(self, param):
        """删除数据库关联关系"""
        try:
            rel_id = param.get("rel_id")
            
            if not rel_id:
                return {"success": False, "message": "缺少必要参数"}
            
            # 删除关联关系
            if self.db_obj.delete_rel_sql_by_rel_id(rel_id):
                return {"success": True, "message": "删除关联关系成功"}
            else:
                return {"success": False, "message": "关联关系不存在或删除失败"}
            
        except Exception as e:
            logger.error(f"删除关联关系失败: {e}")
            return {"success": False, "message": f"删除关联关系失败: {str(e)}"}
            
    def insert_sql_rel(self, param):
        """插入数据库关联关系"""
        try:
            sql_id = param.get("sql_id")
            relations = param.get("relations", [])
            
            if not sql_id:
                return {"success": False, "message": "缺少必要参数"}
            
            # 插入新的关联关系
            for relation in relations:
                rel_id = self.generate_id("rel")
                rel_param = {
                    "rel_id": rel_id,
                    "sql_id": sql_id,
                    "from_table": relation.get("from_table"),
                    "from_col": relation.get("from_col"),
                    "to_table": relation.get("to_table"),
                    "to_col": relation.get("to_col")
                }
                self.db_obj.insert_rel_sql(rel_param)
            
            return {"success": True, "message": "插入关联关系成功"}
            
        except Exception as e:
            logger.error(f"插入关联关系失败: {e}")
            return {"success": False, "message": f"插入关联关系失败: {str(e)}"}
    
    def delete_sql_info(self, param):
        """删除数据库数据"""
        sql_id = param.get("sql_id")
        
        # self.graph_obj.delete_sql_graph_data(sql_id)
        # self.graph_obj.delete_all_graph()
        
        self.vector_agent.delete_vector_store_by_sql_id(sql_id)
        
        self.elasticsearch_obj.delete_knowledge_elasticsearch_data(knowledge_id=sql_id)
        
        try:
            success = cSingleSqlite.delete_base_sql(sql_id)
            if success:
                return {"success": True, "message": "删除数据库信息成功"}
            else:
                return {"success": False, "message": "删除数据库信息失败"}
        except Exception as e:
            logger.error(f"删除数据库信息失败: {e}")
            return {"success": False, "message": f"删除数据库信息失败: {str(e)}"}
        return {"success": False, "message": "删除数据库信息失败"}
    
    def update_sql_info(self, param):
        """更新数据库信息 - 保存列关联数据"""
        try:
            success = self.delete_sql_info(param)
            if(success):
                self.insert_sql_info(param)
                return {"success": True, "message": "更新成功"}
            else:
                return {"success": False, "message": "更新失败"}
        except Exception as e:
            logger.error(f"更新数据库信息失败: {e}")
            return {"success": False, "message": f"更新数据库信息失败: {str(e)}"}

    # def build_schema_vector_store(self, param):
    #     """构建数据库模式向量库"""
    #     try:
    #         user_id = param.get("user_id")
    #         if not user_id:
    #             return {"success": False, "message": "缺少用户ID"}
    #
    #         # 调用向量代理构建向量库
    #         agent = SqlSchemaVectorAgent()
    #         result = agent.build_or_update_store(user_id)
    #
    #         return result
    #     except Exception as e:
    #         logger.error(f"构建向量库失败: {e}")
    #         return {"success": False, "message": f"构建向量库失败: {str(e)}"}


class SchemaGraphBuilder:
    """数据库模式关联图构建器"""

    def __init__(self):
        try:
            self.nx = nx
            # NETWORKX_AVAILABLE = True
        except ImportError:
            raise ImportError("NetworkX未安装，请安装: pip install networkx")

    def build_graph(self, sql_id: str, filtered_tables: List[str] = None) -> Any:
        """构建数据库模式的关联图"""
        try:
            # 创建多重有向图
            G = self.nx.MultiDiGraph()

            # 获取表信息
            tables = self.db_obj.query_table_sql_by_sql_id(sql_id)

            # 如果指定了过滤表，则只处理这些表
            if filtered_tables:
                table_name_set = set(filtered_tables)
                tables = [t for t in tables if t["table_name"] in table_name_set]

            # 添加表节点
            for table in tables:
                table_name = table["table_name"]
                G.add_node(table_name,
                          node_type="table",
                          table_id=table["table_id"],
                          description=table.get("table_description", ""),
                          sql_id=sql_id)

                # 获取列信息并添加到节点属性
                columns = self.db_obj.query_col_sql_by_table_id(table["table_id"])
                col_info = {}
                for col in columns:
                    col_info[col["col_name"]] = {
                        "col_id": col["col_id"],
                        "col_type": col.get("col_type", ""),
                        "col_info": col.get("col_info", {})
                    }
                G.nodes[table_name]["columns"] = col_info

            # 获取关联关系并添加边
            relations = self.db_obj.query_rel_sql_by_sql_id(sql_id)

            for rel in relations:
                from_table = rel["from_table"]
                to_table = rel["to_table"]
                from_col = rel["from_col"]
                to_col = rel["to_col"]

                # 只添加在过滤表范围内的关联
                if filtered_tables:
                    if from_table not in table_name_set or to_table not in table_name_set:
                        continue

                # 添加有向边（外键关系）
                G.add_edge(from_table, to_table,
                          from_col=from_col,
                          to_col=to_col,
                          relation_type="foreign_key",
                          weight=1.0)  # 基础权重

                # 同时添加反向边（用于查询路径）
                G.add_edge(to_table, from_table,
                          from_col=to_col,
                          to_col=from_col,
                          relation_type="reverse_foreign_key",
                          weight=2.0)  # 反向查询权重稍高

            logger.info(f"构建关联图完成: {G.number_of_nodes()} 个节点, {G.number_of_edges()} 条边")
            return G

        except Exception as e:
            logger.error(f"构建关联图失败: {e}")
            raise

    def find_optimal_paths(self, graph: Any, query_entities: List[str],
                          max_depth: int = 3) -> Dict[str, Any]:
        """寻找最优的关联路径"""
        try:
            if not query_entities:
                return {"paths": [], "tables": set(), "columns": set()}

            # 找到图中存在的查询实体（表名）
            available_entities = []
            for entity in query_entities:
                if entity in graph.nodes:
                    available_entities.append(entity)
                else:
                    # 尝试模糊匹配
                    matches = [n for n in graph.nodes if entity.lower() in n.lower()]
                    available_entities.extend(matches[:1])  # 最多匹配一个

            if not available_entities:
                return {"paths": [], "tables": set(), "columns": set()}

            all_paths = []
            visited_tables = set()
            visited_columns = set()

            # 从每个查询实体出发，寻找关联路径
            for start_entity in available_entities:
                # BFS搜索关联路径
                paths_from_start = self._bfs_search(graph, start_entity, max_depth)

                for path_info in paths_from_start:
                    all_paths.append(path_info)

                    # 收集涉及的表和列
                    for node in path_info["path"]:
                        visited_tables.add(node)

                        # 获取该表的所有列
                        if node in graph.nodes:
                            columns = graph.nodes[node].get("columns", {})
                            visited_columns.update(columns.keys())

            # 按路径长度和权重排序
            all_paths.sort(key=lambda x: (len(x["path"]), x["total_weight"]))

            # 去重并保留最优路径
            unique_paths = self._deduplicate_paths(all_paths)

            return {
                "paths": unique_paths[:10],  # 最多返回10条最优路径
                "tables": list(visited_tables),
                "columns": list(visited_columns)
            }

        except Exception as e:
            logger.error(f"寻找最优路径失败: {e}")
            raise

    def _bfs_search(self, graph: Any, start_node: str, max_depth: int) -> List[Dict[str, Any]]:
        """BFS搜索从起始节点出发的路径"""
        from collections import deque

        paths = []
        visited = set()
        queue = deque([(start_node, [start_node], 0.0, [])])  # (当前节点, 路径, 总权重, 边信息)

        while queue:
            current_node, path, total_weight, edge_info = queue.popleft()

            if len(path) > max_depth + 1:  # 路径长度超过最大深度
                continue

            # 记录路径
            if len(path) > 1:  # 至少包含两个节点
                paths.append({
                    "path": path.copy(),
                    "total_weight": total_weight,
                    "edges": edge_info.copy(),
                    "start_table": start_node,
                    "end_table": current_node
                })

            # 避免重复访问
            if current_node in visited and len(path) > 2:
                continue
            visited.add(current_node)

            # 探索邻居节点
            for neighbor in graph.neighbors(current_node):
                if neighbor not in path:  # 避免环
                    # 获取边信息
                    edges = graph.get_edge_data(current_node, neighbor)
                    if edges:
                        for edge_key, edge_data in edges.items():
                            new_path = path + [neighbor]
                            new_weight = total_weight + edge_data.get("weight", 1.0)
                            new_edge_info = edge_info + [{
                                "from_table": current_node,
                                "to_table": neighbor,
                                "from_col": edge_data.get("from_col", ""),
                                "to_col": edge_data.get("to_col", ""),
                                "relation_type": edge_data.get("relation_type", "")
                            }]

                            queue.append((neighbor, new_path, new_weight, new_edge_info))

        return paths

    def _deduplicate_paths(self, paths: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去重路径，保留权重最小的"""
        path_dict = {}

        for path_info in paths:
            path_tuple = tuple(path_info["path"])
            weight = path_info["total_weight"]

            if path_tuple not in path_dict or weight < path_dict[path_tuple]["total_weight"]:
                path_dict[path_tuple] = path_info

        return list(path_dict.values())

    def get_related_tables_and_columns(self, sql_id: str, related_tables: List[str]) -> Dict[str, Any]:
        """获取关联的表和列信息"""
        try:
            result = {
                "tables": [],
                "columns": [],
                "relations": []
            }

            # 获取表信息
            for table_name in related_tables:
                table_info = self.db_obj.query_table_sql_by_sql_id_and_name(sql_id, table_name)
                if table_info:
                    result["tables"].append(table_info)

                    # 获取列信息
                    columns = self.db_obj.query_col_sql_by_table_id(table_info["table_id"])
                    result["columns"].extend(columns)

            # 获取关联关系
            relations = self.db_obj.query_rel_sql_by_sql_id(sql_id)

            # 过滤只包含相关表的关联关系
            related_table_set = set(related_tables)
            filtered_relations = [
                rel for rel in relations
                if rel["from_table"] in related_table_set and rel["to_table"] in related_table_set
            ]
            result["relations"] = filtered_relations

            return result

        except Exception as e:
            logger.error(f"获取关联表和列信息失败: {e}")
            raise


# 添加到CControl类中作为方法
def build_schema_graph(self, param):
    """构建数据库模式关联图"""
    try:
        sql_id = param.get("sql_id")
        filtered_tables = param.get("filtered_tables", [])

        if not sql_id:
            return {"success": False, "message": "缺少sql_id"}

        graph_builder = SchemaGraphBuilder()
        graph = graph_builder.build_graph(sql_id, filtered_tables if filtered_tables else None)

        return {
            "success": True,
            "message": "关联图构建成功",
            "graph_info": {
                "nodes": graph.number_of_nodes(),
                "edges": graph.number_of_edges(),
                "tables": list(graph.nodes())
            }
        }

    except Exception as e:
        logger.error(f"构建关联图失败: {e}")
        return {"success": False, "message": f"构建关联图失败: {str(e)}"}

def find_schema_paths(self, param):
    """寻找数据库模式的最优关联路径"""
    try:
        sql_id = param.get("sql_id")
        query_entities = param.get("query_entities", [])
        max_depth = param.get("max_depth", 3)

        if not sql_id:
            return {"success": False, "message": "缺少sql_id"}

        # 先构建完整图
        graph_builder = SchemaGraphBuilder()
        graph = graph_builder.build_graph(sql_id)

        # 寻找最优路径
        path_result = graph_builder.find_optimal_paths(graph, query_entities, max_depth)

        # 获取详细的表和列信息
        if path_result["tables"]:
            detail_info = graph_builder.get_related_tables_and_columns(sql_id, path_result["tables"])
            path_result["detail_info"] = detail_info

        return {
            "success": True,
            "message": "路径搜索成功",
            "result": path_result
        }

    except Exception as e:
        logger.error(f"路径搜索失败: {e}")
        return {"success": False, "message": f"路径搜索失败: {str(e)}"}

# 将方法添加到CControl类
CControl.build_schema_graph = build_schema_graph
CControl.find_schema_paths = find_schema_paths

def generate_table_ddl(self, conn, db_type: str, table_name: str) -> str:
    """
    生成表的DDL语句

    Args:
        conn: 数据库连接
        db_type: 数据库类型
        table_name: 表名

    Returns:
        DDL语句字符串
    """
    try:
        if db_type.lower() == "mysql":
            # MySQL DDL生成
            cursor = conn.cursor()
            cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
            result = cursor.fetchone()
            if result:
                ddl = result[1]  # SHOW CREATE TABLE 返回 (表名, DDL)
                return ddl
        elif db_type.lower() == "postgresql":
            # PostgreSQL DDL生成
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            # 获取表结构信息
            cursor.execute("""
                SELECT
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length,
                    numeric_precision,
                    numeric_scale
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))

            columns = cursor.fetchall()

            if not columns:
                return ""

            # 构建CREATE TABLE语句
            ddl_parts = [f"CREATE TABLE {table_name} ("]

            col_defs = []
            for col in columns:
                col_def = f"{col['column_name']} {col['data_type']}"

                # 处理长度
                if col['character_maximum_length']:
                    col_def += f"({col['character_maximum_length']})"
                elif col['numeric_precision'] and col['data_type'].upper() in ('DECIMAL', 'NUMERIC'):
                    if col['numeric_scale']:
                        col_def += f"({col['numeric_precision']},{col['numeric_scale']})"
                    else:
                        col_def += f"({col['numeric_precision']})"

                # 处理NOT NULL
                if col['is_nullable'] == 'NO':
                    col_def += " NOT NULL"

                # 处理默认值
                if col['column_default']:
                    col_def += f" DEFAULT {col['column_default']}"

                col_defs.append(col_def)

            ddl_parts.append(",\n    ".join(col_defs))
            ddl_parts.append(");")

            return "".join(ddl_parts)

        logger.warning(f"不支持的数据库类型: {db_type}")
        return ""

    except Exception as e:
        logger.error(f"生成表 {table_name} DDL失败: {e}")
        return ""

def generate_table_ddl_from_sqlite(self, sql_id: str, table_name: str, db_type: str) -> str:
    """
    从SQLite中读取表和列信息生成DDL语句

    Args:
        sql_id: 数据库ID
        table_name: 表名
        db_type: 数据库类型 ('mysql' 或 'postgresql')

    Returns:
        DDL语句字符串
    """
    try:
        # 获取表信息
        table_info = self.db_obj.query_table_sql_by_sql_id_and_name(sql_id, table_name)
        if not table_info:
            logger.warning(f"未找到表 {table_name} 的信息")
            return ""

        table_id = table_info["table_id"]
        table_desc = table_info.get("table_description", "")

        # 获取列信息
        columns = self.db_obj.query_col_sql_by_table_id(table_id)
        if not columns:
            logger.warning(f"表 {table_name} 没有列信息")
            return ""

        # 转换列信息格式以匹配control_chat.py的格式
        formatted_columns = []
        for col in columns:
            col_info = col.get("col_info", {})
            if isinstance(col_info, str):
                try:
                    col_info = json.loads(col_info)
                except:
                    col_info = {}

            formatted_col = {
                "col_name": col.get("col_name", ""),
                "col_type": col_info.get("col_type", ""),
                "is_nullable": col_info.get("is_nullable", "YES") if db_type.lower() == "postgresql" else ("NO" if col_info.get("is_null", "").upper() == "NO" else "YES"),
                "column_default": col_info.get("column_default") if db_type.lower() == "postgresql" else col_info.get("default"),
                "comment": col_info.get("comment")
            }
            formatted_columns.append(formatted_col)

        # 创建模拟的表数据结构
        table_data = {
            "table_name": table_name,
            "table_description": table_desc,
            "columns": formatted_columns
        }

        # 使用现有的格式化方法
        if db_type.lower() == "mysql":
            return self._format_table_structure_mysql([table_data])
        elif db_type.lower() == "postgresql":
            return self._format_table_structure_postgresql([table_data])
        else:
            logger.warning(f"不支持的数据库类型: {db_type}")
            return ""

    except Exception as e:
        logger.error(f"从SQLite生成表 {table_name} DDL失败: {e}")
        return ""

def _format_table_structure_mysql(self, tables):
    """将表格数据转成mysql的ddl格式"""
    try:
        if not tables:
            return "暂无表结构信息"

        ddl_statements = []

        for table in tables:
            table_name = table.get("table_name", "")
            table_desc = table.get("table_description", "")
            columns = table.get("columns", [])

            if not table_name:
                continue

            # 构建CREATE TABLE语句
            ddl_lines = []
            ddl_lines.append(f"CREATE TABLE `{table_name}` (")

            # 添加列定义
            column_defs = []
            for col in columns:
                col_name = col.get("col_name", "")
                col_type = col.get("col_type", "")
                is_nullable = col.get("is_nullable", "YES")
                column_default = col.get("column_default")
                comment = col.get("comment")

                if not col_name or not col_type:
                    continue

                # 映射PostgreSQL类型到MySQL类型
                mysql_type = self._map_postgres_to_mysql_type(col_type)

                # 构建列定义
                col_def = f"`{col_name}` {mysql_type}"

                # 添加NULL/NOT NULL约束
                if is_nullable.upper() == "NO":
                    col_def += " NOT NULL"
                else:
                    col_def += " NULL"

                # 添加默认值
                if column_default is not None:
                    if isinstance(column_default, str):
                        col_def += f" DEFAULT '{column_default}'"
                    else:
                        col_def += f" DEFAULT {column_default}"

                column_defs.append(col_def)

            # 组合列定义
            ddl_lines.append(",\n".join(f"  {col_def}" for col_def in column_defs))
            ddl_lines.append(") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;")

            # 添加表注释
            if table_desc:
                ddl_lines.append(f"")
                ddl_lines.append(f"ALTER TABLE `{table_name}` COMMENT = '{table_desc}';")

            # 添加列注释
            for col in columns:
                col_name = col.get("col_name", "")
                comment = col.get("comment")
                if comment:
                    ddl_lines.append(f"ALTER TABLE `{table_name}` MODIFY COLUMN `{col_name}` {self._map_postgres_to_mysql_type(col.get('col_type', ''))} COMMENT '{comment}';")

            ddl_statements.append("\n".join(ddl_lines))

        return "\n\n".join(ddl_statements)

    except Exception as e:
        logger.error(f"MySQL DDL格式化失败: {e}")
        return "MySQL DDL格式化失败"

def _format_table_structure_postgresql(self, tables):
    """将表格数据转成postgresql的ddl格式"""
    try:
        if not tables:
            return "暂无表结构信息"

        ddl_statements = []

        for table in tables:
            table_name = table.get("table_name", "")
            table_desc = table.get("table_description", "")
            columns = table.get("columns", [])

            if not table_name:
                continue

            # 构建CREATE TABLE语句
            ddl_lines = []
            ddl_lines.append(f'CREATE TABLE "{table_name}" (')

            # 添加列定义
            column_defs = []
            for col in columns:
                col_name = col.get("col_name", "")
                col_type = col.get("col_type", "")
                is_nullable = col.get("is_nullable", "YES")
                column_default = col.get("column_default")
                comment = col.get("comment")

                if not col_name or not col_type:
                    continue

                # 构建列定义
                col_def = f'"{col_name}" {col_type}'

                # 添加NULL/NOT NULL约束
                if is_nullable.upper() == "NO":
                    col_def += " NOT NULL"
                else:
                    col_def += " NULL"

                # 添加默认值
                if column_default is not None:
                    if isinstance(column_default, str):
                        col_def += f" DEFAULT '{column_default}'"
                    else:
                        col_def += f" DEFAULT {column_default}"

                column_defs.append(col_def)

            # 组合列定义
            ddl_lines.append(",\n".join(f"  {col_def}" for col_def in column_defs))
            ddl_lines.append(");")

            # 添加表注释
            if table_desc:
                ddl_lines.append(f"")
                ddl_lines.append(f"COMMENT ON TABLE \"{table_name}\" IS '{table_desc}';")

            # 添加列注释
            for col in columns:
                col_name = col.get("col_name", "")
                comment = col.get("comment")
                if comment:
                    ddl_lines.append(f"COMMENT ON COLUMN \"{table_name}\".\"{col_name}\" IS '{comment}';")

            ddl_statements.append("\n".join(ddl_lines))

        return "\n\n".join(ddl_statements)

    except Exception as e:
        logger.error(f"PostgreSQL DDL格式化失败: {e}")
        return "PostgreSQL DDL格式化失败"

def _map_postgres_to_mysql_type(self, postgres_type):
    """将PostgreSQL数据类型映射到MySQL数据类型"""
    if not postgres_type:
        return "VARCHAR(255)"

    type_mapping = {
        "character varying": "VARCHAR(255)",
        "varchar": "VARCHAR(255)",
        "text": "TEXT",
        "integer": "INT",
        "int": "INT",
        "bigint": "BIGINT",
        "smallint": "SMALLINT",
        "numeric": "DECIMAL(10,2)",
        "decimal": "DECIMAL(10,2)",
        "real": "FLOAT",
        "double precision": "DOUBLE",
        "boolean": "TINYINT(1)",
        "timestamp": "TIMESTAMP",
        "timestamp without time zone": "TIMESTAMP",
        "timestamp with time zone": "TIMESTAMP",
        "date": "DATE",
        "time": "TIME",
        "json": "JSON",
        "jsonb": "JSON",
    }

    # 处理带长度限制的类型
    if postgres_type.startswith("character varying(") or postgres_type.startswith("varchar("):
        return postgres_type.replace("character varying", "VARCHAR").replace("varchar", "VARCHAR")
    elif postgres_type.startswith("numeric(") or postgres_type.startswith("decimal("):
        return postgres_type.replace("numeric", "DECIMAL").replace("decimal", "DECIMAL")

    return type_mapping.get(postgres_type.lower(), postgres_type.upper())

# 添加到CControl类
CControl.generate_table_ddl = generate_table_ddl
CControl.generate_table_ddl_from_sqlite = generate_table_ddl_from_sqlite
CControl._format_table_structure_mysql = _format_table_structure_mysql
CControl._format_table_structure_postgresql = _format_table_structure_postgresql
CControl._map_postgres_to_mysql_type = _map_postgres_to_mysql_type


def _filter_schema_analysis_result(schema_analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    筛选Schema分析结果：排除测试表和命名不规范的表
    
    Args:
        schema_analysis_result: 原始Schema分析结果
        
    Returns:
        Dict[str, Any]: 筛选后的Schema分析结果
    """
    try:
        if not schema_analysis_result.get("success"):
            return schema_analysis_result
        
        tables_analysis = schema_analysis_result.get("tables_analysis", [])
        filtered_tables = []
        filtered_test_count = 0
        filtered_non_standard_count = 0
        
        for table_analysis in tables_analysis:
            analysis_result = table_analysis.get("analysis_result", {})
            
            # 检查是否为测试表
            is_test_table = analysis_result.get("is_test_table", False)
            if is_test_table:
                filtered_test_count += 1
                continue
            
            # 检查命名规范
            naming_standard = analysis_result.get("naming_standard", "")
            if naming_standard == "non_standard":
                filtered_non_standard_count += 1
                continue
            
            # 保留该表
            filtered_tables.append(table_analysis)
        
        # 构建筛选后的结果
        filtered_result = {
            "success": schema_analysis_result.get("success", True),
            "sql_id": schema_analysis_result.get("sql_id", ""),
            "tables_analysis": filtered_tables,
            "total_tables": len(filtered_tables),
            "test_tables_count": schema_analysis_result.get("test_tables_count", 0),
            "standard_naming_count": len(filtered_tables),  # 更新为标准命名表数量
            "filtered_test_tables": filtered_test_count,
            "filtered_non_standard_tables": filtered_non_standard_count
        }
        
        logger.info(f"Schema分析结果筛选: 原始 {len(tables_analysis)} 个表, "
                   f"筛选后 {len(filtered_tables)} 个表 "
                   f"(排除 {filtered_test_count} 个测试表, {filtered_non_standard_count} 个命名不规范的表)")
        
        return filtered_result
        
    except Exception as e:
        logger.error(f"筛选Schema分析结果失败: {e}")
        return schema_analysis_result  # 如果筛选失败，返回原始结果

