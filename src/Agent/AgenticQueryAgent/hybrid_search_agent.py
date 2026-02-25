# -*- coding:utf-8 -*-
"""
双引擎搜索智能体
通过milvus和Elasticsearch双引擎搜索知识库
"""

from typing import Dict, Any, List
from Control.control_milvus import CControl as ControlMilvus
from Control.control_elastic import CControl as ElasticSearchController
from Config.embedding_config import get_embeddings
from Config.elasticsearch_config import is_elasticsearch_enabled
from Config.milvus_config import is_milvus_enabled


class HybridSearchAgent:
    """双引擎搜索智能体：通过milvus和Elasticsearch搜索知识库"""
    
    def __init__(self):
        self.milvus_controller = ControlMilvus()
        self.elasticsearch_controller = ElasticSearchController()
        self.embedding_model = get_embeddings()
    
    def search(self, knowledge_id: str, query: str, user_id: str = None, 
               top_k: int = 10, permission_flag: bool = True) -> Dict[str, Any]:
        """
        通过双引擎搜索知识库
        
        Args:
            knowledge_id: 知识库ID
            query: 查询文本
            user_id: 用户ID（可选）
            top_k: 返回结果数量
            permission_flag: 权限标志
            
        Returns:
            搜索结果，包含：
            - milvus_results: Milvus搜索结果
            - elasticsearch_results: Elasticsearch搜索结果
            - combined_results: 合并后的结果
        """
        try:
            # Milvus搜索（如果启用）
            milvus_results = []
            if is_milvus_enabled():
                milvus_results = self._search_milvus(knowledge_id, query, user_id, top_k, permission_flag)
            
            # Elasticsearch搜索（如果启用）
            elasticsearch_results = []
            if is_elasticsearch_enabled():
                elasticsearch_results = self._search_elasticsearch(knowledge_id, query, user_id, top_k, permission_flag)
            
            # 合并结果
            combined_results = self._merge_results(milvus_results, elasticsearch_results)
            
            return {
                "success": True,
                "milvus_results": milvus_results,
                "elasticsearch_results": elasticsearch_results,
                "combined_results": combined_results,
                "total_count": len(combined_results)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"双引擎搜索失败: {str(e)}",
                "milvus_results": [],
                "elasticsearch_results": [],
                "combined_results": []
            }
    
    def _search_milvus(self, knowledge_id: str, query: str, user_id: str = None,
                      top_k: int = 10, permission_flag: bool = True) -> List[Dict[str, Any]]:
        """搜索Milvus"""
        try:
            # 检查权限
            flag = True
            if user_id and not self.milvus_controller.check_knowledge_and_user(knowledge_id, user_id):
                flag = False
            
            # 设置搜索参数
            index_params = {
                "index_type": "HNSW",
                "metric_type": "IP",
                "params": {"nlist": 128}
            }
            
            # 执行搜索
            results = self.milvus_controller.search_content(
                knowledge_id, query, self.embedding_model, index_params, top_k, flag
            )
            
            # 格式化结果
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "title": result.get("title", ""),
                    "content": result.get("content", ""),
                    "score": result.get("score", 0.0),
                    "search_engine": "milvus",
                    "id": result.get("id", ""),
                    "partition": result.get("partition", ""),
                    "metadata": result.get("metadata", {})
                })
            
            return formatted_results
            
        except Exception as e:
            import logging
            logging.warning(f"⚠️ Milvus搜索失败: {e}")
            return []
    
    def _search_elasticsearch(self, knowledge_id: str, query: str, user_id: str = None,
                             top_k: int = 10, permission_flag: bool = True) -> List[Dict[str, Any]]:
        """搜索Elasticsearch"""
        try:
            # 执行搜索
            results = self.elasticsearch_controller.search_similar_documents(
                knowledge_id=knowledge_id,
                user_id=user_id or "",
                permission_flag=permission_flag,
                query_text=query,
                size=top_k
            )
            
            # 格式化结果
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "title": result.get("title", ""),
                    "content": result.get("content", ""),
                    "score": result.get("_score", 0.0),
                    "search_engine": "elasticsearch",
                    "id": result.get("_id", ""),
                    "metadata": {
                        "file_id": result.get("file_id", ""),
                        "file_name": result.get("file_name", ""),
                        "knowledge_id": result.get("knowledge_id", "")
                    }
                })
            
            return formatted_results
            
        except Exception as e:
            import logging
            logging.warning(f"⚠️ Elasticsearch搜索失败: {e}")
            return []
    
    def _merge_results(self, milvus_results: List[Dict[str, Any]], 
                      elasticsearch_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并两个搜索引擎的结果"""
        combined = []
        seen_ids = set()
        
        # 添加Milvus结果
        for result in milvus_results:
            result_id = result.get("id") or result.get("partition", "")
            if result_id and result_id not in seen_ids:
                combined.append(result)
                seen_ids.add(result_id)
        
        # 添加Elasticsearch结果（去重）
        for result in elasticsearch_results:
            result_id = result.get("id", "")
            if result_id and result_id not in seen_ids:
                combined.append(result)
                seen_ids.add(result_id)
        
        # 按评分排序
        combined.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        
        return combined
