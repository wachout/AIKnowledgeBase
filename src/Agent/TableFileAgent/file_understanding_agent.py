# -*- coding:utf-8 -*-
"""
文件理解智能体
理解用户的要求，理解文件的基础信息，读取文件的类型、多个表格、表格列名
将列的描述保存到临时文件中
"""

import os
import json
import logging
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from Config.llm_config import get_chat_tongyi

logger = logging.getLogger(__name__)


class FileUnderstandingAgent:
    """文件理解智能体：理解文件基础信息和用户要求"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, enable_thinking=False)
        
        self.understanding_prompt = ChatPromptTemplate.from_template(
            """你是一个专业的数据分析师，擅长理解表格文件的结构和用户需求。

文件信息：
- 文件类型: {file_type}
- 工作表数量: {sheets_count}
- 工作表名称: {sheets}
- 列信息: {columns_info}

用户查询: {query}

请分析以下内容：
1. 理解用户的核心需求和分析目标
2. 分析文件结构（工作表、列名、数据类型）
3. 识别关键列和重要字段
4. 为每个列生成描述性信息

请以JSON格式返回分析结果：
{{
    "user_intent": "用户的核心需求和分析目标",
    "file_structure": {{
        "total_sheets": 工作表总数,
        "sheets_info": [
            {{
                "sheet_name": "工作表名称",
                "columns_count": 列数,
                "rows_count": 行数,
                "columns": [
                    {{
                        "column_name": "列名",
                        "description": "列的语义描述",
                        "importance": "high/medium/low",
                        "suggested_analysis": "建议的分析方向"
                    }}
                ]
            }}
        ]
    }},
    "key_columns": ["关键列名列表"],
    "analysis_focus": "分析重点和方向"
}}
"""
        )
    
    def analyze(self, file_info: Dict[str, Any], query: str = "") -> Dict[str, Any]:
        """
        分析文件并理解用户需求
        
        Args:
            file_info: 文件信息字典
            query: 用户查询
            
        Returns:
            分析结果字典
        """
        try:
            # 准备列信息字符串
            columns_info_str = ""
            for sheet_name, columns in file_info.get("columns_info", {}).items():
                columns_info_str += f"\n工作表 '{sheet_name}': {', '.join(columns)}"
            
            # 构建提示
            prompt = self.understanding_prompt.format(
                file_type=file_info.get("file_type", "unknown"),
                sheets_count=len(file_info.get("sheets", [])),
                sheets=", ".join(file_info.get("sheets", [])),
                columns_info=columns_info_str,
                query=query if query else "请分析这个表格文件"
            )
            
            # 调用LLM
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 解析JSON响应
            try:
                # 尝试提取JSON部分
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    content = content[json_start:json_end].strip()
                elif "```" in content:
                    json_start = content.find("```") + 3
                    json_end = content.find("```", json_start)
                    content = content[json_start:json_end].strip()
                
                result = json.loads(content)
            except json.JSONDecodeError:
                # 如果解析失败，返回基础结构
                logger.warning("⚠️ LLM返回的不是有效JSON，使用默认结构")
                result = {
                    "user_intent": query if query else "分析表格数据",
                    "file_structure": {
                        "total_sheets": len(file_info.get("sheets", [])),
                        "sheets_info": []
                    },
                    "key_columns": [],
                    "analysis_focus": "数据探索性分析"
                }
            
            # 保存列描述到临时文件
            temp_file_path = self._save_columns_description(file_info, result)
            result["columns_description_file"] = temp_file_path
            
            logger.info(f"✅ 文件理解分析完成，列描述已保存到: {temp_file_path}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 文件理解分析失败: {e}")
            raise
    
    def _save_columns_description(self, file_info: Dict[str, Any], analysis_result: Dict[str, Any]) -> str:
        """
        保存列描述到临时文件
        
        Args:
            file_info: 文件信息
            analysis_result: 分析结果
            
        Returns:
            临时文件路径
        """
        import tempfile
        
        # 创建临时文件
        temp_dir = "conf/tmp/table_analysis"
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_file = os.path.join(temp_dir, f"columns_description_{os.path.basename(file_info['file_path'])}.json")
        
        # 保存列描述信息
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump({
                "file_path": file_info["file_path"],
                "file_type": file_info.get("file_type"),
                "columns_description": analysis_result.get("file_structure", {}).get("sheets_info", []),
                "key_columns": analysis_result.get("key_columns", []),
                "user_intent": analysis_result.get("user_intent", "")
            }, f, ensure_ascii=False, indent=2)
        
        return temp_file
