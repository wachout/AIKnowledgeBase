# -*- coding:utf-8 -*-
"""
DummyReactAgent - 虚拟智能体
测试、占位，主要是监督，根据任务，中间返回给思考智能体
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class DummyReactAgent:
    """虚拟智能体：用于测试和监督"""
    
    def __init__(self):
        pass
    
    def supervise(self, task: str, current_state: Dict[str, Any],
                 step_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        监督任务执行
        
        Args:
            task: 任务描述
            current_state: 当前状态
            step_results: 步骤结果列表
            
        Returns:
            监督结果
        """
        try:
            # 检查任务进度
            progress = len(step_results) / 10.0  # 假设总共10步
            progress = min(progress, 1.0)
            
            # 检查是否有错误
            errors = [r for r in step_results if not r.get("success", True)]
            
            # 生成监督报告
            report = {
                "task": task,
                "progress": progress,
                "completed_steps": len(step_results),
                "has_errors": len(errors) > 0,
                "errors": [e.get("error") for e in errors],
                "recommendations": self._generate_recommendations(step_results, errors)
            }
            
            logger.info(f"✅ 监督完成，进度: {progress*100:.1f}%")
            return report
            
        except Exception as e:
            logger.error(f"❌ 监督失败: {e}")
            return {
                "task": task,
                "progress": 0,
                "error": str(e)
            }
    
    def _generate_recommendations(self, step_results: List[Dict[str, Any]],
                                 errors: List[Dict[str, Any]]) -> List[str]:
        """生成建议"""
        recommendations = []
        
        if errors:
            recommendations.append("检测到错误，建议检查并修复")
        
        if len(step_results) < 3:
            recommendations.append("任务刚开始，建议继续执行")
        elif len(step_results) >= 7:
            recommendations.append("任务接近完成，建议检查最终结果")
        
        return recommendations
