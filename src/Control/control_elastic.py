"""
Elasticsearch 控制层
提供对 Elasticsearch 数据库的高级操作和业务逻辑封装
"""

import json
import time
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from Db.elastic_db import get_elasticsearch_instance, ElasticSearchDB
from Config.elasticsearch_config import is_elasticsearch_enabled
from Config.embedding_config import get_embeddings, get_vector_length
import logging

logger = logging.getLogger(__name__)


class CControl():
    """Elasticsearch 控制层"""

    def __init__(self):
        """初始化控制器"""
        self.enabled = is_elasticsearch_enabled()
        if self.enabled:
            self.es_db: ElasticSearchDB = get_elasticsearch_instance()
            # 初始化 embedding 模型用于生成向量
            try:
                self.embeddings = get_embeddings()
                self.vector_dimension = get_vector_length()
                logger.info(f"Elasticsearch 向量搜索已启用，向量维度: {self.vector_dimension}")
            except Exception as e:
                logger.warning(f"无法初始化 embedding 模型: {e}，将仅使用全文搜索")
                self.embeddings = None
                self.vector_dimension = None
        else:
            self.es_db = None
            self.embeddings = None
            self.vector_dimension = None
            logger.info("Elasticsearch已禁用（ELASTICSEARCG_FLAG=False），跳过初始化")
        self.index_name = "knowledge_base"  # 默认索引名称

    def split_text_with_overlap(self, text: str, chunk_size: int = 1024, overlap: int = 128) -> List[Dict[str, Any]]:
        """
        将长文本分割成重叠的段落

        Args:
            text: 原始文本
            chunk_size: 每个段落的字符数
            overlap: 段落之间的重叠字符数

        Returns:
            List[Dict[str, Any]]: 段落列表，每个包含文本内容和位置信息
        """
        if not text or len(text) <= chunk_size:
            return [{
                "content": text,
                "start_pos": 0,
                "end_pos": len(text),
                "chunk_index": 0,
                "total_chunks": 1
            }]

        chunks = []
        start = 0
        chunk_index = 0
        text_length = len(text)

        while start < text_length:
            # 计算结束位置
            end = min(start + chunk_size, text_length)

            # 如果不是最后一段，尝试在句子边界结束
            if end < text_length:
                # 寻找最近的句子结束符
                sentence_endings = ['。', '！', '？', '\n', '. ', '! ', '? ']
                best_end = end

                for ending in sentence_endings:
                    last_ending = text.rfind(ending, start, end + 50)
                    if last_ending != -1 and last_ending > start + chunk_size // 2:
                        best_end = last_ending + len(ending)
                        break

                end = min(best_end, text_length)

            # 提取段落内容
            chunk_content = text[start:end]
            chunks.append({
                "content": chunk_content.strip(),
                "start_pos": start,
                "end_pos": end,
                "chunk_index": chunk_index,
                "total_chunks": 0  # 稍后更新
            })

            chunk_index += 1

            # 计算下一个起始位置（考虑重叠）
            start = max(end - overlap, start + 1)

            # 防止无限循环
            if start >= text_length:
                break

        # 更新总段落数
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk["total_chunks"] = total_chunks

        return chunks

    def set_index_name(self, index_name: str):
        """
        设置索引名称

        Args:
            index_name: 索引名称
        """
        self.index_name = index_name

    def save_document_to_elastic(self, knowledge_id: str, file_id: str,
                                user_id: str, permission_level: str,
                                title: str, content: str, **kwargs) -> bool:
        """
        保存文档到 Elasticsearch

        Args:
            knowledge_id: 知识库ID
            file_id: 文件ID
            user_id: 用户ID
            permission_level: 权限级别
            title: 文档标题
            content: 文档内容
            **kwargs: 其他可选字段

        Returns:
            bool: 保存是否成功
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过保存文档操作")
            return False
            
        try:
            # 生成文档ID (基于文件ID和知识库ID)
            doc_id = f"{knowledge_id}_{file_id}"

            # 构建文档
            document = {
                "knowledge_id": knowledge_id,
                "file_id": file_id,
                "user_id": user_id,
                "permission_level": permission_level,
                "title": title,
                "content": content,
                "upload_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            }

            # 添加可选字段
            for key, value in kwargs.items():
                if value is not None:
                    document[key] = value

            # 计算内容哈希，用于去重
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            document["content_hash"] = content_hash

            # 保存到 Elasticsearch
            success = self.es_db.index_document(self.index_name, doc_id, document)

            if success:
                logger.info(f"文档 {doc_id} 保存到 Elasticsearch 成功")
            else:
                logger.error(f"文档 {doc_id} 保存到 Elasticsearch 失败")

            return success

        except Exception as e:
            logger.error(f"保存文档到 Elasticsearch 失败: {e}")
            return False

    def save_markdown_content(self, knowledge_id: str, file_id: str,
                             user_id: str, permission_level: str,
                             file_name: str, markdown_content: str,
                             summary: str = "", authors: str = "",
                             category: str = "") -> bool:
        """
        保存 Markdown 内容到 Elasticsearch（支持文本分段和父子关系）

        Args:
            knowledge_id: 知识库ID
            file_id: 文件ID
            user_id: 用户ID
            permission_level: 权限级别
            file_name: 文件名
            markdown_content: Markdown 内容
            summary: 摘要
            authors: 作者
            category: 分类

        Returns:
            bool: 保存是否成功
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过保存Markdown内容操作")
            return False
            
        try:
            # 1. 保存父文档（文件基本信息）
            parent_doc_id = f"{knowledge_id}_{file_id}"
            parent_document = {
                "knowledge_id": knowledge_id,
                "file_id": file_id,
                "user_id": user_id,
                "permission_level": permission_level,
                "title": file_name,
                "content": markdown_content[:2000] if len(markdown_content) > 2000 else markdown_content,  # 父文档只保存部分内容
                "full_content_length": len(markdown_content),
                "summary": summary,
                "authors": authors,
                "category": category,
                "upload_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "doc_type": "parent",  # 标记为父文档
                "has_children": True
            }

            # 计算父文档内容哈希
            content_hash = hashlib.md5(markdown_content.encode('utf-8')).hexdigest()
            parent_document["content_hash"] = content_hash

            # 生成向量（如果启用）
            if self.embeddings:
                try:
                    # 生成标题向量
                    title_text = file_name
                    # 确保标题是字符串类型且不为空
                    if not isinstance(title_text, str):
                        title_text = str(title_text) if title_text is not None else ""
                    if title_text.strip():
                        parent_document["title_vector"] = self.embeddings.embed_query(title_text)
                    else:
                        logger.warning(f"父文档 {parent_doc_id} 标题为空，跳过标题向量生成")
                    
                    # 生成内容向量（使用前2000字符）
                    content_text = markdown_content[:2000] if len(markdown_content) > 2000 else markdown_content
                    # 确保内容是字符串类型且不为空
                    if not isinstance(content_text, str):
                        content_text = str(content_text) if content_text is not None else ""
                    if content_text.strip():
                        parent_document["content_vector"] = self.embeddings.embed_query(content_text)
                    else:
                        logger.warning(f"父文档 {parent_doc_id} 内容为空，跳过内容向量生成")
                    logger.debug(f"已为父文档 {parent_doc_id} 生成向量")
                except Exception as e:
                    logger.warning(f"生成父文档向量失败: {e}，将仅使用全文搜索")
                    import traceback
                    logger.debug(f"向量生成错误详情: {traceback.format_exc()}")

            # 保存父文档
            parent_success = self.es_db.index_document(self.index_name, parent_doc_id, parent_document)
            if not parent_success:
                logger.error(f"保存父文档失败: {parent_doc_id}")
                return False

            # 2. 分段处理文本内容
            chunks = self.split_text_with_overlap(markdown_content, chunk_size=1024, overlap=128)

            # 3. 保存子文档（各个段落）
            child_documents = []
            for chunk in chunks:
                child_doc_id = f"{parent_doc_id}_chunk_{chunk['chunk_index']}"

                child_document = {
                    "knowledge_id": knowledge_id,
                    "file_id": file_id,
                    "user_id": user_id,
                    "permission_level": permission_level,
                    "title": f"{file_name} (段落 {chunk['chunk_index'] + 1}/{chunk['total_chunks']})",
                    "content": chunk["content"],
                    "chunk_index": chunk["chunk_index"],
                    "total_chunks": chunk["total_chunks"],
                    "start_pos": chunk["start_pos"],
                    "end_pos": chunk["end_pos"],
                    "parent_id": parent_doc_id,  # 父文档ID
                    "summary": summary,
                    "authors": authors,
                    "category": category,
                    "upload_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    "doc_type": "child",  # 标记为子文档
                    "content_hash": hashlib.md5(chunk["content"].encode('utf-8')).hexdigest()
                }

                # 生成向量（如果启用）
                if self.embeddings:
                    try:
                        # 生成标题向量
                        chunk_title = child_document.get("title", "")
                        # 确保标题是字符串类型且不为空
                        if not isinstance(chunk_title, str):
                            chunk_title = str(chunk_title) if chunk_title is not None else ""
                        if chunk_title.strip():
                            child_document["title_vector"] = self.embeddings.embed_query(chunk_title)
                        else:
                            logger.warning(f"子文档 {child_doc_id} 标题为空，跳过标题向量生成")
                        
                        # 生成内容向量
                        chunk_content = chunk.get("content", "")
                        # 确保内容是字符串类型且不为空
                        if not isinstance(chunk_content, str):
                            chunk_content = str(chunk_content) if chunk_content is not None else ""
                        if chunk_content.strip():
                            child_document["content_vector"] = self.embeddings.embed_query(chunk_content)
                        else:
                            logger.warning(f"子文档 {child_doc_id} 内容为空，跳过内容向量生成")
                    except Exception as e:
                        logger.warning(f"生成子文档 {child_doc_id} 向量失败: {e}")
                        import traceback
                        logger.debug(f"向量生成错误详情: {traceback.format_exc()}")

                child_documents.append((child_doc_id, child_document))

            # 批量保存子文档
            if child_documents:
                batch_success = self.es_db.bulk_index_documents(self.index_name, child_documents)
                if not batch_success:
                    logger.error(f"批量保存子文档失败: {file_id}")
                    return False

            logger.info(f"成功保存文档 {file_name}: 1个父文档 + {len(child_documents)}个子文档")
            return True

        except Exception as e:
            logger.error(f"保存 Markdown 内容失败: {e}")
            return False

    def search_documents(self, knowledge_id: str, user_id: str,
                        permission_flag: bool, search_query: str = "",
                        size: int = 10, use_hybrid_search: bool = True) -> List[Dict[str, Any]]:
        """
        搜索文档（根据权限控制，支持 Hybrid Search）
        
        Elasticsearch 9.2.4+ 支持混合搜索，结合全文搜索和AI驱动的向量搜索

        Args:
            knowledge_id: 知识库ID
            user_id: 用户ID
            permission_flag: 权限标志 (True: 可访问所有, False: 仅公开)
            search_query: 搜索查询内容
            size: 返回结果数量
            use_hybrid_search: 是否使用混合搜索（默认True）

        Returns:
            List[Dict[str, Any]]: 搜索结果列表
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过搜索文档操作")
            return []
            
        try:
            # 如果启用混合搜索，生成查询向量
            query_vector = None
            if use_hybrid_search and search_query and self.embeddings:
                try:
                    # 确保查询文本是字符串类型且不为空
                    if not isinstance(search_query, str):
                        search_query = str(search_query) if search_query is not None else ""
                    if search_query.strip():
                        query_vector = self.embeddings.embed_query(search_query)
                        logger.debug(f"已生成查询向量，维度: {len(query_vector)}")
                    else:
                        logger.warning("查询文本为空，跳过向量生成")
                        use_hybrid_search = False
                except Exception as e:
                    logger.warning(f"生成查询向量失败: {e}，将仅使用全文搜索")
                    import traceback
                    logger.debug(f"向量生成错误详情: {traceback.format_exc()}")
                    use_hybrid_search = False
            
            results = self.es_db.search_by_knowledge_and_permission(
                index_name=self.index_name,
                knowledge_id=knowledge_id,
                user_id=user_id,
                permission_flag=permission_flag,
                search_query=search_query,
                size=size,
                use_hybrid_search=use_hybrid_search,
                query_vector=query_vector
            )
            logger.info(f"搜索完成，返回 {len(results)} 个结果（混合搜索: {use_hybrid_search}）")
            return results

        except Exception as e:
            logger.error(f"搜索文档失败: {e}")
            return []

    def get_document_by_id(self, knowledge_id: str, file_id: str) -> Optional[Dict[str, Any]]:
        """
        根据知识库ID和文件ID获取文档

        Args:
            knowledge_id: 知识库ID
            file_id: 文件ID

        Returns:
            Optional[Dict[str, Any]]: 文档内容
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过获取文档操作")
            return None
            
        doc_id = f"{knowledge_id}_{file_id}"
        return self.es_db.get_document(self.index_name, doc_id)

    def update_document(self, knowledge_id: str, file_id: str,
                       updates: Dict[str, Any]) -> bool:
        """
        更新文档

        Args:
            knowledge_id: 知识库ID
            file_id: 文件ID
            updates: 更新内容

        Returns:
            bool: 更新是否成功
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过更新文档操作")
            return False
            
        doc_id = f"{knowledge_id}_{file_id}"
        return self.es_db.update_document(self.index_name, doc_id, updates)

    def delete_document(self, knowledge_id: str, file_id: str) -> bool:
        """
        删除文档

        Args:
            knowledge_id: 知识库ID
            file_id: 文件ID

        Returns:
            bool: 删除是否成功
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过删除文档操作")
            return False
            
        doc_id = f"{knowledge_id}_{file_id}"
        return self.es_db.delete_document(self.index_name, doc_id)

    def get_knowledge_documents(self, knowledge_id: str, user_id: str,
                               permission_flag: bool, size: int = 100) -> List[Dict[str, Any]]:
        """
        获取知识库中的所有文档（根据权限）

        Args:
            knowledge_id: 知识库ID
            user_id: 用户ID
            permission_flag: 权限标志
            size: 返回结果数量

        Returns:
            List[Dict[str, Any]]: 文档列表
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过获取知识库文档操作")
            return []
            
        # 使用空的搜索查询来获取所有文档
        return self.search_documents(knowledge_id, user_id, permission_flag, "", size)

    def search_similar_documents(self, knowledge_id: str, user_id: str,
                                permission_flag: bool, query_text: str,
                                size: int = 10) -> List[Dict[str, Any]]:
        """
        搜索相似文档

        Args:
            knowledge_id: 知识库ID
            user_id: 用户ID
            permission_flag: 权限标志
            query_text: 查询文本
            size: 返回结果数量

        Returns:
            List[Dict[str, Any]]: 相似文档列表
        """
        if not self.enabled:
            logger.debug("Elasticsearch已禁用，跳过搜索相似文档操作")
            return []
            
        return self.search_documents(knowledge_id, user_id, permission_flag, query_text, size)

    def get_document_with_chunks(self, knowledge_id: str, file_id: str) -> Optional[Dict[str, Any]]:
        """
        获取文档及其所有段落信息

        Args:
            knowledge_id: 知识库ID
            file_id: 文件ID

        Returns:
            Optional[Dict[str, Any]]: 包含父文档和所有子文档的信息
        """
        try:
            parent_doc_id = f"{knowledge_id}_{file_id}"

            # 获取父文档
            parent_doc = self.es_db.get_document(self.index_name, parent_doc_id)
            if not parent_doc:
                return None

            # 获取所有子文档
            child_docs = self.es_db.get_child_documents(self.index_name, parent_doc_id)

            return {
                "parent_document": parent_doc,
                "child_documents": child_docs,
                "total_chunks": len(child_docs)
            }

        except Exception as e:
            logger.error(f"获取文档段落信息失败: {e}")
            return None

    def search_with_context(self, knowledge_id: str, user_id: str, permission_flag: bool,
                          search_query: str, context_size: int = 1, size: int = 10) -> List[Dict[str, Any]]:
        """
        搜索文档并提供上下文信息（前后段落）

        Args:
            knowledge_id: 知识库ID
            user_id: 用户ID
            permission_flag: 权限标志
            search_query: 搜索查询
            context_size: 上下文段落数量
            size: 返回结果数量

        Returns:
            List[Dict[str, Any]]: 包含上下文的搜索结果
        """
        try:
            # 先进行普通搜索
            results = self.search_documents(knowledge_id, user_id, permission_flag, search_query, size)

            # 为每个结果添加上下文信息
            enriched_results = []
            for result in results:
                enriched_result = result.copy()

                # 如果是子文档，获取上下文段落
                if result.get("doc_type") == "child" and result.get("parent_id"):
                    parent_id = result["parent_id"]
                    chunk_index = result.get("chunk_index", 0)

                    # 获取所有相关段落
                    child_docs = self.es_db.get_child_documents(self.index_name, parent_id)

                    # 按chunk_index排序
                    child_docs.sort(key=lambda x: x.get("chunk_index", 0))

                    # 获取上下文段落
                    context_chunks = []
                    start_idx = max(0, chunk_index - context_size)
                    end_idx = min(len(child_docs), chunk_index + context_size + 1)

                    for i in range(start_idx, end_idx):
                        chunk = child_docs[i]
                        context_chunks.append({
                            "index": i,
                            "content": chunk.get("content", ""),
                            "is_target": (i == chunk_index)
                        })

                    enriched_result["context_chunks"] = context_chunks
                    enriched_result["has_context"] = True
                else:
                    enriched_result["has_context"] = False

                enriched_results.append(enriched_result)

            return enriched_results

        except Exception as e:
            logger.error(f"上下文搜索失败: {e}")
            return results  # 返回原始结果

    def get_document_stats(self, knowledge_id: str = None) -> Dict[str, Any]:
        """
        获取文档统计信息

        Args:
            knowledge_id: 知识库ID（可选，如果提供则统计特定知识库）

        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            if knowledge_id:
                # 统计特定知识库（注意：字段是 text 类型，使用 match 查询）
                query = {"match": {"knowledge_id": {"query": knowledge_id, "operator": "and"}}}
                total_docs = self.es_db.get_document_count(self.index_name, query)

                # 统计公开文档数量
                public_query = {
                    "bool": {
                        "must": [
                            {"match": {"knowledge_id": {"query": knowledge_id, "operator": "and"}}},
                            {"match": {"permission_level": {"query": "public", "operator": "and"}}}
                        ]
                    }
                }
                public_docs = self.es_db.get_document_count(self.index_name, public_query)

                # 统计私有文档数量
                private_query = {
                    "bool": {
                        "must": [
                            {"match": {"knowledge_id": {"query": knowledge_id, "operator": "and"}}},
                            {"match": {"permission_level": {"query": "private", "operator": "and"}}}
                        ]
                    }
                }
                private_docs = self.es_db.get_document_count(self.index_name, private_query)

                return {
                    "knowledge_id": knowledge_id,
                    "total_documents": total_docs,
                    "public_documents": public_docs,
                    "private_documents": private_docs
                }
            else:
                # 统计所有文档
                total_docs = self.es_db.get_document_count(self.index_name)
                return {
                    "total_documents": total_docs
                }

        except Exception as e:
            logger.error(f"获取文档统计失败: {e}")
            return {"error": str(e)}

    def batch_save_documents(self, documents: List[Tuple[str, str, Dict[str, Any]]]) -> bool:
        """
        批量保存文档

        Args:
            documents: 文档列表 [(knowledge_id, file_id, document_data), ...]

        Returns:
            bool: 批量保存是否成功
        """
        try:
            bulk_docs = []
            for knowledge_id, file_id, doc_data in documents:
                doc_id = f"{knowledge_id}_{file_id}"
                bulk_docs.append((doc_id, doc_data))

            return self.es_db.bulk_index_documents(self.index_name, bulk_docs)

        except Exception as e:
            logger.error(f"批量保存文档失败: {e}")
            return False

    def check_knowledge_and_user(self, knowledge_id: str, user_id: str) -> bool:
        """
        检查用户是否有权限访问知识库

        Args:
            knowledge_id: 知识库ID
            user_id: 用户ID

        Returns:
            bool: True 表示有权限访问所有数据，False 表示只能访问公开数据
        """
        # 这里可以根据实际业务逻辑实现权限检查
        # 例如：检查用户是否是知识库的创建者或协作者
        # 目前简化为：检查知识库ID是否以用户ID开头（表示用户创建的知识库）

        # 实际实现应该查询数据库检查用户权限
        # 这里提供一个示例实现
        try:
            # 示例：如果知识库ID包含用户ID，则认为用户有完全访问权限
            return user_id in knowledge_id or knowledge_id.startswith(f"kb_{user_id}")
        except Exception as e:
            logger.error(f"权限检查失败: {e}")
            return False

    def reindex_document(self, knowledge_id: str, file_id: str) -> bool:
        """
        重新索引文档（用于更新索引结构后）

        Args:
            knowledge_id: 知识库ID
            file_id: 文件ID

        Returns:
            bool: 重新索引是否成功
        """
        try:
            # 获取现有文档
            doc = self.get_document_by_id(knowledge_id, file_id)
            if not doc:
                logger.warning(f"文档不存在，无法重新索引: {knowledge_id}_{file_id}")
                return False

            # 删除旧文档
            self.delete_document(knowledge_id, file_id)

            # 重新保存文档（会自动创建索引）
            doc_id = f"{knowledge_id}_{file_id}"
            return self.es_db.index_document(self.index_name, doc_id, doc)

        except Exception as e:
            logger.error(f"重新索引文档失败: {e}")
            return False

    def delete_all_elasticsearch(self) -> bool:
        """
        删除 Elasticsearch 中的所有索引和数据

        Returns:
            bool: 删除是否成功
        """
        try:
            logger.info("开始删除所有 Elasticsearch 索引和数据...")
            success = self.es_db.delete_all_indices()
            if success:
                logger.info("✅ 成功删除所有 Elasticsearch 索引和数据")
            else:
                logger.error("❌ 删除所有 Elasticsearch 索引和数据失败")
            return success
        except Exception as e:
            logger.error(f"删除所有 Elasticsearch 数据时出错: {e}")
            return False

    def delete_file_elasticsearch_data(self, file_id: str) -> bool:
        """
        根据文件ID删除 Elasticsearch 中的所有相关数据

        Args:
            file_id: 文件ID

        Returns:
            bool: 删除是否成功
        """
        try:
            logger.info(f"开始删除文件 {file_id} 的 Elasticsearch 数据...")
            success = self.es_db.delete_documents_by_file_id(self.index_name, file_id)
            if success:
                logger.info(f"✅ 成功删除文件 {file_id} 的 Elasticsearch 数据")
            else:
                logger.error(f"❌ 删除文件 {file_id} 的 Elasticsearch 数据失败")
            return success
        except Exception as e:
            logger.error(f"删除文件 {file_id} 的 Elasticsearch 数据时出错: {e}")
            return False

    def delete_knowledge_elasticsearch_data(self, knowledge_id: str) -> bool:
        """
        根据知识库ID删除 Elasticsearch 中的所有相关数据

        Args:
            knowledge_id: 知识库ID

        Returns:
            bool: 删除是否成功
        """
        try:
            logger.info(f"开始删除知识库 {knowledge_id} 的 Elasticsearch 数据...")
            success = self.es_db.delete_documents_by_knowledge_id(self.index_name, knowledge_id)
            if success:
                logger.info(f"✅ 成功删除知识库 {knowledge_id} 的 Elasticsearch 数据")
            else:
                logger.error(f"❌ 删除知识库 {knowledge_id} 的 Elasticsearch 数据失败")
            return success
        except Exception as e:
            logger.error(f"删除知识库 {knowledge_id} 的 Elasticsearch 数据时出错: {e}")
            return False


# 全局实例
elastic_controller = CControl()

def get_elastic_controller() -> CControl:
    """
    获取 Elasticsearch 控制器实例

    Returns:
        ElasticSearchController: Elasticsearch 控制器实例
    """
    return elastic_controller


# if __name__ == "__main__":
#     # 测试连接
#     controller = get_elastic_controller()
#     print("🧪 Elasticsearch 控制层测试")

#     # 测试权限检查
#     flag = controller.check_knowledge_and_user("kb_user123", "user123")
#     print(f"✅ 权限检查结果: {flag}")

#     # 测试文档统计
#     stats = controller.get_document_stats()
#     print(f"📊 文档统计: {stats}")
