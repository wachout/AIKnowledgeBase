# -*- coding:utf-8 -*-

import os
import json
# import xml.etree.ElementTree as ET

# from neo4j import GraphDatabase
import traceback
from typing import Dict, Any, List, Optional

from Db.neo4j_db import cSingleNeo4j
from Db.sqlite_db import cSingleSqlite
from Graphrag import read_graph
from Config.neo4j_config import is_neo4j_enabled

# from Emb.xinference_embedding import cSingleEmb
# from sklearn.metrics.pairwise import cosine_similarity

from Sql.schema_vector import SqlSchemaVectorAgent


# from Control.control_milvus import CControl as MilvusControl

# from Utils import utils

BATCH_SIZE_NODES = 500
BATCH_SIZE_EDGES = 100

class CControl():
    
    def __init__(self):
        # self.milvus_control = MilvusControl()
        self.vector_agent = SqlSchemaVectorAgent()
    
    def delete_all_graph(self):
        if not is_neo4j_enabled():
            return False
        return cSingleNeo4j.delete_all()
    
    # def delete_all_grap_user_id(self, user_id):
        
    
    def delete_node(self, chunk):
        if not is_neo4j_enabled():
            return False
            
        #MATCH (n {source_id: 'chunk-69395ec4b2edd1cf012bf53c44a72208'})-[r]-() DELETE n, r
        # query = """MATCH (n {source_id: '""" + chunk + """'})-[r]-() DELETE n, r;"""
        
        query = """MATCH (n)-[r]-() 
WHERE n.source_id CONTAINS '""" + chunk + """' 
DELETE n, r;"""
        cSingleNeo4j.delete_node(query)
        
        query = """MATCH (n) WHERE n.source_id CONTAINS '""" + chunk + """'  DELETE n"""
        cSingleNeo4j.delete_node(query)
        
        return True
    
    def execute_query(self, param):
        """
        Cypher查询语句
        """
        if not is_neo4j_enabled():
            return []
            
        cypher_query = param.get("cypher_query", "")
        return cSingleNeo4j.query(cypher_query)
    
    
    def delete_sql_graph_data(self, sql_id):
        """
        删除 SQL Schema 相关的 Neo4j 图数据
        
        删除规则：
        - 删除所有 sql_id 属性等于指定 sql_id 的节点及其关联的关系
        
        Args:
            sql_id: SQL 数据库 ID
            
        Returns:
            bool: 删除是否成功
        """
        if not is_neo4j_enabled():
            print(f"⚠️ Neo4j已禁用，跳过删除 SQL Schema 图数据 (sql_id: {sql_id})")
            return False
            
        try:
            print(f"🗑️ 开始删除 SQL Schema 图数据 (sql_id: {sql_id})...")
            
            # 构建 Cypher 查询：删除所有 sql_id 匹配的节点及其关系
            # 先删除关系，再删除节点
            # 删除所有与 sql_id 匹配的节点相关的关系（包括双向关系）
            delete_relationships_query = f"""
            MATCH (n1)-[r]-(n2)
            WHERE n1.sql_id = '{sql_id}' OR n2.sql_id = '{sql_id}'
            DELETE r
            """
            
            # 删除所有 sql_id 匹配的节点
            delete_nodes_query = f"""
            MATCH (n)
            WHERE n.sql_id = '{sql_id}'
            DELETE n
            """
            
            try:
                # 删除关系（使用 delete_node 方法执行 Cypher 查询）
                cSingleNeo4j.delete_node(delete_relationships_query)
                print(f"  ✅ 删除关系完成")
                
                # 删除节点
                cSingleNeo4j.delete_node(delete_nodes_query)
                print(f"  ✅ 删除节点完成")
                
                print(f"✅ SQL Schema 图数据删除成功 (sql_id: {sql_id})")
                return True
                
            except Exception as e:
                print(f"❌ 执行删除查询时出错: {e}")
                
                traceback.print_exc()
                return False
                    
        except Exception as e:
            print(f"❌ 删除 SQL Schema 图数据失败: {e}")
            traceback.print_exc()
            return False
    
    def save_schema_analysis_graph_data(self, schema_analysis_result: Dict[str, Any], 
                                       sql_id: str, permission_level: str) -> bool:
        """
        将 Schema 分析结果保存到 Neo4j 图数据库
        
        规则：
        1. 创建节点：
           - attributes 中每一个 attribute 都是一个节点（节点类型：attribute）
           - unique_identifiers 中每一个 unique_identifier 都是一个节点（节点类型：unique_identifier）
           - 每一个 entity 也是一个节点（节点类型：entity）
           - 每一个外键也为一个节点（节点类型：foreign_key）
           - 每个节点都有 table_id 和 table_name
        
        2. 创建关系：
           - entity 与 attribute 是属性关系 (HAS_ATTRIBUTE)
           - entity 与 unique_identifiers 建立唯一标识关系 (HAS_IDENTIFIER)
           - entity 与 foreign_keys，建立外键关系 (HAS_FOREIGN_KEY)
           - attribute 对应的表格的列，如果名字相同或者列的描述相似相同，那建立相似关系 (SIMILAR_TO)
        
        Args:
            schema_analysis_result: Schema 分析结果
                {
                    "success": True/False,
                    "sql_id": "...",
                    "tables_analysis": [
                        {
                            "table_name": "...",
                            "table_id": "...",
                            "analysis_result": {
                                "entity": {...},
                                "attributes": [...],  # 每个包含 col_name
                                "unique_identifiers": [...],  # 每个包含 col_name
                                "foreign_keys": [...],  # 每个包含 from_col, to_col
                                ...
                            }
                        }
                    ]
                }
            sql_id: SQL 数据库 ID
            permission_level: 权限级别
        """
        try:
            print(f"📊 开始保存 Schema 分析结果到 Neo4j (sql_id: {sql_id})...")
            
            if not schema_analysis_result.get("success"):
                print(f"⚠️ Schema 分析结果不成功，跳过图数据保存")
                return False
            
            tables_analysis = schema_analysis_result.get("tables_analysis", [])
            if not tables_analysis:
                print(f"⚠️ 没有表分析结果，跳过图数据保存")
                return False
            
            # 节点映射：{node_id: neo4j_node}
            entity_nodes = {}  # {entity_id: neo4j_node}
            attribute_nodes = {}  # {attribute_id: neo4j_node}
            identifier_nodes = {}  # {identifier_id: neo4j_node}
            metric_nodes = {}  # {metric_id: neo4j_node}
            # foreign_key_nodes = {}  # {foreign_key_id: neo4j_node}
            
            # 节点ID到信息的映射（用于建立相似关系）
            entity_info_map = {}  # {entity_id: {"name": ..., "col_name": ..., "col_comment": ..., "table_id": ..., "table_name": ...}}
            attribute_info_map = {}  # {attribute_id: {"name": ..., "col_name": ..., "col_comment": ..., "table_id": ..., "table_name": ...}}
            identifier_info_map = {}  # {identifier_id: {"name": ..., "col_name": ..., "col_comment": ..., "description": ..., "table_id": ..., "table_name": ...}}
            metric_info_map = {}  # {metric_id: {"name": ..., "col_name": ..., "col_comment": ..., "description": ..., "table_id": ..., "table_name": ...}}
            
            # 收集所有表的列信息（用于获取列描述）
            table_columns_map = {}  # {table_id: [{"col_name": ..., "col_comment": ...}, ...]}
            for table_analysis in tables_analysis:
                table_id = table_analysis.get("table_id", "")
                if table_id:
                    columns = cSingleSqlite.query_col_sql_by_table_id(table_id)
                    col_info_list = []
                    for col in columns or []:
                        col_info = col.get("col_info", {})
                        if isinstance(col_info, str):
                            try:
                                col_info = json.loads(col_info)
                            except:
                                col_info = {}
                        elif col_info is None:
                            col_info = {}
                        col_comment = col_info.get("comment", "") if isinstance(col_info, dict) else ""
                        col_info_list.append({
                            "col_name": col.get("col_name", ""),
                            "col_comment": col_comment
                        })
                    table_columns_map[table_id] = col_info_list
            
            # 第一步：创建所有节点
            for table_analysis in tables_analysis:
                table_name = table_analysis.get("table_name", "")
                table_id = table_analysis.get("table_id", "")
                analysis_result = table_analysis.get("analysis_result", {})
                
                if not analysis_result:
                    continue
                
                # 创建 Entity 节点
                entity = analysis_result.get("entity", {})
                entity_name = entity.get("entity_name", table_name)
                entity_description = entity.get("entity_description", "")
                
                if entity_name:
                    entity_id = f"{table_id}_{entity_name}"
                    entity_node_properties = {
                        "node_id": entity_id,
                        "node_type": "entity",
                        "entity_name": entity_name,
                        "entity_description": entity_description,
                        "table_id": table_id,
                        "table_name": table_name,
                        "sql_id": sql_id,
                        "permission_level": permission_level
                    }
                    
                    try:
                        entity_node = cSingleNeo4j.create_node("Entity", **entity_node_properties)
                        entity_nodes[entity_id] = entity_node
                        entity_info_map[entity_id] = {
                            "name": entity_name,
                            "col_name": "",  # entity 没有对应的列
                            "col_comment": "",  # entity 没有对应的列描述
                            "entity_description": entity_description,  # entity 的描述
                            "table_id": table_id,
                            "table_name": table_name
                        }
                        print(f"  ✅ 创建 Entity 节点: {entity_name} (table: {table_name})")
                    except Exception as e:
                        print(f"  ⚠️ 创建 Entity 节点失败: {entity_name} - {e}")
                
                # 创建 Attribute 节点
                attributes = analysis_result.get("attributes", [])
                for attr in attributes:
                    attr_name = attr.get("attr_name", "")
                    attr_col_name = attr.get("col_name", "")
                    attr_description = attr.get("attr_description", "")
                    
                    # 获取列描述
                    attr_col_comment = ""
                    if attr_col_name and table_id in table_columns_map:
                        for col_info in table_columns_map[table_id]:
                            if col_info.get("col_name") == attr_col_name:
                                attr_col_comment = col_info.get("col_comment", "")
                                break
                    
                    if attr_name and attr_col_name:  # 必须有列名
                        attribute_id = f"{table_id}_{attr_col_name}"
                        attribute_node_properties = {
                            "node_id": attribute_id,
                            "node_type": "attribute",
                            "attribute_name": attr_name,
                            "attribute_description": attr_description,
                            "col_name": attr_col_name,
                            "col_comment": attr_col_comment,
                            "table_id": table_id,
                            "table_name": table_name,
                            "sql_id": sql_id,
                            "permission_level": permission_level
                        }
                        
                        try:
                            # 如果节点已存在，跳过（避免重复）
                            if attribute_id not in attribute_nodes:
                                attribute_node = cSingleNeo4j.create_node("Attribute", **attribute_node_properties)
                                attribute_nodes[attribute_id] = attribute_node
                                attribute_info_map[attribute_id] = {
                                    "name": attr_name,
                                    "col_name": attr_col_name,
                                    "col_comment": attr_col_comment,
                                    "table_id": table_id,
                                    "table_name": table_name
                                }
                                print(f"    ✅ 创建 Attribute 节点: {attr_name} (col: {attr_col_name}, table: {table_name})")
                        except Exception as e:
                            print(f"    ⚠️ 创建 Attribute 节点失败: {attr_name} - {e}")
                
                # 创建 Unique Identifier 节点
                unique_identifiers = analysis_result.get("unique_identifiers", [])
                for identifier in unique_identifiers:
                    identifier_name = identifier.get("identifier_name", "")
                    identifier_col_name = identifier.get("col_name", "")
                    identifier_type = identifier.get("identifier_type", "")
                    identifier_description = identifier.get("description", "")
                    
                    if identifier_name and identifier_col_name:  # 必须有列名
                        identifier_id = f"{table_id}_{identifier_col_name}"
                        
                        # 获取列描述
                        identifier_col_comment = ""
                        if identifier_col_name and table_id in table_columns_map:
                            for col_info in table_columns_map[table_id]:
                                if col_info.get("col_name") == identifier_col_name:
                                    identifier_col_comment = col_info.get("col_comment", "")
                                    break
                        
                        identifier_node_properties = {
                            "node_id": identifier_id,
                            "node_type": "unique_identifier",
                            "identifier_name": identifier_name,
                            "identifier_type": identifier_type,
                            "identifier_description": identifier_description,
                            "col_name": identifier_col_name,
                            "col_comment": identifier_col_comment,
                            "table_id": table_id,
                            "table_name": table_name,
                            "sql_id": sql_id,
                            "permission_level": permission_level
                        }
                        
                        try:
                            if identifier_id not in identifier_nodes:
                                identifier_node = cSingleNeo4j.create_node("UniqueIdentifier", **identifier_node_properties)
                                identifier_nodes[identifier_id] = identifier_node
                                identifier_info_map[identifier_id] = {
                                    "name": identifier_name,
                                    "col_name": identifier_col_name,
                                    "col_comment": identifier_col_comment,
                                    "description": identifier_description,
                                    "table_id": table_id,
                                    "table_name": table_name
                                }
                                print(f"    ✅ 创建 UniqueIdentifier 节点: {identifier_name} (col: {identifier_col_name}, table: {table_name})")
                        except Exception as e:
                            print(f"    ⚠️ 创建 UniqueIdentifier 节点失败: {identifier_name} - {e}")
                
                # 创建 Metric 节点
                metrics = analysis_result.get("metrics", [])
                for metric in metrics:
                    metric_name = metric.get("metric_name", "")
                    metric_col_name = metric.get("col_name", "")
                    metric_type = metric.get("metric_type", "")
                    metric_description = metric.get("metric_description", "")
                    
                    if metric_name and metric_col_name:  # 必须有列名
                        metric_id = f"{table_id}_{metric_col_name}"
                        
                        # 获取列描述
                        metric_col_comment = ""
                        if metric_col_name and table_id in table_columns_map:
                            for col_info in table_columns_map[table_id]:
                                if col_info.get("col_name") == metric_col_name:
                                    metric_col_comment = col_info.get("col_comment", "")
                                    break
                        
                        metric_node_properties = {
                            "node_id": metric_id,
                            "node_type": "metric",
                            "metric_name": metric_name,
                            "metric_type": metric_type,
                            "metric_description": metric_description,
                            "col_name": metric_col_name,
                            "col_comment": metric_col_comment,
                            "table_id": table_id,
                            "table_name": table_name,
                            "sql_id": sql_id,
                            "permission_level": permission_level
                        }
                        
                        try:
                            if metric_id not in metric_nodes:
                                metric_node = cSingleNeo4j.create_node("Metric", **metric_node_properties)
                                metric_nodes[metric_id] = metric_node
                                metric_info_map[metric_id] = {
                                    "name": metric_name,
                                    "col_name": metric_col_name,
                                    "col_comment": metric_col_comment,
                                    "description": metric_description,
                                    "table_id": table_id,
                                    "table_name": table_name
                                }
                                print(f"    ✅ 创建 Metric 节点: {metric_name} (col: {metric_col_name}, table: {table_name})")
                        except Exception as e:
                            print(f"    ⚠️ 创建 Metric 节点失败: {metric_name} - {e}")
                
                # 外键节点将在第二步创建关系时处理，这里先收集外键信息
                # 不在这里创建 ForeignKey 节点，而是在创建关系时检查 Attribute 节点是否存在
            
            print(f"✅ 节点创建完成:")
            print(f"   - Entity 节点: {len(entity_nodes)}")
            print(f"   - Attribute 节点: {len(attribute_nodes)}")
            print(f"   - UniqueIdentifier 节点: {len(identifier_nodes)}")
            print(f"   - Metric 节点: {len(metric_nodes)}")
            
            # 第二步：创建关系
            relationships_created = 0
            
            # 2.1 创建 Entity -> Attribute 关系 (HAS_ATTRIBUTE)
            for table_analysis in tables_analysis:
                table_id = table_analysis.get("table_id", "")
                analysis_result = table_analysis.get("analysis_result", {})
                
                entity = analysis_result.get("entity", {})
                entity_name = entity.get("entity_name", "")
                if not entity_name:
                    continue
                
                entity_id = f"{table_id}_{entity_name}"
                if entity_id not in entity_nodes:
                    continue
                
                entity_node = entity_nodes[entity_id]
                attributes = analysis_result.get("attributes", [])
                
                for attr in attributes:
                    attr_col_name = attr.get("col_name", "")
                    attr_name = attr.get("attr_name", "")
                    
                    if attr_col_name:
                        attribute_id = f"{table_id}_{attr_col_name}"
                    else:
                        attribute_id = f"{table_id}_{attr_name}"
                    
                    if attribute_id in attribute_nodes:
                        try:
                            attribute_node = attribute_nodes[attribute_id]
                            rel_properties = {
                                "sql_id": sql_id,
                                "permission_level": permission_level,
                                "table_id": table_id,
                                "table_name": table_analysis.get("table_name", "")
                            }
                            cSingleNeo4j.create_relationship(
                                entity_node,
                                "HAS_ATTRIBUTE",
                                attribute_node,
                                **rel_properties
                            )
                            relationships_created += 1
                        except Exception as e:
                            print(f"  ⚠️ 创建 HAS_ATTRIBUTE 关系失败: {entity_name} -> {attr_name} - {e}")
            
            # 2.2 创建 Entity -> UniqueIdentifier 关系 (HAS_IDENTIFIER)
            for table_analysis in tables_analysis:
                table_id = table_analysis.get("table_id", "")
                analysis_result = table_analysis.get("analysis_result", {})
                
                entity = analysis_result.get("entity", {})
                entity_name = entity.get("entity_name", "")
                if not entity_name:
                    continue
                
                entity_id = f"{table_id}_{entity_name}"
                if entity_id not in entity_nodes:
                    continue
                
                entity_node = entity_nodes[entity_id]
                unique_identifiers = analysis_result.get("unique_identifiers", [])
                
                for identifier in unique_identifiers:
                    identifier_col_name = identifier.get("col_name", "")
                    identifier_name = identifier.get("identifier_name", "")
                    
                    if identifier_col_name:
                        identifier_id = f"{table_id}_{identifier_col_name}"
                    else:
                        identifier_id = f"{table_id}_{identifier_name}"
                    
                    if identifier_id in identifier_nodes:
                        try:
                            identifier_node = identifier_nodes[identifier_id]
                            rel_properties = {
                                "sql_id": sql_id,
                                "permission_level": permission_level,
                                "table_id": table_id,
                                "table_name": table_analysis.get("table_name", ""),
                                "identifier_type": identifier.get("identifier_type", "")
                            }
                            cSingleNeo4j.create_relationship(
                                entity_node,
                                "HAS_IDENTIFIER",
                                identifier_node,
                                **rel_properties
                            )
                            relationships_created += 1
                        except Exception as e:
                            print(f"  ⚠️ 创建 HAS_IDENTIFIER 关系失败: {entity_name} -> {identifier_name} - {e}")
            
            # 2.3 创建 Entity -> Metric 关系 (HAS_METRIC)
            for table_analysis in tables_analysis:
                table_id = table_analysis.get("table_id", "")
                analysis_result = table_analysis.get("analysis_result", {})
                
                entity = analysis_result.get("entity", {})
                entity_name = entity.get("entity_name", "")
                if not entity_name:
                    continue
                
                entity_id = f"{table_id}_{entity_name}"
                if entity_id not in entity_nodes:
                    continue
                
                entity_node = entity_nodes[entity_id]
                metrics = analysis_result.get("metrics", [])
                
                for metric in metrics:
                    metric_col_name = metric.get("col_name", "")
                    metric_name = metric.get("metric_name", "")
                    
                    if metric_col_name:
                        metric_id = f"{table_id}_{metric_col_name}"
                    else:
                        metric_id = f"{table_id}_{metric_name}"
                    
                    if metric_id in metric_nodes:
                        try:
                            metric_node = metric_nodes[metric_id]
                            rel_properties = {
                                "sql_id": sql_id,
                                "permission_level": permission_level,
                                "table_id": table_id,
                                "table_name": table_analysis.get("table_name", ""),
                            "metric_type": metric.get("metric_type", "")
                            }
                            cSingleNeo4j.create_relationship(
                                entity_node,
                            "HAS_METRIC",
                            metric_node,
                                **rel_properties
                            )
                            relationships_created += 1
                        except Exception as e:
                            print(f"  ⚠️ 创建 HAS_METRIC 关系失败: {entity_name} -> {metric_name} - {e}")
            
            # 2.4 创建外键关系：处理 from_table 的列和 to_table 的列之间的关系
            # 辅助函数：根据 table_name 查找对应的 table_id 和 Entity 节点
            def find_table_info_by_name(table_name: str):
                """根据表名查找 table_id 和 Entity 节点"""
                for ta in tables_analysis:
                    if ta.get("table_name", "") == table_name:
                        table_id = ta.get("table_id", "")
                        analysis_result = ta.get("analysis_result", {})
                        entity = analysis_result.get("entity", {})
                        entity_name = entity.get("entity_name", "")
                        if entity_name:
                            entity_id = f"{table_id}_{entity_name}"
                            if entity_id in entity_nodes:
                                return {
                                    "table_id": table_id,
                                    "entity_id": entity_id,
                                    "entity_node": entity_nodes[entity_id],
                                    "entity_name": entity_name
                                }
                return None
            
            # 处理外键关系
            for table_analysis in tables_analysis:
                from_table_id = table_analysis.get("table_id", "")
                from_table_name = table_analysis.get("table_name", "")
                analysis_result = table_analysis.get("analysis_result", {})
                
                # 获取 from_table 的 Entity 节点
                entity = analysis_result.get("entity", {})
                from_entity_name = entity.get("entity_name", "")
                if not from_entity_name:
                    continue
                
                from_entity_id = f"{from_table_id}_{from_entity_name}"
                if from_entity_id not in entity_nodes:
                    continue
                
                from_entity_node = entity_nodes[from_entity_id]
                foreign_keys = analysis_result.get("foreign_keys", [])
                
                for fk in foreign_keys:
                    from_col = fk.get("from_col", "")
                    to_table_name = fk.get("to_table", "")
                    to_col = fk.get("to_col", "")
                    relationship_type = fk.get("relationship_type", "")
                    fk_description = fk.get("description", "")
                    
                    if not (from_col and to_table_name and to_col):
                        continue
                    
                    # 1. 检查 from_col 对应的 Attribute 节点是否存在
                    from_attribute_id = f"{from_table_id}_{from_col}"
                    if from_attribute_id not in attribute_nodes:
                        print(f"  ⚠️ 外键关系跳过: {from_table_name}.{from_col} -> {to_table_name}.{to_col} (from_col 的 Attribute 节点不存在)")
                        continue
                    
                    from_attribute_node = attribute_nodes[from_attribute_id]
                    
                    # 2. 查找 to_table 的信息
                    to_table_info = find_table_info_by_name(to_table_name)
                    if not to_table_info:
                        print(f"  ⚠️ 外键关系跳过: {from_table_name}.{from_col} -> {to_table_name}.{to_col} (to_table 不存在)")
                        continue
                    
                    to_table_id = to_table_info["table_id"]
                    to_entity_node = to_table_info["entity_node"]
                    to_entity_name = to_table_info["entity_name"]
                    
                    # 3. 检查 to_col 对应的 Attribute 节点是否存在
                    to_attribute_id = f"{to_table_id}_{to_col}"
                    if to_attribute_id not in attribute_nodes:
                        print(f"  ⚠️ 外键关系跳过: {from_table_name}.{from_col} -> {to_table_name}.{to_col} (to_col 的 Attribute 节点不存在)")
                        continue
                    
                    to_attribute_node = attribute_nodes[to_attribute_id]
                    
                    # 4. 创建 from_table 的 Entity -> to_table 的 Entity 关系 (REFERENCES)
                    try:
                        rel_properties = {
                            "sql_id": sql_id,
                            "permission_level": permission_level,
                        "from_table_id": from_table_id,
                        "from_table_name": from_table_name,
                        "from_col": from_col,
                        "to_table_id": to_table_id,
                        "to_table_name": to_table_name,
                        "to_col": to_col,
                        "relationship_type": relationship_type,
                        "description": fk_description
                        }
                        cSingleNeo4j.create_relationship(
                        from_entity_node,
                        "REFERENCES",
                        to_entity_node,
                            **rel_properties
                        )
                        relationships_created += 1
                        print(f"    ✅ 创建 Entity 关系: {from_table_name}.{from_entity_name} -> {to_table_name}.{to_entity_name} (via {from_col} -> {to_col})")
                    except Exception as e:
                        print(f"  ⚠️ 创建 Entity REFERENCES 关系失败: {from_table_name}.{from_entity_name} -> {to_table_name}.{to_entity_name} - {e}")
                    
                    # 5. 创建 from_col 的 Attribute -> to_col 的 Attribute 关系 (REFERENCED_BY)
                    try:
                        rel_properties = {
                            "sql_id": sql_id,
                        "permission_level": permission_level,
                        "from_table_id": from_table_id,
                        "from_table_name": from_table_name,
                        "to_table_id": to_table_id,
                        "to_table_name": to_table_name,
                        "relationship_type": relationship_type,
                        "description": fk_description
                        }
                        cSingleNeo4j.create_relationship(
                        from_attribute_node,
                        "REFERENCED_BY",
                        to_attribute_node,
                            **rel_properties
                        )
                        relationships_created += 1
                        print(f"    ✅ 创建 Attribute 关系: {from_table_name}.{from_col} -> {to_table_name}.{to_col}")
                    except Exception as e:
                        print(f"  ⚠️ 创建 Attribute REFERENCED_BY 关系失败: {from_table_name}.{from_col} -> {to_table_name}.{to_col} - {e}")
            
            # 2.4 创建相似关系：多个表格之间，只建立属性（attributes）之间的相似关系
            # 条件：1. 只能是属性（attributes）
            #       2. 排除时间属性（datetime类型）
            #       3. 排除空间区域属性（location, region, area, coordinate等）
            #       4. col_name 和 col_description 都要相同才能建立相似链接
            # all_col_nodes_info = {}  # {node_id: {"node_type": ..., "name": ..., "col_name": ..., "col_comment": ..., "description": ..., "attr_type": ..., "table_id": ..., "table_name": ..., "node": ...}}
            
            # 辅助函数：判断是否是空间区域属性
            def is_spatial_attribute(attr_name: str, col_name: str, col_comment: str, description: str) -> bool:
                """判断是否是空间区域属性"""
                spatial_keywords = [
                    'location', 'loc', 'address', 'addr', 'region', 'area', 'zone', 'district',
                    'coordinate', 'coord', 'latitude', 'lat', 'longitude', 'lng', 'lon',
                    'geography', 'geo', 'spatial', 'position', 'pos', 'point', 'polygon',
                    'boundary', 'bound', 'territory', 'territorial',
                    '位置', '地址', '区域', '地区', '地理', '坐标', '经纬度', '边界', '范围'
                ]
                
                text_to_check = f"{attr_name} {col_name} {col_comment} {description}".lower()
                return any(keyword.lower() in text_to_check for keyword in spatial_keywords)
            
            # # 只收集 attributes（排除时间属性和空间区域属性）
            # for table_analysis in tables_analysis:
            #     table_id = table_analysis.get("table_id", "")
            #     table_name = table_analysis.get("table_name", "")
            #     analysis_result = table_analysis.get("analysis_result", {})
            #     attributes = analysis_result.get("attributes", [])
            #
            #     for attr in attributes:
            #         attr_name = attr.get("attr_name", "")
            #         attr_col_name = attr.get("col_name", "")
            #         attr_type = attr.get("attr_type", "")  # 获取属性类型（如：datetime, text, other）
            #         attr_description = attr.get("attr_description", "")
            #
            #         # 排除时间属性
            #         if attr_type == "datetime":
            #             continue
            #
            #         # 获取列描述
            #         attr_col_comment = ""
            #         if attr_col_name and table_id in table_columns_map:
            #             for col_info in table_columns_map[table_id]:
            #                 if col_info.get("col_name") == attr_col_name:
            #                     attr_col_comment = col_info.get("col_comment", "")
            #                     break
            #
            #         # 排除空间区域属性
            #         if is_spatial_attribute(attr_name, attr_col_name, attr_col_comment, attr_description):
            #             continue
            #         # 排除包含 _id 的列名（通常是外键ID列）
            #         if "_id" in attr_col_name:
            #             continue
            #         # 只处理有效的属性节点（必须有列名，且节点已创建）
            #         if attr_col_name:
            #             attribute_id = f"{table_id}_{attr_col_name}"
            #             if attribute_id in attribute_nodes:
            #                 all_col_nodes_info[attribute_id] = {
            #                     "node_type": "attribute",
            #                     "name": attr_name,
            #                     "col_name": attr_col_name,
            #                     "col_comment": attr_col_comment,
            #                     "description": attr_description or attr_col_comment,  # 使用 attr_description 或 col_comment
            #                     "attr_type": attr_type,
            #                     "table_id": table_id,
            #                     "table_name": table_name,
            #                     "node": attribute_nodes.get(attribute_id)
            #                 }
            
            # # 比较属性节点之间的相似关系（跨表比较）
            # # 条件：col_name 和 col_description 都要相同才能建立相似链接
            # for node_id1, node_info1 in all_col_nodes_info.items():
            #     node_col_name1 = node_info1.get("col_name", "")
            #     node_description1 = node_info1.get("description", "")
            #     table_id1 = node_info1.get("table_id", "")
            #     table_name1 = node_info1.get("table_name", "")
            #     node1 = node_info1.get("node")
            #
            #     # 确保节点存在
            #     if not node1 or not node_col_name1:
            #         continue
            #
            #     if("_id" not in node_col_name1):
            #         continue
            #
            #     for node_id2, node_info2 in all_col_nodes_info.items():
            #         if node_id1 >= node_id2:  # 避免重复和自环
            #             continue
            #
            #         table_id2 = node_info2.get("table_id", "")
            #         if table_id1 == table_id2:  # 只比较不同表的列
            #             continue
            #
            #         node_col_name2 = node_info2.get("col_name", "")
            #         node_description2 = node_info2.get("description", "")
            #         table_name2 = node_info2.get("table_name", "")
            #         node2 = node_info2.get("node")
            #
            #         # 确保节点存在
            #         if not node2 or not node_col_name2:
            #             continue
            #
            #         # 建立相似关系的条件：col_name 和 col_description 都要相同
            #         should_create_similar = False
            #         similarity_type = ""
            #         similarity_score = 1.0  # 完全匹配，相似度为1.0
            #
            #         # 检查 col_name 是否相同
            #         col_name_match = node_col_name1 and node_col_name2 and node_col_name1 == node_col_name2
            #
            #         # 检查 col_description 是否相同（使用 description 字段）
            #         # 如果 description 为空，则使用 col_comment
            #         desc1 = node_description1 or node_info1.get("col_comment", "")
            #         desc2 = node_description2 or node_info2.get("col_comment", "")
            #         description_match = desc1 and desc2 and desc1.strip() == desc2.strip()
            #
            #         # 只有 col_name 和 col_description 都相同才建立相似关系
            #         if col_name_match and description_match:
            #             should_create_similar = True
            #             similarity_type = "same_col_name_and_description"
            #
            #         if should_create_similar:
            #             try:
            #                 # 获取 col_comment 用于关系属性
            #                 node_col_comment1 = node_info1.get("col_comment", "")
            #                 node_col_comment2 = node_info2.get("col_comment", "")
            #                 node_name1 = node_info1.get("name", "")
            #                 node_name2 = node_info2.get("name", "")
            #
            #                 rel_properties = {
            #                     "similarity_type": similarity_type,
            #                     "similarity_score": similarity_score,
            #                     "sql_id": sql_id,
            #                     "permission_level": permission_level,
            #                     "table_name1": table_name1,
            #                     "table_name2": table_name2,
            #                     "col_name1": node_col_name1,
            #                     "col_name2": node_col_name2,
            #                     "col_comment1": (node_col_comment1[:200] if node_col_comment1 else ""),
            #                     "col_comment2": (node_col_comment2[:200] if node_col_comment2 else ""),
            #                     "description1": (node_description1[:200] if node_description1 else ""),
            #                     "description2": (node_description2[:200] if node_description2 else "")
            #                 }
            #                 cSingleNeo4j.create_relationship(
            #                     node1,
            #                     "SIMILAR_TO",
            #                     node2,
            #                     **rel_properties
            #                 )
            #                 relationships_created += 1
            #                 print(f"    ✅ 创建跨表相似关系: {table_name1}.{node_col_name1} ({node_info1.get('node_type')}) <-> {table_name2}.{node_col_name2} ({node_info2.get('node_type')}) ({similarity_type})")
            #             except Exception as e:
            #                 print(f"  ⚠️ 创建跨表 SIMILAR_TO 关系失败: {node_col_name1} <-> {node_col_name2} - {e}")
            
            print(f"✅ Schema 分析图数据保存完成:")
            print(f"   - Entity 节点: {len(entity_nodes)}")
            print(f"   - Attribute 节点: {len(attribute_nodes)}")
            print(f"   - UniqueIdentifier 节点: {len(identifier_nodes)}")
            print(f"   - Metric 节点: {len(metric_nodes)}")
            print(f"   - 关系数量: {relationships_created}")
            
            # 将所有节点保存到Milvus向量库
            try:
                # 收集所有节点数据
                nodes_data = []
                entity_data = []
                # Entity 节点
                for entity_id, entity_node in entity_nodes.items():
                    entity_info = entity_info_map.get(entity_id, {})
                    if(len(entity_id) > 256):
                        print(entity_id)
                    entity_data.append({
                        "node_type": "entity",
                        "node_id": entity_id,
                        "entity_name": entity_info.get("name", ""),
                        "entity_description": entity_info.get("entity_description", ""),
                        "table_name": entity_info.get("table_name", ""),
                        "table_id": entity_info.get("table_id", ""),
                        "sql_id": sql_id
                    })
                
                vector_result = self.vector_agent.save_graph_nodes_to_vector_store(
                    entity_data, sql_id
                )
                attribute_data = []
                # Attribute 节点
                for attribute_id, attribute_node in attribute_nodes.items():
                    attribute_info = attribute_info_map.get(attribute_id, {})
                    if(len(attribute_id) > 256):
                        print(attribute_id)
                    attribute_data.append({
                        "node_type": "attribute",
                        "node_id": attribute_id,
                        "attribute_name": attribute_info.get("name", ""),
                        "attribute_description": attribute_info.get("col_comment", ""),  # 使用列注释作为描述
                        "col_name": attribute_info.get("col_name", ""),
                        "table_name": attribute_info.get("table_name", ""),
                        "table_id": attribute_info.get("table_id", ""),
                        "sql_id": sql_id
                    })
                vector_result = self.vector_agent.save_graph_nodes_to_vector_store(
                    entity_data, sql_id
                )

                # UniqueIdentifier 节点 (需要从图数据中提取)
                for table_analysis in tables_analysis:
                    table_id = table_analysis.get("table_id", "")
                    analysis_result = table_analysis.get("analysis_result", {})
                    unique_identifiers = analysis_result.get("unique_identifiers", [])

                    for identifier in unique_identifiers:
                        identifier_col_name = identifier.get("col_name", "")
                        identifier_id = f"{table_id}_{identifier_col_name}"
                        if identifier_id in identifier_nodes:
                            nodes_data.append({
                                "node_type": "unique_identifier",
                                "node_id": identifier_id,
                                "identifier_name": identifier.get("identifier_name", ""),
                                "identifier_description": identifier.get("description", ""),
                                "col_name": identifier_col_name,
                                "table_name": table_analysis.get("table_name", ""),
                                "table_id": table_id,
                                "sql_id": sql_id
                            })
                
                metric_data = []
                # Metric 节点
                for metric_id, metric_node in metric_nodes.items():
                    metric_info = metric_info_map.get(metric_id, {})
                    metric_data.append({
                        "node_type": "metric",
                        "node_id": metric_id,
                        "metric_name": metric_info.get("name", ""),
                        "metric_description": metric_info.get("description", ""),
                        "col_name": metric_info.get("col_name", ""),
                        "table_name": metric_info.get("table_name", ""),
                        "table_id": metric_info.get("table_id", ""),
                        "sql_id": sql_id
                    })
                # print(nodes_data)
                # 保存到向量库
                vector_result = self.vector_agent.save_graph_nodes_to_vector_store(
                    metric_data, sql_id
                )

                if vector_result.get("success"):
                    print(f"✅ 节点向量数据保存成功: {vector_result.get('saved_count', 0)} 个节点")
                else:
                    print(f"⚠️ 节点向量数据保存失败: {vector_result.get('message', '')}")

            except Exception as e:
                print(f"⚠️ 保存节点到向量库异常: {e}")
            
            return True
            
        except Exception as e:
            print(f"❌ 保存 Schema 分析图数据到 Neo4j 失败: {e}")
            traceback.print_exc()
            return False
    
    def save_graph(self, graph_result, database_graph_code, 
                   partition_core, file, permission_level):
        if not is_neo4j_enabled():
            print(f"⚠️ Neo4j已禁用，跳过保存图数据")
            return None
        
        graph_path = os.path.join(graph_result, "graph_chunk_entity_relation.graphml")
        graph = read_graph.run_importer(graph_path)
    
        if(graph is None):
            return None
        node_list = []
        for node_id, data in graph.nodes(data=True):
            properties = {k: v for k, v in data.items() if k != 'labels'}
            properties["file_path"] = file
            properties["file_id"] = partition_core
            properties["knowledge_id"] = database_graph_code
            properties["permission_level"] = permission_level
            node = cSingleNeo4j.create_node(node_id, **properties)
            node_list.append(node)
            param = {
                "knowledge_id": database_graph_code,
                "file_id": partition_core,
                "entity_id":node_id,
                "entity_name": node_id,
                "entity_type": properties.get("entity_type", "未知"),
                "source_id":properties.get("source_id", ""),
                "entity_description":properties.get("description", ""),
                "entity_source_file":file,
                }
            
            cSingleSqlite.insert_node_info(param)
    
        for source_id, target_id, data in graph.edges(data=True):
            rel_type = data.get('type', 'RELATED_TO')
            properties = {k: v for k, v in data.items() if k != 'type'}
            properties["file_path"] = file
            properties["file_id"] = partition_core
            properties["knowledge_id"] = database_graph_code
            properties["permission_level"] = permission_level
            start_node = None
            end_node = None
            for node in node_list:
                node_id = node.get("entity_id", "")
                if(node_id == source_id):
                    start_node = node
                if(node_id == target_id):
                    end_node = node
            
            param = {
                "knowledge_id": database_graph_code,
                "file_id": partition_core,
                "relation_weight": properties.get("weight", 1.0),
                "description": properties.get("description", ""),
                "keywords": properties.get("keywords", ""),
                "relation_source_id": properties.get("source_id", ""),
                "file_name": file,
                "start_node": source_id,
                "end_node": target_id,
                "relation_type":rel_type
                }
            
            cSingleSqlite.insert_graph_relation(param)
            
            cSingleNeo4j.create_relationship(start_node, rel_type, end_node, **properties)
            
    def save_graph_info(self, graph_result, database_graph_code, 
                          partition_core, file, title):
        
        milvus_path = os.path.join(graph_result, "kv_store_text_chunks.json")
        
        str_json = read_graph.read_graph_json(milvus_path)
        
        if(str_json is None or str_json == ""):
            return None
        for _chunk in str_json.keys():
            chunk = str_json[_chunk]
            content = chunk["content"]
            
            param = {
                "knowledge_id":database_graph_code,
                "file_id": partition_core,
                "chunk_id": _chunk,
                "chunk_summary": title,
                "chunk_text": content,
                "file_name":file
            }
            
            cSingleSqlite.insert_graph_chunk(param)
        
        return True

