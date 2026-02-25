# -*- coding:utf-8 -*-


'''
Created on 2025年9月19日

@author: 
'''

# import os

from pymilvus import FieldSchema
from pymilvus import CollectionSchema
from pymilvus import DataType

from pymilvus import AnnSearchRequest
from pymilvus import WeightedRanker

from Db.milvus_db import MilvusService
from Config.milvus_config import is_milvus_enabled
import logging
# from Db.splite_db import cSingleSqlite

logger = logging.getLogger(__name__)

class CControl():
    
    def __init__(self):
        self.enabled = is_milvus_enabled()
        if self.enabled:
            self.milvus_service = MilvusService()
        else:
            self.milvus_service = None
            logger.info("Milvus已禁用（MILVUS_FLAG=False），跳过初始化")
        
    def add_text(self, param, embedding, index_params):
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过添加文本操作")
            return False
            
        partition_code = param["knowledge_partition"]
        if("knowledge_collection" not in param.keys()):
            _core = "default"
            param["knowledge_collection"] = _core
        
        data = param["data"]
        title = param["title"]
        database_code = param["knowledge_collection"]
        permission_level = param["permission_level"]
        emb = embedding
        dim = len(emb.embed_query("foo"))
        schema = self.get_schema(dim)
        doc_id = param.get("doc_id", 1)
        # query_params = {"knowledge_collection":database_code, "knowledge_partition":partition_code}
        
        if(self.milvus_service.has_collection(database_code)):
            if(self.milvus_service.has_partition(database_code, partition_code) == False):
                self.milvus_service.create_partition(database_code, partition_code)
                self.insert_data_to_partition(database_code, partition_code, title, 
                                              data, permission_level, emb, doc_id)
            else:
                self.insert_data_to_partition(database_code, partition_code, title, 
                                              data, permission_level, emb, doc_id)
        else:
            self.milvus_service.create_collection(database_code, schema, index_params)
            self.milvus_service.create_partition(database_code, partition_code)
            self.insert_data_to_partition(database_code, partition_code, title, 
                                          data, permission_level, emb, doc_id)

    def get_schema(self, dim):
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64,max_length=128,is_primary=True, auto_id=True),  # 主键索引
            FieldSchema(name="doc_id", dtype=DataType.INT64),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="title_embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
            FieldSchema(name="content_embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
            FieldSchema(name="permission_level", dtype=DataType.VARCHAR, max_length=128)
        ]
        schema = CollectionSchema(fields=fields, description="Knowledge Base Collection")
        return schema

    def insert_data_to_partition(self, database_code, partition_code, title, 
                                 _txt, permission_level, embeddings, doc_id=1):
            docs_embeddings = embeddings.embed_query(_txt)
            title_embedding = embeddings.embed_query(title)
            batched_entities = [
                [doc_id],
                [title],
                [_txt],
                [title_embedding],
                [docs_embeddings],
                [permission_level],
            ]
            self.milvus_service.insert(database_code, batched_entities, partition_code)
            
    def search(self, collection, query, embedding, search_params, limit, flag):    
        query_embedding = embedding.embed_query(query)
        if(flag):
            title_results = collection.search(
                data=[query_embedding],
                anns_field="title_embedding",
                param=search_params,
                limit=limit,
                output_fields=["title", "content"]
            )
    
            # Search in content embedding
            content_results = collection.search(
                data=[query_embedding],
                anns_field="content_embedding",
                param=search_params,
                limit=limit,
                output_fields=["title", "content"]
            )
        else:
            title_results = collection.search(
                data=[query_embedding],
                anns_field="title_embedding",
                param=search_params,
                limit=limit,
                output_fields=["title", "content"],
                expr="permission_level == 'public'"
            )
    
            # Search in content embedding
            content_results = collection.search(
                data=[query_embedding],
                anns_field="content_embedding",
                param=search_params,
                limit=limit,
                output_fields=["title", "content"],
                expr="permission_level == 'public'"
            )

        # Combine and deduplicate results
        all_results = []
        seen_ids = set()

        # Process results
        for hits in [title_results[0], content_results[0]]:
            for hit in hits:
                if hit.id not in seen_ids:
                    all_results.append({
                        "id": hit.id,
                        "score": hit.distance,
                        "title": hit.entity.get('title'),
                        "content": hit.entity.get('content'),
                        "doc_id": hit.entity.get('doc_id')
                    })
                    seen_ids.add(hit.id)
        
        # Sort by score (distance)
        all_results.sort(key=lambda x: x["score"])

        return all_results
    
    def search_meg(self, collection, query, embedding, search_params, limit,
                   flag, name_weight=1.0, text_weight=1.0):
        metric_type = search_params["metric_type"]
        query_embedding = embedding.embed_query(query)
        
        dense_search_params = {"metric_type": metric_type, "params": {}}
        sparse_search_params = {"metric_type": metric_type, "params": {}}
        
        if(flag):
            dense_name_req = AnnSearchRequest(
                [query_embedding], "title_embedding", dense_search_params, limit=limit
            )
            dense_text_req = AnnSearchRequest(
                [query_embedding], "content_embedding", sparse_search_params, limit=limit
            )
        else:
            dense_name_req = AnnSearchRequest(
                [query_embedding], "title_embedding", 
                dense_search_params, limit=limit,
                expr="permission_level == 'public'"
            )
            dense_text_req = AnnSearchRequest(
                [query_embedding], "content_embedding", 
                sparse_search_params, limit=limit,
                expr="permission_level == 'public'"
            )
            
        rerank = WeightedRanker(name_weight, text_weight)
        res = collection.hybrid_search(
            reqs=[dense_name_req, dense_text_req], 
            rerank=rerank, 
            limit=limit, 
            output_fields=["title", "content"]
        )[0]
        # res = collection.hybrid_search(
        #     reqs=[
        #         AnnSearchRequest(
        #             data=[['{your_text_query_vector}']],  # Replace with your text vector data
        #             anns_field='{text_vector_field_name}',  # Textual data vector field
        #             param=dense_search_params, # Search parameters
        #             limit=limit
        #         ),
        #         AnnSearchRequest(
        #             data=[['{your_image_query_vector}']],  # Replace with your image vector data
        #             anns_field='{image_vector_field_name}',  # Image data vector field
        #             param=sparse_search_params, # Search parameters
        #             limit=limit
        #         )
        #     ],
        #     rerank=rerank,
        #     limit=limit
        # )
        
        # Combine and deduplicate results
        all_results = []
        seen_ids = set()

        # Process results
        for hit in res:
            all_results.append({
                "id": hit.id,
                "score": hit.distance,
                "title": hit.entity.get('title'),
                "content": hit.entity.get('content'),
                "partition": hit.partition_name
            })
            seen_ids.add(hit.id)
        
        # Sort by score (distance)
        all_results.sort(key=lambda x: x["score"])
        all_content = []
        for item in all_results:
            _tmp_d = {}
            # _tmp_d["id"] = item["id"]
            _tmp_d["score"] = item["score"]
            _tmp_d["title"] = item["title"]
            _tmp_d["content"] = item["content"]
            _tmp_d["partition"] = item["partition"]
            all_content.append(_tmp_d)
            print(f"ID: {item['id']}, Score: {item['score']}, Title: {item['title']}, Content: {item['content']}")
        return all_content
        
        # return txt_lt
    
    def search_content(self, collection_name, query, embedding, 
                       index_params, limit, flag=True):
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过搜索操作")
            return []
            
        if(self.milvus_service.has_collection(collection_name) == False):
            raise ValueError(f"Collection '{collection_name}' does not exist.")
        collection = self.milvus_service.get_collection(collection_name)
        if collection is None:
            return []
        # results = self.search(collection, query, embedding, index_params, limit)
        results = self.search_meg(collection, query, embedding, index_params, limit, flag)
        return results
    
    def delete_collection(self, collection_name):
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过删除集合操作")
            return False
            
        if(self.milvus_service.has_collection(collection_name)):
            self.milvus_service.drop_collection(collection_name)
            return True
        return False
    
    def delete_partition(self, collection_name, partition_name):
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过删除分区操作")
            return False
            
        if(self.milvus_service.has_collection(collection_name)):
            if(self.milvus_service.has_partition(collection_name, partition_name)):
                self.milvus_service.drop_partition(collection_name, partition_name)
                return True
        return False
    
    def delete_all_partition(self, collection_name):
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过删除所有分区操作")
            return False
            
        if(self.milvus_service.has_collection(collection_name)):
            partitions = self.milvus_service.get_partitions(collection_name)
            for partition in partitions:
                if(partition.name != "_default"):
                    self.milvus_service.drop_partition(collection_name, partition.name)
            return True
        return False
    
    def delete_all_collection(self):
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过删除所有集合操作")
            return False
            
        collections = self.milvus_service.list_collections()
        for collection in collections:
            self.milvus_service.delete_collection(collection)
        return True
    
    def colse_milvus(self):
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过关闭操作")
            return False
            
        self.milvus_service.close()
        return True
    
    def check_knowledge_and_user(self, knowledge_id: str, user_id: str) -> bool:
        """
        检查用户是否有权限访问知识库
        
        Args:
            knowledge_id: 知识库ID
            user_id: 用户ID
            
        Returns:
            bool: True 表示有权限访问所有数据，False 表示只能访问公开数据
        """
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过权限检查")
            return False
            
        # 这里可以根据实际业务逻辑实现权限检查
        # 例如：检查用户是否是知识库的创建者或协作者
        # 目前简化为：检查知识库ID是否以用户ID开头（表示用户创建的知识库）
        try:
            # 示例：如果知识库ID包含用户ID，则认为用户有完全访问权限
            return user_id in knowledge_id or knowledge_id.startswith(f"kb_{user_id}")
        except Exception as e:
            logger.error(f"权限检查失败: {e}")
            return False
    
    
