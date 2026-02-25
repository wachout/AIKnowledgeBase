# -*- coding:utf-8 -*-

import time

from typing import List, Dict, Any
from Agent.emb_graph_chat_run import emb_graph_chat_run
from Agent.emb_query_run import run_agent
from Agent.emb_graph_chat_run import emb_graph_chat_stream_run
from Agent import entity_relation_split_run
import logging
import threading

# 搜索相关模块
from Config.embedding_config import get_embeddings
from Control.control_milvus import CControl as MilvusController
from Control.control_graph import CControl as ControlGraph
from Control.control_elastic import get_elastic_controller
from Db.sqlite_db import cSingleSqlite
from Emb.xinference_embedding import cSingleEmb
from Utils import utils

# 创建线程安全的logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 设置日志级别
logger_lock = threading.Lock()

def thread_safe_log(level_func, message, *args, **kwargs):
    """线程安全的日志记录函数"""
    with logger_lock:
        level_func(message, *args, **kwargs)

class CControl():
    
    def __init__(self):
        self.milvus_obj = MilvusController()
        self.graph_obj = ControlGraph()
        
    def search_graph_emb(self, query_text, graph_data, milvus_data):
        print("query_text:", query_text)
        print("graph_data:", graph_data)
        print("milvus_data:", milvus_data)
        result = emb_graph_chat_run(query_text, graph_data, milvus_data)
        print("最终结果:", result)
        return result
    
    def search_emb(self, query_text, database_code, index_params, limit):
        chat_history = []
        result = run_agent(query_text, chat_history, database_code, index_params, limit)
        return result
        
    def stream_openai_chat(self, query_text, graph_data, milvus_data):
        """
        实现stream_openai_chat方法，提供与OpenAI兼容的流式聊天接口
        """
        logger.info(f"stream_openai_chat called with query_text: {query_text}")
        logger.info(f"graph_data: {graph_data}")
        logger.info(f"milvus_data: {milvus_data}")
        
        # 使用现有的emb_graph_chat_stream_run方法
        logger.info("Calling emb_graph_chat_stream_run")
        stream_result = emb_graph_chat_stream_run(query_text, graph_data, milvus_data)
        logger.info(f"emb_graph_chat_stream_run returned: {type(stream_result)}")
        
        # 包装结果以符合OpenAI格式
        
        _id = f"chatcmpl-{int(time.time())}"
        created = int(time.time())
        model = "emb-graph-chat-model"
        
        chunk_count = 0
        has_data = False
        # 逐个yield符合OpenAI格式的数据块，{'content': '', 'additional_kwargs': {}, 'id': 'run--88fb5a1b-6ca5-450b-ae11-278c87f9e463'}
        for chunk in stream_result:
            chunk_count += 1
            has_data = True
            logger.info(f"Processing chunk #{chunk_count} in stream_openai_chat: {chunk}")
            if("id" in chunk.keys()):
                _id = chunk["id"]
            yield {
                "id": _id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "content": chunk["content"],
                            "type": "text"
                        },
                        "finish_reason": None
                    }
                ]
            }
        
        # 如果没有数据，记录警告
        if not has_data:
            logger.warning("No data received from emb_graph_chat_stream_run")
            yield {
                "id": _id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "content": "No data returned from chat processing",
                            "type": "text"
                        },
                        "finish_reason": None
                    }
                ]
            }
        else:
            logger.info(f"Total chunks processed in stream_openai_chat: {chunk_count}")
        
        # 发送结束标记
        logger.info("Sending finish message")
        yield {
            "id": _id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": "",
                        "type": "text"
                    },
                    "finish_reason": "stop"
                }
            ]
        }
        logger.info("Finish message sent")
    
    def process_text_knowledge(self, text_knowledge: List[Dict[str, Any]]) -> str:
        """处理文本知识库数据 - 保留完整文本段落"""
        processed_content = []
        for item in text_knowledge:
            title = item.get("title", "未知标题")
            content = item.get("content", "")
            score = item.get("score", 0.0)
            
            # 保留完整文本，包括可能包含表格、图片及其说明的内容
            processed_item = f"标题: {title}\n相关度: {score}\n内容:\n{content}"
            processed_content.append(processed_item)
        
        return "\n\n".join(processed_content)
    
    def process_graph_knowledge(self, graph_knowledge: List[List[Dict[str, Any]]]) -> str:
        """处理图数据库知识"""
        processed_content = []
        
        for edge_group in graph_knowledge:
            for edge in edge_group:
                # 提取实体信息
                start_node = edge.get("start_node", {})
                end_node = edge.get("end_node", {})
                relation = edge.get("relation", {})
                
                # 构建实体关系表示
                start_entity = f"实体1: {start_node.get('entity_id', '未知')} ({start_node.get('entity_type', '未知类型')})"
                end_entity = f"实体2: {end_node.get('entity_id', '未知')} ({end_node.get('entity_type', '未知类型')})"
                
                # 提取关系描述
                relation_desc = relation.get('description', '')
                relation_keywords = relation.get('keywords', '')
                
                # 合并节点描述信息
                start_desc = start_node.get('description', '')
                end_desc = end_node.get('description', '')
                
                # 如果存在chunks信息，将其添加到处理后的内容中
                start_chunks = start_node.get('chunks', [])
                end_chunks = end_node.get('chunks', [])
                start_titles = start_node.get('titles', [])
                end_titles = end_node.get('titles', [])
                
                # 构建完整的关系表示
                graph_item = (
                    f"{start_entity}\n{end_entity}\n关系描述: {relation_desc}\n"
                    f"关系关键词: {relation_keywords}\n"
                )
                
                # 添加节点描述
                if start_desc:
                    graph_item += f"实体1描述: {start_desc}\n"
                if end_desc:
                    graph_item += f"实体2描述: {end_desc}\n"
                
                # 添加chunks信息 - 可能包含表格和图片信息
                if start_chunks:
                    graph_item += f"实体1相关文本段落: {', '.join(start_chunks)}\n"
                if end_chunks:
                    graph_item += f"实体2相关文本段落: {', '.join(end_chunks)}\n"
                if start_titles:
                    graph_item += f"实体1相关文档标题: {', '.join(start_titles)}\n"
                if end_titles:
                    graph_item += f"实体2相关文档标题: {', '.join(end_titles)}\n"
                
                processed_content.append(graph_item)
        
        return "\n\n".join(processed_content)
    
    # ============================================================================
    # Milvus 向量搜索
    # ============================================================================
    
    def check_knowledge_and_user(self, knowledge_id: str, user_id: str) -> bool:
        """检查用户是否有权限访问知识库
        
        Args:
            knowledge_id: 知识库ID
            user_id: 用户ID
            
        Returns:
            是否有权限
        """
        param = {"knowledge_id": knowledge_id, "user_id": user_id}
        result = cSingleSqlite.search_knowledge_base_by_id_and_user_id(param)
        return result
    
    def query_milvus(self, param: Dict[str, Any]) -> List[Dict[str, Any]]:
        """在 Milvus 中搜索向量数据
        
        Args:
            param: 搜索参数
                - query: 查询文本
                - knowledge_id: 知识库ID
                - user_id: 用户ID
                - top_k: 返回结果数量（默认5）
                - metric_type: 度量类型（默认IP）
                - index_type: 索引类型（默认HNSW）
                
        Returns:
            搜索结果列表
        """
        query_text = param["query"]
        database_code = param["knowledge_id"]
        user_id = param["user_id"]
        
        flag = True
        if not self.check_knowledge_and_user(database_code, user_id):
            flag = False
        
        top_k = param.get("top_k", 5)
        metric_type = param.get("metric_type", "IP")
        index_type = param.get("index_type", "HNSW")
        
        index_params = {
            "index_type": index_type,
            "metric_type": metric_type,
            "params": {"nlist": 128}
        }
        
        # 搜索Milvus（如果启用）
        from Config.milvus_config import is_milvus_enabled
        if not is_milvus_enabled():
            logger.debug("Milvus已禁用，跳过搜索操作")
            return []
            
        embedding = get_embeddings()
        result = self.milvus_obj.search_content(database_code, query_text, 
                                                embedding, index_params, 
                                                top_k, flag)
        
        return result
    
    def query_elasticsearch(self, param: Dict[str, Any]) -> List[Dict[str, Any]]:
        """在 Elasticsearch 中搜索文档
        
        Args:
            param: 搜索参数
                - query: 查询文本
                - knowledge_id: 知识库ID
                - user_id: 用户ID
                - flag: 权限标志（默认True）
                - size: 返回结果数量（默认10）
                
        Returns:
            搜索结果列表
        """
        from Config.elasticsearch_config import is_elasticsearch_enabled
        if not is_elasticsearch_enabled():
            return []
            
        try:
            elastic_controller = get_elastic_controller()
            
            query_text = param["query"]
            knowledge_id = param["knowledge_id"]
            user_id = param.get("user_id", "")
            flag = param.get("flag", True)
            size = param.get("size", 10)

            # 搜索文档
            hits = elastic_controller.search_similar_documents(
                knowledge_id=knowledge_id,
                user_id=user_id,
                permission_flag=flag,
                query_text=query_text,
                size=size
            )
            
            # 格式化搜索结果
            results = []
            for hit in hits:
                result = {
                    "title": hit.get("title", ""),
                    "content": hit.get("content", ""),
                    "score": hit.get("_score", hit.get("score", 0)),
                    "source": hit.get("file_name", ""),
                    "search_engine": "elasticsearch",
                    "metadata": {
                        "file_id": hit.get("file_id", ""),
                        "knowledge_id": hit.get("knowledge_id", ""),
                        "permission_level": hit.get("permission_level", ""),
                        "user_id": hit.get("user_id", ""),
                        "create_time": hit.get("create_time", "")
                    }
                }
                file_id = hit.get("file_id", "")
                if file_id:
                    file_detail = cSingleSqlite.search_file_detail_info_by_file_id(file_id)
                    result["file_detail"] = file_detail
                results.append(result)

            return results

        except Exception as e:
            print(f"❌ Elasticsearch搜索失败: {e}")
            return []
    
    def search_milvus_formatted(self, param: Dict[str, Any]) -> List[Dict[str, Any]]:
        """在 Milvus 中搜索并返回统一格式的结果
        
        Args:
            param: 搜索参数
                - query: 查询文本
                - knowledge_id: 知识库ID
                - user_id: 用户ID
                - top_k: 返回结果数量（默认10）
                
        Returns:
            统一格式的搜索结果列表
        """
        results = self.query_milvus(param)
        
        # 格式化为统一格式
        formatted_results = []
        for hit in results:
            result = {
                "title": hit.get("title", ""),
                "content": hit.get("content", ""),
                "score": hit.get("score", hit.get("distance", 0)),
                "source": hit.get("source", ""),
                "search_engine": "milvus",
                "metadata": hit.get("metadata", {}),
            }
            doc_id = hit.get("partition", "")
            if doc_id:
                file_detail = cSingleSqlite.search_file_detail_info_by_file_id(doc_id)
                result["file_detail"] = file_detail
            formatted_results.append(result)
        
        return formatted_results
    
    # ============================================================================
    # Neo4j 图数据库搜索
    # ============================================================================
    
    def query_graph_neo4j(self, param: Dict[str, Any], merge_result: bool = False):
        """在 Neo4j 图数据库中搜索实体关系
        
        Args:
            param: 搜索参数
                - query: 查询文本
                - knowledge_id: 知识库ID
                - user_id: 用户ID
            merge_result: 是否合并结果（True返回列表，False返回字典）
            
        Returns:
            图数据搜索结果
        """
        from Config.neo4j_config import is_neo4j_enabled
        if not is_neo4j_enabled():
            if not merge_result:
                return {"error_code": 7, "error_msg": "Neo4j is disabled."}
            else:
                return []
                
        if "query" not in param.keys():
            if not merge_result:
                return {"error_code": 3, "error_msg": "Error, lack of query."}
            else:
                return []
                
        query_text = param["query"]
        knowledge_id = param.get("knowledge_id")
        user_id = param.get("user_id")
        
        # 实体关系抽取
        key_word_json = entity_relation_split_run.entity_relation_split_run(query_text)
        
        if "decomposed_query" not in key_word_json.keys():
            if not merge_result:
                return {"error_code": 4, "error_msg": "Error, the decomposed_query is not exist."}
            else:
                return []
        if "entities" not in key_word_json["decomposed_query"].keys():
            if not merge_result:
                return {"error_code": 5, "error_msg": "Error, the entities is not exist."}
            else:
                return []
                
        flag = True
        if not self.check_knowledge_and_user(knowledge_id, user_id):
            flag = False

        entities = key_word_json.get("decomposed_query", {}).get("entities", [])
        keywords = key_word_json.get("decomposed_query", {}).get("keywords", [])
        entities.extend(keywords)
        if len(entities) == 0:
            if not merge_result:
                return {"error_code": 6, "error_msg": "Error, the entities is empty."}
            else:
                return []
        
        # 实体匹配和筛选
        entity_list = []
        for _e in entities:
            param_query = {"knowledge_id": knowledge_id, "entity_name": _e}
            _e_em = cSingleEmb.embeddings.embed_query(_e)
            if flag is False:
                _entity = cSingleSqlite.query_graph_node_by_node_name_public(param_query)
            else:
                param_query = {"entity_name": _e, "knowledge_id": knowledge_id}
                _entity = cSingleSqlite.query_graph_node_by_node_name(param_query)
            if _entity is not None and len(_entity) > 0:
                en_lt = []
                for _en in _entity:
                    if _en["entity_name"] not in entity_list:
                        en_lt.append(_en["entity_name"])
            
                emb_list = cSingleEmb.embeddings.embed_documents(en_lt)
                key_list = []
                for i in range(len(en_lt)):
                    _emb = emb_list[i]
                    score = utils.cos_sim(_e_em, _emb)
                    key_list.append({"entity": en_lt[i], "score": score})
                key_list = sorted(key_list, key=lambda x: x["score"], reverse=True)
                if len(key_list) > 2:
                    key_list = key_list[0:2]
                entity_list.extend([k["entity"] for k in key_list])
        
        if len(entity_list) == 0:
            if not merge_result:
                return {"error_code": 6, "error_msg": "Error, the entities is empty."}
            else:
                return []
        
        # 执行 Cypher 查询
        graph_data = []
        for entity in entity_list:
            if flag:
                cypher_query = """MATCH (start_node {entity_id: '"""+entity+"""'})-[relation]-(end_node) RETURN start_node, relation, end_node"""
            else:
                cypher_query = """MATCH (start_node {entity_id: '"""+entity+"""', permission_level: 'public'})-[relation]-(end_node {permission_level: 'public'}) RETURN start_node, relation, end_node"""
            cypher_result = {"cypher_query": cypher_query}
            if "cypher_query" in cypher_result.keys():
                cypher_query = cypher_result["cypher_query"]
                query_dict = {"cypher_query": cypher_query}
                results = self.graph_obj.execute_query(query_dict)
                
                tmp_list = []
                for _item in results:
                    _tm_d = {}
                    s_node = _item.get("start_node")
                    s_node_d = {}
                    s_node_d["entity_name"] = s_node.get("entity_id", "")
                    s_node_d["entity_type"] = s_node.get("entity_type", "")
                    s_node_d["description"] = s_node.get("description", "")
                    s_node_d["file"] = s_node.get("file_path", "")
                    s_node_d["created_at"] = s_node.get("created_at", "")
                    s_node_d["source_id"] = s_node.get("source_id", "")
                    
                    if "source_id" in s_node_d.keys():
                        chunk_param = {"chunk_id": s_node_d["source_id"],
                                 "knowledge_id": knowledge_id}
                        chunk_list = []
                        if "<SEP>" in s_node_d["source_id"]:
                            source_id_lt = s_node_d["source_id"].split("<SEP>")
                            for source_id in source_id_lt:
                                chunk_param = {"chunk_id": source_id,
                                     "knowledge_id": knowledge_id}
                                chunk_lt = cSingleSqlite.query_graph_chunk_by_chunk_id_and_knowledge_id(chunk_param)
                                for _ch in chunk_lt:
                                    chunk_list.append(_ch)
                        else:
                            chunk_list = cSingleSqlite.query_graph_chunk_by_chunk_id_and_knowledge_id(chunk_param) 
                        s_node_d["chunks"] = [chunk["chunk_text"] for chunk in chunk_list]
                        s_node_d["titles"] = [chunk["chunk_summary"] for chunk in chunk_list]
                       
                        s_node_d.pop("source_id")
                    
                    if "created_at" in s_node_d.keys():
                        s_node_d.pop("created_at")
                    _tm_d["start_node"] = s_node_d
                    
                    r_node = _item.get("relation")
                    r_node_d = {}
                    r_node_d["description"] = r_node.get("description", "")
                    r_node_d["keywords"] = r_node.get("keywords", "")
                    r_node_d["file_path"] = r_node.get("file_path", "")
                    r_node_d["source_id"] = r_node.get("source_id", "")
                    r_node_d["weight"] = r_node.get("weight", 1.0)
                    if "source_id" in r_node_d.keys():
                        r_node_d.pop("source_id")
                    _tm_d["relation"] = r_node_d
                    
                    e_node = _item.get("end_node")
                    e_node_d = {}
                    e_node_d["entity_name"] = e_node.get("entity_id", "")
                    e_node_d["entity_type"] = e_node.get("entity_type", "")
                    e_node_d["description"] = e_node.get("description", "")
                    e_node_d["file"] = e_node.get("file_path", "")
                    e_node_d["created_at"] = e_node.get("created_at", "")
                    e_node_d["source_id"] = e_node.get("source_id", "")
                    if "source_id" in e_node_d.keys():
                        
                        chunk_param = {"chunk_id": e_node_d["source_id"],
                                 "knowledge_id": knowledge_id}
                        chunk_list = []
                        if "<SEP>" in e_node_d["source_id"]:
                            source_id_lt = e_node_d["source_id"].split("<SEP>")
                            for source_id in source_id_lt:
                                chunk_param = {"chunk_id": source_id,
                                     "knowledge_id": knowledge_id}
                                chunk_lt = cSingleSqlite.query_graph_chunk_by_chunk_id_and_knowledge_id(chunk_param)
                                for _ch in chunk_lt:
                                    chunk_list.append(_ch)
                        else:
                            chunk_list = cSingleSqlite.query_graph_chunk_by_chunk_id_and_knowledge_id(chunk_param)
                        
                        e_node_d["chunks"] = [chunk["chunk_text"] for chunk in chunk_list]
                        e_node_d["titles"] = [chunk["chunk_summary"] for chunk in chunk_list]
                        
                        e_node_d.pop("source_id")
                        
                    if "created_at" in e_node_d.keys():
                        e_node_d.pop("created_at")
                    _tm_d["end_node"] = e_node_d
                    
                    tmp_list.append(_tm_d)
                if len(tmp_list) > 0:
                    graph_data.append(tmp_list)
                    
        if not merge_result:
            return {"error_code": 0, "error_msg": "Success", "data": graph_data}
        else:
            return graph_data
    
    def search_graph_data(self, param: Dict[str, Any]) -> List[Dict[str, Any]]:
        """在图数据中搜索相关内容，并计算相关性分数
        
        Args:
            param: 搜索参数
                - query: 查询文本
                - knowledge_id: 知识库ID
                - user_id: 用户ID
                
        Returns:
            图数据搜索结果列表
        """
        import re
        
        try:
            print("🕸️ 执行图数据搜索...")
            
            # 使用 query_graph_neo4j 获取图数据
            graph_data = self.query_graph_neo4j(param, merge_result=True)

            if not graph_data:
                print("⚠️ 没有获取到图数据")
                return []

            results = []
            query_text = param.get("query", "")
            query_lower = query_text.lower()

            # 遍历所有图关系
            for relation_group in graph_data:
                for relation in relation_group:
                    try:
                        start_node = relation.get("start_node", {})
                        end_node = relation.get("end_node", {})
                        relation_info = relation.get("relation", {})

                        # 提取相关文本进行匹配
                        texts_to_search = []
                        media_info = {
                            "images": [],
                            "tables": []
                        }

                        # 节点描述
                        if start_node.get("description"):
                            texts_to_search.append(start_node["description"])
                        if end_node.get("description"):
                            texts_to_search.append(end_node["description"])

                        # 关系描述
                        if relation_info.get("description"):
                            texts_to_search.append(relation_info["description"])

                        # 关系关键词
                        if relation_info.get("keywords"):
                            texts_to_search.append(relation_info["keywords"])

                        # 处理chunks内容
                        for node in [start_node, end_node]:
                            chunks = node.get("chunks", [])
                            titles = node.get("titles", [])

                            for i, chunk in enumerate(chunks):
                                if isinstance(chunk, str) and chunk not in ["chunk1", "chunk2"]:
                                    texts_to_search.append(chunk)

                                    # 提取图片信息
                                    img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', chunk, re.IGNORECASE)
                                    media_info["images"].extend(img_matches)

                                    http_matches = re.findall(r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp|bmp|svg)(?:\?[^\s]*)?', chunk, re.IGNORECASE)
                                    media_info["images"].extend(http_matches)

                                    # 提取表格信息
                                    if '<table' in chunk or '<tr' in chunk:
                                        clean_table = re.sub(r'<[^>]+>', ' | ', chunk)
                                        clean_table = re.sub(r'\s+', ' ', clean_table).strip()
                                        if len(clean_table) > 20:
                                            media_info["tables"].append({
                                                "content": clean_table[:1000],
                                                "title": titles[i] if i < len(titles) and titles[i] != f"title{i+1}" else f"表格{i+1}"
                                            })

                        # 计算相关性分数
                        max_score = 0
                        for text in texts_to_search:
                            if not isinstance(text, str):
                                continue

                            text_lower = text.lower()
                            score = 0
                            query_words = query_lower.split()

                            for word in query_words:
                                if word in text_lower:
                                    score += 1

                            if score > 1:
                                score *= 1.5

                            if score > max_score:
                                max_score = score

                        # 如果找到相关内容
                        if max_score > 0:
                            result = {
                                "search_engine": "graph_data",
                                "title": f"图关系: {start_node.get('entity_id', '未知')} → {end_node.get('entity_id', '未知')}",
                                "content": f"关系描述: {relation_info.get('description', '无描述')}\n\n起始节点: {start_node.get('entity_id', '未知')} ({start_node.get('entity_type', '未知类型')})\n{start_node.get('description', '')[:200]}...\n\n结束节点: {end_node.get('entity_id', '未知')} ({end_node.get('entity_type', '未知类型')})\n{end_node.get('description', '')[:200]}...",
                                "score": max_score,
                                "combined_score": max_score,
                                "graph_relation": {
                                    "start_node": {
                                        "entity_id": start_node.get("entity_id"),
                                        "entity_type": start_node.get("entity_type"),
                                        "description": start_node.get("description", ""),
                                        "chunks": start_node.get("chunks", []),
                                        "titles": start_node.get("titles", [])
                                    },
                                    "end_node": {
                                        "entity_id": end_node.get("entity_id"),
                                        "entity_type": end_node.get("entity_type"),
                                        "description": end_node.get("description", ""),
                                        "chunks": end_node.get("chunks", []),
                                        "titles": end_node.get("titles", [])
                                    },
                                    "relation": {
                                        "description": relation_info.get("description", ""),
                                        "keywords": relation_info.get("keywords", ""),
                                        "weight": relation_info.get("weight", 0)
                                    }
                                },
                                "metadata": {
                                    "start_entity": start_node.get("entity_id"),
                                    "end_entity": end_node.get("entity_id"),
                                    "relation_type": "graph_relation",
                                    "has_images": len(media_info["images"]) > 0,
                                    "has_tables": len(media_info["tables"]) > 0,
                                    "image_count": len(media_info["images"]),
                                    "table_count": len(media_info["tables"])
                                },
                                "media_content": media_info
                            }
                            results.append(result)

                    except Exception as e:
                        print(f"⚠️ 处理图关系时出错: {e}")
                        continue

            # 按分数排序
            results.sort(key=lambda x: x.get("score", 0), reverse=True)

            # 限制结果数量
            results = results[:10]

            print(f"✅ 图数据搜索完成，获得 {len(results)} 个结果")
            return results

        except Exception as e:
            print(f"❌ 图数据搜索异常: {e}")
            return []
    
