# -*- coding:utf-8 -*-
"""
扩展搜索智能体
如果不满意搜索结果，进行扩展搜索
"""

from typing import Dict, Any, List
from Agent.AgenticQueryAgent.hybrid_search_agent import HybridSearchAgent


class ExpandedSearchAgent:
    """扩展搜索智能体：基于评估结果进行扩展搜索"""
    
    def __init__(self):
        self.hybrid_search_agent = HybridSearchAgent()
    
    def expand_search(self, knowledge_id: str, query: str, 
                     evaluation_result: Dict[str, Any],
                     initial_results: List[Dict[str, Any]],
                     user_id: str = None, permission_flag: bool = True) -> Dict[str, Any]:
        """
        扩展搜索
        
        Args:
            knowledge_id: 知识库ID
            query: 原始查询
            evaluation_result: 评估结果
            initial_results: 初始搜索结果
            user_id: 用户ID
            permission_flag: 权限标志
            
        Returns:
            扩展搜索结果
        """
        try:
            expansion_suggestions = evaluation_result.get("expansion_suggestions", [])
            missing_entities = evaluation_result.get("missing_entities", [])
            missing_metrics = evaluation_result.get("missing_metrics", [])
            missing_attributes = evaluation_result.get("missing_attributes", [])
            
            # 构建扩展查询
            expanded_queries = self._build_expanded_queries(
                query, expansion_suggestions, missing_entities, missing_metrics, missing_attributes
            )
            
            # 执行扩展搜索
            expanded_results = []
            for expanded_query in expanded_queries:
                search_result = self.hybrid_search_agent.search(
                    knowledge_id=knowledge_id,
                    query=expanded_query,
                    user_id=user_id,
                    top_k=5,
                    permission_flag=permission_flag
                )
                if search_result.get("success"):
                    expanded_results.extend(search_result.get("combined_results", []))
            
            # 合并初始结果和扩展结果（去重）
            all_results = self._merge_and_deduplicate(initial_results, expanded_results)
            
            return {
                "success": True,
                "expanded_queries": expanded_queries,
                "expanded_results": expanded_results,
                "all_results": all_results,
                "total_count": len(all_results)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"扩展搜索失败: {str(e)}",
                "all_results": initial_results
            }
    
    def _build_expanded_queries(self, original_query: str, 
                               expansion_suggestions: List[str],
                               missing_entities: List[str],
                               missing_metrics: List[str],
                               missing_attributes: List[str]) -> List[str]:
        """构建扩展查询"""
        expanded_queries = []
        
        # 基于缺失的实体构建查询
        for entity in missing_entities[:3]:  # 最多3个
            expanded_queries.append(f"{original_query} {entity}")
        
        # 基于缺失的指标构建查询
        for metric in missing_metrics[:3]:  # 最多3个
            expanded_queries.append(f"{original_query} {metric}")
        
        # 基于扩展建议构建查询
        for suggestion in expansion_suggestions[:3]:  # 最多3个
            expanded_queries.append(f"{original_query} {suggestion}")
        
        # 去重
        expanded_queries = list(dict.fromkeys(expanded_queries))
        
        # 如果没有任何扩展查询，返回原始查询的变体
        if not expanded_queries:
            expanded_queries.append(original_query)
        
        return expanded_queries
    
    def _merge_and_deduplicate(self, initial_results: List[Dict[str, Any]],
                              expanded_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并并去重结果"""
        all_results = []
        seen_ids = set()
        
        # 添加初始结果
        for result in initial_results:
            result_id = result.get("id") or result.get("partition", "")
            if result_id:
                if result_id not in seen_ids:
                    all_results.append(result)
                    seen_ids.add(result_id)
            else:
                # 如果没有ID，使用内容hash
                content_hash = hash(result.get("content", ""))
                if content_hash not in seen_ids:
                    all_results.append(result)
                    seen_ids.add(content_hash)
        
        # 添加扩展结果（去重）
        for result in expanded_results:
            result_id = result.get("id") or result.get("partition", "")
            if result_id:
                if result_id not in seen_ids:
                    all_results.append(result)
                    seen_ids.add(result_id)
            else:
                content_hash = hash(result.get("content", ""))
                if content_hash not in seen_ids:
                    all_results.append(result)
                    seen_ids.add(content_hash)
        
        # 按评分排序
        all_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        
        return all_results
