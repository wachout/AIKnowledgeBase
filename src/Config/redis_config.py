# -*- coding:utf-8 -*-
"""
统一的Redis配置工具
从.env文件中读取Redis配置
"""

import os
from typing import Optional
from urllib.parse import urlparse
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()


class RedisConfig:
    """Redis配置类，统一管理Redis配置"""
    
    def __init__(self):
        # 从.env文件读取配置
        redis_url = os.getenv("REDIS_URL", "")
        self.username = os.getenv("REDIS_NAME", "") or os.getenv("REDIS_USERNAME", "")
        self.password = os.getenv("REDIS_PASSWORD", "") or None
        
        # 解析URL
        if redis_url:
            # 处理URL格式（支持redis://, https://, http://等）
            parsed = urlparse(redis_url)
            
            # 提取host和port
            self.host = parsed.hostname or parsed.netloc.split(':')[0] if parsed.netloc else "localhost"
            
            # 提取port
            if parsed.port:
                self.port = parsed.port
            elif ':' in parsed.netloc:
                port_str = parsed.netloc.split(':')[-1]
                try:
                    self.port = int(port_str)
                except ValueError:
                    self.port = 6379
            else:
                self.port = 6379
        else:
            # 如果没有URL，尝试从单独的环境变量读取
            self.host = os.getenv("REDIS_HOST", "localhost")
            port_str = os.getenv("REDIS_PORT", "6379")
            try:
                self.port = int(port_str)
            except ValueError:
                self.port = 6379
        
        # 数据库编号（可选）
        self.db = int(os.getenv("REDIS_DB", "0"))
        
        # 验证必要的配置
        if not self.host:
            raise ValueError("REDIS_URL or REDIS_HOST not found in .env file")
    
    def get_connection_params(self) -> dict:
        """
        获取Redis连接参数
        
        Returns:
            dict: 包含host, port, db, password, username的字典
        """
        params = {
            "host": self.host,
            "port": self.port,
            "db": self.db,
        }
        
        if self.password:
            params["password"] = self.password
        
        if self.username:
            params["username"] = self.username
        
        return params


# 全局单例
_redis_config: Optional[RedisConfig] = None


def get_redis_config() -> RedisConfig:
    """获取Redis配置单例"""
    global _redis_config
    if _redis_config is None:
        _redis_config = RedisConfig()
    return _redis_config


def get_redis_connection_params() -> dict:
    """便捷函数：获取Redis连接参数"""
    return get_redis_config().get_connection_params()
