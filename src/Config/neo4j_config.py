# -*- coding:utf-8 -*-
"""
统一的Neo4j配置工具
从.env文件中读取Neo4j配置
"""

import os
from typing import Optional
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()


class Neo4jConfig:
    """Neo4j配置类，统一管理Neo4j配置"""
    
    def __init__(self):
        # 读取启用标志
        flag_str = os.getenv("NEO4J_FLAG", "True")
        self.enabled = flag_str.lower() == "true"
        
        # 从.env文件读取配置
        self.uri = os.getenv("NEO4J_URI", "") or os.getenv("neo4j_uri", "")
        self.user = os.getenv("NEO4J_USER", "") or os.getenv("neo4j_user", "") or os.getenv("NEO4J_USERNAME", "")
        self.password = os.getenv("NEO4J_PASSWORD", "") or os.getenv("neo4j_password", "")
        
        # 只有在启用时才验证必要的配置
        if self.enabled:
            if not self.uri:
                raise ValueError("NEO4J_URI (or neo4j_uri) not found in .env file")
            if not self.user:
                raise ValueError("NEO4J_USER (or neo4j_user) not found in .env file")
            if not self.password:
                raise ValueError("NEO4J_PASSWORD (or neo4j_password) not found in .env file")
    
    def is_enabled(self) -> bool:
        """
        检查Neo4j是否启用
        
        Returns:
            bool: 如果启用返回True，否则返回False
        """
        return self.enabled
    
    def get_connection_params(self) -> dict:
        """
        获取Neo4j连接参数
        
        Returns:
            dict: 包含uri, user, password的字典
        """
        return {
            "uri": self.uri,
            "user": self.user,
            "password": self.password
        }


# 全局单例
_neo4j_config: Optional[Neo4jConfig] = None


def get_neo4j_config() -> Neo4jConfig:
    """获取Neo4j配置单例"""
    global _neo4j_config
    if _neo4j_config is None:
        _neo4j_config = Neo4jConfig()
    return _neo4j_config


def get_neo4j_connection_params() -> dict:
    """便捷函数：获取Neo4j连接参数"""
    return get_neo4j_config().get_connection_params()


def is_neo4j_enabled() -> bool:
    """便捷函数：检查Neo4j是否启用"""
    return get_neo4j_config().is_enabled()
