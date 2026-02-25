"""
Artifact 处理机制

实现透明化机制：
- 给 AI 看：清洗后的纯文本内容
- 给用户看：带有相关性评分和元数据的原始文档片段（Artifact）
"""

from typing import Dict, Any, List, Optional
import re

class ArtifactHandler:
    """Artifact 处理机制"""
    
    def __init__(self):
        pass
    
    def process_search_results(self, search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        处理搜索结果，分离清洗内容和原始 Artifact
        
        Args:
            search_results: 原始搜索结果
            
        Returns:
            包含清洗内容和 Artifact 的字典：
            {
                "cleaned_content": "清洗后的纯文本（给AI看）",
                "artifacts": [
                    {
                        "content": "原始内容",
                        "score": 0.85,
                        "metadata": {...},
                        "source": "milvus/elasticsearch/graph_data"
                    }
                ]
            }
        """
        cleaned_contents = []
        artifacts = []
        
        for result in search_results:
            # 提取原始内容
            raw_content = result.get("content", "")
            score = result.get("score", result.get("relevance_score", 0.5))
            source = result.get("search_engine", "unknown")
            
            # 提取元数据
            metadata = self._extract_metadata(result)
            
            # 清洗内容（给AI看）
            cleaned_content = self._clean_content(raw_content)
            cleaned_contents.append(cleaned_content)
            
            # 构建 Artifact（给用户看）
            artifact = {
                "content": raw_content,  # 保留原始内容
                "score": score,
                "metadata": metadata,
                "source": source,
                "title": result.get("title", ""),
                "file_id": result.get("file_id") or result.get("doc_id", ""),
                "file_name": metadata.get("file_name", "")
            }
            artifacts.append(artifact)
        
        # 组装清洗后的内容（用于AI处理）
        cleaned_content_text = self._assemble_cleaned_content(cleaned_contents, search_results)
        
        return {
            "cleaned_content": cleaned_content_text,
            "artifacts": artifacts,
            "total_count": len(search_results)
        }
    
    def _clean_content(self, content: str) -> str:
        """
        清洗内容：移除HTML标签、特殊字符等，保留纯文本
        
        Args:
            content: 原始内容
            
        Returns:
            清洗后的纯文本
        """
        if not content:
            return ""
        
        # 移除HTML标签
        cleaned = re.sub(r'<[^>]+>', '', content)
        
        # 移除多余的空白字符
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # 移除特殊控制字符（保留换行）
        cleaned = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', cleaned)
        
        return cleaned.strip()
    
    def _extract_metadata(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """提取元数据"""
        metadata = {}
        
        # 从结果中提取元数据
        if "metadata" in result:
            metadata.update(result["metadata"])
        
        # 从 file_detail 中提取
        if "file_detail" in result:
            file_detail = result["file_detail"]
            metadata.update({
                "file_name": file_detail.get("file_name", ""),
                "recognized_title": file_detail.get("recognized_title", ""),
                "category": file_detail.get("category", ""),
                "tags": file_detail.get("tags", ""),
                "author": file_detail.get("author", "")
            })
        
        # 从 graph_relation 中提取（如果是图数据）
        if "graph_relation" in result:
            graph_relation = result["graph_relation"]
            metadata["graph_relation"] = {
                "start_entity": graph_relation.get("start_node", {}).get("entity_id", ""),
                "end_entity": graph_relation.get("end_node", {}).get("entity_id", ""),
                "relation_description": graph_relation.get("relation", {}).get("description", "")
            }
        
        return metadata
    
    def _assemble_cleaned_content(self, cleaned_contents: List[str], 
                                  search_results: List[Dict[str, Any]]) -> str:
        """
        组装清洗后的内容（用于AI处理）
        
        Args:
            cleaned_contents: 清洗后的内容列表
            search_results: 原始搜索结果（用于添加来源信息）
            
        Returns:
            组装后的文本
        """
        assembled_parts = []
        
        for i, (cleaned, result) in enumerate(zip(cleaned_contents, search_results), 1):
            title = result.get("title", "无标题")
            
            # 提取图片URL并直接添加到内容中
            cleaned_with_images = self._add_image_urls(cleaned, result)
            
            # 统一使用"从多个搜索引擎搜到的知识"，不显示具体搜索引擎
            part = f"[知识片段{i}] {title}\n{cleaned_with_images}"
            assembled_parts.append(part)
        
        return "\n\n".join(assembled_parts)
    
    def _add_image_urls(self, cleaned_content: str, result: Dict[str, Any]) -> str:
        """
        提取图片URL并直接添加到内容中
        
        Args:
            cleaned_content: 清洗后的内容
            result: 搜索结果
            
        Returns:
            包含图片URL的内容
        """
        image_urls = []
        
        # 从media_content中提取图片
        media_content = result.get("media_content", {})
        if isinstance(media_content, dict):
            images = media_content.get("images", [])
            if images:
                image_urls.extend(images)
        
        # 从graph_relation中提取图片
        graph_relation = result.get("graph_relation", {})
        if graph_relation:
            # 检查start_node和end_node的chunks中的图片
            for node_key in ["start_node", "end_node"]:
                node = graph_relation.get(node_key, {})
                chunks = node.get("chunks", [])
                for chunk in chunks:
                    if isinstance(chunk, str):
                        # 提取<img>标签中的URL
                        import re
                        img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', chunk, re.IGNORECASE)
                        image_urls.extend(img_matches)
                        
                        # 提取HTTP图片链接
                        http_matches = re.findall(r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp|bmp|svg)(?:\?[^\s]*)?', chunk, re.IGNORECASE)
                        image_urls.extend(http_matches)
        
        # 去重
        image_urls = list(set(image_urls))
        
        # 如果有图片URL，直接添加到内容末尾（不添加提示信息）
        if image_urls:
            # 直接输出URL，每行一个
            image_section = "\n".join(image_urls)
            return f"{cleaned_content}\n{image_section}"
        
        return cleaned_content
    
    def format_artifacts_for_frontend(self, artifacts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        格式化 Artifact 用于前端显示
        
        Args:
            artifacts: Artifact 列表
            
        Returns:
            格式化后的 Artifact 列表
        """
        formatted_artifacts = []
        
        for artifact in artifacts:
            formatted = {
                "content": artifact.get("content", ""),
                "score": round(artifact.get("score", 0), 3),
                "source": artifact.get("source", "unknown"),
                "title": artifact.get("title", ""),
                "file_name": artifact.get("file_name", ""),
                "metadata": artifact.get("metadata", {})
            }
            formatted_artifacts.append(formatted)
        
        # 按评分排序
        formatted_artifacts.sort(key=lambda x: x["score"], reverse=True)
        
        return formatted_artifacts
