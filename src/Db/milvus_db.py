# -*- coding:utf-8 -*-


'''
Created on 2024年9月5日

@author: 
'''

import os

# from Emb.rerankers_embedding import CControl as RerankControl

from pymilvus import connections 
from pymilvus import utility
from pymilvus import Collection
# from pymilvus import CollectionSchema
# from pymilvus import FieldSchema
from pymilvus import DataType
from pymilvus import Partition

# from pymilvus.model.reranker import BGERerankFunction
# from pymilvus.model.hybrid import BGEM3EmbeddingFunction

from dotenv import load_dotenv
from Config.milvus_config import get_milvus_connection_params, is_milvus_enabled
import logging

load_dotenv()

logger = logging.getLogger(__name__)

class MilvusService:
    '''
    Milvus向量数据库服务类
    提供对Milvus数据库的基本操作封装，包括集合管理、数据插入、搜索等功能
    '''
    
    def __init__(self, host=None, port=None, alias='default'):
        '''
        初始化Milvus连接
        
        Args:
            host: Milvus服务器地址（可选，默认从.env读取）
            port: Milvus服务器端口（可选，默认从.env读取）
            alias: 连接别名
        '''
        # 检查是否启用Milvus
        self.enabled = is_milvus_enabled()
        
        if not self.enabled:
            logger.info("Milvus已禁用（MILVUS_FLAG=False），跳过连接初始化")
            self.alias = alias
            self.host = None
            self.port = None
            return
        
        # 如果未提供参数，从.env文件读取配置
        if host is None or port is None:
            config = get_milvus_connection_params()
            host = host or config["host"]
            port = port or config["port"]
        
        self.alias = alias
        self.host = host
        self.port = port
        
        try:
            connections.connect(alias=self.alias, host=host, port=port)
        except Exception as e:
            logger.error(f"Milvus连接失败: {e}")
            raise
        
        # self.rerank_control = RerankControl(model_name="bge-reranker-large")
        
        # self.embed_fn = BGEM3EmbeddingFunction(model_name="BAAI/bge-reranker-v2-m3",
        #                                   device='cuda:0')
        #
        # self.rerank_fn = BGERerankFunction(
        #     model_name="BAAI/bge-reranker-v2-m3",  # Specify the model name. Defaults to `BAAI/bge-reranker-v2-m3`.
        #     device="cuda:0" # Specify the device to use, e.g., 'cpu' or 'cuda:0'
        # )

    def close(self):
        '''
        断开Milvus连接
        
        Returns:
            bool: 连接断开成功返回True
        '''
        connections.disconnect(self.alias)
        return True
        
    def create_collection(self, collection_name, schema, index_params=None):
        '''
        创建集合
        
        Args:
            collection_name: 集合名称
            schema: 集合模式定义
            index_params: 索引参数
            
        Returns:
            Collection: 创建的集合对象
        '''
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过创建集合操作")
            return None
            
        # fields = [
        #     FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True, auto_id=True),
        #     FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        #     FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim)
        # ]
        # schema = CollectionSchema(fields=fields, description=description)
        collection = Collection(name=collection_name, schema=schema, using=self.alias)
        fields = schema.fields
        self.create_index(collection_name, fields, index_params)
        return collection
    
    def create_index(self, collection_name, fields, index_params):
        '''
        为集合字段创建索引
        
        Args:
            collection_name: 集合名称
            fields: 字段列表
            index_params: 索引参数
            
        Returns:
            Collection: 集合对象
        '''
        collection = self.get_collection(collection_name)
        if("params" not in index_params):
            index_params["params"] = {}
        for field in fields:
            if(field.is_primary):
                continue
            if(field.auto_id):
                continue
            if(field.dtype == DataType.FLOAT_VECTOR):
                field_name = field.name
                # Create index for the field
                collection.create_index(field_name=field_name, index_params=index_params,index_name=field_name)
        collection.load()
        return collection

    def has_collection(self, collection_name):
        '''
        检查集合是否存在
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 存在返回True，否则返回False
        '''
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过检查集合操作")
            return False
            
        try:
            # collection = self.get_collection(collection_name)
            # _ = collection.num_entities  # 尝试访问属性以确认集合是否存在
            return utility.has_collection(collection_name, using=self.alias)
        except Exception:
            return False

    def drop_collection(self, collection_name):
        '''
        删除集合
        
        Args:
            collection_name: 集合名称
        '''
        utility.drop_collection(collection_name, using=self.alias)

    def get_collection(self, collection_name):
        '''
        获取集合对象
        
        Args:
            collection_name: 集合名称
            
        Returns:
            Collection: 集合对象
        '''
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过获取集合操作")
            return None
            
        return Collection(collection_name, using=self.alias)

    def create_partition(self, collection_name, partition_name):
        '''
        创建分区
        
        Args:
            collection_name: 集合名称
            partition_name: 分区名称
        '''
        collection = self.get_collection(collection_name)
        collection.create_partition(partition_name)
        
    def get_partitions(self, collection_name):
        '''
        获取集合的所有分区
        
        Args:
            collection_name: 集合名称
            
        Returns:
            list: 分区列表
        '''
        collection = self.get_collection(collection_name)
        return collection.partitions

    def has_partition(self, collection_name, partition_name):
        '''
        检查分区是否存在
        
        Args:
            collection_name: 集合名称
            partition_name: 分区名称
            
        Returns:
            bool: 存在返回True，否则返回False
        '''
        collection = self.get_collection(collection_name)
        return collection.has_partition(partition_name)
    
    def release_partition(self, collection_name, partition_name):
        '''
        释放分区资源
        
        Args:
            collection_name: 集合名称
            partition_name: 分区名称
        '''
        partition = Partition(collection_name, partition_name)
        partition.release()

    def drop_partition(self, collection_name, partition_name):
        '''
        删除分区
        
        Args:
            collection_name: 集合名称
            partition_name: 分区名称
            
        Raises:
            ValueError: 当分区不存在时抛出异常
        '''
        collection = self.get_collection(collection_name)
        if not collection.has_partition(partition_name):
            raise ValueError(f"Partition '{partition_name}' does not exist in collection '{collection_name}'.")
        else:
            self.release_partition(collection_name, partition_name)
            collection.drop_partition(partition_name)

    def insert(self, collection_name, data, partition_name=None):
        '''
        向集合中插入数据
        
        Args:
            collection_name: 集合名称
            data: 插入的数据
            partition_name: 分区名称（可选）
            
        Returns:
            MutationResult: 插入结果
        '''
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过插入数据操作")
            return None
            
        collection = self.get_collection(collection_name)
        if collection is None:
            return None
        return collection.insert(data, partition_name=partition_name)

    def search(self, collection_name, vectors, anns_field, param, limit, partition_names=None, expr=None):
        '''
        在集合中搜索向量数据
        
        Args:
            collection_name: 集合名称
            vectors: 查询向量
            anns_field: 向量字段名
            param: 搜索参数
            limit: 返回结果数量限制
            partition_names: 分区名称列表（可选）
            expr: 过滤表达式（可选）
            
        Returns:
            SearchResult: 搜索结果
        '''
        if not self.enabled:
            logger.debug("Milvus已禁用，跳过搜索操作")
            return []
            
        collection = self.get_collection(collection_name)
        if collection is None:
            return []
        return collection.search(vectors, anns_field, param, limit, partition_names=partition_names, expr=expr)

    def delete(self, collection_name, expr, partition_name=None):
        '''
        删除集合中的数据
        
        Args:
            collection_name: 集合名称
            expr: 删除条件表达式
            partition_name: 分区名称（可选）
        '''
        collection = self.get_collection(collection_name)
        collection.delete(expr, partition_name=partition_name)
        
    def drop_index(self, collection_name):
        '''
        删除集合的所有索引
        
        Args:
            collection_name: 集合名称
        '''
        # Drop all indexes for the collection
        collection = self.get_collection(collection_name)
        collection.release()
        collection_schema = collection._schema
        for field in collection_schema.fields:
            if field.is_indexed:
                collection.drop_index(index_name=field.name)
        # collection.drop_index(index_name="dense_text")
        # collection.drop_index(index_name="dense_name")
        # collection.drop_index(index_name="add_num")
        
    def delete_collection(self, collection_name):
        '''
        删除集合及其所有索引
        
        Args:
            collection_name: 集合名称
        '''
        self.drop_index(collection_name)
        self.drop_collection(collection_name)
        
    def list_collections(self):
        '''
        列出所有集合名称
        
        Returns:
            list: 集合名称列表
        '''
        collection_names = utility.list_collections(using=self.alias)
        return collection_names
    
    def delete_all_collections(self):
        '''
        删除所有集合
        '''
        collection_names = self.list_collections()
        for collection_name in collection_names:
            self.delete_collection(collection_name)
    
    def close_con(self):
        '''
        断开连接
        '''
        connections.disconnect(self.alias)