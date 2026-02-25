# -*- coding: utf-8 -*-

"""
Vanna SQL生成器管理器
用于管理不同数据库的Vanna实例，实现自然语言到SQL的转换
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from vanna.openai import OpenAI_Chat
from vanna.chromadb import ChromaDB_VectorStore

from Db.sqlite_db import cSingleSqlite

# 导入Vanna相关模块
try:
    from vanna.remote import VannaDefault
    from openai import OpenAI
except ImportError as e:
    logging.error(f"导入Vanna相关模块失败: {e}")
    raise ImportError("需要安装vanna相关依赖: pip install vanna[all] langchain-openai langchain-community")

logger = logging.getLogger(__name__)

api_key = os.getenv("QWEN_API_KEY")
base_url = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
model_name = os.getenv("THEME_MODEL", "qwen3-32b")

client = OpenAI(
    api_key=api_key,
    base_url=base_url,
    default_headers = {"x-foo": "true"},
)

# 1. Define a standard Vanna class
class MyVanna(ChromaDB_VectorStore, OpenAI_Chat):
    def __init__(self, client=None, config=None, extra_body=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        OpenAI_Chat.__init__(self, client=client, config=config)

class VannaManager:
    """
    Vanna管理器，负责管理不同sql_id的Vanna实例
    """

    def __init__(self):
        self.vanna_instances: Dict[str, VannaDefault] = {}
        self.training_data: Dict[str, Dict[str, List[str]]] = {}
        self.config_dir = Path("conf/vanna_data")
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _get_llm_config(self, model_type: str = "deepseek") -> Dict[str, Any]:
        """
        获取LLM配置信息

        Args:
            model_type: 模型类型 ("deepseek" 或 "tongyi")

        Returns:
            LLM配置字典
        """
        if model_type not in self.llm_configs:
            logger.warning(f"未知的模型类型 {model_type}，使用默认的deepseek")
            model_type = "deepseek"

        return self.llm_configs[model_type]["params"]

    def get_vanna_instance(self, sql_id: str, set_model_type: str = "deepseek") -> VannaDefault:
        """
        获取或创建指定sql_id的Vanna实例
        Vanna通过环境变量配置LLM，不需要显式传入LLM实例

        Args:
            sql_id: 数据库ID
            model_type: 使用的模型类型 ("deepseek" 或 "tongyi")

        Returns:
            VannaDefault实例
        """
        if sql_id not in self.vanna_instances:
            logger.info(f"创建新的Vanna实例 for sql_id: {sql_id}")

            # 获取LLM配置（用于环境变量设置）
            
            chroma_path = str(self.config_dir / f"chroma_{sql_id}")
            
            db_info = cSingleSqlite.query_base_sql_by_sql_id(sql_id)
            
            # 创建Vanna实例
            # Vanna通常通过环境变量配置API，使用默认的OpenAI兼容接口
            try:
                # 设置环境变量以配置API
                vn = MyVanna(client=client,config={"model": model_name, 'path': chroma_path})
                database_type = db_info.get("sql_type", "postgresql").lower()
                if(database_type == "postgresql"):
                    vn.connect_to_postgres(
                        host=db_info.get("ip", "localhost"),
                        dbname=db_info.get("sql_name", "postgres"),
                        user=db_info.get("sql_user_name", "postgres"), 
                        password=db_info.get("sql_user_password", "password"),
                        port=int(db_info.get("port", "password"))
                    )
                if(database_type == "mysql"):
                    vn.connect_to_mysql(
                        host=db_info.get("ip", "localhost"),
                        dbname=db_info.get("sql_name", "postgres"),
                        user=db_info.get("sql_user_name", "postgres"), 
                        password=db_info.get("sql_user_password", "password"),
                        port=int(db_info.get("port", "password"))
                    )
                
                logger.info("使用默认配置初始化Vanna")

            except Exception as e:
                logger.warning(f"Vanna初始化失败: {e}，使用基本配置")
                vn = VannaDefault()
            if(sql_id not in self.vanna_instances.keys()):
                # 加载已有的训练数据
                vn = self._load_training_data(sql_id, vn)

                self.vanna_instances[sql_id] = vn
                logger.info(f"Vanna实例创建完成 for sql_id: {sql_id}")

        return self.vanna_instances[sql_id]

    def _get_data_file_path(self, sql_id: str, data_type: str) -> Path:
        """
        获取数据文件路径

        Args:
            sql_id: 数据库ID
            data_type: 数据类型 (ddl, documentation, sql)

        Returns:
            文件路径
        """
        return self.config_dir / f"vanna_{sql_id}_{data_type}.json"

    def _load_training_data(self, sql_id: str, vn: VannaDefault):
        """
        加载指定sql_id的训练数据到Vanna实例

        Args:
            sql_id: 数据库ID
            vn: Vanna实例
        """
        try:
            # 加载DDL
            ddl_file = self._get_data_file_path(sql_id, "ddl")
            if ddl_file.exists():
                with open(ddl_file, 'r', encoding='utf-8') as f:
                    ddl_data = json.load(f)
                    for ddl in ddl_data:
                        try:
                            vn.train(ddl=ddl)
                        except Exception as e:
                            logger.warning(f"加载DDL失败: {e}")
                logger.info(f"加载了 {len(ddl_data)} 条DDL数据 for sql_id: {sql_id}")

            # 加载文档
            doc_file = self._get_data_file_path(sql_id, "documentation")
            if doc_file.exists():
                with open(doc_file, 'r', encoding='utf-8') as f:
                    doc_data = json.load(f)
                    for doc in doc_data:
                        try:
                            vn.train(documentation=doc)
                        except Exception as e:
                            logger.warning(f"加载文档失败: {e}")
                logger.info(f"加载了 {len(doc_data)} 条文档数据 for sql_id: {sql_id}")

            # 加载SQL示例
            sql_file = self._get_data_file_path(sql_id, "sql")
            if sql_file.exists():
                with open(sql_file, 'r', encoding='utf-8') as f:
                    sql_data = json.load(f)
                    for sql_item in sql_data:
                        try:
                            if isinstance(sql_item, dict) and 'sql' in sql_item:
                                vn.train(sql=sql_item['sql'])
                            elif isinstance(sql_item, str):
                                vn.train(sql=sql_item)
                        except Exception as e:
                            logger.warning(f"加载SQL示例失败: {e}")
                logger.info(f"加载了 {len(sql_data)} 条SQL示例数据 for sql_id: {sql_id}")
            return vn
        except Exception as e:
            logger.error(f"加载训练数据失败 for sql_id {sql_id}: {e}")
            return vn

    def _save_training_data(self, sql_id: str, data_type: str, data: List[str]):
        """
        保存训练数据到文件

        Args:
            sql_id: 数据库ID
            data_type: 数据类型
            data: 数据列表
        """
        try:
            file_path = self._get_data_file_path(sql_id, data_type)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"保存了 {len(data)} 条{data_type}数据到文件: {file_path}")
        except Exception as e:
            logger.error(f"保存{data_type}数据失败 for sql_id {sql_id}: {e}")

    def add_ddl(self, sql_id: str, ddl_statements: List[str], model_type: str = "deepseek"):
        """
        添加DDL语句到Vanna训练数据

        Args:
            sql_id: 数据库ID
            ddl_statements: DDL语句列表
            model_type: 模型类型
        """
        try:
            vn = self.get_vanna_instance(sql_id, model_type)

            for ddl in ddl_statements:
                try:
                    vn.train(ddl=ddl)
                except Exception as e:
                    logger.warning(f"添加DDL失败: {e}")

            # 保存到文件
            if sql_id not in self.training_data:
                self.training_data[sql_id] = {"ddl": [], "documentation": [], "sql": []}

            self.training_data[sql_id]["ddl"].extend(ddl_statements)
            self._save_training_data(sql_id, "ddl", self.training_data[sql_id]["ddl"])

            logger.info(f"为sql_id {sql_id} 添加了 {len(ddl_statements)} 条DDL语句")
        except Exception as e:
            logger.error(f"添加DDL到Vanna失败 for sql_id {sql_id}: {e}")

    def add_documentation(self, sql_id: str, documents: List[str], model_type: str = "deepseek"):
        """
        添加文档到Vanna训练数据

        Args:
            sql_id: 数据库ID
            documents: 文档列表
            model_type: 模型类型
        """
        try:
            vn = self.get_vanna_instance(sql_id, model_type)

            for doc in documents:
                try:
                    vn.train(documentation=doc)
                except Exception as e:
                    logger.warning(f"添加文档失败: {e}")

            # 保存到文件
            if sql_id not in self.training_data:
                self.training_data[sql_id] = {"ddl": [], "documentation": [], "sql": []}

            self.training_data[sql_id]["documentation"].extend(documents)
            self._save_training_data(sql_id, "documentation", self.training_data[sql_id]["documentation"])

            logger.info(f"为sql_id {sql_id} 添加了 {len(documents)} 条文档")
        except Exception as e:
            logger.error(f"添加文档到Vanna失败 for sql_id {sql_id}: {e}")

    def add_sql_examples(self, sql_id: str, sql_examples: List[str], model_type: str = "deepseek"):
        """
        添加SQL示例到Vanna训练数据

        Args:
            sql_id: 数据库ID
            sql_examples: SQL示例列表
            model_type: 模型类型
        """
        try:
            vn = self.get_vanna_instance(sql_id, model_type)

            for sql in sql_examples:
                try:
                    vn.train(sql=sql)
                except Exception as e:
                    logger.warning(f"添加SQL示例失败: {e}")

            # 保存到文件
            if sql_id not in self.training_data:
                self.training_data[sql_id] = {"ddl": [], "documentation": [], "sql": []}

            self.training_data[sql_id]["sql"].extend(sql_examples)
            self._save_training_data(sql_id, "sql", self.training_data[sql_id]["sql"])

            logger.info(f"为sql_id {sql_id} 添加了 {len(sql_examples)} 条SQL示例")
        except Exception as e:
            logger.error(f"添加SQL示例到Vanna失败 for sql_id {sql_id}: {e}")

    def generate_sql(self, sql_id: str, question: str, model_type: str = "deepseek") -> Optional[str]:
        """
        使用Vanna生成SQL查询
        Vanna使用环境变量中配置的LLM来生成SQL

        Args:
            sql_id: 数据库ID
            question: 自然语言问题
            model_type: 模型类型 ("deepseek" 或 "tongyi")

        Returns:
            生成的SQL字符串，如果失败返回None
        """
        try:
            vn = self.get_vanna_instance(sql_id, model_type)
            sql = vn.generate_sql(question)
            logger.info(f"Vanna为sql_id {sql_id}生成了SQL: {sql}")
            return sql
        except Exception as e:
            logger.error(f"Vanna生成SQL失败 for sql_id {sql_id}: {e}")
            return None

    def get_training_data_stats(self, sql_id: str) -> Dict[str, int]:
        """
        获取指定sql_id的训练数据统计

        Args:
            sql_id: 数据库ID

        Returns:
            训练数据统计字典
        """
        if sql_id not in self.training_data:
            return {"ddl": 0, "documentation": 0, "sql": 0}

        data = self.training_data[sql_id]
        return {
            "ddl": len(data.get("ddl", [])),
            "documentation": len(data.get("documentation", [])),
            "sql": len(data.get("sql", []))
        }

    def clear_instance(self, sql_id: str):
        """
        清除指定sql_id的Vanna实例（释放内存）

        Args:
            sql_id: 数据库ID
        """
        if sql_id in self.vanna_instances:
            del self.vanna_instances[sql_id]
            logger.info(f"清除了sql_id {sql_id}的Vanna实例")

    def clear_all_instances(self):
        """
        清除所有Vanna实例
        """
        self.vanna_instances.clear()
        logger.info("清除了所有Vanna实例")

    def add_sql_list(self, sql_id: str, sql_list: List[Dict[str, Any]]):
        """
        添加SQL列表到Vanna训练数据

        Args:
            sql_id: 数据库ID
            sql_list: SQL对象列表，每个对象包含 'sql' 和 'des' 字段
        """
        try:
            vn = self.get_vanna_instance(sql_id)
            for sql_item in sql_list:
                vn.train(question=sql_item.get("des", ""), sql=sql_item.get("sql", ""))

            logger.info(f"为sql_id {sql_id} 添加了 {len(sql_list)} 条SQL示例")
        except Exception as e:
            logger.error(f"添加SQL列表到Vanna失败 for sql_id {sql_id}: {e}")

# 全局Vanna管理器实例
vanna_manager = VannaManager()


def get_vanna_manager() -> VannaManager:
    """
    获取全局Vanna管理器实例

    Returns:
        VannaManager实例
    """
    return vanna_manager


# if __name__ == "__main__":
#     # 测试代码
#     manager = get_vanna_manager()

#     # 测试基本功能
#     print("=== Vanna管理器测试 ===")

#     # 创建实例
#     vn = manager.get_vanna_instance("test_db")
#     print("✓ Vanna实例创建成功")

#     # 测试添加训练数据
#     manager.add_ddl("test_db", ["CREATE TABLE users (id INT, name VARCHAR(50));"])
#     manager.add_documentation("test_db", ["用户表包含用户的基本信息"])
#     manager.add_sql_examples("test_db", ["SELECT * FROM users WHERE id = 1;"])

#     # 查看统计
#     stats = manager.get_training_data_stats("test_db")
#     print(f"训练数据统计: {stats}")

#     print("✓ Vanna管理器测试完成")
