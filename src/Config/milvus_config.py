# -*- coding:utf-8 -*-
"""
统一的Milvus配置工具
从.env文件中读取Milvus配置
"""

import os
from typing import Optional
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()


class MilvusConfig:
    """Milvus配置类，统一管理Milvus配置"""
    
    def __init__(self):
        # 读取启用标志
        flag_str = os.getenv("MILVUS_FLAG", "True")
        self.enabled = flag_str.lower() == "true"
        
        # 从.env文件读取配置
        self.url = os.getenv("MILVUS_URL", "localhost")
        port_str = os.getenv("MILVUS_PORT", "19530")
        try:
            self.port = int(port_str)
        except ValueError:
            self.port = 19530
        
        # 只有在启用时才验证必要的配置
        if self.enabled:
            if not self.url:
                raise ValueError("MILVUS_URL not found in .env file")
    
    def is_enabled(self) -> bool:
        """
        检查Milvus是否启用
        
        Returns:
            bool: 如果启用返回True，否则返回False
        """
        return self.enabled
    
    def get_connection_params(self) -> dict:
        """
        获取Milvus连接参数
        
        Returns:
            dict: 包含host, port的字典
        """
        return {
            "host": self.url,
            "port": self.port
        }


# 全局单例
_milvus_config: Optional[MilvusConfig] = None


def get_milvus_config() -> MilvusConfig:
    """获取Milvus配置单例"""
    global _milvus_config
    if _milvus_config is None:
        _milvus_config = MilvusConfig()
    return _milvus_config


def get_milvus_connection_params() -> dict:
    """便捷函数：获取Milvus连接参数"""
    return get_milvus_config().get_connection_params()


def is_milvus_enabled() -> bool:
    """便捷函数：检查Milvus是否启用"""
    return get_milvus_config().is_enabled()
