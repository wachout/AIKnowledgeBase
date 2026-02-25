# -*- coding:utf-8 -*-
"""
统一的Elasticsearch配置工具
从.env文件中读取Elasticsearch配置
"""

import os
from typing import Optional
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()


class ElasticsearchConfig:
    """Elasticsearch配置类，统一管理Elasticsearch配置"""
    
    def __init__(self):
        # 读取启用标志（注意：用户提供的变量名有拼写错误）
        flag_str = os.getenv("ELASTICSEARCG_FLAG", "False") or os.getenv("ELASTICSEARCH_FLAG", "False")
        self.enabled = flag_str.lower() == "true"
        
        # 注意：用户提供的变量名有拼写错误，但为了兼容性我们使用用户提供的名称
        # 建议在.env文件中使用正确的拼写：ELASTICSEARCH_URL, ELASTICSEARCH_USERNAME, ELASTICSEARCH_PASSWORD
        self.url = os.getenv("ELASTICSEARCG_URL") or os.getenv("ELASTICSEARCH_URL", "")
        self.username = os.getenv("ELASTICSEARCG_MAME") or os.getenv("ELASTICSEARCH_USERNAME") or os.getenv("ELASTICSEARCG_NAME", "")
        self.password = os.getenv("ELASTICSEARCG_PASSWORD") or os.getenv("ELASTICSEARCH_PASSWORD", "")
        self.verify_certs = os.getenv("ELASTICSEARCH_VERIFY_CERTS", "false").lower() == "true"
        
        # 只有在启用时才验证必要的配置
        if self.enabled:
            if not self.url:
                raise ValueError("ELASTICSEARCH_URL (or ELASTICSEARCG_URL) not found in .env file")
            if not self.username:
                raise ValueError("ELASTICSEARCH_USERNAME (or ELASTICSEARCG_MAME) not found in .env file")
            if not self.password:
                raise ValueError("ELASTICSEARCH_PASSWORD (or ELASTICSEARCG_PASSWORD) not found in .env file")
    
    def is_enabled(self) -> bool:
        """
        检查Elasticsearch是否启用
        
        Returns:
            bool: 如果启用返回True，否则返回False
        """
        return self.enabled
    
    def get_connection_params(self) -> dict:
        """
        获取Elasticsearch连接参数
        
        Returns:
            dict: 包含host, username, password, verify_certs的字典
        """
        return {
            "host": self.url,
            "username": self.username,
            "password": self.password,
            "verify_certs": self.verify_certs
        }


# 全局单例
_elasticsearch_config: Optional[ElasticsearchConfig] = None


def get_elasticsearch_config() -> ElasticsearchConfig:
    """获取Elasticsearch配置单例"""
    global _elasticsearch_config
    if _elasticsearch_config is None:
        _elasticsearch_config = ElasticsearchConfig()
    return _elasticsearch_config


def get_elasticsearch_connection_params() -> dict:
    """便捷函数：获取Elasticsearch连接参数"""
    return get_elasticsearch_config().get_connection_params()


def is_elasticsearch_enabled() -> bool:
    """便捷函数：检查Elasticsearch是否启用"""
    return get_elasticsearch_config().is_enabled()
