"""
双重切分策略

采用 MarkdownHeader切分 + 递归字符切分 的双重策略：
- 保留文档的语义结构（章节归属）
- 控制 Token 长度
"""

from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from langchain_core.documents import Document
import re

class HybridTextSplitter:
    """双重切分策略：MarkdownHeader + RecursiveCharacter"""
    
    def __init__(self, 
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 markdown_headers_to_split_on: List[tuple] = None):
        """
        初始化混合切分器
        
        Args:
            chunk_size: 最终chunk的大小
            chunk_overlap: chunk之间的重叠大小
            markdown_headers_to_split_on: Markdown标题级别配置
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # 默认的Markdown标题配置
        if markdown_headers_to_split_on is None:
            markdown_headers_to_split_on = [
                ("#", "Header 1"),
                ("##", "Header 2"),
                ("###", "Header 3"),
            ]
        
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=markdown_headers_to_split_on
        )
        
        self.recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", ". ", " ", ""]
        )
    
    def split_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Document]:
        """
        双重切分文本
        
        流程：
        1. 首先尝试按Markdown标题切分（保留语义结构）
        2. 如果chunk仍然太大，再用递归字符切分
        
        Args:
            text: 要切分的文本
            metadata: 文档元数据
            
        Returns:
            切分后的Document列表
        """
        if not text or not text.strip():
            return []
        
        # 步骤1: 尝试Markdown标题切分
        try:
            md_docs = self.markdown_splitter.split_text(text)
            
            # 检查是否有有效的Markdown结构
            if len(md_docs) > 1 or (len(md_docs) == 1 and md_docs[0].metadata):
                # 有Markdown结构，使用Markdown切分结果
                final_docs = []
                for doc in md_docs:
                    # 如果单个chunk仍然太大，进一步切分
                    if len(doc.page_content) > self.chunk_size * 1.5:
                        sub_docs = self.recursive_splitter.split_documents([doc])
                        final_docs.extend(sub_docs)
                    else:
                        final_docs.append(doc)
                
                # 添加元数据
                if metadata:
                    for doc in final_docs:
                        doc.metadata.update(metadata)
                
                return final_docs
            else:
                # 没有有效的Markdown结构，直接使用递归切分
                doc = Document(page_content=text, metadata=metadata or {})
                return self.recursive_splitter.split_documents([doc])
                
        except Exception as e:
            # Markdown切分失败，回退到递归切分
            print(f"⚠️ Markdown切分失败，使用递归切分: {e}")
            doc = Document(page_content=text, metadata=metadata or {})
            return self.recursive_splitter.split_documents([doc])
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        切分多个文档
        
        Args:
            documents: Document列表
            
        Returns:
            切分后的Document列表
        """
        all_splits = []
        
        for doc in documents:
            splits = self.split_text(doc.page_content, doc.metadata)
            all_splits.extend(splits)
        
        return all_splits
    
    def is_markdown(self, text: str) -> bool:
        """
        判断文本是否包含Markdown结构
        
        Args:
            text: 文本内容
            
        Returns:
            是否包含Markdown结构
        """
        # 检查是否包含Markdown标题
        markdown_header_pattern = r'^#{1,6}\s+.+$'
        lines = text.split('\n')
        
        for line in lines[:20]:  # 只检查前20行
            if re.match(markdown_header_pattern, line.strip()):
                return True
        
        return False
