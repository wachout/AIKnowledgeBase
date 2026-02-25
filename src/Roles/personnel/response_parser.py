# -*- coding: utf-8 -*-
"""
响应解析器模块

提供 LLM 响应的统一解析和处理工具类，消除各智能体中的重复代码。
"""

import json
import re
import logging
from typing import Dict, Any, List, Optional, Union

logger = logging.getLogger(__name__)


class LLMResponseAdapter:
    """
    LLM 响应适配器
    
    处理不同 LLM 的响应格式差异，提供统一的内容提取接口。
    """
    
    @staticmethod
    def get_content(response) -> str:
        """
        统一获取 LLM 响应内容
        
        支持多种响应格式：
        - 字符串
        - 具有 content 属性的对象
        - 具有 text 属性的对象
        - 其他可转换为字符串的对象
        
        Args:
            response: LLM 响应对象
            
        Returns:
            响应文本内容
        """
        if response is None:
            return ""
        if hasattr(response, 'content'):
            return response.content or ""
        if hasattr(response, 'text'):
            return response.text or ""
        if isinstance(response, str):
            return response
        return str(response)
    
    @staticmethod
    def is_valid_response(response) -> bool:
        """
        检查响应是否有效
        
        Args:
            response: LLM 响应对象
            
        Returns:
            是否为有效响应
        """
        content = LLMResponseAdapter.get_content(response)
        return bool(content and content.strip())
    
    @staticmethod
    def get_metadata(response) -> Dict[str, Any]:
        """
        提取响应元数据
        
        Args:
            response: LLM 响应对象
            
        Returns:
            元数据字典
        """
        metadata = {}
        
        if hasattr(response, 'response_metadata'):
            metadata['response_metadata'] = response.response_metadata
        if hasattr(response, 'usage_metadata'):
            metadata['usage_metadata'] = response.usage_metadata
        if hasattr(response, 'id'):
            metadata['response_id'] = response.id
        if hasattr(response, 'model'):
            metadata['model'] = response.model
            
        return metadata


class ResponseParser:
    """
    响应解析器
    
    处理各种 LLM 响应格式，提供多种解析方法。
    """
    
    @staticmethod
    def extract_sections(text: str, section_markers: List[str] = None) -> Dict[str, str]:
        """
        提取 Markdown 章节
        
        Args:
            text: 包含 Markdown 章节的文本
            section_markers: 自定义章节标记列表（可选）
            
        Returns:
            章节字典，键为章节标题，值为章节内容
        """
        if not text:
            return {}
            
        sections = {}
        current_section = ""
        current_content = []
        
        # 默认使用 ## 和 ### 作为章节标记
        markers = section_markers or ['##', '###']
        
        for line in text.split('\n'):
            stripped_line = line.strip()
            
            # 检查是否是章节标题
            is_section_header = False
            for marker in markers:
                if stripped_line.startswith(marker):
                    is_section_header = True
                    break
            
            if is_section_header:
                # 保存之前的章节
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                # 开始新章节
                current_section = stripped_line.lstrip('#').strip()
                current_content = []
            elif current_section:
                current_content.append(line)
        
        # 保存最后一个章节
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections
    
    @staticmethod
    def extract_section_by_markers(text: str, start_marker: str, 
                                   end_marker: str = None) -> str:
        """
        按标记提取文本段落
        
        Args:
            text: 原文本
            start_marker: 起始标记
            end_marker: 结束标记（可选，如果不提供则提取到文本末尾）
            
        Returns:
            提取的文本段落
        """
        if not text or not start_marker:
            return ""
            
        try:
            start_idx = text.find(start_marker)
            if start_idx == -1:
                return ""
            
            # 尝试找冒号后的内容
            start_content = text.find(':', start_idx)
            if start_content == -1:
                start_content = start_idx + len(start_marker)
            else:
                start_content += 1  # 跳过冒号
            
            if end_marker:
                end_idx = text.find(end_marker, start_content)
                if end_idx != -1:
                    return text[start_content:end_idx].strip()
                else:
                    return text[start_content:].strip()
            else:
                return text[start_content:].strip()
                
        except Exception as e:
            logger.warning(f"提取文本段落失败: {e}")
            return ""
    
    @staticmethod
    def parse_as_json(text: str, fallback: Dict = None) -> Dict:
        """
        尝试解析 JSON
        
        支持直接 JSON 或 Markdown 代码块中的 JSON。
        
        Args:
            text: 包含 JSON 的文本
            fallback: 解析失败时的后备值
            
        Returns:
            解析后的字典
        """
        if not text:
            return fallback if fallback is not None else {}
        
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 JSON 代码块
        try:
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
            if json_match:
                return json.loads(json_match.group(1).strip())
        except (json.JSONDecodeError, Exception):
            pass
        
        # 尝试查找 JSON 对象
        try:
            # 查找 { } 包围的内容
            brace_match = re.search(r'\{[\s\S]*\}', text)
            if brace_match:
                return json.loads(brace_match.group())
        except (json.JSONDecodeError, Exception):
            pass
        
        return fallback if fallback is not None else {"raw_text": text}
    
    @staticmethod
    def extract_list_items(text: str, marker: str = "-") -> List[str]:
        """
        提取列表项
        
        Args:
            text: 包含列表的文本
            marker: 列表标记（默认 '-'）
            
        Returns:
            列表项列表
        """
        if not text:
            return []
            
        items = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith(marker):
                item = line[len(marker):].strip()
                if item:
                    items.append(item)
        return items
    
    @staticmethod
    def extract_numbered_items(text: str) -> List[str]:
        """
        提取编号项
        
        支持 "1." 或 "1)" 格式的编号。
        
        Args:
            text: 包含编号列表的文本
            
        Returns:
            编号项内容列表（不含编号）
        """
        if not text:
            return []
            
        items = []
        pattern = r'^\s*\d+[\.\)]\s*(.+)$'
        for line in text.split('\n'):
            match = re.match(pattern, line)
            if match:
                item = match.group(1).strip()
                if item:
                    items.append(item)
        return items
    
    @staticmethod
    def extract_key_value_pairs(text: str, separator: str = ":") -> Dict[str, str]:
        """
        提取键值对
        
        Args:
            text: 包含键值对的文本
            separator: 分隔符（默认 ':'）
            
        Returns:
            键值对字典
        """
        if not text:
            return {}
            
        pairs = {}
        for line in text.split('\n'):
            line = line.strip()
            if separator in line:
                key, _, value = line.partition(separator)
                key = key.strip()
                value = value.strip()
                if key and value:
                    pairs[key] = value
        return pairs
    
    @staticmethod
    def extract_code_blocks(text: str, language: str = None) -> List[str]:
        """
        提取代码块
        
        Args:
            text: 包含代码块的文本
            language: 指定语言（可选，如 'python', 'json'）
            
        Returns:
            代码块内容列表
        """
        if not text:
            return []
        
        if language:
            pattern = rf'```{language}\s*([\s\S]*?)```'
        else:
            pattern = r'```(?:\w+)?\s*([\s\S]*?)```'
        
        matches = re.findall(pattern, text)
        return [match.strip() for match in matches if match.strip()]


class StructuredResponseBuilder:
    """
    结构化响应构建器
    
    帮助构建统一格式的响应字典。
    """
    
    def __init__(self, key_name: str):
        """
        初始化构建器
        
        Args:
            key_name: 主键名称
        """
        self.key_name = key_name
        self._result = {}
    
    def set_content(self, content: str) -> 'StructuredResponseBuilder':
        """设置主内容"""
        self._result[self.key_name] = content
        return self
    
    def set_sections(self, sections: Dict[str, str]) -> 'StructuredResponseBuilder':
        """设置解析的章节"""
        self._result["parsed_sections"] = sections
        return self
    
    def set_timestamp(self, timestamp: str) -> 'StructuredResponseBuilder':
        """设置时间戳"""
        self._result["timestamp"] = timestamp
        return self
    
    def add_field(self, key: str, value: Any) -> 'StructuredResponseBuilder':
        """添加自定义字段"""
        self._result[key] = value
        return self
    
    def add_fields(self, fields: Dict[str, Any]) -> 'StructuredResponseBuilder':
        """批量添加字段"""
        self._result.update(fields)
        return self
    
    def build(self) -> Dict[str, Any]:
        """构建最终结果"""
        return self._result.copy()
    
    @classmethod
    def from_response(cls, response: str, key_name: str, 
                      timestamp: str = None) -> Dict[str, Any]:
        """
        从响应文本快速构建结构化响应
        
        Args:
            response: 响应文本
            key_name: 主键名称
            timestamp: 时间戳（可选）
            
        Returns:
            结构化响应字典
        """
        from datetime import datetime
        
        builder = cls(key_name)
        builder.set_content(response)
        builder.set_sections(ResponseParser.extract_sections(response))
        builder.set_timestamp(timestamp or datetime.now().isoformat())
        
        return builder.build()


# 便捷函数
def get_response_content(response) -> str:
    """便捷函数：获取响应内容"""
    return LLMResponseAdapter.get_content(response)


def parse_sections(text: str) -> Dict[str, str]:
    """便捷函数：解析章节"""
    return ResponseParser.extract_sections(text)


def parse_json(text: str, fallback: Dict = None) -> Dict:
    """便捷函数：解析 JSON"""
    return ResponseParser.parse_as_json(text, fallback)
