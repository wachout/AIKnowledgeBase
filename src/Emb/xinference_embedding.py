# -*- coding:utf-8 _*-


# 初始化标准logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 使用统一的embedding配置
from Config.embedding_config import get_embeddings

class CControl():
    """
    Embedding控制类
    使用统一的配置从.env文件读取embedding配置
    """
    
    def __init__(self, model_name=None):
        """
        初始化Embedding实例
        
        Args:
            model_name: 模型名称（保留参数以兼容旧代码，实际从.env读取）
        """
        # 从.env文件读取配置并创建embeddings实例
        self.embeddings = get_embeddings()
        
cSingleEmb = CControl()

