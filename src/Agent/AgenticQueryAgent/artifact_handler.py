# -*- coding:utf-8 -*-
"""
Artifact处理智能体
分离清洗内容和原始内容
"""

import re
from typing import Dict, Any, List
from Agent.AgenticRagAgent.artifact_handler import ArtifactHandler as BaseArtifactHandler


class ArtifactHandler(BaseArtifactHandler):
    """Artifact处理智能体：分离清洗内容和原始内容"""
    
    def __init__(self):
        super().__init__()
    
    def process_for_query(self, search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        处理搜索结果，分离清洗内容和原始Artifact（用于查询场景）
        
        Args:
            search_results: 搜索结果列表
            
        Returns:
            处理结果，包含：
            - cleaned_content: 清洗后的内容（给AI看）
            - artifacts: 原始Artifact列表（给用户看）
        """
        return self.process_search_results(search_results)
