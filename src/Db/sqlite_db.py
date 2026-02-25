# -*- coding:utf-8 -*-

import os
import sqlite3
import threading
# import logging
import json
from datetime import datetime

# logger = logging.getLogger('werkzeug')

class KnowledgeBaseDB():
    
    def __init__(self):
        self.conn = None
        self.db_path = "conf/sqlite/knowledge_base.sqlite"
        
        # 初始化连接
        self.load_db()
        
    def load_db(self):
        """初始化数据库连接并创建所有表"""
        self.conn = self.create_connection(self.db_path)
        
        # 创建知识库表
        self.create_knowledge_base_table()
        
        # 创建文件基础信息表
        self.create_file_basic_info_table()
        
        # 创建文件详细信息表
        self.create_file_detail_info_table()
        
        # 创建用户表
        self.create_user_table()
        
        # 创建向量文件表
        self.create_vector_file_table()
        
        # 创建图数据chunk表
        self.create_graph_chunk_table()
        
        # 创建图数据节点表
        self.create_graph_node_table()
        
        # 创建图数据关系表
        self.create_graph_relation_table()

        # 创建图片数据表
        self.create_image_file_table()

        # 创建表格数据表
        self.create_table_table()

        # 创建聊天记录表
        self.create_session_table()
        
        # 创建任务记录表
        self.create_discussion_task_record_table()
        
        # 创建所有需要的表
        self.create_base_sql_table()
        self.create_table_sql_table()
        self.create_col_sql_table()
        self.create_rel_sql_table()
        self.create_sql_des_table()
        self.create_schema_analysis_table()
        
    def create_schema_analysis_table(self):
        """创建Schema分析结果表"""
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS schema_analysis_result (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sql_id TEXT NOT NULL,
                        table_id TEXT NOT NULL,
                        table_name TEXT NOT NULL,
                        analysis_result TEXT NOT NULL,
                        total_tables INTEGER DEFAULT 0,
                        test_tables_count INTEGER DEFAULT 0,
                        standard_naming_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(sql_id, table_id)
                    );'''
            c.execute(sql)
            self.conn.commit()
            print("创建Schema分析结果表成功")
            return True
        except Exception as e:
            print(f"创建Schema分析结果表失败: {e}")
            return False
    def insert_schema_analysis_result(self, sql_id: str, table_id: str, table_name: str, 
                                     analysis_result: dict, total_tables: int = 0,
                                     test_tables_count: int = 0, standard_naming_count: int = 0) -> bool:
        """
        插入或更新Schema分析结果

        Args:
            sql_id: 数据库ID
            table_id: 表ID
            table_name: 表名
            analysis_result: 分析结果字典
            total_tables: 总表数
            test_tables_count: 测试表数量
            standard_naming_count: 标准命名表数量

        Returns:
            bool: 是否成功
        """
        try:
            c = self.conn.cursor()
            analysis_result_json = json.dumps(analysis_result, ensure_ascii=False)

            # 使用 INSERT OR REPLACE 实现插入或更新
            sql = '''INSERT OR REPLACE INTO schema_analysis_result 
                     (sql_id, table_id, table_name, analysis_result, total_tables, 
                      test_tables_count, standard_naming_count, updated_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);'''

            c.execute(sql, (sql_id, table_id, table_name, analysis_result_json, 
                           total_tables, test_tables_count, standard_naming_count))
            self.conn.commit()
            print(f"插入Schema分析结果成功: sql_id={sql_id}, table_id={table_id}")
            return True
        except Exception as e:
            print(f"插入Schema分析结果失败: {e}")
            return False
    #
    def batch_insert_schema_analysis_results(self, schema_analysis_result: dict) -> bool:
        """
        批量插入Schema分析结果

        Args:
            schema_analysis_result: 完整的schema分析结果
                {
                    "success": True/False,
                    "sql_id": "...",
                    "tables_analysis": [...],
                    "total_tables": 0,
                    "test_tables_count": 0,
                    "standard_naming_count": 0
                }

        Returns:
            bool: 是否成功
        """
        try:
            if not schema_analysis_result.get("success"):
                print("Schema分析结果不成功，跳过保存")
                return False

            sql_id = schema_analysis_result.get("sql_id", "")
            tables_analysis = schema_analysis_result.get("tables_analysis", [])
            total_tables = schema_analysis_result.get("total_tables", 0)
            test_tables_count = schema_analysis_result.get("test_tables_count", 0)
            standard_naming_count = schema_analysis_result.get("standard_naming_count", 0)

            if not sql_id or not tables_analysis:
                print("缺少必要的参数")
                return False

            # 先删除该sql_id的所有旧数据
            self.delete_schema_analysis_by_sql_id(sql_id)

            # 批量插入
            success_count = 0
            for table_analysis in tables_analysis:
                table_id = table_analysis.get("table_id", "")
                table_name = table_analysis.get("table_name", "")
                analysis_result = table_analysis.get("analysis_result", {})

                if table_id and table_name and analysis_result:
                    if self.insert_schema_analysis_result(
                        sql_id=sql_id,
                        table_id=table_id,
                        table_name=table_name,
                        analysis_result=analysis_result,
                        total_tables=total_tables,
                        test_tables_count=test_tables_count,
                        standard_naming_count=standard_naming_count
                    ):
                        success_count += 1

            print(f"批量插入Schema分析结果完成: {success_count}/{len(tables_analysis)}")
            return success_count > 0

        except Exception as e:
            print(f"批量插入Schema分析结果失败: {e}")
            return False
    #
    def query_schema_analysis_by_sql_id(self, sql_id: str) -> list:
        """
        根据sql_id查询Schema分析结果

        Args:
            sql_id: 数据库ID

        Returns:
            list: Schema分析结果列表
        """
        try:
            c = self.conn.cursor()
            sql = '''SELECT sql_id, table_id, table_name, analysis_result, total_tables,
                            test_tables_count, standard_naming_count, created_at, updated_at
                     FROM schema_analysis_result 
                     WHERE sql_id = ?
                     ORDER BY table_name;'''

            c.execute(sql, (sql_id,))
            rows = c.fetchall()

            results = []
            for row in rows:
                try:
                    analysis_result = json.loads(row[3]) if row[3] else {}
                except:
                    analysis_result = {}

                results.append({
                    "sql_id": row[0],
                    "table_id": row[1],
                    "table_name": row[2],
                    "analysis_result": analysis_result,
                    "total_tables": row[4],
                    "test_tables_count": row[5],
                    "standard_naming_count": row[6],
                    "created_at": row[7],
                    "updated_at": row[8]
                })

            return results

        except Exception as e:
            print(f"查询Schema分析结果失败: {e}")
            return []
    #
    def query_schema_analysis_by_table_id(self, sql_id: str, table_id: str) -> dict:
        """
        根据sql_id和table_id查询单个表的Schema分析结果

        Args:
            sql_id: 数据库ID
            table_id: 表ID

        Returns:
            dict: Schema分析结果，如果不存在返回None
        """
        try:
            c = self.conn.cursor()
            sql = '''SELECT sql_id, table_id, table_name, analysis_result, total_tables,
                            test_tables_count, standard_naming_count, created_at, updated_at
                     FROM schema_analysis_result 
                     WHERE sql_id = ? AND table_id = ?;'''

            c.execute(sql, (sql_id, table_id))
            row = c.fetchone()

            if not row:
                return None

            try:
                analysis_result = json.loads(row[3]) if row[3] else {}
            except:
                analysis_result = {}

            return {
                "sql_id": row[0],
                "table_id": row[1],
                "table_name": row[2],
                "analysis_result": analysis_result,
                "total_tables": row[4],
                "test_tables_count": row[5],
                "standard_naming_count": row[6],
                "created_at": row[7],
                "updated_at": row[8]
            }

        except Exception as e:
            print(f"查询Schema分析结果失败: {e}")
            return None
    #
    def update_schema_analysis_result(self, sql_id: str, table_id: str, 
                                     analysis_result: dict) -> bool:
        """
        更新Schema分析结果

        Args:
            sql_id: 数据库ID
            table_id: 表ID
            analysis_result: 新的分析结果字典

        Returns:
            bool: 是否成功
        """
        try:
            c = self.conn.cursor()
            analysis_result_json = json.dumps(analysis_result, ensure_ascii=False)

            sql = '''UPDATE schema_analysis_result 
                     SET analysis_result = ?, updated_at = CURRENT_TIMESTAMP
                     WHERE sql_id = ? AND table_id = ?;'''

            c.execute(sql, (analysis_result_json, sql_id, table_id))
            self.conn.commit()

            if c.rowcount > 0:
                print(f"更新Schema分析结果成功: sql_id={sql_id}, table_id={table_id}")
                return True
            else:
                print(f"未找到要更新的记录: sql_id={sql_id}, table_id={table_id}")
                return False

        except Exception as e:
            print(f"更新Schema分析结果失败: {e}")
            return False
    #
    def delete_schema_analysis_by_sql_id(self, sql_id: str) -> bool:
        """
        根据sql_id删除所有Schema分析结果

        Args:
            sql_id: 数据库ID

        Returns:
            bool: 是否成功
        """
        try:
            c = self.conn.cursor()
            sql = '''DELETE FROM schema_analysis_result WHERE sql_id = ?;'''

            c.execute(sql, (sql_id,))
            self.conn.commit()

            deleted_count = c.rowcount
            print(f"删除Schema分析结果成功: sql_id={sql_id}, 删除 {deleted_count} 条记录")
            return True

        except Exception as e:
            print(f"删除Schema分析结果失败: {e}")
            return False
    #
    def delete_schema_analysis_by_table_id(self, sql_id: str, table_id: str) -> bool:
        """
        根据sql_id和table_id删除单个表的Schema分析结果

        Args:
            sql_id: 数据库ID
            table_id: 表ID

        Returns:
            bool: 是否成功
        """
        try:
            c = self.conn.cursor()
            sql = '''DELETE FROM schema_analysis_result 
                     WHERE sql_id = ? AND table_id = ?;'''

            c.execute(sql, (sql_id, table_id))
            self.conn.commit()

            if c.rowcount > 0:
                print(f"删除Schema分析结果成功: sql_id={sql_id}, table_id={table_id}")
                return True
            else:
                print(f"未找到要删除的记录: sql_id={sql_id}, table_id={table_id}")
                return False

        except Exception as e:
            print(f"删除Schema分析结果失败: {e}")
            return False
        
    def create_sql_des_table(self):
        """创建SQL描述表"""
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS sql_des (
                        user_id TEXT NOT NULL,
                        sql_id TEXT NOT NULL,
                        sql TEXT NOT NULL,
                        sql_des TEXT NOT NULL
                        );'''
            c.execute(sql)
            self.conn.commit()
            print("创建SQL描述表成功")
            return True
        except Exception as e:
            print(f"创建SQL描述表失败: {e}")
            return False

    def insert_sql_des(self, param):
        """插入SQL描述"""
        try:
            c = self.conn.cursor()
            sql = '''INSERT INTO sql_des (user_id, sql_id, sql, sql_des) VALUES (?, ?, ?, ?);'''
            c.execute(sql, ( param["user_id"], param["sql_id"], param["sql"], param["sql_des"]))
            self.conn.commit()
            print("插入SQL描述成功")
            return True
        except Exception as e:
            print(f"插入SQL描述失败: {e}")
            return False

    def delete_sql_des_by_sql_id(self, sql_id):
        """根据sql_id删除SQL描述"""
        try:
            c = self.conn.cursor()
            sql = '''DELETE FROM sql_des WHERE sql_id = ?;'''
            c.execute(sql, (sql_id,))
            self.conn.commit()
            print("删除SQL描述成功")
            return True
        except Exception as e:
            print(f"删除SQL描述失败: {e}")
            return False

    def query_sql_des_by_sql_id(self, sql_id):
        """根据sql_id查询SQL描述"""
        try:
            c = self.conn.cursor()
            sql = '''SELECT * FROM sql_des WHERE sql_id = ?;'''
            c.execute(sql, (sql_id,))
            rows = c.fetchall()
            result = []
            if(rows):
                for row in rows:
                    result.append({
                        "user_id": row[0],
                        "sql_id": row[1],
                        "sql": row[2],
                        "sql_des": row[3]
                    })
            return result
        except Exception as e:
            print(f"查询SQL描述失败: {e}")
            return []
     
    def create_session_table(self):
        """创建会话表"""
        # try: 
        if(True):
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS session (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        session_name TEXT NOT NULL,
                        session_desc TEXT,
                        session_type TEXT,
                        session_status TEXT,
                        session_create_time TEXT,
                        session_update_time TEXT,
                        knowledge_base_name TEXT
                        );'''
            c.execute(sql)
            self.conn.commit()
            print("创建会话表成功")
            return True
        else:
        # except Exception as e:
        #     print(f"创建会话表失败: {e}")
            return False

    def save_session_info(self, param):
        """保存会话信息"""
        try:
            c = self.conn.cursor()
            sql = '''INSERT INTO session (user_id, session_id, session_name, session_desc, session_type, session_status, session_create_time,knowledge_base_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?);'''
            values = (param.get("user_id", ""),
                      param.get("session_id", ""),
                      param.get("session_name", ""),
                      param.get("session_desc", ""),
                      param.get("session_type", ""),
                      param.get("session_status", ""),
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                      param.get("knowledge_base_name", ""),)
            c.execute(sql, values)
            self.conn.commit()
            print("保存会话成功")
            return True
        except Exception as e:
            print(f"保存会话失败: {e}")
            return False

    def search_session_by_session_id(self, session_id):
        """根据session_id查询会话"""
        try:
            c = self.conn.cursor()
            sql = '''SELECT * FROM session WHERE session_id = ?;'''
            c.execute(sql, (session_id,))
            row = c.fetchone()
            if(row):
                return {
                    "id": row[0],
                    "user_id": row[1],
                    "session_id": row[2],
                    "session_name": row[3],
                    "session_desc": row[4],
                    "session_type": row[5],
                    "session_status": row[6],
                    "session_create_time": row[7],
                    "knowledge_base_name": row[8]
                }
            return None
        except Exception as e:
            print(f"查询会话失败: {e}")
            return None

    def search_session_by_user_id(self, user_id):
        """根据user_id查询会话"""
        try:
            c = self.conn.cursor()
            sql = '''SELECT * FROM session WHERE user_id = ?;'''
            c.execute(sql, (user_id,))
            rows = c.fetchall()
            result = []
            if(rows):
                for row in rows:
                    result.append(
                        {
                            "id": row[0],
                            "user_id": row[1],
                            "session_id": row[2],
                            "session_name": row[3],
                            "session_desc": row[4],
                            "session_type": row[5],
                            "session_status": row[6],
                            "session_create_time": row[7],
                            "knowledge_base_name": row[8]
                        }
                    )
            return result
        except Exception as e:
            print(f"查询会话失败: {e}")
            return []

    def delete_sessions_by_session_id(self, session_id):
        """根据session_id删除会话"""
        #try:
        if(True):
            c = self.conn.cursor()
            sql = '''DELETE FROM session WHERE session_id = ?;'''
            c.execute(sql, (session_id,))
            self.conn.commit()
            print("删除会话成功")
            return True
        # except Exception as e:
        #     print(f"删除会话失败: {e}")
        else:
            return False
    
    def delete_sessions_by_user_id(self, user_id):
        """根据user_id删除会话"""
        try:
            c = self.conn.cursor()
            sql = '''DELETE FROM session WHERE user_id = ?;'''
            c.execute(sql, (user_id,))
            self.conn.commit()
            print("删除会话成功")
            return True
        except Exception as e:
            print(f"删除会话失败: {e}") 
            return False

    def create_discussion_task_record_table(self):
        """创建任务记录表"""
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS discussion_task_record (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        discussion_id TEXT NOT NULL,
                        user_id TEXT,
                        task_status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(session_id, discussion_id)
                    );'''
            c.execute(sql)
            self.conn.commit()
            print("创建任务记录表成功")
            return True
        except Exception as e:
            print(f"创建任务记录表失败: {e}")
            return False

    def insert_discussion_task_record(self, session_id, discussion_id, user_id=None, task_status='active'):
        """插入任务记录"""
        try:
            c = self.conn.cursor()
            sql = '''INSERT OR REPLACE INTO discussion_task_record 
                     (session_id, discussion_id, user_id, task_status, updated_at)
                     VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP);'''
            c.execute(sql, (session_id, discussion_id, user_id, task_status))
            self.conn.commit()
            print(f"插入任务记录成功: session_id={session_id}, discussion_id={discussion_id}")
            return True
        except Exception as e:
            print(f"插入任务记录失败: {e}")
            return False

    def query_discussion_task_by_session_id(self, session_id):
        """根据session_id查询任务记录"""
        try:
            c = self.conn.cursor()
            sql = '''SELECT session_id, discussion_id, user_id, task_status, 
                            created_at, updated_at
                     FROM discussion_task_record 
                     WHERE session_id = ? 
                     ORDER BY updated_at DESC 
                     LIMIT 1;'''
            c.execute(sql, (session_id,))
            row = c.fetchone()
            if row:
                return {
                    "session_id": row[0],
                    "discussion_id": row[1],
                    "user_id": row[2],
                    "task_status": row[3],
                    "created_at": row[4],
                    "updated_at": row[5]
                }
            return None
        except Exception as e:
            print(f"查询任务记录失败: {e}")
            return None

    def count_discussion_tasks_by_session_id(self, session_id):
        """根据session_id统计讨论任务数量"""
        try:
            c = self.conn.cursor()
            # 查询总任务数
            sql_total = '''SELECT COUNT(*) FROM discussion_task_record WHERE session_id = ?;'''
            c.execute(sql_total, (session_id,))
            total_count = c.fetchone()[0]
            
            # 查询活跃任务数
            sql_active = '''SELECT COUNT(*) FROM discussion_task_record 
                           WHERE session_id = ? AND task_status = 'active';'''
            c.execute(sql_active, (session_id,))
            active_count = c.fetchone()[0]
            
            # 查询已完成任务数
            sql_completed = '''SELECT COUNT(*) FROM discussion_task_record 
                              WHERE session_id = ? AND task_status = 'completed';'''
            c.execute(sql_completed, (session_id,))
            completed_count = c.fetchone()[0]
            
            # 查询所有任务列表（按更新时间倒序）
            sql_list = '''SELECT discussion_id, task_status, created_at, updated_at
                         FROM discussion_task_record 
                         WHERE session_id = ? 
                         ORDER BY updated_at DESC;'''
            c.execute(sql_list, (session_id,))
            rows = c.fetchall()
            tasks_list = []
            for row in rows:
                tasks_list.append({
                    "discussion_id": row[0],
                    "task_status": row[1],
                    "created_at": row[2],
                    "updated_at": row[3]
                })
            
            return {
                "total_count": total_count,
                "active_count": active_count,
                "completed_count": completed_count,
                "tasks": tasks_list
            }
        except Exception as e:
            print(f"统计讨论任务数量失败: {e}")
            return {
                "total_count": 0,
                "active_count": 0,
                "completed_count": 0,
                "tasks": []
            }

    def update_discussion_task_status(self, session_id, discussion_id, task_status):
        """更新任务状态"""
        try:
            c = self.conn.cursor()
            sql = '''UPDATE discussion_task_record 
                     SET task_status = ?, updated_at = CURRENT_TIMESTAMP
                     WHERE session_id = ? AND discussion_id = ?;'''
            c.execute(sql, (task_status, session_id, discussion_id))
            self.conn.commit()
            if c.rowcount > 0:
                print(f"更新任务状态成功: session_id={session_id}, discussion_id={discussion_id}, status={task_status}")
                return True
            else:
                print(f"未找到要更新的记录: session_id={session_id}, discussion_id={discussion_id}")
                return False
        except Exception as e:
            print(f"更新任务状态失败: {e}")
            return False

    def delete_discussion_task_by_discussion_id(self, discussion_id):
        """根据discussion_id删除任务记录"""
        try:
            c = self.conn.cursor()
            sql = '''DELETE FROM discussion_task_record WHERE discussion_id = ?;'''
            c.execute(sql, (discussion_id,))
            self.conn.commit()
            deleted_count = c.rowcount
            if deleted_count > 0:
                print(f"删除任务记录成功: discussion_id={discussion_id}, 删除 {deleted_count} 条记录")
                return True
            else:
                print(f"未找到要删除的记录: discussion_id={discussion_id}")
                return False
        except Exception as e:
            print(f"删除任务记录失败: {e}")
            return False

    def create_image_file_table(self):
        """创建图片数据表"""
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS image_file (
                        id TEXT PRIMARY KEY,
                        file_id TEXT NOT NULL,
                        img_path TEXT NOT NULL,
                        caption TEXT,
                        footnote TEXT,
                        upload_time TEXT
                        );'''
            c.execute(sql)
            self.conn.commit()
            print("创建图片数据表成功")
            return True
        except Exception as e:
            print(f"创建图片数据表失败: {e}")
            return False

    def insert_image_file(self, param):
        """插入图片数据"""
        try:
            c = self.conn.cursor()
            sql = '''INSERT INTO image_file (file_id, img_path, caption, footnote, upload_time) VALUES (?, ?, ?, ?, ?);'''
            c.execute(sql, ( param["file_id"], param["img_path"], param["caption"], param["footnote"], param["upload_time"]))
            self.conn.commit()
            print("插入图片数据成功")
            return True
        except Exception as e:
            print(f"插入图片数据失败: {e}")
            return False
        
    def search_images_by_file_id(self, file_id):
        """根据file_id查询图片数据"""
        try:
            c = self.conn.cursor()
            sql = '''SELECT * FROM image_file WHERE file_id = ?;'''
            c.execute(sql, (file_id,))
            rows = c.fetchall()
            result = []
            if(rows):
                for row in rows:
                    result.append({
                        "file_id": row[1],
                        "img_path": row[2],
                        "caption": row[3],
                        "footnote": row[4],
                        "upload_time": row[5]
                    })
            return result
        except Exception as e:
            print(f"查询图片数据失败: {e}")
            return []

    def delete_image_file(self, param):
        """删除图片数据"""
        try:
            c = self.conn.cursor()
            sql = '''DELETE FROM image_file WHERE file_id = ?;'''
            c.execute(sql, (param["file_id"],))
            self.conn.commit()
            print("删除图片数据成功")
            return True
        except Exception as e:
            print(f"删除图片数据失败: {e}") 
            return False

    def create_table_table(self):
        """创建表格数据表"""
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS table_data (
                        id TEXT PRIMARY KEY,
                        file_id TEXT NOT NULL,
                        caption TEXT,
                        footnote TEXT,
                        table_data TEXT,
                        upload_time TEXT
                        );'''
            c.execute(sql)
            self.conn.commit()
            print("创建表格数据表成功")
            return True
        except Exception as e:
            print(f"创建表格数据表失败: {e}")
            return False

    def insert_table_data(self,param):
        """插入表格数据"""
        try:
            c = self.conn.cursor()
            sql = '''INSERT INTO table_data (file_id, caption, footnote, table_data, upload_time) VALUES (?, ?, ?, ?, ?);'''
            c.execute(sql, ( param["file_id"], param["caption"], param["footnote"], param["table_data"], param["upload_time"]))
            self.conn.commit()
            print("插入表格数据成功")
            return True
        except Exception as e:
            print(f"插入表格数据失败: {e}")
            return False

    def delete_table_data(self, param):
        """删除表格数据"""
        try:
            c = self.conn.cursor()
            sql = '''DELETE FROM table_data WHERE file_id = ?;'''
            c.execute(sql, (param["file_id"],))
            self.conn.commit()
            print("删除表格数据成功")
            return True
        except Exception as e:
            print(f"删除表格数据失败: {e}") 
            return False
        
    def create_connection(self, db_file):
        """创建数据库连接"""
        conn = None
        try:
            conn = sqlite3.connect(db_file, check_same_thread=False)
            return conn
        except Exception as e:
            print(e)
        return conn
    
    def create_knowledge_base_table(self):
        """创建知识库表
            知识库名称
            知识库id
            知识库创建时间
            知识库描述
            知识库有效时间（例如：2023-01-01 00:00:00 至 2023-12-31 23:59:59）
            知识库创建用户id
        """
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS knowledge_base (
                        id TEXT PRIMARY KEY,
                        knowledge_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        create_time TEXT NOT NULL,
                        description TEXT,
                        valid_start_time TEXT,
                        valid_end_time TEXT,
                        create_user_id TEXT
                    );'''
            c.execute(sql)
            self.conn.commit()
        except Exception as e:
            print(f"创建知识库表失败: {e}")

    def delete_knowledge_base_by_id(self, knowledge_id):
        """根据id删除知识库"""
        try:
            c = self.conn.cursor()
            sql = '''DELETE FROM knowledge_base WHERE knowledge_id = ?;'''
            c.execute(sql, (knowledge_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"删除知识库失败: {e}")
            return False

    def search_knowledge_base_by_user_id_and_name(self, param):
        """根据用户id和知识库名称查询知识库"""
        user_id = param["user_id"]
        knowledge_name = param["knowledge_name"]
        try: 
            c = self.conn.cursor()
            sql = f"""SELECT * FROM knowledge_base WHERE create_user_id = '{user_id}' AND name = '{knowledge_name}';"""
            c.execute(sql)
            row = c.fetchone()
            if row:
                return {
                    "knowledge_id": row[1],
                }
        except Exception as e:
            print(f"查询知识库失败: {e}")
            return None
        
    def search_knowledge_base_by_knowledge_id(self, knowledge_id):
        """根据知识库id查询知识库"""
        try:
            c = self.conn.cursor()
            sql = f"""SELECT * FROM knowledge_base WHERE knowledge_id ='{knowledge_id}';"""
            c.execute(sql)
            row = c.fetchone()
            if row:
                return {
                    "knowledge_id": row[1],
                    "name": row[2],
                    "create_time": row[3],
                    "description": row[4],
                    "user_id": row[7]
                }
            return None
        except Exception as e:
            print(f"查询知识库失败: {e}")
            return None
                
    def query_knowledge_base_by_user_id(self, param):
        """获取用户的知识库"""
        user_id = param.get('user_id')
        try:
            c = self.conn.cursor()
            sql = "SELECT * FROM knowledge_base WHERE create_user_id=?"
            c.execute(sql, (user_id,))
            rows = c.fetchall()
            result = []
            if rows:
                for row in rows:
                    result.append({
                        "knowledge_id": row[1],
                        "name": row[2],
                        "create_time": row[3],
                        "description": row[4],
                        "user_id": row[7]
                    })
            return result
        except Exception as e:
            # logger.error(f"获取用户知识库列表失败: {e}")
            return []
                    
    def search_user_id_by_user_name_password(self, user_name, password):
        """根据用户名密码查询用户id"""
        try:
            c = self.conn.cursor()
            sql = '''SELECT user_id FROM user_info WHERE user_name = ? AND password = ?;'''
            c.execute(sql, (user_name, password))
            row = c.fetchone()

            if row:
                return row[0]
            else:
                return None
        except Exception as e:
            print(f"查询用户id失败: {e}")
            return None

    def create_file_basic_info_table(self):
        """创建文件基础信息表
            知识库id
            文件id
            文件名称
            文件路径
            文件大小
            文件上传时间
            文件上传用户id
            文件权限等级
            文件url
            对话session_id
        """
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS file_basic_info (
                        knowledge_id TEXT,
                        file_id TEXT PNOT NULL,
                        file_name TEXT NOT NULL,
                        file_path TEXT,
                        file_size TEXT,
                        upload_time TEXT,
                        upload_user_id TEXT,
                        permission_level TEXT,
                        url TEXT,
                        session_id TEXT
                    );'''
            c.execute(sql)
            self.conn.commit()
        except Exception as e:
            print(f"创建文件基础信息表失败: {e}")

    def search_file_basic_info_by_session_id(self, session_id):
        """根据对话session_id查询文件基础信息"""
        try:
            c = self.conn.cursor()
            # 使用参数化查询避免SQL注入，并处理空字符串和None的情况
            if not session_id:
                sql = """SELECT * FROM file_basic_info WHERE session_id IS NULL OR session_id = '';"""
                c.execute(sql)
            else:
                sql = """SELECT * FROM file_basic_info WHERE session_id = ?;"""
                c.execute(sql, (session_id,))
            rows = c.fetchall()
            # 将元组转换为字典列表
            result = []
            for row in rows:
                result.append({
                    "knowledge_id": row[0],
                    "file_id": row[1],
                    "file_name": row[2],
                    "file_path": row[3],
                    "file_size": row[4],
                    "upload_time": row[5],
                    "upload_user_id": row[6],
                    "permission_level": row[7],
                    "url": row[8],
                    "session_id": row[9] if len(row) > 9 else ""
                })
            return result
        except Exception as e:
            print(f"查询文件基础信息失败: {e}")
            return []
            
    def search_file_name_by_words_user_id(self, param):
        """通过用户id和关键词模糊匹配文件名"""
        user_id = param["user_id"]
        keywords = param["keywords"]
        try:
            c = self.conn.cursor()
            sql = f"""SELECT file_name FROM file_basic_info WHERE upload_user_id = ? AND file_name LIKE ?;"""
            c.execute(sql, (user_id, f"%{keywords}%"))
            rows = c.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            print(f"查询文件名失败: {e}")
            return []
        
    def search_file_name_by_knowledge_id(self, knowledge_id):
        """根据知识库id查询文件名称，只获取前50个文件名称"""
        try:
            c = self.conn.cursor()
            sql = f"""SELECT file_name FROM file_basic_info WHERE knowledge_id ='{knowledge_id}' limit 50;"""
            c.execute(sql)
            rows = c.fetchall()
            result = []
            for row in rows:
                result.append(row[0])
            return result
        except Exception as e:
            print(f"查询文件名称失败: {e}")
            return []

    def search_file_name_by_knowledge_id_public(self, knowledge_id):
        """根据知识库id查询公共文件名称，只获取前50个文件名称"""
        try:
            c = self.conn.cursor()
            sql = f"""SELECT file_name FROM file_basic_info WHERE knowledge_id ='{knowledge_id}' and permission_level = 'public' limit 50;"""
            c.execute(sql)
            rows = c.fetchall()
            result = []
            for row in rows:
                result.append(row[0])
            return result
        except Exception as e:
            print(f"查询公共文件名称失败: {e}")
            return []

    def search_file_num_by_knowledge_id(self, knowledge_id):
        """根据知识库id查询文件数量"""
        try:
            c = self.conn.cursor()
            sql = f"""SELECT COUNT(*) FROM file_basic_info WHERE knowledge_id ='{knowledge_id}';"""
            c.execute(sql)
            row = c.fetchone()
            if row:
                return row[0]
            return 0
        except Exception as e:
            print(f"查询文件数量失败: {e}")
            return 0
    
    def search_file_num_by_knowledge_id_public(self, knowledge_id):
        """根据知识库id查询公共文件数量"""
        try:
            c = self.conn.cursor()
            sql = f"""SELECT COUNT(*) FROM file_basic_info WHERE knowledge_id ='{knowledge_id}' and permission_level = 'public';"""
            c.execute(sql)
            row = c.fetchone()
            if row:
                return row[0]
            return 0
        except Exception as e:
            print(f"查询公共文件数量失败: {e}")
            return 0
    
    def search_file_basic_info_by_file_id(self, file_id):
        """根据文件id查询文件基础信息"""
        try:
            c = self.conn.cursor()
            # sql = '''SELECT * FROM file_basic_info WHERE file_id = ?;'''
            sql = f"""SELECT * FROM file_basic_info WHERE file_id ='{file_id}';"""
            c.execute(sql)
            row = c.fetchone()
            if row:
                return {
                    "knowledge_id": row[0],
                    "file_id": row[1],
                    "file_name": row[2],
                    "file_path": row[3],
                    "file_size": row[4],
                    "upload_time": row[5],
                    "upload_user_id": row[6],
                    "permission_level": row[7],
                    "url": row[8]
                }
            return None
        except Exception as e:
            print(f"查询文件基础信息失败: {e}")
            return None
        
    def search_file_basic_info_by_file_name(self, file_name):
        """根据文件名字查询文件基础信息"""
        try:
            c = self.conn.cursor()
            # sql = '''SELECT * FROM file_basic_info WHERE file_id = ?;'''
            sql = f"""SELECT * FROM file_basic_info WHERE file_name ='{file_name}';"""
            c.execute(sql)
            row = c.fetchone()
            if row:
                return {
                    "knowledge_id": row[0],
                    "file_id": row[1],
                    "file_name": row[2],
                    "file_path": row[3],
                    "file_size": row[4],
                    "upload_time": row[5],
                    "upload_user_id": row[6],
                    "permission_level": row[7],
                    "url": row[8]
                }
            return None
        except Exception as e:
            print(f"查询文件基础信息失败: {e}")
            return None
    
    def search_file_basic_info_by_file_name_user_id(self, param):
        """根据文件名称和用户id查询文件基础信息"""
        file_name = param.get("file_name")
        user_id = param.get("user_id")
        try:
            c = self.conn.cursor()
            sql = '''SELECT * FROM file_basic_info WHERE file_name = ? AND upload_user_id = ?;'''
            c.execute(sql, (file_name, user_id))
            rows = c.fetchall()
            result = []
            for row in rows:
                result.append({
                    "knowledge_id": row[0],
                    "file_id": row[1],
                    "file_name": row[2],
                })
            return result
        except Exception as e:
            print(f"查询文件基础信息失败: {e}")
            return []

    def query_file_basic_info_by_knowledge_id(self, knowledge_id):
        """根据知识库id查询文件基础信息"""
        try:
            c = self.conn.cursor()
            sql = '''SELECT * FROM file_basic_info WHERE knowledge_id = ?;'''
            c.execute(sql, (knowledge_id,))
            rows = c.fetchall()

            result = []
            for row in rows:
                result.append({
                    "knowledge_id": row[0],
                    "file_id": row[1],
                    "file_name": row[2],
                })
            return result
        except Exception as e:
            print(f"查询文件基础信息失败: {e}")
            return None
    
    def query_file_basic_info_by_file_name(self, file_name):
        """根据文件名称查询文件基础信息"""
        try:
            c = self.conn.cursor()
            sql = '''SELECT * FROM file_basic_info WHERE file_name = ?;'''
            c.execute(sql, (file_name,))
            rows = c.fetchall()

            result = []
            for row in rows:
                result.append({
                    "knowledge_id": row[0],
                    "file_id": row[1],
                    "file_name": row[2],
                    "file_path": row[3],
                    "file_size": row[4],
                    "upload_time": row[5],
                    "upload_user_id": row[6],
                    "permission_level": row[7],
                    "url": row[8]
                })
            return result

            return rows
        except Exception as e:
            print(f"查询文件基础信息失败: {e}")
            return None

    def create_file_detail_info_table(self):
        """创建文件详细信息表
            文件id
            文件名称
            文件中识别题目
            文件的概述
            文件作者
            文件创建时间
            文件更新时间
            文件有效区域（省，市等）
            文件标签（例如：高中，高中数学，高中英语等）
            文件类别 （例如：高中数学，高中英语等）
            文件有效时间（例如：2023-01-01 00:00:00 至 2023-12-31 23:59:59）
            文件目录
        """
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS file_detail_info (
                        file_id TEXT NOT NULL,
                        file_name TEXT NOT NULL,
                        recognized_title TEXT,
                        overview TEXT,
                        author TEXT,
                        create_time TEXT,
                        valid_area_province TEXT,
                        valid_area_city TEXT,
                        tags TEXT,
                        category TEXT,
                        valid_start_time TEXT,
                        valid_end_time TEXT,
                        catalog TEXT
                    );'''
            c.execute(sql)
            self.conn.commit()
        except Exception as e:
            print(f"创建文件详细信息表失败: {e}")
            
    def search_file_detail_info_by_file_id(self, file_id):
        """根据文件id查询文件详细信息"""
        try:
            c = self.conn.cursor()
            sql = '''SELECT * FROM file_detail_info WHERE file_id = ?;'''
            c.execute(sql, (file_id,))
            row = c.fetchone()
            if row:
                return {
                    "file_id": row[0],
                    "file_name": row[1],
                    "recognized_title": row[2],
                    "overview": row[3],
                    "author": row[4],
                    "create_time": row[5],
                    "valid_area_province": row[6],
                    "valid_area_city": row[7],
                    "tags": row[8],
                    "category": row[9],
                    "valid_start_time": row[10],
                    "valid_end_time": row[11],
                    "catalog": row[12]
                }
            return None
        except Exception as e:
            print(f"查询文件详细信息失败: {e}")
            return None
        
    def search_file_detail_info_by_file_name(self, file_name):
        """根据文件名称查询文件详细信息
            详细信息包含：
            文件id
            文件名称
            文件中识别题目
            文件的概述
            文件作者
            文件创建时间
            文件更新时间
            文件有效区域（省，市等）
            文件标签（例如：高中，高中数学，高中英语等）
            文件类别 （例如：高中数学，高中英语等）
            文件有效时间（例如：2023-01-01 00:00:00 至 2023-12-31 23:59:59）
            文件目录
        """
        try:
            c = self.conn.cursor()
            sql = '''SELECT * FROM file_detail_info WHERE file_name = ?;'''
            c.execute(sql, (file_name,))
            row = c.fetchone()
            if row:
                return {
                    "file_id": row[0],
                    "file_name": row[1],
                    "recognized_title": row[2],
                    "overview": row[3],
                    "author": row[4],
                    "create_time": row[5],
                    "valid_area_province": row[6],
                    "valid_area_city": row[7],
                    "tags": row[8],
                    "category": row[9],
                    "valid_start_time": row[10],
                    "valid_end_time": row[11],
                    "catalog": row[12]
                }
            return None
        except Exception as e:
            print(f"查询文件详细信息失败: {e}")
            return None
        
    def search_user_id(self):
        """查询所有用户id"""
        try:
            c = self.conn.cursor()
            sql = '''SELECT user_id FROM user_info;'''
            c.execute(sql)
            rows = c.fetchall()
            result = []
            for row in rows:
                result.append(row[0])
            return result
        except Exception as e:
            print(f"查询用户id失败: {e}")
            return []
                                    
    def delete_user_by_user_id(self, param):
        """根据用户id删除用户"""
        if("user_id" not in param.keys()):
            return {"error_code":1, "error_msg":"Fail, loss user id."}
        user_id = param["user_id"]
        try:
            c = self.conn.cursor()
            sql = f"""DELETE FROM user_info WHERE user_id = '{user_id}';"""
            c.execute(sql)
            self.conn.commit()
            return True
        except Exception as e:
            print(f"删除用户失败: {e}")
            return False
            
    def create_user_table(self):
        """创建用户表
            用户id
            用户名字
            用户密码
            用户权限
        """
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS user_info (
                        user_id TEXT NOT NULL,
                        user_name TEXT NOT NULL,
                        password TEXT NOT NULL,
                        permissions TEXT
                    );'''
            c.execute(sql)
            self.conn.commit()
        except Exception as e:
            print(f"创建用户表失败: {e}")

    
    def search_user_name_by_user_id(self, param):
        """根据用户id查询用户名"""
        if("user_id" not in param.keys()):
            return {"error_code":1, "error_msg":"Fail, loss user id."}
        user_id = param["user_id"]
        try:
            c = self.conn.cursor()
            sql = f"""SELECT user_name FROM user_info WHERE user_id = '{user_id}';"""
            c.execute(sql)
            return c.fetchone()[0]
        except Exception as e:
            print(f"查询用户名失败: {e}")
            return None
            
    def create_vector_file_table(self):
        """创建向量文件表
            每个partition 对应的 collection name 
            每个文件对应的id
            每个文件对应的partition_id
            每个文件，切成长度为512的段落的描述
            每个文件，在生成向量数据时切成长度为512的段落
        """
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS vector_file (
                        knowledge_id TEXT NOT NULL,
                        file_id TEXT NOT NULL,
                        partition_id TEXT NOT NULL,
                        paragraph_description TEXT,
                        paragraph_content TEXT
                    );'''
            c.execute(sql)
            self.conn.commit()
        except Exception as e:
            print(f"创建向量文件表失败: {e}")

    def delete_vector_file_by_file_id(self, param):
        """删除向量文件"""
        file_id = param.get("file_id", "")
        try:
            c = self.conn.cursor()
            sql = '''DELETE FROM vector_file WHERE file_id = ?;'''
            c.execute(sql, (file_id,))
            self.conn.commit()
        except Exception as e:
            print(f"删除向量文件失败: {e}")
        return True
    
    def delete_graph_chunk_table(self, file_id):
        """删除图数据chunk表"""
        # try:
        if(True):
            c = self.conn.cursor()
            sql = f"""DELETE FROM graph_chunk WHERE file_id='{file_id}';"""
            c.execute(sql)
            self.conn.commit()
        # except Exception as e:
        #     print(f"删除图数据chunk表失败: {e}")
        return True

    def delete_graph_chunk_by_knowledge_id(self, param):
        """根据知识id删除图数据chunk表"""
        knowledge_id = param.get("knowledge_id", "")
        try:
            c = self.conn.cursor()
            sql = '''DELETE FROM graph_chunk WHERE knowledge_id = ?;'''
            c.execute(sql, (knowledge_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"删除图数据chunk表失败: {e}")
            return False

    def create_graph_chunk_table(self):
        """创建图数据chunk表
            每个文件对应的id
            每个chunk的id，从lightrag服务生成的文件中读取
            每个chunk文本的概述，
            每个chunk的文本，
        """
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS graph_chunk (
                        knowledge_id TEXT,
                        file_id TEXT NOT NULL,
                        chunk_id TEXT,
                        chunk_summary TEXT,
                        chunk_text TEXT,
                        file_name TEXT
                    );'''
            c.execute(sql)
            self.conn.commit()
        except Exception as e:
            print(f"创建图数据chunk表失败: {e}")
    
    def insert_graph_chunk(self, param):
        """插入图数据chunk表"""
        try:
            c = self.conn.cursor()
            sql = '''INSERT INTO graph_chunk (knowledge_id, file_id, chunk_id, chunk_summary, chunk_text, file_name) VALUES (?, ?, ?, ?, ?, ?);'''
            c.execute(sql, (param.get("knowledge_id", ""), param.get("file_id", ""), param.get("chunk_id", ""),  param.get("chunk_summary", ""), param.get("chunk_text", ""), param.get("file_name", "")))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"插入图数据chunk表失败: {e}")
            return False

    def query_graph_chunk_by_chunk_id_and_knowledge_id(self, param):
        """根据chunk_id查询图数据chunk表"""
        chunk_id = param.get("chunk_id", "")
        knowledge_id = param.get("knowledge_id", "")
        try: 
            c = self.conn.cursor()
            sql = f"""select t.* from graph_chunk t where chunk_id='{chunk_id}' 
 and knowledge_id='{knowledge_id}';"""
            c.execute(sql)
            rows = c.fetchall()
            result = []
            for row in rows:
                result.append({
                    "file_id": row[0],
                    "knowledge_id": row[1],
                    "chunk_id": row[2],
                    "chunk_summary": row[3],
                    "chunk_text": row[4],
                    "file_name": row[5]
                })
            return result
        except Exception as e:
            print(f"根据chunk_id查询图数据chunk表失败: {e}")
            return []

    def query_graph_chunk_by_file_id(self, file_id):
        """根据文件id查询图数据chunk表"""
        try: 
            c = self.conn.cursor()
            sql = '''SELECT * FROM graph_chunk WHERE file_id = ?;'''
            c.execute(sql, (file_id,))
            rows = c.fetchall()
            result = []
            for row in rows:
                result.append({
                    "knowledge_id":row[0],
                    "file_id": row[1],
                    "chunk_id": row[2],
                    "chunk_summary": row[3],
                    "chunk_text": row[4],
                    "file_name": row[5]
                })
            return result
        except Exception as e:
            print(f"根据文件id查询图数据chunk表失败: {e}")
            return []
    
    def delete_graph_node_table(self, file_id):
        """删除图数据节点表"""
        # try:
        if(True):
            c = self.conn.cursor()
            sql = '''DELETE FROM graph_node WHERE file_id = ?;'''
            c.execute(sql, (file_id,))
            self.conn.commit()
        # except Exception as e:
        #     print(f"删除图数据节点表失败: {e}")
        return True

    def delete_graph_node_by_knowledge_id(self, param):
        """根据知识id删除图数据节点表"""
        knowledge_id = param.get("knowledge_id", "")
        try:
            c = self.conn.cursor()
            sql = '''DELETE FROM graph_node WHERE knowledge_id = ?;'''
            c.execute(sql, (knowledge_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"删除图数据节点表失败: {e}")
            return False
        
    def create_graph_node_table(self):
        """创建图数据节点表
            文件id
            结点名称
            结点id
            结点文件来源
            结点对应的chunk的id
        """
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS graph_node (
                        entity_id TEXT NOT NULL,
                        knowledge_id TEXT NOT NULL,
                        file_id TEXT NOT NULL,
                        entity_name TEXT NOT NULL,
                        entity_type TEXT NOT NULL,
                        source_id TEXT,
                        entity_description TEXT,
                        entity_source_file TEXT
                    );'''
            c.execute(sql)
            self.conn.commit()
        except Exception as e:
            print(f"创建图数据节点表失败: {e}")
    
    def insert_node_info(self, param):
        """插入图数据节点表"""
        try:
            c = self.conn.cursor()
            sql = '''INSERT INTO graph_node (entity_id, knowledge_id, file_id, entity_name, entity_type, source_id, entity_description, entity_source_file) VALUES (?, ?, ?, ?, ?, ?, ?, ?);'''
            c.execute(sql, (param.get("entity_id"), param.get("knowledge_id"), param.get("file_id"), param.get("entity_name"), param.get("entity_type"), param.get("source_id"), param.get("entity_description"), param.get("entity_source_file")))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"插入图数据节点表失败: {e}")
            return False

    def query_graph_node_by_node_name_public(self, param):
        """根据结点名称查询图数据节点表，仅查询权限等级为public的文件"""
        entity_name = param.get("entity_name", "")
        knowledge_id = param.get("knowledge_id", "")
        try: 
            c = self.conn.cursor()
            sql = '''SELECT gn.* FROM graph_node gn 
                     JOIN file_basic_info fbi ON gn.file_id = fbi.file_id 
                     WHERE gn.entity_name LIKE ? AND gn.knowledge_id = ? AND fbi.permission_level = 'public' '''
            c.execute(sql, (f'%{entity_name}%', knowledge_id))
            rows = c.fetchall()
            result = []
            for row in rows:
                result.append({
                    "entity_id": row[0],
                    "knowledge_id": row[1],
                    "file_id": row[2],
                    "entity_name": row[3],
                    "entity_type": row[4],
                    "source_id": row[5],
                    "entity_description": row[6],
                    "entity_source_file": row[7]
                })
            return result
        except Exception as e:
            print(f"查询图数据节点失败: {e}")
            return []

    def query_graph_node_by_node_name(self, param):
        """根据结点名称查询图数据节点表"""
        entity_name = param.get("entity_name", "")
        knowledge_id = param.get("knowledge_id", "")
        try: 
            c = self.conn.cursor()
            sql = f"""SELECT * FROM graph_node WHERE entity_name like '%{entity_name}%' and knowledge_id='{knowledge_id}'"""
            c.execute(sql)
            rows = c.fetchall()
            result = []
            for row in rows:
                result.append({
                    "entity_id": row[0],
                    "knowledge_id": row[1],
                    "file_id": row[2],
                    "entity_name": row[3],
                    "entity_type": row[4],
                    "source_id": row[5],
                    "entity_description": row[6],
                    "entity_source_file": row[7]
                })
            return result
        except Exception as e:
            print(f"根据结点名称查询图数据节点表失败: {e}")
            return []

    def delete_graph_relation_table(self, file_id):
        """删除图数据关系表"""
        # try:
        if(True):
            c = self.conn.cursor()
            sql = f"""DELETE FROM graph_relation WHERE file_id = '{file_id}';"""
            c.execute(sql)
            self.conn.commit()
        # except Exception as e:
        #     print(f"删除图数据关系表失败: {e}")
        return True

    def delete_graph_relation_by_knowledge_id(self, param):
        """根据知识id删除图数据关系表"""
        knowledge_id = param.get("knowledge_id", "")
        try:
            c = self.conn.cursor()
            sql = '''DELETE FROM graph_relation WHERE knowledge_id = ?;'''
            c.execute(sql, (knowledge_id,))
            self.conn.commit()
        except Exception as e:
            print(f"删除图数据关系表失败: {e}")
        return True
    
    def create_graph_relation_table(self):
        """创建图数据关系表
            文件id
            文件名称
            关系源id
            关系类型
            关系的开始结点
            关系的结束结点
            关系权重
            关系描述
            关系关键词
        """
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS graph_relation (
                        knowledge_id TEXT NOT NULL,
                        file_id TEXT NOT NULL,
                        file_name TEXT NOT NULL,
                        relation_source_id TEXT,
                        relation_type TEXT NOT NULL,
                        start_node TEXT NOT NULL,
                        end_node TEXT NOT NULL,
                        weight REAL,
                        description TEXT,
                        keywords TEXT
                    );'''
            c.execute(sql)
            self.conn.commit()
        except Exception as e:
            print(f"创建图数据关系表失败: {e}")

    def insert_graph_relation(self, param):
        """插入图数据关系表"""
        try:
            c = self.conn.cursor()
            sql = '''INSERT INTO graph_relation (knowledge_id, file_id, file_name, relation_source_id, relation_type, start_node, end_node, weight, description, keywords) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);'''
            c.execute(sql, (
                param.get("knowledge_id"), param.get("file_id"), param.get("file_name"), 
                param.get("relation_source_id"), param.get("relation_type"),
                param.get("start_node"), param.get("end_node"), 
                param.get("weight"), param.get("description"), param.get("keywords")
            ))
            self.conn.commit()
            return c.lastrowid
        except Exception as e:
            print(f"插入图数据关系表失败: {e}")
            return False

    # 知识库操作方法
    def insert_knowledge_base(self, kb_info):
        """插入知识库信息"""
        try:
            c = self.conn.cursor()
            sql = '''INSERT INTO knowledge_base(
                        knowledge_id, name, create_time, description, 
                        valid_start_time, valid_end_time, create_user_id)
                     VALUES(?,?,?,?,?,?,?)'''
            c.execute(sql, (
                kb_info['knowledge_id'], kb_info['name'], kb_info['create_time'], kb_info['description'],
                kb_info['valid_start_time'], kb_info['valid_end_time'], kb_info['create_user_id']
            ))
            self.conn.commit()
            return c.lastrowid
        except Exception as e:
            print(f"插入知识库信息失败: {e}")
            return None
        
    def query_knowledge_by_knowledge_id(self, knowledge_id):
        """根据知识库ID查询知识库信息"""
        try:
            c = self.conn.cursor()
            sql = f"SELECT * FROM knowledge_base WHERE knowledge_id='{knowledge_id}'"
            c.execute(sql)
            row = c.fetchone()
            if row:
                return {
                    'knowledge_id': row[1],
                    'name': row[2],
                    'create_time': row[3],
                    'description': row[4],
                    'valid_start_time': row[5],
                    'valid_end_time': row[6],
                    'create_user_id': row[7]
                }
            return None
        except Exception as e:
            print(f"根据知识库ID查询知识库信息失败: {e}")
            return None
            
    def query_knowledge_by_knowledge_name(self, param):
        """根据名称查询知识库信息"""
        name = param.get("name", "")
        try:
            c = self.conn.cursor()
            sql = f"SELECT * FROM knowledge_base WHERE name='{name}'"
            c.execute(sql)
            rows = c.fetchall()
            result = []
            if(rows):
                for row in rows:
                    result.append({
                        'knowledge_id': row[1],
                    })
                return result
            return []
        except Exception as e:
            print(f"根据名称查询知识库信息失败: {e}")
            return []
        
    def search_knowledge_base_by_user_id(self, user_id):
        """根据用户ID查询知识库信息"""
        try:
            c = self.conn.cursor()
            sql = f"SELECT * FROM knowledge_base WHERE create_user_id='{user_id}'"
            c.execute(sql)
            rows = c.fetchall()
            result = []
            if(rows):
                for row in rows:
                    result.append({
                        'knowledge_id': row[1],
                        'name': row[2],
                        'create_time': row[3],
                        'description': row[4],
                        'valid_start_time': row[5],
                        'valid_end_time': row[6],
                        'create_user_id': row[7]
                    })
                return result
            return []
        except Exception as e:
            print(f"根据用户ID查询知识库信息失败: {e}")
            return []

    def search_knowledge_base_by_id_and_user_id(self, param):
        """根据知识库ID和用户ID查询知识库信息"""
        knowledge_id = param.get("knowledge_id", "")
        user_id = param.get("user_id", "")
        try:
            c = self.conn.cursor()
            sql = f"SELECT * FROM knowledge_base WHERE knowledge_id='{knowledge_id}' AND create_user_id='{user_id}'"
            c.execute(sql)
            rows = c.fetchall()
            result = []
            if(rows):
                for row in rows:
                    result.append({
                        'knowledge_id': row[1],
                        'name': row[2],
                        'create_user_id': row[7]
                    })
                return result
            return []
        except Exception as e:
            print(f"根据知识库ID和用户ID查询知识库信息失败: {e}")
            return []
        
    def query_knowledge_by_knowledge_name_and_user_id(self, param):
        """根据名称和用户ID查询知识库信息"""
        name = param.get("name", "")
        user_id = param.get("user_id", "")
        try:
            c = self.conn.cursor()
            sql = f"SELECT * FROM knowledge_base WHERE name='{name}' AND create_user_id='{user_id}'"
            c.execute(sql)
            rows = c.fetchall()
            result = []
            if(rows):
                for row in rows:
                    result.append({
                        'id': row[0],
                        'knowledge_id': row[1],
                        'name': row[2],
                        'create_time': row[3],
                        'description': row[4],
                        'valid_start_time': row[5],
                        'valid_end_time': row[6],
                        'create_user_id': row[7]
                    })
                return result
        except Exception as e:
            print(f"根据名称和用户ID查询知识库信息失败: {e}")
            return []

    def query_knowledge_base_by_id(self, kb_id):
        """根据ID查询知识库信息"""
        try:
            c = self.conn.cursor()
            sql = f"SELECT * FROM knowledge_base WHERE knowledge_id='{kb_id}';"
            c.execute(sql)
            row = c.fetchone()
            if row:
                return {
                    'knowledge_id': row[1],
                    'name': row[2],
                    'create_time': row[3],
                    'description': row[4],
                    'valid_start_time': row[5],
                    'valid_end_time': row[6],
                    'create_user_id': row[7]
                }
            return None
        except Exception as e:
            print(f"查询知识库信息失败: {e}")
            return None

    def query_all_knowledge_bases(self):
        """查询所有知识库信息"""
        try:
            c = self.conn.cursor()
            sql = "SELECT * FROM knowledge_base;"
            c.execute(sql)
            rows = c.fetchall()
            result = []
            if rows:
                for row in rows:
                    result.append({
                        'knowledge_id': row[1],
                        'name': row[2],
                        'create_time': row[3],
                        'description': row[4],
                        'valid_start_time': row[5],
                        'valid_end_time': row[6],
                        'create_user_id': row[7]
                    })
            return result
        except Exception as e:
            print(f"查询所有知识库信息失败: {e}")
            return []

    def search_knowledge_base_name(self):
        """搜索知识库"""
        try:
            c = self.conn.cursor()
            sql = "SELECT * FROM knowledge_base"
            c.execute(sql)
            rows = c.fetchall()
            result = []
            if(rows):
                for row in rows:
                    result.append({
                        "knowledge_name": row[2],
                    })
            return result
        except Exception as e:
            print(f"搜索知识库失败: {e}")
            return []

    def delete_file_basic_info(self, file_id):
        """删除文件基础信息"""
        try:
            c = self.conn.cursor()
            sql = "DELETE FROM file_basic_info WHERE file_id=?"
            c.execute(sql, (file_id,))
            self.conn.commit()
        except Exception as e:
            print(f"删除文件基础信息失败: {e}")
        return True

    def delete_file_detail_info(self, file_id):
        """删除文件详情信"""
        try:
            c = self.conn.cursor()
            sql = "DELETE FROM file_detail_info WHERE file_id=?"
            c.execute(sql, (file_id,))
            self.conn.commit()
        except Exception as e:
            print(f"删除文件详情信息失败: {e}")
        return True
    
    # 文件基础信息操作方法
    def insert_file_basic_info(self, file_info):
        """插入文件基础信息"""
        #try:
        if(True):
            c = self.conn.cursor()
            sql = '''INSERT INTO file_basic_info(
                        knowledge_id, file_id, file_name, file_path,
                        file_size, upload_time, upload_user_id, permission_level, url, session_id)
                     VALUES(?,?,?,?,?,?,?,?,?,?)'''
            c.execute(sql, (
                file_info['knowledge_id'], file_info['file_id'], file_info['file_name'], file_info['file_path'],
                file_info['file_size'], file_info['upload_time'], file_info['upload_user_id'], file_info['permission_level'],
                file_info.get('url', ""), file_info.get('session_id', "")
            ))
            self.conn.commit()
            print("插入文件基础信息成功")
            return c.lastrowid
        #except Exception as e:
        #    print(f"插入文件基础信息失败: {e}")
        else:
            return None

    # 用户操作方法
    def insert_user(self, user_info):
        """插入用户信息"""
        try:
            c = self.conn.cursor()
            sql = '''INSERT INTO user_info(user_id, user_name, password, permissions)
                     VALUES(?,?,?,?)'''
            c.execute(sql, (
                user_info['user_id'], user_info['user_name'], user_info['password'], user_info['permissions']
            ))
            self.conn.commit()
            return c.lastrowid
        except Exception as e:
            print(f"插入用户信息失败: {e}")
            return None
        
    def insert_file_detail_info(self, file_info):
        """插入文件详细信息"""
        # 判断输入参数是否为空
        if not file_info:
            print("插入文件详细信息失败: 输入参数为空")
            return None
            
        # 检查必需字段是否存在
        required_fields = ['file_id', 'file_name']
        for field in required_fields:
            if field not in file_info or not file_info[field]:
                print(f"插入文件详细信息失败: 缺少必需字段 '{field}' 或字段为空")
                return None
        if(True):
        # try:
            c = self.conn.cursor()
            sql = '''INSERT INTO file_detail_info(
                        file_id, file_name, recognized_title, overview, author,
                        create_time, valid_area_province, valid_area_city,
                        tags, category, valid_start_time, valid_end_time, catalog)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)'''
            c.execute(sql, (
                file_info['file_id'], 
                file_info['file_name'], 
                file_info.get('recognized_title', '') or '',
                file_info.get('overview', '') or '',
                file_info.get('authors', '') or '',
                file_info.get('create_time', '') or '',
                file_info.get('valid_area_province', '') or '',
                file_info.get('valid_area_city', '') or '',
                file_info.get('tags', '') or '',
                file_info.get('category', '') or '',
                file_info.get('valid_start_time', '') or '',
                file_info.get('valid_end_time', '') or '',
                file_info.get('catalog', '') or ''
            ))
            print("插入文件详细信息成功")
            self.conn.commit()
            return c.lastrowid
        # except Exception as e:
        #     print(f"插入文件详细信息失败: {e}")
        else:
            print("插入文件详细信息失败: 模拟错误")
            return None

    def search_file_from_name_userid(self, file_name, user_id):
        """根据文件名、用户ID和数据核心查询文件信息"""
        try:
            c = self.conn.cursor()
            sql = '''SELECT * FROM file_basic_info 
                     WHERE file_name=? AND upload_user_id=?'''
            c.execute(sql, (file_name, user_id))
            rows = c.fetchall()
            
            # 校验文件是否存在
            result = []
            for row in rows:
                file_info = {
                    'knowledge_id': row[0],
                    'file_id': row[1],
                    'file_name': row[2],
                    'file_path': row[3],
                    'file_size': row[4],
                    'upload_time': row[5],
                    'upload_user_id': row[6],
                    'permission_level': row[7],
                    'url': row[8]
                }
                
                # 校验文件物理路径是否存在
                if file_info['file_path'] and os.path.exists(file_info['file_path']):
                    result.append(file_info)
                    
            return result
        except Exception as e:
            print(f"搜索文件信息失败: {e}")
            return []

    def search_file_by_knowledge_id(self, knowledge_id):
        """根据知识库ID查询文件列表"""
        try:
            c = self.conn.cursor()
            sql = "SELECT * FROM file_basic_info WHERE knowledge_id=?"
            c.execute(sql, (knowledge_id,))
            rows = c.fetchall()
            result = []
            if(rows):
                for row in rows:
                    result.append({
                        'file_id': row[1],
                        'file_name': row[2],
                        'file_path': row[3],
                        'file_size': row[4],
                        'upload_time': row[5],
                        'upload_user_id': row[6],
                        'permission_level': row[7],
                        'url': row[8]
                    })
                return result
            return result
        except Exception as e:
            print(f"根据知识库ID查询文件列表失败: {e}")
            return []
        
    def create_base_sql_table(self):
        """创建base_sql表 - 保存数据库连接信息"""
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS base_sql (
                        sql_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        ip TEXT NOT NULL,
                        port TEXT NOT NULL,
                        sql_type TEXT NOT NULL,
                        sql_name TEXT NOT NULL,
                        sql_user_name TEXT NOT NULL,
                        sql_user_password TEXT NOT NULL,
                        sql_description TEXT,
                        create_time TEXT,
                        update_time TEXT
                        );'''
            c.execute(sql)
            self.conn.commit()
            # logger.info("创建base_sql表成功")
        except Exception as e:
            # logger.error(f"创建base_sql表失败: {e}")
            raise
    
    def create_table_sql_table(self):
        """创建table_sql表 - 保存表描述信息"""
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS table_sql (
                        table_id TEXT PRIMARY KEY,
                        sql_id TEXT NOT NULL,
                        table_name TEXT NOT NULL,
                        table_description TEXT,
                        create_time TEXT,
                        update_time TEXT,
                        FOREIGN KEY (sql_id) REFERENCES base_sql(sql_id)
                        );'''
            c.execute(sql)
            self.conn.commit()
            # logger.info("创建table_sql表成功")
        except Exception as e:
            # logger.error(f"创建table_sql表失败: {e}")
            raise
    
    def create_col_sql_table(self):
        """创建col_sql表 - 保存列信息"""
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS col_sql (
                        col_id TEXT PRIMARY KEY,
                        table_id TEXT NOT NULL,
                        col_name TEXT NOT NULL,
                        col_type TEXT,
                        col_info TEXT,
                        create_time TEXT,
                        FOREIGN KEY (table_id) REFERENCES table_sql(table_id)
                        );'''
            c.execute(sql)
            self.conn.commit()
            # logger.info("创建col_sql表成功")
        except Exception as e:
            # logger.error(f"创建col_sql表失败: {e}")
            raise
    
    def create_rel_sql_table(self):
        """创建rel_sql表 - 保存列关联关系"""
        try:
            c = self.conn.cursor()
            sql = '''CREATE TABLE IF NOT EXISTS rel_sql (
                        rel_id TEXT PRIMARY KEY,
                        sql_id TEXT NOT NULL,
                        from_table TEXT NOT NULL,
                        from_col TEXT NOT NULL,
                        to_table TEXT NOT NULL,
                        to_col TEXT NOT NULL,
                        create_time TEXT,
                        update_time TEXT,
                        FOREIGN KEY (sql_id) REFERENCES base_sql(sql_id)
                        );'''
            c.execute(sql)
            self.conn.commit()
            # logger.info("创建rel_sql表成功")
        except Exception as e:
            # logger.error(f"创建rel_sql表失败: {e}")
            raise
    
    # base_sql表操作
    def insert_base_sql(self, param):
        """插入数据库连接信息"""
        try:
            c = self.conn.cursor()
            sql = '''INSERT INTO base_sql (sql_id, user_id, ip, port, sql_type, sql_name, 
                     sql_user_name, sql_user_password, sql_description, create_time, update_time) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);'''
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            values = (
                param.get("sql_id"),
                param.get("user_id"),
                param.get("ip"),
                param.get("port"),
                param.get("sql_type"),
                param.get("sql_name"),
                param.get("sql_user_name"),
                param.get("sql_user_password"),
                param.get("sql_description", ""),
                now,
                now
            )
            c.execute(sql, values)
            self.conn.commit()
            # logger.info(f"插入数据库连接信息成功: {param.get('sql_id')}")
            return True
        except Exception as e:
            # logger.error(f"插入数据库连接信息失败: {e}")
            return False
    
    def query_base_sql_by_user_id(self, user_id):
        """根据user_id查询所有数据库连接信息"""
        try:
            c = self.conn.cursor()
            sql = '''SELECT sql_id, user_id, ip, port, sql_type, sql_name, sql_user_name,
                     sql_description, create_time, update_time
                     FROM base_sql WHERE user_id = ? ORDER BY create_time DESC;'''
            c.execute(sql, (user_id,))
            rows = c.fetchall()
            result = []
            for row in rows:
                result.append({
                    "sql_id": row[0],
                    "user_id": row[1],
                    "ip": row[2],
                    "port": row[3],
                    "sql_type": row[4],
                    "sql_name": row[5],
                    "sql_user_name": row[6],
                    "sql_description": row[7],
                    "create_time": row[8],
                    "update_time": row[9]
                })
            return result
        except Exception as e:
            # logger.error(f"查询数据库连接信息失败: {e}")
            return []
    
    def query_base_sql_by_sql_id(self, sql_id):
        """根据sql_id查询数据库连接信息
        sql_id: 数据库连接id
        return: 数据库连接信息
            {
                "sql_id": 数据库连接id,
                "user_id": 用户id,
                "ip": 数据库ip,
                "port": 数据库端口,
                "sql_type": 数据库类型,
                "sql_name": 数据库名称,
                "sql_user_name": 数据库用户名,
                "sql_user_password": 数据库密码,
                "sql_description": 数据库描述,
                "create_time": 创建时间,
                "update_time": 更新时间
            }
        """
        try:
            c = self.conn.cursor()
            sql = '''SELECT * FROM base_sql WHERE sql_id = ?;'''
            c.execute(sql, (sql_id,))
            row = c.fetchone()
            if row:
                return {
                    "sql_id": row[0],
                    "user_id": row[1],
                    "ip": row[2],
                    "port": row[3],
                    "sql_type": row[4],
                    "sql_name": row[5],
                    "sql_user_name": row[6],
                    "sql_user_password": row[7],
                    "sql_description": row[8],
                    "create_time": row[9],
                    "update_time": row[10]
                }
            return None
        except Exception as e:
            # logger.error(f"查询数据库连接信息失败: {e}")
            return None
    
    def update_base_sql_description(self, sql_id, sql_description):
        """更新数据库描述信息"""
        try:
            c = self.conn.cursor()
            sql = '''UPDATE base_sql SET sql_description = ?, update_time = ? WHERE sql_id = ?;'''
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute(sql, (sql_description, now, sql_id))
            self.conn.commit()
            # logger.info(f"更新数据库描述成功: {sql_id}")
            return True
        except Exception as e:
            # logger.error(f"更新数据库描述失败: {e}")
            return False

    def delete_base_sql(self, sql_id):
        """删除数据库连接信息（级联删除相关表信息）"""
        try:
            c = self.conn.cursor()
            # 先删除关联的rel_sql记录
            c.execute('''DELETE FROM rel_sql WHERE sql_id = ?;''', (sql_id,))
            # 删除col_sql（通过table_id）
            c.execute('''DELETE FROM col_sql WHERE table_id IN 
                         (SELECT table_id FROM table_sql WHERE sql_id = ?);''', (sql_id,))
            # 删除table_sql
            c.execute('''DELETE FROM table_sql WHERE sql_id = ?;''', (sql_id,))
            # 删除base_sql
            c.execute('''DELETE FROM base_sql WHERE sql_id = ?;''', (sql_id,))
            
            # 删除sql_des
            c.execute('''DELETE FROM sql_des WHERE sql_id = ?;''', (sql_id,))
            self.conn.commit()
            # logger.info(f"删除数据库连接信息成功: {sql_id}")
            return True
        except Exception as e:
            # logger.error(f"删除数据库连接信息失败: {e}")
            self.conn.rollback()
            return False
    
    # table_sql表操作
    def insert_table_sql(self, param):
        """插入表描述信息"""
        try:
            c = self.conn.cursor()
            sql = '''INSERT OR REPLACE INTO table_sql (table_id, sql_id, table_name, 
                     table_description, create_time, update_time) 
                     VALUES (?, ?, ?, ?, ?, ?);'''
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            values = (
                param.get("table_id"),
                param.get("sql_id"),
                param.get("table_name"),
                param.get("table_description", ""),
                now,
                now
            )
            c.execute(sql, values)
            self.conn.commit()
            return True
        except Exception as e:
            # logger.error(f"插入表描述信息失败: {e}")
            return False
    
    def update_table_sql_description(self, sql_id, table_name, table_description):
        """更新表描述信息"""
        try:
            c = self.conn.cursor()
            sql = '''UPDATE table_sql SET table_description = ?, update_time = ? 
                     WHERE sql_id = ? AND table_name = ?;'''
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute(sql, (table_description, now, sql_id, table_name))
            self.conn.commit()
            return True
        except Exception as e:
            # logger.error(f"更新表描述信息失败: {e}")
            return False
    
    def query_table_sql_by_sql_id(self, sql_id):
        """根据sql_id查询所有表信息
        sql_id: 数据库连接id
        return: 表信息列表
        [
            {
                "table_id": 表id,
                "sql_id": 数据库连接id,
                "table_name": 表名称,
                "table_description": 表描述,
                "create_time": 创建时间,
                "update_time": 更新时间
            }
        ]
        """
        try:
            c = self.conn.cursor()
            sql = '''SELECT table_id, sql_id, table_name, table_description, 
                     create_time, update_time FROM table_sql WHERE sql_id = ?;'''
            c.execute(sql, (sql_id,))
            rows = c.fetchall()
            result = []
            for row in rows:
                result.append({
                    "table_id": row[0],
                    "sql_id": row[1],
                    "table_name": row[2],
                    "table_description": row[3],
                    "create_time": row[4],
                    "update_time": row[5]
                })
            return result
        except Exception as e:
            # logger.error(f"查询表信息失败: {e}")
            return []

    def query_table_sql_by_sql_id_and_name(self, sql_id, table_name):
        """根据sql_id和table_name查询表信息"""
        try:
            c = self.conn.cursor()
            sql = '''SELECT table_id, sql_id, table_name, table_description,
                     create_time, update_time FROM table_sql WHERE sql_id = ? AND table_name = ?;'''
            c.execute(sql, (sql_id, table_name))
            row = c.fetchone()
            if row:
                return {
                    "table_id": row[0],
                    "sql_id": row[1],
                    "table_name": row[2],
                    "table_description": row[3],
                    "create_time": row[4],
                    "update_time": row[5]
                }
            return None
        except Exception as e:
            # logger.error(f"查询表信息失败: {e}")
            return None
    
    # col_sql表操作
    def insert_col_sql(self, param):
        """插入列信息"""
        try:
            c = self.conn.cursor()
            sql = '''INSERT OR REPLACE INTO col_sql (col_id, table_id, col_name, col_type, col_info, create_time) 
                     VALUES (?, ?, ?, ?, ?, ?);'''
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            col_info_json = json.dumps(param.get("col_info", {})) if param.get("col_info") else None
            values = (
                param.get("col_id"),
                param.get("table_id"),
                param.get("col_name"),
                param.get("col_type"),
                col_info_json,
                now
            )
            c.execute(sql, values)
            self.conn.commit()
            return True
        except Exception as e:
            # logger.error(f"插入列信息失败: {e}")
            return False
    
    def query_col_sql_by_table_id(self, table_id):
        """根据table_id查询所有列信息
        table_id: 表id
        return: 列信息列表
        [
            {
                "col_id": 列id,
                "table_id": 表id,
                "col_name": 列名称,
                "col_type": 列类型,
                "col_info": 列信息,
                "create_time": 创建时间
            }
        ]
        """
        try:
            c = self.conn.cursor()
            sql = '''SELECT col_id, table_id, col_name, col_type, col_info, create_time 
                     FROM col_sql WHERE table_id = ?;'''
            c.execute(sql, (table_id,))
            rows = c.fetchall()
            result = []
            for row in rows:
                col_info = None
                if row[4]:
                    try:
                        col_info = json.loads(row[4])
                    except:
                        col_info = row["col_info"]
                result.append({
                    "col_id": row[0],
                    "table_id": row[1],
                    "col_name": row[2],
                    "col_type": row[3],
                    "col_info": col_info,
                    "create_time": row[5]
                })
            return result
        except Exception as e:
            # logger.error(f"查询列信息失败: {e}")
            return []

    def query_col_sql_by_table_id_and_name(self, table_id, col_name):
        """根据table_id和col_name查询列信息"""
        try:
            c = self.conn.cursor()
            sql = '''SELECT col_id, table_id, col_name, col_type, col_info, create_time
                     FROM col_sql WHERE table_id = ? AND col_name = ?;'''
            c.execute(sql, (table_id, col_name))
            row = c.fetchone()
            if row:
                col_info = None
                if row[4]:
                    try:
                        col_info = json.loads(row[4])
                    except:
                        col_info = row[4]
                return {
                    "col_id": row[0],
                    "table_id": row[1],
                    "col_name": row[2],
                    "col_type": row[3],
                    "col_info": col_info,
                    "create_time": row[5]
                }
            return None
        except Exception as e:
            # logger.error(f"查询列信息失败: {e}")
            return None

    def update_col_sql_info(self, col_id, col_info_json):
        """更新列的col_info字段"""
        try:
            c = self.conn.cursor()
            sql = '''UPDATE col_sql SET col_info = ?, update_time = ? WHERE col_id = ?;'''
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute(sql, (col_info_json, now, col_id))
            self.conn.commit()
            return True
        except Exception as e:
            # logger.error(f"更新列信息失败: {e}")
            return False

    def query_tables_by_description_like(self, sql_id, search_term):
        """根据表描述LIKE搜索表信息
        sql_id: 数据库连接id
        search_term: 搜索关键词
        return: 表信息列表
        """
        try:
            c = self.conn.cursor()
            sql = '''SELECT table_id, sql_id, table_name, table_description, 
                     create_time, update_time FROM table_sql 
                     WHERE sql_id = ? AND table_description LIKE ?;'''
            c.execute(sql, (sql_id, f'%{search_term}%'))
            rows = c.fetchall()
            result = []
            for row in rows:
                result.append({
                    "table_id": row[0],
                    "sql_id": row[1],
                    "table_name": row[2],
                    "table_description": row[3],
                    "create_time": row[4],
                    "update_time": row[5]
                })
            return result
        except Exception as e:
            return []
    
    def query_columns_by_description_like(self, sql_id, search_term):
        """根据列描述LIKE搜索列信息
        sql_id: 数据库连接id
        search_term: 搜索关键词
        return: 列信息列表（包含表信息）
        """
        try:
            c = self.conn.cursor()
            # 先查询所有列，然后过滤col_info中包含search_term的列
            sql = '''SELECT c.col_id, c.table_id, c.col_name, c.col_type, c.col_info, c.create_time,
                            t.table_id, t.sql_id, t.table_name, t.table_description
                     FROM col_sql c
                     JOIN table_sql t ON c.table_id = t.table_id
                     WHERE t.sql_id = ?;'''
            c.execute(sql, (sql_id,))
            rows = c.fetchall()
            result = []
            for row in rows:
                col_info = None
                if row[4]:
                    try:
                        col_info = json.loads(row[4])
                    except:
                        col_info = row[4]
                
                # 检查col_info中的comment字段是否包含search_term
                comment = ""
                if isinstance(col_info, dict):
                    comment = col_info.get("comment", "")
                elif isinstance(col_info, str):
                    try:
                        col_info_dict = json.loads(col_info)
                        comment = col_info_dict.get("comment", "")
                    except:
                        comment = ""
                
                # 如果comment中包含search_term，则添加到结果中
                if search_term.lower() in comment.lower():
                    result.append({
                        "col_id": row[0],
                        "table_id": row[1],
                        "col_name": row[2],
                        "col_type": row[3],
                        "col_info": col_info,
                        "create_time": row[5],
                        "table_name": row[8],
                        "table_description": row[9],
                        "col_comment": comment
                    })
            return result
        except Exception as e:
            return []

    def delete_col_sql_by_table_id(self, table_id):
        """删除指定表的所有列信息"""
        try:
            c = self.conn.cursor()
            sql = '''DELETE FROM col_sql WHERE table_id = ?;'''
            c.execute(sql, (table_id,))
            self.conn.commit()
            return True
        except Exception as e:
            # logger.error(f"删除列信息失败: {e}")
            return False
    
    # rel_sql表操作
    def insert_rel_sql(self, param):
        """插入列关联关系"""
        try:
            c = self.conn.cursor()
            sql = '''INSERT OR REPLACE INTO rel_sql (rel_id, sql_id, from_table, from_col, 
                     to_table, to_col, create_time, update_time) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?);'''
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            values = (
                param.get("rel_id"),
                param.get("sql_id"),
                param.get("from_table"),
                param.get("from_col"),
                param.get("to_table"),
                param.get("to_col"),
                now,
                now
            )
            c.execute(sql, values)
            self.conn.commit()
            return True
        except Exception as e:
            # logger.error(f"插入列关联关系失败: {e}")
            return False
        
    def delete_rel_sql_by_rel_id(self, rel_id):
        """删除指定关联关系"""
        try:
            c = self.conn.cursor()
            sql = '''DELETE FROM rel_sql WHERE rel_id = ?;'''
            c.execute(sql, (rel_id,))
            self.conn.commit()
            return True
        except Exception as e:
            # logger.error(f"删除列关联关系失败: {e}")
            return False
        
    def delete_rel_sql_by_sql_id(self, sql_id):
        """删除指定数据库的所有关联关系"""
        try:
            c = self.conn.cursor()
            sql = '''DELETE FROM rel_sql WHERE sql_id = ?;'''
            c.execute(sql, (sql_id,))
            self.conn.commit()
            return True
        except Exception as e:
            # logger.error(f"删除列关联关系失败: {e}")
            return False
    
    def query_rel_sql_by_sql_id(self, sql_id):
        """根据sql_id查询所有列关联关系"""
        try:
            c = self.conn.cursor()
            sql = '''SELECT rel_id, sql_id, from_ta
            ble, from_col, to_table, to_col, 
                     create_time, update_time FROM rel_sql WHERE sql_id = ?;'''
            c.execute(sql, (sql_id,))
            rows = c.fetchall()
            result = []
            for row in rows:
                result.append({
                    "rel_id": row[0],
                    "sql_id": row[1],
                    "from_table": row[2],
                    "from_col": row[3],
                    "to_table": row[4],
                    "to_col": row[5],
                    "create_time": row[6],
                    "update_time": row[7]
                })
            return result
        except Exception as e:
            # logger.error(f"查询列关联关系失败: {e}")
            return []

# 全局单例实例
cSingleSqlite = KnowledgeBaseDB()
