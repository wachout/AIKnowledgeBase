#!/usr/bin/env python3
"""
Elasticsearch 数据库操作类
提供对 Elasticsearch 的连接、索引、文档增删改查功能
"""

import json
import time
from typing import Dict, List, Any, Optional, Tuple
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, NotFoundError
import logging
from Config.elasticsearch_config import get_elasticsearch_connection_params, is_elasticsearch_enabled

logger = logging.getLogger(__name__)


class ElasticSearchDB:
    """Elasticsearch 数据库操作类"""

    def __init__(self, host: str = None,
                 username: str = None,
                 password: str = None,
                 verify_certs: bool = None):
        """
        初始化 Elasticsearch 连接

        Args:
            host: Elasticsearch 服务器地址（可选，默认从.env读取）
            username: 用户名（可选，默认从.env读取）
            password: 密码（可选，默认从.env读取）
            verify_certs: 是否验证 SSL 证书（可选，默认从.env读取）
        """
        # 检查是否启用Elasticsearch
        self.enabled = is_elasticsearch_enabled()
        
        if not self.enabled:
            logger.info("Elasticsearch已禁用（ELASTICSEARCG_FLAG=False），跳过连接初始化")
            self.es = None
            self.host = None
            self.username = None
            self.password = None
            self.verify_certs = False
            return
        
        # 如果未提供参数，从.env文件读取配置
        if host is None or username is None or password is None:
            config = get_elasticsearch_connection_params()
            self.host = host or config["host"]
            self.username = username or config["username"]
            self.password = password or config["password"]
            self.verify_certs = verify_certs if verify_certs is not None else config["verify_certs"]
        else:
            self.host = host
            self.username = username
            self.password = password
            self.verify_certs = verify_certs if verify_certs is not None else False
        
        self.es: Optional[Elasticsearch] = None
        self._connect()

    def _connect(self) -> bool:
        """
        建立 Elasticsearch 连接

        Returns:
            bool: 连接是否成功
        """
        if not self.enabled:
            logger.info("Elasticsearch已禁用，跳过连接")
            return False
            
        try:
            self.es = Elasticsearch(
                [self.host],
                http_auth=(self.username, self.password),
                verify_certs=self.verify_certs
            )

            if self.es.ping():
                logger.info("Elasticsearch 连接成功！")
                return True
            else:
                logger.error("Elasticsearch 连接失败！")
                return False

        except Exception as e:
            logger.error(f"Elasticsearch 连接时出错：{e}")
            return False

    def ping(self) -> bool:
        """
        测试连接状态

        Returns:
            bool: 连接是否正常
        """
        if not self.enabled:
            return False
        if not self.es:
            return False
        try:
            return self.es.ping()
        except Exception as e:
            logger.error(f"连接测试失败: {e}")
            return False

    def create_index(self, index_name: str, mappings: Dict[str, Any] = None) -> bool:
        """
        创建索引

        Args:
            index_name: 索引名称
            mappings: 索引映射配置

        Returns:
            bool: 创建是否成功
        """
        if not self.enabled:
            logger.info("Elasticsearch已禁用，跳过创建索引操作")
            return False
            
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return False

            # 默认映射配置（支持父子关系和向量搜索）
            if mappings is None:
                # 获取向量维度长度
                try:
                    from Config.embedding_config import get_vector_length
                    vector_dimension = get_vector_length()
                except Exception as e:
                    logger.warning(f"无法获取向量维度，使用默认值2048: {e}")
                    vector_dimension = 2048
                
                mappings = {
                    "properties": {
                        "knowledge_id": {"type": "keyword"},
                        "file_id": {"type": "keyword"},
                        "user_id": {"type": "keyword"},
                        "permission_level": {"type": "keyword"},
                        "title": {"type": "text", "analyzer": "ik_max_word"},
                        "content": {"type": "text", "analyzer": "ik_max_word"},
                        "summary": {"type": "text", "analyzer": "ik_max_word"},
                        "authors": {"type": "keyword"},
                        "category": {"type": "keyword"},
                        "create_time": {"type": "date"},
                        "upload_time": {"type": "date"},
                        "doc_type": {"type": "keyword"},  # 文档类型：parent 或 child
                        "parent_id": {"type": "keyword"},  # 父文档ID
                        "chunk_index": {"type": "integer"},  # 段落索引
                        "total_chunks": {"type": "integer"},  # 总段落数
                        "start_pos": {"type": "integer"},  # 段落起始位置
                        "end_pos": {"type": "integer"},  # 段落结束位置
                        "full_content_length": {"type": "integer"},  # 完整内容长度
                        "has_children": {"type": "boolean"},  # 是否有子文档
                        "content_hash": {"type": "keyword"},  # 内容哈希，用于去重
                        # Elasticsearch 9.2.4+ 向量字段支持
                        "title_vector": {
                            "type": "dense_vector",
                            "dims": vector_dimension,
                            "index": True,
                            "similarity": "cosine"
                        },
                        "content_vector": {
                            "type": "dense_vector",
                            "dims": vector_dimension,
                            "index": True,
                            "similarity": "cosine"
                        }
                    }
                }

            body = {
                "mappings": mappings,
                "settings": {
                    "number_of_shards": 3,
                    "number_of_replicas": 1,
                    "analysis": {
                        "analyzer": {
                            "ik_max_word": {
                                "type": "custom",
                                "tokenizer": "ik_max_word"
                            }
                        }
                    }
                }
            }

            if not self.es.indices.exists(index=index_name):
                response = self.es.indices.create(index=index_name, body=body)
                logger.info(f"索引 {index_name} 创建成功")
                return response.get('acknowledged', False)
            else:
                logger.info(f"索引 {index_name} 已存在")
                return True

        except Exception as e:
            logger.error(f"创建索引 {index_name} 失败: {e}")
            return False

    def delete_index(self, index_name: str) -> bool:
        """
        删除索引

        Args:
            index_name: 索引名称

        Returns:
            bool: 删除是否成功
        """
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return False

            if self.es.indices.exists(index=index_name):
                response = self.es.indices.delete(index=index_name)
                logger.info(f"索引 {index_name} 删除成功")
                return response.get('acknowledged', False)
            else:
                logger.info(f"索引 {index_name} 不存在")
                return True

        except Exception as e:
            logger.error(f"删除索引 {index_name} 失败: {e}")
            return False

    def index_document(self, index_name: str, doc_id: str, document: Dict[str, Any]) -> bool:
        """
        索引文档

        Args:
            index_name: 索引名称
            doc_id: 文档ID
            document: 文档内容

        Returns:
            bool: 索引是否成功
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过索引文档操作")
            return False
            
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return False

            # 确保索引存在
            self.create_index(index_name)

            # 添加时间戳
            document['create_time'] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

            response = self.es.index(index=index_name, id=doc_id, body=document)
            logger.info(f"文档 {doc_id} 索引成功")
            return response.get('_shards', {}).get('successful', 0) > 0

        except Exception as e:
            logger.error(f"索引文档 {doc_id} 失败: {e}")
            return False

    def get_document(self, index_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        获取文档

        Args:
            index_name: 索引名称
            doc_id: 文档ID

        Returns:
            Optional[Dict[str, Any]]: 文档内容，如果不存在返回 None
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过获取文档操作")
            return None
            
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return None

            response = self.es.get(index=index_name, id=doc_id)
            return response.get('_source')

        except NotFoundError:
            logger.info(f"文档 {doc_id} 不存在")
            return None
        except Exception as e:
            logger.error(f"获取文档 {doc_id} 失败: {e}")
            return None

    def update_document(self, index_name: str, doc_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新文档

        Args:
            index_name: 索引名称
            doc_id: 文档ID
            updates: 更新内容

        Returns:
            bool: 更新是否成功
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过更新文档操作")
            return False
            
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return False

            # 添加更新时间戳
            updates['update_time'] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

            body = {
                "doc": updates
            }

            response = self.es.update(index=index_name, id=doc_id, body=body)
            logger.info(f"文档 {doc_id} 更新成功")
            return response.get('_shards', {}).get('successful', 0) > 0

        except Exception as e:
            logger.error(f"更新文档 {doc_id} 失败: {e}")
            return False

    def delete_document(self, index_name: str, doc_id: str) -> bool:
        """
        删除文档

        Args:
            index_name: 索引名称
            doc_id: 文档ID

        Returns:
            bool: 删除是否成功
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过删除文档操作")
            return False
            
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return False

            response = self.es.delete(index=index_name, id=doc_id)
            logger.info(f"文档 {doc_id} 删除成功")
            return response.get('_shards', {}).get('successful', 0) > 0

        except NotFoundError:
            logger.info(f"文档 {doc_id} 不存在")
            return True
        except Exception as e:
            logger.error(f"删除文档 {doc_id} 失败: {e}")
            return False

    def search_documents(self, index_name: str, query: Dict[str, Any],
                        size: int = 10, from_: int = 0) -> List[Dict[str, Any]]:
        """
        搜索文档

        Args:
            index_name: 索引名称
            query: 查询条件
            size: 返回结果数量
            from_: 起始位置

        Returns:
            List[Dict[str, Any]]: 搜索结果列表
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过搜索文档操作")
            return []
            
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return []

            # 检查索引是否存在
            if not self.es.indices.exists(index=index_name):
                logger.warning(f"索引 {index_name} 不存在，返回空结果")
                return []

            body = {
                "query": query,
                "size": size,
                "from": from_,
                "sort": [
                    {"_score": {"order": "desc"}}
                ]
            }

            response = self.es.search(index=index_name, body=body)
            hits = response.get('hits', {}).get('hits', [])

            results = []
            for hit in hits:
                result = hit.get('_source', {})
                result['_id'] = hit.get('_id')
                result['_score'] = hit.get('_score')
                results.append(result)

            logger.info(f"搜索完成，返回 {len(results)} 个结果")
            return results

        except Exception as e:
            import traceback
            error_msg = str(e)
            # 如果是索引不存在的错误，记录警告而不是错误
            if 'index_not_found_exception' in error_msg or 'no such index' in error_msg.lower():
                logger.warning(f"索引 {index_name} 不存在: {e}")
            else:
                logger.error(f"搜索失败: {e}")
                logger.error(f"错误详情: {traceback.format_exc()}")
            return []

    def search_by_knowledge_and_permission(self, index_name: str, knowledge_id: str,
                                          user_id: str, permission_flag: bool,
                                          search_query: str = "", size: int = 10,
                                          use_hybrid_search: bool = True,
                                          query_vector: List[float] = None) -> List[Dict[str, Any]]:
        """
        根据知识库ID和权限搜索文档（支持 Hybrid Search）
        
        Elasticsearch 9.2.4+ 支持混合搜索，结合：
        - Full-text search（全文搜索）
        - AI-powered search（向量搜索）

        Args:
            index_name: 索引名称
            knowledge_id: 知识库ID
            user_id: 用户ID
            permission_flag: 权限标志 (True: 可访问所有, False: 仅公开)
            search_query: 搜索查询内容
            size: 返回结果数量
            use_hybrid_search: 是否使用混合搜索（默认True）
            query_vector: 查询向量（如果提供，将用于向量搜索）

        Returns:
            List[Dict[str, Any]]: 搜索结果列表
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过搜索操作")
            return []
            
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return []
            
            # 检查索引是否存在
            if not self.es.indices.exists(index=index_name):
                logger.warning(f"索引 {index_name} 不存在，返回空结果")
                return []
            
            # 如果启用混合搜索且有查询文本，使用混合搜索
            if use_hybrid_search and search_query:
                return self._hybrid_search(
                    index_name=index_name,
                    knowledge_id=knowledge_id,
                    permission_flag=permission_flag,
                    search_query=search_query,
                    query_vector=query_vector,
                    size=size
                )
            
            # 否则使用传统的全文搜索（保持向后兼容）


            # 构建查询条件
            # 注意：由于字段是 text 类型，需要使用 match 查询而不是 term 查询
            must_conditions = [
                {"match": {"knowledge_id": {"query": knowledge_id, "operator": "and"}}}
            ]

            # 根据权限添加条件
            if permission_flag:
                # 可访问所有数据（用户是知识库所有者）
                # 对于 text 类型字段，使用 should + match 来模拟 terms 查询
                must_conditions.append({
                    "bool": {
                        "should": [
                            {"match": {"permission_level": {"query": "public", "operator": "and"}}},
                            {"match": {"permission_level": {"query": "private", "operator": "and"}}}
                        ],
                        "minimum_should_match": 1
                    }
                })
            else:
                # 只能访问公开数据
                must_conditions.append({"match": {"permission_level": {"query": "public", "operator": "and"}}})

            # 优先搜索子文档（段落），因为它们包含更具体的文本内容
            child_query = {
                "bool": {
                    "must": must_conditions + [{"match": {"doc_type": {"query": "child", "operator": "and"}}}]
                }
            }
            
            # 添加搜索内容条件
            if search_query:
                # 将搜索查询添加到 must 中，但使用更宽松的匹配
                child_query["bool"]["must"].append({
                    "multi_match": {
                        "query": search_query,
                        "fields": ["title^3", "content^2", "summary"],
                        "type": "best_fields",
                        "operator": "or",  # 使用 OR 操作符，更宽松
                        "fuzziness": "AUTO"  # 允许模糊匹配
                    }
                })

            child_results = self.search_documents(index_name, child_query, size)

            # 如果子文档结果不够，补充父文档结果
            if len(child_results) < size:
                parent_query = {
                    "bool": {
                        "must": must_conditions + [{"match": {"doc_type": {"query": "parent", "operator": "and"}}}]
                    }
                }
                
                # 添加搜索内容条件（如果有）
                if search_query:
                    parent_query["bool"]["must"].append({
                        "multi_match": {
                            "query": search_query,
                            "fields": ["title^3", "content^2", "summary"],
                            "type": "best_fields",
                            "operator": "or",
                            "fuzziness": "AUTO"
                        }
                    })
                
                remaining_size = size - len(child_results)
                parent_results = self.search_documents(index_name, parent_query, remaining_size)

                # 为父文档结果添加标记
                for result in parent_results:
                    result["is_parent_doc"] = True

                child_results.extend(parent_results)

            # 为每个结果添加父文档信息（如果有的话）
            enriched_results = []
            for result in child_results:
                enriched_result = result.copy()

                # 如果是子文档，获取父文档信息
                if result.get("doc_type") == "child" and result.get("parent_id"):
                    parent_info = self.get_parent_document(index_name, result["parent_id"])
                    if parent_info:
                        enriched_result["parent_title"] = parent_info.get("title", "")
                        enriched_result["parent_summary"] = parent_info.get("summary", "")
                        enriched_result["full_content_length"] = parent_info.get("full_content_length", 0)

                enriched_results.append(enriched_result)

            return enriched_results

        except Exception as e:
            logger.error(f"按权限搜索失败: {e}")
            return []
    
    def _hybrid_search(self, index_name: str, knowledge_id: str,
                      permission_flag: bool, search_query: str,
                      query_vector: List[float] = None,
                      size: int = 10) -> List[Dict[str, Any]]:
        """
        执行混合搜索（Hybrid Search）
        
        结合全文搜索和向量搜索，使用 RRF (Reciprocal Rank Fusion) 算法合并结果
        
        Args:
            index_name: 索引名称
            knowledge_id: 知识库ID
            permission_flag: 权限标志
            search_query: 搜索查询文本
            query_vector: 查询向量（可选，如果不提供将使用查询文本生成）
            size: 返回结果数量
            
        Returns:
            List[Dict[str, Any]]: 合并后的搜索结果
        """
        try:
            # 构建基础过滤条件
            must_conditions = [
                {"match": {"knowledge_id": {"query": knowledge_id, "operator": "and"}}}
            ]
            
            # 权限过滤
            if permission_flag:
                must_conditions.append({
                    "bool": {
                        "should": [
                            {"match": {"permission_level": {"query": "public", "operator": "and"}}},
                            {"match": {"permission_level": {"query": "private", "operator": "and"}}}
                        ],
                        "minimum_should_match": 1
                    }
                })
            else:
                must_conditions.append({"match": {"permission_level": {"query": "public", "operator": "and"}}})
            
            # 优先搜索子文档
            must_conditions.append({"match": {"doc_type": {"query": "child", "operator": "and"}}})
            
            # 1. 全文搜索查询
            text_query = {
                "bool": {
                    "must": must_conditions.copy()
                }
            }
            
            if search_query:
                text_query["bool"]["must"].append({
                    "multi_match": {
                        "query": search_query,
                        "fields": ["title^3", "content^2", "summary"],
                        "type": "best_fields",
                        "operator": "or",
                        "fuzziness": "AUTO"
                    }
                })
            
            # 2. 向量搜索查询（如果提供了向量）
            # Elasticsearch 9.2.4+ 使用顶层 knn 选项进行向量搜索
            vector_results = []
            if query_vector:
                try:
                    # 使用顶层 knn 选项（推荐方式）
                    # 先搜索 content_vector
                    vector_body_content = {
                        "knn": {
                            "field": "content_vector",
                            "query_vector": query_vector,
                            "k": size * 2,
                            "num_candidates": size * 4  # 候选数量应该大于 k
                        },
                        "query": {
                            "bool": {
                                "must": must_conditions.copy()
                            }
                        },
                        "size": size * 2,
                        "_source": True
                    }
                    
                    # 再搜索 title_vector
                    vector_body_title = {
                        "knn": {
                            "field": "title_vector",
                            "query_vector": query_vector,
                            "k": size * 2,
                            "num_candidates": size * 4
                        },
                        "query": {
                            "bool": {
                                "must": must_conditions.copy()
                            }
                        },
                        "size": size * 2,
                        "_source": True
                    }
                    
                    # 执行两个向量搜索
                    content_response = self.es.search(index=index_name, body=vector_body_content)
                    title_response = self.es.search(index=index_name, body=vector_body_title)
                    
                    # 合并结果
                    all_vector_hits = []
                    all_vector_hits.extend(content_response.get('hits', {}).get('hits', []))
                    all_vector_hits.extend(title_response.get('hits', {}).get('hits', []))
                    
                    # 去重并处理结果
                    seen_ids = set()
                    for hit in all_vector_hits:
                        doc_id = hit.get('_id')
                        if doc_id and doc_id not in seen_ids:
                            seen_ids.add(doc_id)
                            result = hit.get('_source', {})
                            result['_id'] = doc_id
                            result['_score'] = hit.get('_score')
                            result['_search_type'] = 'vector'
                            vector_results.append(result)
                            
                except Exception as e:
                    logger.warning(f"向量搜索失败: {e}，将仅使用全文搜索")
                    import traceback
                    logger.debug(f"向量搜索错误详情: {traceback.format_exc()}")
            
            # 3. 执行全文搜索
            text_results = self.search_documents(index_name, text_query, size * 2)
            for result in text_results:
                result['_search_type'] = 'text'
            
            # 4. 使用 RRF 算法合并结果
            if vector_results:
                merged_results = self._rrf_merge(text_results, vector_results, size)
            else:
                # 如果没有向量结果，直接返回全文搜索结果
                merged_results = text_results[:size]
            
            # 5. 为每个结果添加父文档信息
            enriched_results = []
            for result in merged_results:
                enriched_result = result.copy()
                
                if result.get("doc_type") == "child" and result.get("parent_id"):
                    parent_info = self.get_parent_document(index_name, result["parent_id"])
                    if parent_info:
                        enriched_result["parent_title"] = parent_info.get("title", "")
                        enriched_result["parent_summary"] = parent_info.get("summary", "")
                        enriched_result["full_content_length"] = parent_info.get("full_content_length", 0)
                
                enriched_results.append(enriched_result)
            
            logger.info(f"混合搜索完成: 全文搜索 {len(text_results)} 个结果，向量搜索 {len(vector_results)} 个结果，合并后 {len(enriched_results)} 个结果")
            return enriched_results
            
        except Exception as e:
            logger.error(f"混合搜索失败: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            # 降级到普通全文搜索
            return self.search_by_knowledge_and_permission(
                index_name, knowledge_id, "", permission_flag, search_query, size, use_hybrid_search=False
            )
    
    def _rrf_merge(self, text_results: List[Dict[str, Any]], 
                   vector_results: List[Dict[str, Any]], 
                   size: int = 10, k: int = 60) -> List[Dict[str, Any]]:
        """
        使用 RRF (Reciprocal Rank Fusion) 算法合并搜索结果
        
        RRF 公式: score = sum(1 / (k + rank))
        
        Args:
            text_results: 全文搜索结果
            vector_results: 向量搜索结果
            size: 最终返回结果数量
            k: RRF 参数（默认60）
            
        Returns:
            List[Dict[str, Any]]: 合并后的结果列表
        """
        # 创建文档ID到RRF分数的映射
        doc_scores = {}
        
        # 处理全文搜索结果
        for rank, result in enumerate(text_results, start=1):
            doc_id = result.get('_id')
            if doc_id:
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {
                        'doc': result,
                        'rrf_score': 0.0
                    }
                doc_scores[doc_id]['rrf_score'] += 1.0 / (k + rank)
        
        # 处理向量搜索结果
        for rank, result in enumerate(vector_results, start=1):
            doc_id = result.get('_id')
            if doc_id:
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {
                        'doc': result,
                        'rrf_score': 0.0
                    }
                doc_scores[doc_id]['rrf_score'] += 1.0 / (k + rank)
        
        # 按RRF分数排序
        sorted_docs = sorted(
            doc_scores.values(),
            key=lambda x: x['rrf_score'],
            reverse=True
        )
        
        # 返回前size个结果
        merged_results = []
        for item in sorted_docs[:size]:
            doc = item['doc'].copy()
            doc['_rrf_score'] = item['rrf_score']
            merged_results.append(doc)
        
        return merged_results

    def bulk_index_documents(self, index_name: str, documents: List[Tuple[str, Dict[str, Any]]]) -> bool:
        """
        批量索引文档

        Args:
            index_name: 索引名称
            documents: 文档列表 [(doc_id, document), ...]

        Returns:
            bool: 批量索引是否成功
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过批量索引操作")
            return False
            
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return False

            # 确保索引存在
            self.create_index(index_name)

            body = []
            for doc_id, document in documents:
                # 添加操作头
                body.extend([
                    {"index": {"_index": index_name, "_id": doc_id}},
                    {**document, "create_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}
                ])

            if body:
                response = self.es.bulk(body=body)
                successful = response.get('errors', True) is False
                logger.info(f"批量索引完成，成功: {response.get('items', []).__len__() if successful else 0}")
                return successful

            return True

        except Exception as e:
            logger.error(f"批量索引失败: {e}")
            return False

    def get_document_count(self, index_name: str, query: Optional[Dict[str, Any]] = None) -> int:
        """
        获取文档数量

        Args:
            index_name: 索引名称
            query: 查询条件（可选），直接传递查询对象，如 {"term": {...}} 或 {"bool": {...}}

        Returns:
            int: 文档数量
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过获取文档数量操作")
            return 0
            
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return 0

            # 检查索引是否存在
            if not self.es.indices.exists(index=index_name):
                logger.debug(f"索引 {index_name} 不存在，返回文档数量 0")
                return 0

            # 构建查询体：如果提供了查询，包装它；否则使用 match_all
            if query is None:
                body = {"query": {"match_all": {}}}
            else:
                # 如果已经是包装格式（包含 "query" 键），直接使用；否则包装
                if "query" in query:
                    body = query
                else:
                    body = {"query": query}
            
            response = self.es.count(index=index_name, body=body)
            return response.get('count', 0)

        except Exception as e:
            error_msg = str(e)
            # 如果是索引不存在的错误，记录调试信息而不是错误
            if 'index_not_found_exception' in error_msg or 'no such index' in error_msg.lower():
                logger.debug(f"索引 {index_name} 不存在: {e}")
            else:
                logger.error(f"获取文档数量失败: {e}")
                import traceback
                logger.error(f"错误详情: {traceback.format_exc()}")
            return 0

    def list_all_indices_with_stats(self) -> List[Dict[str, Any]]:
        """
        列出所有索引及其统计信息
        
        Returns:
            List[Dict[str, Any]]: 索引列表及其统计信息
        """
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return []
            
            # 获取所有索引
            indices_info = self.es.cat.indices(format="json", h="index,docs.count,store.size")
            
            # 过滤掉系统索引
            user_indices = [
                {
                    "index": idx.get("index", ""),
                    "docs_count": idx.get("docs.count", "0"),
                    "store_size": idx.get("store.size", "0")
                }
                for idx in indices_info
                if not idx.get("index", "").startswith(".")
            ]
            
            return user_indices
            
        except Exception as e:
            logger.error(f"获取索引列表失败: {e}")
            return []

    def get_index_mapping(self, index_name: str) -> Dict[str, Any]:
        """
        获取索引的映射（字段定义）
        
        Args:
            index_name: 索引名称
            
        Returns:
            Dict[str, Any]: 索引映射
        """
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return {}
            
            mapping = self.es.indices.get_mapping(index=index_name)
            return mapping.get(index_name, {}).get("mappings", {})
            
        except Exception as e:
            logger.error(f"获取索引映射失败: {e}")
            return {}
    
    def get_sample_documents(self, index_name: str, size: int = 5) -> List[Dict[str, Any]]:
        """
        获取索引中的样本文档
        
        Args:
            index_name: 索引名称
            size: 返回文档数量
            
        Returns:
            List[Dict[str, Any]]: 样本文档列表
        """
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return []
            
            body = {
                "query": {"match_all": {}},
                "size": size
            }
            
            response = self.es.search(index=index_name, body=body)
            hits = response.get('hits', {}).get('hits', [])
            
            samples = []
            for hit in hits:
                doc = hit.get('_source', {})
                doc['_id'] = hit.get('_id')
                samples.append(doc)
            
            return samples
            
        except Exception as e:
            logger.error(f"获取样本文档失败: {e}")
            return []

    def debug_index_data(self, index_name: str, knowledge_id: str = None) -> Dict[str, Any]:
        """
        调试方法：检查索引中的数据情况
        
        Args:
            index_name: 索引名称
            knowledge_id: 知识库ID（可选）
            
        Returns:
            Dict[str, Any]: 调试信息
        """
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return {"error": "连接未建立"}
            
            # 检查索引是否存在
            index_exists = bool(self.es.indices.exists(index=index_name))
            
            debug_info = {
                "index_exists": index_exists,
                "total_docs": 0,
                "by_knowledge_id": {},
                "by_doc_type": {},
                "by_permission_level": {},
                "sample_docs": []
            }
            
            if not debug_info["index_exists"]:
                logger.warning(f"索引 {index_name} 不存在")
                return debug_info
            
            # 获取总文档数
            debug_info["total_docs"] = int(self.get_document_count(index_name))
            
            # 如果指定了 knowledge_id，检查该知识库的数据
            # 注意：由于字段是 text 类型，需要使用 match 查询
            if knowledge_id:
                query = {"match": {"knowledge_id": {"query": knowledge_id, "operator": "and"}}}
                debug_info["by_knowledge_id"]["total"] = int(self.get_document_count(index_name, query))
                
                # 检查 doc_type 分布
                for doc_type in ["parent", "child"]:
                    type_query = {
                        "bool": {
                            "must": [
                                {"match": {"knowledge_id": {"query": knowledge_id, "operator": "and"}}},
                                {"match": {"doc_type": {"query": doc_type, "operator": "and"}}}
                            ]
                        }
                    }
                    debug_info["by_doc_type"][doc_type] = int(self.get_document_count(index_name, type_query))
                
                # 检查 permission_level 分布
                for perm_level in ["public", "private"]:
                    perm_query = {
                        "bool": {
                            "must": [
                                {"match": {"knowledge_id": {"query": knowledge_id, "operator": "and"}}},
                                {"match": {"permission_level": {"query": perm_level, "operator": "and"}}}
                            ]
                        }
                    }
                    debug_info["by_permission_level"][perm_level] = int(self.get_document_count(index_name, perm_query))
                
                # 获取一些示例文档
                sample_query = {
                    "bool": {
                        "must": [{"match": {"knowledge_id": {"query": knowledge_id, "operator": "and"}}}]
                    }
                }
                samples = self.search_documents(index_name, sample_query, size=5)
                debug_info["sample_docs"] = [
                    {
                        "_id": str(doc.get("_id", "")),
                        "doc_type": str(doc.get("doc_type", "")),
                        "permission_level": str(doc.get("permission_level", "")),
                        "title": str(doc.get("title", ""))[:50] if doc.get("title") else ""
                    }
                    for doc in samples
                ]
            
            return debug_info
            
        except Exception as e:
            import traceback
            logger.error(f"调试索引数据失败: {e}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            return {"error": str(e)}

    def get_parent_document(self, index_name: str, child_doc_id: str) -> Optional[Dict[str, Any]]:
        """
        根据子文档ID获取父文档信息

        Args:
            index_name: 索引名称
            child_doc_id: 子文档ID

        Returns:
            Optional[Dict[str, Any]]: 父文档信息
        """
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return None

            # 从子文档ID中提取父文档ID
            # 子文档ID格式: {knowledge_id}_{file_id}_chunk_{chunk_index}
            # 父文档ID格式: {knowledge_id}_{file_id}
            if "_chunk_" in child_doc_id:
                parent_doc_id = child_doc_id.split("_chunk_")[0]
                return self.get_document(index_name, parent_doc_id)
            else:
                # 如果已经是父文档ID，直接返回
                return self.get_document(index_name, child_doc_id)

        except Exception as e:
            logger.error(f"获取父文档失败: {e}")
            return None

    def get_child_documents(self, index_name: str, parent_doc_id: str) -> List[Dict[str, Any]]:
        """
        获取父文档的所有子文档

        Args:
            index_name: 索引名称
            parent_doc_id: 父文档ID

        Returns:
            List[Dict[str, Any]]: 子文档列表
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过获取子文档操作")
            return []
            
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return []

            # 搜索所有以 parent_doc_id 开头的文档，且 doc_type 为 child
            # 注意：由于字段是 text 类型，需要使用 match 查询
            query = {
                "bool": {
                    "must": [
                        {"match": {"parent_id": {"query": parent_doc_id, "operator": "and"}}},
                        {"match": {"doc_type": {"query": "child", "operator": "and"}}}
                    ]
                }
            }

            # 获取所有子文档（设置较大的size）
            return self.search_documents(index_name, query, size=1000)

        except Exception as e:
            logger.error(f"获取子文档失败: {e}")
            return []

    def get_indices_info(self) -> List[Dict[str, Any]]:
        """
        获取所有索引信息

        Returns:
            List[Dict[str, Any]]: 索引信息列表
        """
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return []

            response = self.es.cat.indices(format="json")
            return response

        except Exception as e:
            logger.error(f"获取索引信息失败: {e}")
            return []

    def delete_all_indices(self) -> bool:
        """
        删除所有索引（除了系统索引）

        Returns:
            bool: 删除是否成功
        """
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return False

            # 获取所有索引
            indices_info = self.get_indices_info()

            success_count = 0
            total_count = 0

            for index_info in indices_info:
                index_name = index_info.get("index", "")

                # 跳过系统索引（以点开头的索引）
                if index_name.startswith("."):
                    continue

                total_count += 1
                if self.delete_index(index_name):
                    success_count += 1
                    logger.info(f"成功删除索引: {index_name}")
                else:
                    logger.error(f"删除索引失败: {index_name}")

            logger.info(f"删除索引完成: {success_count}/{total_count} 个索引成功删除")
            return success_count == total_count

        except Exception as e:
            logger.error(f"删除所有索引失败: {e}")
            return False

    def delete_all_documents(self) -> bool:
        """
        删除所有文档（通过删除所有索引来实现）

        Returns:
            bool: 删除是否成功
        """
        return self.delete_all_indices()

    def delete_documents_by_file_id(self, index_name: str, file_id: str) -> bool:
        """
        根据文件ID删除指定索引中的所有相关文档（包括父文档和所有子文档）

        Args:
            index_name: 索引名称
            file_id: 文件ID

        Returns:
            bool: 删除是否成功
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过删除文件文档操作")
            return False
            
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return False

            # 查找指定索引中包含该 file_id 的文档
            # 注意：由于字段是 text 类型，需要使用 match 查询
            query = {
                "match": {"file_id": {"query": file_id, "operator": "and"}}
            }

            # 搜索指定索引中的相关文档
            try:
                results = self.search_documents(index_name, query, size=1000)
            except Exception as e:
                logger.error(f"搜索索引 {index_name} 失败: {e}")
                return False

            if not results:
                logger.info(f"在索引 {index_name} 中未找到文件 {file_id} 相关的文档")
                return True  # 没有文档需要删除，也算成功

            success_count = 0
            total_docs = len(results)

            logger.info(f"找到 {total_docs} 个与文件 {file_id} 相关的文档，开始删除...")

            # 删除找到的所有文档
            for result in results:
                doc_id = result.get("_id")
                if not doc_id:
                    logger.warning(f"文档缺少 _id 字段: {result}")
                    continue

                if self.delete_document(index_name, doc_id):
                    success_count += 1
                    logger.info(f"成功删除文档: {index_name}/{doc_id}")
                else:
                    logger.error(f"删除文档失败: {index_name}/{doc_id}")

            logger.info(f"删除文件 {file_id} 相关文档完成: {success_count}/{total_docs}")

            return success_count == total_docs

        except Exception as e:
            logger.error(f"根据文件ID删除文档失败: {e}")
            return False

    def delete_documents_by_knowledge_id(self, index_name: str, knowledge_id: str) -> bool:
        """
        根据知识库ID删除指定索引中的所有相关文档
        
        Args:
            index_name: 索引名称
            knowledge_id: 知识库ID
            
        Returns:
            bool: 删除是否成功
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过删除知识库文档操作")
            return False
            
        # try:
        """
        根据知识库ID删除指定索引中的所有相关文档

        Args:
            index_name: 索引名称
            knowledge_id: 知识库ID

        Returns:
            bool: 删除是否成功
        """
        try:
            if not self.es:
                logger.error("Elasticsearch 连接未建立")
                return False

            # 检查索引是否存在
            if not self.es.indices.exists(index=index_name):
                logger.info(f"索引 {index_name} 不存在，无需删除知识库 {knowledge_id} 的文档")
                return True  # 索引不存在，没有文档需要删除，返回成功

            # 查找指定索引中包含该 knowledge_id 的文档
            # 注意：由于字段是 text 类型，需要使用 match 查询
            query = {
                "match": {"knowledge_id": {"query": knowledge_id, "operator": "and"}}
            }

            # 搜索指定索引中的相关文档
            results = self.search_documents(index_name, query, size=10000)

            if not results:
                logger.info(f"在索引 {index_name} 中未找到知识库 {knowledge_id} 相关的文档")
                return True  # 没有文档需要删除，也算成功

            success_count = 0
            total_docs = len(results)

            logger.info(f"找到 {total_docs} 个与知识库 {knowledge_id} 相关的文档，开始删除...")

            # 删除找到的所有文档
            for result in results:
                doc_id = result.get("_id")
                if not doc_id:
                    logger.warning(f"文档缺少 _id 字段: {result}")
                    continue

                if self.delete_document(index_name, doc_id):
                    success_count += 1
                    logger.info(f"成功删除文档: {index_name}/{doc_id}")
                else:
                    logger.error(f"删除文档失败: {index_name}/{doc_id}")

            logger.info(f"删除知识库 {knowledge_id} 相关文档完成: {success_count}/{total_docs}")

            return success_count == total_docs

        except Exception as e:
            logger.error(f"根据知识库ID删除文档失败: {e}")
            return False


# 全局实例
es_db = ElasticSearchDB()


def get_elasticsearch_instance() -> ElasticSearchDB:
    """
    获取 Elasticsearch 数据库实例

    Returns:
        ElasticSearchDB: Elasticsearch 数据库实例
    """
    return es_db


# if __name__ == "__main__":
#     # 测试连接
#     es_instance = get_elasticsearch_instance()
#     if es_instance.ping():
#         print("✅ Elasticsearch 连接测试成功")
#     else:
#         print("❌ Elasticsearch 连接测试失败")
