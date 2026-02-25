# -*- coding:utf-8 -*-
"""
工具智能体 (Tool Agent)

根据意图识别结果判断并执行相应的工具调用
"""

import re
from typing import Dict, Any, Optional

from Agent.AgenticRagAgent.intent_recognition_agent import (
    file_statistics_impl,
    file_list_impl,
    file_summary_impl
)


class ToolAgent:
    """工具智能体：根据意图识别结果执行工具调用"""
    
    def __init__(self):
        """初始化工具智能体"""
        pass
    
    def execute_tool_by_intent(self, intent_result: Dict[str, Any], query: str, 
                               knowledge_id: str) -> Dict[str, Any]:
        """
        根据意图识别结果执行相应的工具
        
        Args:
            intent_result: 意图识别结果，包含 tool_name 等信息
            query: 用户原始查询
            knowledge_id: 知识库ID
            
        Returns:
            工具执行结果，包含：
            - success: 是否成功
            - tool_name: 工具名称
            - tool_result: 工具执行结果
            - formatted_content: 格式化后的内容（用于流式输出）
        """
        tool_name = intent_result.get("tool_name", "")
        
        if not tool_name:
            return {
                "success": False,
                "error": "工具名称为空",
                "tool_name": "",
                "tool_result": None,
                "formatted_content": ""
            }
        
        # 根据工具名称构建参数并执行
        try:
            if tool_name == "file_statistics":
                return self._execute_file_statistics(knowledge_id)
            elif tool_name == "file_list":
                return self._execute_file_list(knowledge_id)
            elif tool_name == "file_summary":
                return self._execute_file_summary(intent_result, query)
            else:
                return {
                    "success": False,
                    "error": f"未知工具: {tool_name}",
                    "tool_name": tool_name,
                    "tool_result": None,
                    "formatted_content": ""
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"工具执行异常: {str(e)}",
                "tool_name": tool_name,
                "tool_result": None,
                "formatted_content": ""
            }
    
    def _execute_file_statistics(self, knowledge_id: str) -> Dict[str, Any]:
        """执行文件统计工具"""
        tool_result = file_statistics_impl(knowledge_id)
        
        if tool_result.get("tool_result", False):
            description = tool_result.get('description', '暂无统计信息')
            file_count = tool_result.get('file_count', 0)
            knowledge_name = tool_result.get('knowledge_name', '未知知识库')
            formatted_content = f"📊 知识库统计信息：\n知识库名称: {knowledge_name}\n文件总数: {file_count}\n{description}"
            
            return {
                "success": True,
                "tool_name": "file_statistics",
                "tool_result": tool_result,
                "formatted_content": formatted_content
            }
        else:
            return {
                "success": False,
                "error": tool_result.get('error', '工具执行失败'),
                "tool_name": "file_statistics",
                "tool_result": tool_result,
                "formatted_content": ""
            }
    
    def _execute_file_list(self, knowledge_id: str) -> Dict[str, Any]:
        """执行文件列表工具"""
        tool_result = file_list_impl(knowledge_id)
        
        if tool_result.get("tool_result", False):
            files = tool_result.get('files', [])
            file_count = tool_result.get('file_count', 0)
            knowledge_name = tool_result.get('knowledge_name', '未知知识库')
            
            formatted_content = f"📁 知识库文件列表（知识库: {knowledge_name}，共{file_count}个文件）：\n"
            if files:
                formatted_content += "\n".join(f"• {file}" for file in files[:20])
                if len(files) > 20:
                    formatted_content += f"\n... 还有{len(files) - 20}个文件"
            else:
                formatted_content += "暂无文件"
            
            return {
                "success": True,
                "tool_name": "file_list",
                "tool_result": tool_result,
                "formatted_content": formatted_content
            }
        else:
            return {
                "success": False,
                "error": tool_result.get('error', '工具执行失败'),
                "tool_name": "file_list",
                "tool_result": tool_result,
                "formatted_content": ""
            }
    
    def _execute_file_summary(self, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """执行文件摘要工具"""
        # 从 intent_result 或 query 中提取文件名
        file_name = self._extract_file_name(intent_result, query)
        
        tool_result = file_summary_impl(file_name)
        
        if tool_result.get("tool_result", False):
            description = tool_result.get('description', '暂无详细信息')
            file_info = tool_result.get('file_info', {})
            file_name_result = tool_result.get('file_name', '未知文件')
            
            formatted_content = f"📄 文件详细信息：\n文件名: {file_name_result}\n{description}"
            
            # 添加文件详细信息（排除大字段）
            if file_info and isinstance(file_info, dict):
                for key, value in file_info.items():
                    if key not in ['content', 'chunks']:
                        formatted_content += f"\n{key}: {value}"
            
            return {
                "success": True,
                "tool_name": "file_summary",
                "tool_result": tool_result,
                "formatted_content": formatted_content
            }
        else:
            return {
                "success": False,
                "error": tool_result.get('error', '工具执行失败'),
                "tool_name": "file_summary",
                "tool_result": tool_result,
                "formatted_content": ""
            }
    
    def _extract_file_name(self, intent_result: Dict[str, Any], query: str) -> str:
        """
        从意图识别结果或查询中提取文件名
        
        Args:
            intent_result: 意图识别结果
            query: 用户查询
            
        Returns:
            提取的文件名
        """
        # 方法1: 从 entities 中查找可能的文件名
        entities = intent_result.get("entities", [])
        for entity in entities:
            if isinstance(entity, str) and ("文件" in entity or "." in entity):
                # 提取文件名（去除"文件"等词）
                file_name = entity.replace("文件", "").strip()
                if file_name:
                    return file_name
        
        # 方法2: 使用正则表达式从查询中提取文件名（带引号）
        file_patterns = re.findall(r'["\']([^"\']+\.[a-zA-Z0-9]+)["\']', query)
        if file_patterns:
            return file_patterns[0]
        
        # 方法3: 从查询中提取文件名（不带引号，包含扩展名）
        file_patterns = re.findall(
            r'\b([\w\-_]+\.(?:pdf|doc|docx|txt|md|xlsx|xls|ppt|pptx|jpg|png|gif|zip|rar))\b', 
            query, 
            re.IGNORECASE
        )
        if file_patterns:
            return file_patterns[0]
        
        # 方法4: 如果查询中包含"文件"关键词，尝试提取文件名
        # 例如："文件XXX的信息" -> "XXX"
        match = re.search(r'文件[：:]\s*([^\s]+)', query)
        if match:
            return match.group(1)
        
        match = re.search(r'["\']([^"\']+)["\']', query)
        if match:
            potential_name = match.group(1)
            # 如果包含常见文件扩展名，认为是文件名
            if '.' in potential_name:
                return potential_name
        
        # 方法5: 如果都找不到，使用查询的一部分作为文件名
        # 去除常见的查询词
        cleaned_query = query.replace("文件", "").replace("的", "").strip()
        if cleaned_query:
            # 取前50个字符
            return cleaned_query[:50]
        
        # 最后兜底：返回查询本身
        return query.strip()[:50]
