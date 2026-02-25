# -*- coding: utf-8 -*-
"""
SQL Schema Vector Agent - 基于Milvus的向量搜索代理

功能：
1. 将表格的描述和列注释存储到Milvus向量库
2. 按sql_id分区，每个sql_id代表一个数据库
3. 支持双向量搜索（表格描述+列注释）
4. 使用WeightedRanker组合搜索结果
"""

import logging
from typing import List, Dict, Any, Tuple

from pymilvus import FieldSchema
from pymilvus import CollectionSchema
from pymilvus import DataType
from pymilvus import AnnSearchRequest
from pymilvus import WeightedRanker

from Db.milvus_db import MilvusService
from Db.sqlite_db import cSingleSqlite
from Config.embedding_config import get_embeddings
from Config.milvus_config import is_milvus_enabled

# 创建线程安全的logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class SqlSchemaVectorAgent:
    """数据库模式向量代理 - 负责将数据库元数据向量化并存储到milvus向量库中，使用partition按sql_id隔离数据"""

    def __init__(self, sql_id=None):
        self.enabled = is_milvus_enabled()
        if self.enabled:
            self.milvus_service = MilvusService()
        else:
            self.milvus_service = None
            logger.info("Milvus已禁用（MILVUS_FLAG=False），跳过初始化")
        self.embedding_model = get_embeddings()
        self.sql_id = sql_id

        # 所有数据存储在同一个默认集合中，通过partition隔离不同sql_id的数据
        # self.graph_nodes_collection_name = "sql_schema_default"
        self.graph_nodes_collection_name = "sql_graph_nodes_default"

    def get_or_create_graph_nodes_collection(self):
        """获取或创建图节点集合"""
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过获取或创建集合操作")
            return None
            
        # 检查集合是否存在
        if not self.milvus_service.has_collection(self.graph_nodes_collection_name):
            # 创建集合
            dim = len(self.embedding_model.embed_query("test"))
            schema = self.get_graph_nodes_schema(dim)
            index_params = self.get_index_params()
            self.milvus_service.create_collection(self.graph_nodes_collection_name, schema, index_params)
            logger.info(f"创建了新的图节点集合: {self.graph_nodes_collection_name}")

        collection = self.milvus_service.get_collection(self.graph_nodes_collection_name)
        return collection

    def ensure_graph_nodes_partition_exists(self, sql_id: str) -> bool:
        """确保图节点集合中指定sql_id的partition存在"""
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过确保分区操作")
            return False
            
        try:
            collection = self.get_or_create_graph_nodes_collection()
            if collection is None:
                return False
            if not self.milvus_service.has_partition(self.graph_nodes_collection_name, sql_id):
                self.milvus_service.create_partition(self.graph_nodes_collection_name, sql_id)
                logger.info(f"创建了新的图节点partition: {sql_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"创建图节点partition失败 (sql_id: {sql_id}): {e}")
            return False

    def get_index_params(self):
        """获取索引参数"""
        index_params = {
            "index_type": "FLAT",
            "metric_type": "COSINE",
            "params": {}
        }
        return index_params

    def _extract_schema_metadata(self, sql_id: str, permission_level="public") -> List[List[Any]]:
        """从数据库提取所有模式的元数据 - 表格双向量模式"""

        batch_data = []

                # 获取数据库的所有表
        tables = cSingleSqlite.query_table_sql_by_sql_id(sql_id)

        for table in tables:
            table_id = table["table_id"]
            table_name = table["table_name"]
            table_description = table.get("table_description", "")

            col_comments_str = ""
                    # 获取表的列信息
            columns = cSingleSqlite.query_col_sql_by_table_id(table_id)
            for column in columns:
                col_info = column.get("col_info", {})
                comment = col_info.get("comment", "")
                if comment.strip():  # 只添加非空注释
                    col_comments_str = col_comments_str + comment + " "

            # 只为有内容的表格创建向量记录
            if table_description.strip() or col_comments_str.strip():
                # 生成向量
                table_description_embedding = self.embedding_model.embed_query(table_description)
                col_comments_str_embedding = self.embedding_model.embed_query(col_comments_str)

                # 添加到批量数据
                batch_data.append([
                    sql_id,
                    table_name,
                    table_description,
                    col_comments_str,
                    table_description_embedding,
                    col_comments_str_embedding,
                    permission_level
                ])

        logger.info(f"提取到 {len(batch_data)} 个表格的元数据记录")
        return batch_data
    
    def get_graph_nodes_schema(self, dim):
        """获取图节点Milvus集合的schema定义"""
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),  # 主键索引
            FieldSchema(name="sql_id", dtype=DataType.VARCHAR, max_length=128),  # 数据库ID
            FieldSchema(name="node_id", dtype=DataType.VARCHAR, max_length=256),  # 节点ID
            FieldSchema(name="node_type", dtype=DataType.VARCHAR, max_length=64),  # 节点类型 (entity/attribute/unique_identifier/foreign_key)
            FieldSchema(name="node_name", dtype=DataType.VARCHAR, max_length=256),  # 节点名称
            FieldSchema(name="node_description", dtype=DataType.VARCHAR, max_length=65535),  # 节点描述
            FieldSchema(name="col_name", dtype=DataType.VARCHAR, max_length=256),  # 列名（如果适用）
            FieldSchema(name="table_name", dtype=DataType.VARCHAR, max_length=256),  # 表名
            FieldSchema(name="table_id", dtype=DataType.VARCHAR, max_length=128),  # 表ID
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),  # 完整内容（用于显示）
            FieldSchema(name="node_name_embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),  # 节点名称向量
            FieldSchema(name="node_description_embedding", dtype=DataType.FLOAT_VECTOR, dim=dim)  # 节点描述向量
        ]
        schema = CollectionSchema(fields=fields, description="SQL Graph Nodes Vector Collection")
        return schema

    def clear_store(self, sql_id: str = None) -> Dict[str, Any]:
        """清空向量库（按sql_id删除partition）"""
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过清空向量库操作")
            return {"success": False, "message": "Milvus已禁用"}
            
        if not sql_id:
            return {
                "success": False,
                "message": "必须指定sql_id"
            }

        try:
            if not self.milvus_service.has_collection(self.graph_nodes_collection_name):
                return {
                    "success": False,
                    "message": f"集合不存在: {self.graph_nodes_collection_name}"
                }

            if not self.milvus_service.has_partition(self.graph_nodes_collection_name, sql_id):
                return {
                    "success": False,
                    "message": f"partition不存在: {sql_id}"
                }

            # 删除partition中的所有数据
            self.milvus_service.drop_partition(self.graph_nodes_collection_name, sql_id)
            logger.info(f"成功删除partition: {sql_id}")

            return {
                "success": True,
                "message": f"成功清空partition: {sql_id}",
                "sql_id": sql_id
            }

        except Exception as e:
            logger.error(f"清空partition失败 (sql_id: {sql_id}): {e}")
            return {
                "success": False,
                "message": f"清空失败: {str(e)}",
                "sql_id": sql_id
            }

    def get_stats(self) -> Dict[str, Any]:
        """获取所有向量库的统计信息"""
        return self.list_all_partitions()

    def get_vector_store_stats_by_sql_id(self, sql_id: str) -> Dict[str, Any]:
        """获取指定sql_id的向量库统计信息 - 按partition统计"""
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过获取统计信息操作")
            return {"success": False, "message": "Milvus已禁用"}
            
        try:
            if not self.milvus_service.has_collection(self.graph_nodes_collection_name):
                return {
                    "success": False,
                    "message": f"集合不存在: {self.graph_nodes_collection_name}",
                    "sql_id": sql_id
                }

            if not self.milvus_service.has_partition(self.graph_nodes_collection_name, sql_id):
                return {
                    "success": False,
                    "message": f"partition不存在: {sql_id}",
                    "sql_id": sql_id
                }

            # 获取集合
            collection = self.milvus_service.get_collection(self.graph_nodes_collection_name)

            # 获取集合总实体数
            total_count = collection.num_entities
            logger.info(f"partition {sql_id} 中共有 {total_count} 个实体")

            # 查询partition中的实体数量和详细信息
            try:
                partition_entities = collection.query(
                    expr=f"sql_id == '{sql_id}'",
                    output_fields=["table_name", "table_description", "col_comments"]
                )
                partition_count = len(partition_entities)

                # 统计有描述和列信息的表格数量
                tables_with_description = sum(1 for entity in partition_entities
                                            if entity.get("table_description", "").strip())
                tables_with_columns = sum(1 for entity in partition_entities
                                        if entity.get("col_comments", "").strip())

            except Exception as e:
                logger.warning(f"查询partition统计信息失败: {e}")
                partition_count = 0
                tables_with_description = 0
                tables_with_columns = 0

            return {
                "success": True,
                "sql_id": sql_id,
                "collection_name": self.graph_nodes_collection_name,
                "partition_name": sql_id,
                "collection_total_entities": total_count,
                "partition_entities": partition_count,
                "tables_with_description": tables_with_description,
                "tables_with_columns": tables_with_columns,
                "vector_mode": "dual_vector",
                "embedding_dims": len(self.embedding_model.embed_query("test"))
            }

        except Exception as e:
            logger.error(f"获取统计信息失败 (sql_id: {sql_id}): {e}")
            return {
                "success": False,
                "message": f"获取统计失败: {str(e)}",
                "sql_id": sql_id
            }

    def delete_vector_store_by_sql_id(self, sql_id: str) -> Dict[str, Any]:
        """删除指定sql_id的向量库（删除partition）"""
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过删除向量库操作")
            return {"success": False, "message": "Milvus已禁用"}
            
        try:
            if not self.milvus_service.has_collection(self.graph_nodes_collection_name):
                return {
                    "success": False,
                    "message": f"集合不存在: {self.graph_nodes_collection_name}",
                    "sql_id": sql_id
                }

            if not self.milvus_service.has_partition(self.graph_nodes_collection_name, sql_id):
                return {
                    "success": False,
                    "message": f"partition不存在: {sql_id}",
                    "sql_id": sql_id
                }

            # 删除partition
            self.milvus_service.drop_partition(self.graph_nodes_collection_name, sql_id)

            logger.info(f"成功删除partition (sql_id: {sql_id})")
            return {
                "success": True,
                "message": f"partition删除成功 (sql_id: {sql_id})",
                "sql_id": sql_id,
                "collection_name": self.graph_nodes_collection_name
            }

        except Exception as e:
            logger.error(f"删除partition失败 (sql_id: {sql_id}): {e}")
            return {
                "success": False,
                "message": f"删除失败: {str(e)}",
                "sql_id": sql_id
            }

    def list_available_vector_stores(self) -> Dict[str, Any]:
        """列出所有可用的向量库partition"""
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过列出向量库操作")
            return {"success": True, "total_partitions": 0, "partitions": []}
            
        try:
            if not self.milvus_service.has_collection(self.graph_nodes_collection_name):
                return {
                    "success": True,
                    "total_partitions": 0,
                    "partitions": []
                }

            # 获取集合的所有partition
            collection = self.milvus_service.get_collection(self.graph_nodes_collection_name)

            # 尝试获取partition列表（如果Milvus支持的话）
            partitions = []
            try:
                # 这里需要根据Milvus的API来获取partition信息
                # 由于不同的Milvus版本API可能不同，我们通过查询来检测partition
                all_sql_ids = set()

                # 通过分页查询获取所有不同的sql_id
                page_size = 1000
                offset = 0
                max_iterations = 10  # 防止无限循环

                for _ in range(max_iterations):
                    try:
                        batch = collection.query(
                            expr="",  # 查询所有
                            output_fields=["sql_id"],
                            limit=page_size,
                            offset=offset
                        )

                        if not batch:
                            break

                        for entity in batch:
                            sql_id = entity.get("sql_id")
                            if sql_id:
                                all_sql_ids.add(sql_id)

                        offset += page_size

                        if len(batch) < page_size:
                            break

                    except Exception as e:
                        logger.warning(f"查询partition时出错: {e}")
                        break

                # 为每个sql_id创建partition信息
                for sql_id in all_sql_ids:
                    try:
                        stats = self.get_vector_store_stats_by_sql_id(sql_id)
                        if stats["success"]:
                            partitions.append({
                                "sql_id": sql_id,
                                "collection_name": self.graph_nodes_collection_name,
                                "partition_name": sql_id,
                                "entity_count": stats.get("partition_entities", 0),
                                "tables_with_description": stats.get("tables_with_description", 0),
                                "tables_with_columns": stats.get("tables_with_columns", 0)
                            })
                    except Exception as e:
                        logger.warning(f"获取partition {sql_id} 统计信息失败: {e}")
                        partitions.append({
                            "sql_id": sql_id,
                            "collection_name": self.graph_nodes_collection_name,
                            "partition_name": sql_id,
                            "entity_count": 0,
                            "error": str(e)
                        })

            except Exception as e:
                logger.warning(f"获取partition列表失败: {e}")
                # 如果无法获取partition列表，至少返回集合信息
                partitions = [{
                    "sql_id": "unknown",
                    "collection_name": self.graph_nodes_collection_name,
                    "partition_name": "unknown",
                    "entity_count": collection.num_entities,
                    "error": f"无法获取partition详情: {str(e)}"
                }]

            return {
                "success": True,
                "collection_name": self.graph_nodes_collection_name,
                "total_partitions": len(partitions),
                "partitions": partitions
            }

        except Exception as e:
            logger.error(f"列出向量库失败: {e}")
            return {
                "success": False,
                "message": f"列出失败: {str(e)}"
            }

    def create_partition(self, sql_id: str) -> Dict[str, Any]:
        """创建指定sql_id的partition"""
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过创建分区操作")
            return {"success": False, "message": "Milvus已禁用"}
            
        try:
            if not self.milvus_service.has_collection(self.graph_nodes_collection_name):
                return {
                    "success": False,
                    "message": f"集合不存在: {self.graph_nodes_collection_name}"
                }

            if self.milvus_service.has_partition(self.graph_nodes_collection_name, sql_id):
                return {
                    "success": True,
                    "message": f"partition已存在: {sql_id}",
                    "existed": True
                }

            self.milvus_service.create_partition(self.graph_nodes_collection_name, sql_id)
            logger.info(f"成功创建partition: {sql_id}")

            return {
                "success": True,
                "message": f"partition创建成功: {sql_id}",
                "sql_id": sql_id,
                "existed": False
            }

        except Exception as e:
            logger.error(f"创建partition失败 (sql_id: {sql_id}): {e}")
            return {
                "success": False,
                "message": f"创建失败: {str(e)}",
                "sql_id": sql_id
            }

    def check_partition_exists(self, sql_id: str) -> bool:
        """检查指定sql_id的partition是否存在"""
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过检查分区操作")
            return False
            
        try:
            return (self.milvus_service.has_collection(self.graph_nodes_collection_name) and
                   self.milvus_service.has_partition(self.graph_nodes_collection_name, sql_id))
        except:
            return False

    def get_partition_stats(self, sql_id: str) -> Dict[str, Any]:
        """获取partition的详细信息"""
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过获取分区统计操作")
            return {"success": False, "message": "Milvus已禁用"}
            
        try:
            if not self.check_partition_exists(sql_id):
                return {
                    "success": False,
                    "message": f"partition不存在: {sql_id}",
                    "sql_id": sql_id
                }

            collection = self.get_or_create_collection()

            # 查询partition中的所有实体
            entities = collection.query(
                expr=f"sql_id == '{sql_id}'",
                output_fields=["table_name", "table_description", "col_comments"]
            )

            # 统计信息
            total_tables = len(entities)
            tables_with_description = sum(1 for e in entities if e.get("table_description", "").strip())
            tables_with_columns = sum(1 for e in entities if e.get("col_comments", "").strip())

            return {
                "success": True,
                "sql_id": sql_id,
                "collection_name": self.graph_nodes_collection_name,
                "partition_name": sql_id,
                "total_tables": total_tables,
                "tables_with_description": tables_with_description,
                "tables_with_columns": tables_with_columns,
                "table_details": entities[:10] if len(entities) <= 10 else entities[:10] + [{"note": f"还有{len(entities)-10}个表格"}]
            }

        except Exception as e:
            logger.error(f"获取partition统计失败 (sql_id: {sql_id}): {e}")
            return {
                "success": False,
                "message": f"获取统计失败: {str(e)}",
                "sql_id": sql_id
            }

    def list_all_partitions(self) -> Dict[str, Any]:
        """列出所有partition的详细信息"""
        try:
            stores_info = self.list_available_vector_stores()
            if not stores_info.get("success"):
                return stores_info

            detailed_partitions = []
            for partition in stores_info.get("partitions", []):
                sql_id = partition.get("sql_id")
                if sql_id and sql_id != "unknown":
                    details = self.get_partition_stats(sql_id)
                    if details.get("success"):
                        detailed_partitions.append(details)
                    else:
                        detailed_partitions.append({
                            "sql_id": sql_id,
                            "error": details.get("message", "获取详情失败")
                        })

            return {
                "success": True,
                "collection_name": self.graph_nodes_collection_name,
                "total_partitions": len(detailed_partitions),
                "partitions": detailed_partitions
            }

        except Exception as e:
            logger.error(f"列出所有partition失败: {e}")
            return {
                "success": False,
                "message": f"列出失败: {str(e)}"
            }

    def rebuild_vector_store_by_sql_id(self, sql_id: str, force: bool = False) -> Dict[str, Any]:
        """重建指定sql_id的向量库"""
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过重建向量库操作")
            return {"success": False, "message": "Milvus已禁用"}
            
        try:
            if force:
                # 先删除现有partition
                delete_result = self.delete_vector_store_by_sql_id(sql_id)
                if not delete_result["success"]:
                    logger.warning(f"删除现有partition失败，继续重建: {delete_result['message']}")

            # 重新构建向量库
            build_result = self.build_or_update_store_by_sql_id(sql_id)

            if build_result["success"]:
                return {
                    "success": True,
                    "message": f"向量库重建成功 (sql_id: {sql_id})",
                    "sql_id": sql_id,
                    "details": build_result
                }
            else:
                return build_result

        except Exception as e:
            logger.error(f"重建向量库失败 (sql_id: {sql_id}): {e}")
            return {
                "success": False,
                "message": f"重建失败: {str(e)}",
                "sql_id": sql_id
            }

    def save_graph_nodes_to_vector_store(self, nodes_data: List[Dict[str, Any]], sql_id: str) -> Dict[str, Any]:
        """
        将图数据库中的节点保存到Milvus向量库

        Args:
            nodes_data: 节点数据列表，每个节点包含：
                {
                    "node_type": "entity|attribute|unique_identifier|metric|foreign_key",
                    "node_id": "...",
                    "entity_name|attribute_name|identifier_name|metric_name|fk_name": "...",
                    "entity_description|attribute_description|identifier_description|metric_description|description": "...",
                    "col_name": "...",  # 对于attribute、identifier和metric
                    "table_name": "...",
                    "table_id": "...",
                    "sql_id": "..."
                }
            sql_id: SQL数据库ID

        Returns:
            Dict[str, Any]: 保存结果
        """
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过保存图节点操作")
            return {"success": False, "message": "Milvus已禁用"}
            
        try:
            logger.info(f"开始保存图节点到向量库 (sql_id: {sql_id}, nodes: {len(nodes_data)})")

            if not nodes_data:
                return {"success": False, "message": "没有节点数据需要保存"}

            # 确保partition存在
            self.ensure_graph_nodes_partition_exists(sql_id)

            # 准备批量插入数据
            batch_data = []

            for node in nodes_data:
                node_type = node.get("node_type", "")
                node_id = node.get("node_id", "")

                # 根据节点类型提取名称和描述
                name_field = ""
                description_field = ""

                if node_type == "entity":
                    name_field = node.get("entity_name", "")
                    description_field = node.get("entity_description", "")
                elif node_type == "attribute":
                    name_field = node.get("attribute_name", "")
                    description_field = node.get("attribute_description", "")
                elif node_type == "unique_identifier":
                    name_field = node.get("identifier_name", "")
                    description_field = node.get("identifier_description", "")
                elif node_type == "metric":
                    name_field = node.get("metric_name", "")
                    description_field = node.get("metric_description", "")
                elif node_type == "foreign_key":
                    name_field = node.get("fk_name", "")
                    description_field = node.get("description", "")

                # 获取共同字段
                col_name = node.get("col_name", "")
                table_name = node.get("table_name", "")
                table_id = node.get("table_id", "")

                # 如果名称或描述为空，跳过
                if not name_field and not description_field:
                    continue

                # 生成双向量（节点名称和描述）
                if not name_field and not description_field:
                    continue

                try:
                    name_embedding = self.embedding_model.embed_query(name_field) if name_field else self.embedding_model.embed_query("")
                    description_embedding = self.embedding_model.embed_query(description_field) if description_field else self.embedding_model.embed_query("")
                except Exception as e:
                    logger.warning(f"生成节点向量失败 (node_id: {node_id}): {e}")
                    continue

                # 准备数据行
                batch_data.append([
                    sql_id,  # sql_id
                    node_id,  # node_id
                    node_type,  # node_type
                    name_field,  # node_name
                    description_field,  # node_description
                    col_name,  # col_name
                    table_name,  # table_name
                    table_id,  # table_id
                    f"{name_field} {description_field}".strip(),  # content (用于显示，名称+描述)
                    name_embedding,  # node_name_embedding
                    description_embedding  # node_description_embedding
                ])

            if not batch_data:
                return {"success": False, "message": "没有有效的节点数据"}

            # 分批插入，每批50条
            batch_size = 50
            total_batches = (len(batch_data) + batch_size - 1) // batch_size  # 向上取整
            inserted_count = 0

            logger.info(f"准备分批插入 {len(batch_data)} 条数据，共 {total_batches} 批，每批 {batch_size} 条")

            for batch_idx in range(total_batches):
                start_idx = batch_idx * batch_size
                end_idx = min(start_idx + batch_size, len(batch_data))
                current_batch = batch_data[start_idx:end_idx]

                try:
                    # 准备当前批次的数据
                    sql_ids = [row[0] for row in current_batch]
                    node_ids = [row[1] for row in current_batch]
                    node_types = [row[2] for row in current_batch]
                    node_names = [row[3] for row in current_batch]
                    node_descriptions = [row[4] for row in current_batch]
                    col_names = [row[5] for row in current_batch]
                    table_names = [row[6] for row in current_batch]
                    table_ids = [row[7] for row in current_batch]
                    contents = [row[8] for row in current_batch]
                    name_embeddings = [row[9] for row in current_batch]
                    description_embeddings = [row[10] for row in current_batch]

                    # 插入当前批次数据到指定分区
                    entities = [
                        sql_ids,  # sql_id
                        node_ids,  # node_id
                        node_types,  # node_type
                        node_names,  # node_name
                        node_descriptions,  # node_description
                        col_names,  # col_name
                        table_names,  # table_name
                        table_ids,  # table_id
                        contents,  # content
                        name_embeddings,  # node_name_embedding
                        description_embeddings  # node_description_embedding
                    ]

                    # 插入当前批次数据
                    self.milvus_service.insert(self.graph_nodes_collection_name, entities, sql_id)
                    inserted_count += len(current_batch)
                    
                    if (batch_idx + 1) % 10 == 0 or batch_idx == total_batches - 1:
                        logger.info(f"已插入 {inserted_count}/{len(batch_data)} 条数据 (批次 {batch_idx + 1}/{total_batches})")

                except Exception as e:
                    logger.error(f"插入第 {batch_idx + 1} 批数据失败: {e}")
                    # 继续插入下一批，不中断整个流程
                    continue

            # 刷新集合以确保数据可见
            collection = self.get_or_create_graph_nodes_collection()
            collection.flush()

            logger.info(f"✅ 成功保存 {inserted_count}/{len(batch_data)} 个图节点到向量库 (sql_id: {sql_id})")

            return {
                "success": True,
                "message": f"成功保存 {inserted_count} 个图节点",
                "saved_count": inserted_count,
                "total_count": len(batch_data)
            }

        except Exception as e:
            logger.error(f"保存图节点到向量库失败 (sql_id: {sql_id}): {e}")
            return {
                "success": False,
                "message": f"保存失败: {str(e)}"
            }

    def search_graph_nodes(self, query: str, sql_id: str = None, limit: int = 20, node_type: str = None, 
                          name_query: str = None, description_query: str = None) -> Dict[str, Any]:
        """
        搜索图节点 - 双向量搜索（节点名称+节点描述）
        
        如果提供了 name_query 和 description_query，则：
        - name_query 用于搜索 node_name_embedding
        - description_query 用于搜索 node_description_embedding
        否则，使用 query 同时搜索名称和描述

        Args:
            query: 搜索查询（默认同时用于名称和描述搜索）
            sql_id: 数据库ID，如果为None则搜索所有数据库
            limit: 返回结果数量限制
            node_type: 节点类型过滤（entity/attribute/unique_identifier/metric/foreign_key），如果为None则不过滤
            name_query: 用于搜索节点名称的查询（如果提供，则优先使用此查询搜索 node_name_embedding）
            description_query: 用于搜索节点描述的查询（如果提供，则优先使用此查询搜索 node_description_embedding）

        Returns:
            Dict[str, Any]: 搜索结果
        """
        try:
            logger.info(f"开始搜索图节点 (query: {query}, sql_id: {sql_id}, limit: {limit}, node_type: {node_type}, name_query: {name_query}, description_query: {description_query})")

            if not self.milvus_service.has_collection(self.graph_nodes_collection_name):
                return {
                    "success": False,
                    "message": f"图节点集合不存在: {self.graph_nodes_collection_name}"
                }

            # 确定用于名称和描述搜索的查询
            name_search_query = name_query if name_query else query
            desc_search_query = description_query if description_query else query

            # 生成查询向量
            try:
                name_embedding = self.embedding_model.embed_query(name_search_query)
                desc_embedding = self.embedding_model.embed_query(desc_search_query)
            except Exception as e:
                logger.error(f"生成查询向量失败: {e}")
                return {
                    "success": False,
                    "message": f"生成查询向量失败: {str(e)}"
                }

            # 构建过滤条件
            filter_conditions = []
            if sql_id:
                filter_conditions.append(f"sql_id == '{sql_id}'")
            if node_type:
                filter_conditions.append(f"node_type == '{node_type}'")
            
            filter_expr = " && ".join(filter_conditions) if filter_conditions else None

            # 构建搜索请求
            search_params = {"metric_type": "COSINE", "params": {}}
            reqs = [
                AnnSearchRequest(
                    [name_embedding],  # 使用 name_query 的向量搜索 node_name_embedding
                    "node_name_embedding",
                    search_params,
                    limit=limit,
                    expr=filter_expr
                ),
                AnnSearchRequest(
                    [desc_embedding],  # 使用 description_query 的向量搜索 node_description_embedding
                    "node_description_embedding",
                    search_params,
                    limit=limit,
                    expr=filter_expr
                )
            ]

            # 执行混合搜索
            collection = self.get_or_create_graph_nodes_collection()

            # 使用 WeightedRanker 进行混合搜索
            ranker = WeightedRanker(0.4, 0.6)  # 名称权重0.4，描述权重0.6

            collection.load()
            search_results = collection.hybrid_search(
                reqs=reqs,
                rerank=ranker,
                limit=limit,
                output_fields=["sql_id", "node_id", "node_type", "node_name", "node_description", "col_name", "table_name", "table_id", "content"]
            )

            # 格式化结果
            results = []
            for hits in search_results:
                for hit in hits:
                    entity = hit.entity
                    results.append({
                        "sql_id": entity.get("sql_id", ""),
                        "node_id": entity.get("node_id", ""),
                        "node_type": entity.get("node_type", ""),
                        "node_name": entity.get("node_name", ""),
                        "node_description": entity.get("node_description", ""),
                        "col_name": entity.get("col_name", ""),
                        "table_name": entity.get("table_name", ""),
                        "table_id": entity.get("table_id", ""),
                        "content": entity.get("content", ""),
                        "score": hit.score
                    })

            # 按照相似度（score）降序排序
            results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            
            # 限制返回数量
            results = results[:limit]

            logger.info(f"图节点搜索完成，返回 {len(results)} 个结果（已按相似度排序）")
            print("图节点搜索完成 results:", results)
            return {
                "success": True,
                "query": query,
                "sql_id": sql_id,
                "results": results,
                "total_count": len(results)
            }

        except Exception as e:
            logger.error(f"搜索图节点失败: {e}")
            return {
                "success": False,
                "message": f"搜索失败: {str(e)}",
                "query": query,
                "sql_id": sql_id
            }


# # 测试函数（仅开发环境使用）
# if __name__ == "__main__":
#     # 测试基本功能
#     agent = SqlSchemaVectorAgent("test_sql_id")

#     # 测试schema生成
#     try:
#         dim = 768  # 假设向量维度
#         schema = agent.get_schema(dim)
#         print(f"✅ Schema生成成功，包含 {len(schema.fields)} 个字段")
#     except Exception as e:
#         print(f"❌ Schema生成失败: {e}")

#     print("基本功能测试完成")
