# -*- coding:utf-8 -*-
"""
调度智能体
根据反思智能体返回的结果，判断是否要进行扩展搜索
最多扩展2次
"""

from typing import Dict, Any, List, Optional


class OrchestratorAgent:
    """调度智能体：管理扩展搜索的流程"""
    
    def __init__(self, max_expansions: int = 2):
        self.max_expansions = max_expansions
    
    def should_expand_search(self, reflection_result: Dict[str, Any], 
                           expansion_count: int) -> Dict[str, Any]:
        """
        判断是否应该进行扩展搜索
        
        Args:
            reflection_result: 反思智能体的结果
            expansion_count: 当前已扩展次数
            
        Returns:
            决策结果：
            - should_expand: 是否应该扩展
            - reason: 决策理由
            - suggested_queries: 建议的查询列表
        """
        # 检查是否已达到最大扩展次数
        if expansion_count >= self.max_expansions:
            return {
                "should_expand": False,
                "reason": f"已达到最大扩展次数（{self.max_expansions}次）",
                "suggested_queries": []
            }
        
        # 检查反思结果
        if not reflection_result.get("success", False):
            return {
                "should_expand": False,
                "reason": "反思智能体返回失败",
                "suggested_queries": []
            }
        
        needs_expansion = reflection_result.get("needs_expansion", False)
        suggested_queries = reflection_result.get("suggested_queries", [])
        
        if needs_expansion and suggested_queries:
            return {
                "should_expand": True,
                "reason": reflection_result.get("reasoning", "需要更多信息"),
                "suggested_queries": suggested_queries[:2]  # 最多2个查询
            }
        else:
            return {
                "should_expand": False,
                "reason": "反思智能体认为当前信息已足够" if not needs_expansion else "没有建议的扩展查询",
                "suggested_queries": []
            }
