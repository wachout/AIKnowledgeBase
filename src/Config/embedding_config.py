# -*- coding:utf-8 -*-
"""
统一的Embedding配置工具
从.env文件中读取向量模型配置
"""

import os
from typing import Optional
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv


# 加载.env文件
load_dotenv()


class EmbeddingsWrapper:
    """
    Embeddings包装类，使用OpenAI SDK直接调用API
    兼容LangChain的embed_query和embed_documents接口
    """
    
    def __init__(self, config: 'EmbeddingConfig'):
        """
        初始化Embeddings包装类
        
        Args:
            config: EmbeddingConfig实例
        """
        self.config = config
        self.client = config.get_openai_client()
        self.model_name = config.model_name
        self.vector_length = config.vector_length
    
    def embed_query(self, text: str) -> list:
        """
        生成单个文本的向量（兼容LangChain接口）
        
        Args:
            text: 输入文本
            
        Returns:
            list: 向量列表
        """
        if not text or not isinstance(text, str) or not text.strip():
            raise ValueError("输入文本不能为空")
        
        try:
            # 调用官方API
            response = self.client.embeddings.create(
                model=self.model_name,
                input=text.strip(),
                dimensions=self.vector_length,
                encoding_format="float"
            )
            
            # 从响应中提取embedding向量
            if response.data and len(response.data) > 0:
                return response.data[0].embedding
            else:
                raise ValueError("API返回的embedding数据为空")
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"生成向量失败: {e}")
            raise
    
    def embed_documents(self, texts: list) -> list:
        """
        批量生成文本向量（兼容LangChain接口）
        
        Args:
            texts: 文本列表
            
        Returns:
            list: 向量列表，每个元素是一个文本的向量
        """
        if not texts:
            return []
        
        # 过滤空文本
        valid_texts = [str(text).strip() for text in texts if text and str(text).strip()]
        if not valid_texts:
            return []
        
        try:
            # 调用官方API（支持批量）
            response = self.client.embeddings.create(
                model=self.model_name,
                input=valid_texts,
                dimensions=self.vector_length,
                encoding_format="float"
            )
            
            # 从响应中提取所有embedding向量
            embeddings = []
            if response.data:
                for item in response.data:
                    embeddings.append(item.embedding)
            
            return embeddings
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"批量生成向量失败: {e}")
            raise


class EmbeddingConfig:
    """Embedding配置类，统一管理向量模型配置"""
    
    def __init__(self):
        self.api_key = os.getenv("EMBEDDING_API_KEY", "")
        self.base_url = os.getenv("EMBEDDING_BASE_URL", "")
        self.model_id = os.getenv("EMBEDDING_MODEL_ID", "")
        self.model_name = os.getenv("EMBEDDING_MODEL_NAME", "")
        self.vector_length = int(os.getenv("EMBEDDING_VECTOR_LENGTH", "2048"))
        
        # 验证必要的配置
        if not self.api_key:
            raise ValueError("EMBEDDING_API_KEY not found in .env file")
        if not self.base_url:
            raise ValueError("EMBEDDING_BASE_URL not found in .env file")
        if not self.model_id:
            raise ValueError("EMBEDDING_MODEL_ID not found in .env file")
        if not self.model_name:
            raise ValueError("EMBEDDING_MODEL_NAME not found in .env file")
    
    def get_openai_client(self):
        """
        创建OpenAI客户端实例（直接使用官方SDK）
        
        Returns:
            OpenAI客户端实例
        """
        try:
            
            return OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        except ImportError:
            raise ImportError("openai not installed. Please install it: pip install openai")
    
    def get_openai_embeddings(self):
        """
        创建OpenAI兼容的Embeddings实例（LangChain封装）
        
        Returns:
            OpenAIEmbeddings实例
        """
        try:
            
            return OpenAIEmbeddings(
                model=self.model_name,
                openai_api_key=self.api_key,
                openai_api_base=self.base_url,
            )
        except ImportError:
            raise ImportError("langchain_openai not installed. Please install it: pip install langchain-openai")
    
    def get_embeddings(self):
        """
        获取Embeddings实例（优先使用官方SDK直接调用，失败则回退到LangChain）
        
        Returns:
            EmbeddingsWrapper或OpenAIEmbeddings实例，兼容LangChain接口
        """
        try:
            # 优先使用官方SDK直接调用
            return EmbeddingsWrapper(self)
        except ImportError:
            # 如果openai包不可用，回退到LangChain封装
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("openai包未安装，回退到LangChain封装方式")
            return self.get_openai_embeddings()
    
    def get_vector_length(self) -> int:
        """
        获取向量维度长度
        
        Returns:
            向量维度长度
        """
        return self.vector_length


# 全局单例
_embedding_config: Optional[EmbeddingConfig] = None


def get_embedding_config() -> EmbeddingConfig:
    """获取Embedding配置单例"""
    global _embedding_config
    if _embedding_config is None:
        _embedding_config = EmbeddingConfig()
    return _embedding_config


def get_embeddings():
    """便捷函数：获取Embeddings实例"""
    return get_embedding_config().get_embeddings()


def get_vector_length() -> int:
    """便捷函数：获取向量维度长度"""
    return get_embedding_config().get_vector_length()
