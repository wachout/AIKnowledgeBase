# -*- coding: utf-8 -*-
"""
代码检查智能体

功能：
1. 检查生成的Python代码是否有语法错误
2. 检查代码是否符合要求（导入、结构、逻辑等）
3. 返回检查结果和错误信息
"""

import json
import re

from typing import Dict, Any
import ast
import logging

try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

from Config import config

logger = logging.getLogger(__name__)


class CodeCheckAgent:
    """代码检查智能体"""
    
    def __init__(self, llm=None):
        """
        初始化智能体
        
        Args:
            llm: 大语言模型实例，如果为None则使用默认配置
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain相关库未安装，请安装必要的依赖")
        
        if llm is None:
            # 使用统一的LLM配置
            temperature = 0.7
            
            self.llm = get_chat_tongyi(temperature=temperature, streaming=False, enable_thinking=False)
            
        else:
            self.llm = llm
    
    def check_code(self, code: str, base_prompt: str = None) -> Dict[str, Any]:
        """
        检查代码
        
        Args:
            code: 要检查的Python代码
            base_prompt: 原始prompt（可选，用于上下文）
        
        Returns:
            检查结果字典:
            {
                "is_valid": True/False,
                "has_syntax_error": True/False,
                "syntax_errors": [],
                "has_logic_error": True/False,
                "logic_errors": [],
                "has_structure_error": True/False,
                "structure_errors": [],
                "suggestions": [],
                "error_summary": ""
            }
        """
        result = {
            "is_valid": True,
            "has_syntax_error": False,
            "syntax_errors": [],
            "has_logic_error": False,
            "logic_errors": [],
            "has_structure_error": False,
            "structure_errors": [],
            "suggestions": [],
            "error_summary": ""
        }
        
        try:
            # 1. 语法检查
            try:
                ast.parse(code)
                logger.debug("✅ 代码语法检查通过")
            except SyntaxError as e:
                result["is_valid"] = False
                result["has_syntax_error"] = True
                error_msg = f"语法错误 (行 {e.lineno}): {e.msg}"
                result["syntax_errors"].append(error_msg)
                logger.warning(f"❌ 代码语法错误: {error_msg}")
            
            # 2. 结构检查（使用LLM）
            structure_check_result = self._check_code_structure(code, base_prompt)
            if not structure_check_result.get("is_valid", True):
                result["is_valid"] = False
                result["has_structure_error"] = True
                result["structure_errors"].extend(structure_check_result.get("errors", []))
                result["suggestions"].extend(structure_check_result.get("suggestions", []))
            
            # 3. 逻辑检查（使用LLM）
            logic_check_result = self._check_code_logic(code, base_prompt)
            if not logic_check_result.get("is_valid", True):
                result["is_valid"] = False
                result["has_logic_error"] = True
                result["logic_errors"].extend(logic_check_result.get("errors", []))
                result["suggestions"].extend(logic_check_result.get("suggestions", []))
            
            # 生成错误摘要
            if not result["is_valid"]:
                error_parts = []
                if result["has_syntax_error"]:
                    error_parts.append(f"语法错误: {len(result['syntax_errors'])}个")
                if result["has_structure_error"]:
                    error_parts.append(f"结构错误: {len(result['structure_errors'])}个")
                if result["has_logic_error"]:
                    error_parts.append(f"逻辑错误: {len(result['logic_errors'])}个")
                result["error_summary"] = "; ".join(error_parts)
            
            return result
            
        except Exception as e:
            logger.error(f"代码检查过程出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            result["is_valid"] = False
            result["error_summary"] = f"检查过程出错: {str(e)}"
            return result
    
    def _check_code_structure(self, code: str, base_prompt: str = None) -> Dict[str, Any]:
        """使用LLM检查代码结构"""
        try:
            prompt_template = ChatPromptTemplate.from_template(
                """你是一个Python代码结构检查专家。请检查以下代码的结构是否符合要求。

代码：
```python
{code}
```

原始要求：
{base_prompt}

检查项：
1. 是否包含必要的导入（pandas, json等）
2. 是否按照模板结构生成（包含CSV读取、逻辑计算部分、文件写入等）
3. 是否有明显的结构缺失（如缺少result变量、缺少文件写入等）
4. 代码格式是否规范

请返回JSON格式：
{{
  "is_valid": true/false,
  "errors": ["错误1", "错误2", ...],
  "suggestions": ["建议1", "建议2", ...]
}}

只返回JSON，不要其他文字。"""
            )
            
            chain = prompt_template | self.llm | StrOutputParser()
            response = chain.invoke({
                "code": code,
                "base_prompt": base_prompt or "无特殊要求"
            })
            
            # 提取JSON
            # 尝试多种方式提取JSON
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    return result
                except json.JSONDecodeError:
                    pass
            
            # 如果正则提取失败，尝试直接解析整个响应
            try:
                result = json.loads(response)
                return result
            except json.JSONDecodeError:
                pass
            
            # 如果都失败，返回默认值
            logger.warning("无法解析结构检查结果，返回默认值")
            return {"is_valid": True, "errors": [], "suggestions": []}
                
        except Exception as e:
            logger.error(f"结构检查失败: {e}")
            return {"is_valid": True, "errors": [], "suggestions": []}
    
    def _check_code_logic(self, code: str, base_prompt: str = None) -> Dict[str, Any]:
        """使用LLM检查代码逻辑"""
        try:
            prompt_template = ChatPromptTemplate.from_template(
                """你是一个Python代码逻辑检查专家。请检查以下代码的逻辑是否正确。

代码：
```python
{code}
```

原始要求：
{base_prompt}

检查项：
1. 逻辑计算部分是否完整
2. result变量是否正确生成和赋值
3. 是否使用了json.dumps进行序列化
4. 是否有明显的逻辑错误（如未定义的变量、类型错误等）
5. 是否满足逻辑要求中的计算需求

请返回JSON格式：
{{
  "is_valid": true/false,
  "errors": ["错误1", "错误2", ...],
  "suggestions": ["建议1", "建议2", ...]
}}

只返回JSON，不要其他文字。"""
            )
            
            chain = prompt_template | self.llm | StrOutputParser()
            response = chain.invoke({
                "code": code,
                "base_prompt": base_prompt or "无特殊要求"
            })
            # 尝试多种方式提取JSON
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    return result
                except json.JSONDecodeError:
                    pass
            
            # 如果正则提取失败，尝试直接解析整个响应
            try:
                result = json.loads(response)
                return result
            except json.JSONDecodeError:
                pass
            
            # 如果都失败，返回默认值
            logger.warning("无法解析逻辑检查结果，返回默认值")
            return {"is_valid": True, "errors": [], "suggestions": []}
                
        except Exception as e:
            logger.error(f"逻辑检查失败: {e}")
            return {"is_valid": True, "errors": [], "suggestions": []}
