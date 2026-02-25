# -*- coding: utf-8 -*-
"""
代码工具函数

功能：
1. 从LLM输出中提取纯Python代码
2. 去除markdown代码块标记和其他非代码内容
"""

import re
import logging

logger = logging.getLogger(__name__)


def extract_python_code(llm_output: str) -> str:
    """
    从LLM输出中提取纯Python代码
    
    Args:
        llm_output: LLM的原始输出，可能包含markdown代码块标记或其他文本
    
    Returns:
        纯Python代码字符串
    """
    if not llm_output or not isinstance(llm_output, str):
        return ""
    
    code = llm_output.strip()
    
    # 1. 尝试提取markdown代码块中的代码
    # 匹配 ```python ... ``` 或 ``` ... ```
    markdown_patterns = [
        r'```python\s*\n(.*?)\n```',  # ```python\ncode\n```
        r'```Python\s*\n(.*?)\n```',  # ```Python\ncode\n```
        r'```py\s*\n(.*?)\n```',      # ```py\ncode\n```
        r'```\s*\n(.*?)\n```',        # ```\ncode\n```
        r'```python\s*(.*?)\s*```',   # ```python code ``` (可能有空格)
        r'```Python\s*(.*?)\s*```',   # ```Python code ``` (可能有空格)
        r'```py\s*(.*?)\s*```',       # ```py code ``` (可能有空格)
        r'```python(.*?)```',         # ```pythoncode``` (无换行)
        r'```Python(.*?)```',         # ```Pythoncode``` (无换行)
        r'```py(.*?)```',             # ```pycode``` (无换行)
        r'```(.*?)```',                # ```code``` (无换行)
    ]
    
    for pattern in markdown_patterns:
        match = re.search(pattern, code, re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            if extracted:
                logger.debug(f"从markdown代码块中提取代码（模式: {pattern[:20]}...）")
                return extracted
    
    # 2. 如果没有markdown标记，尝试查找代码块（以import、from、def、class或编码声明开头）
    # 查找第一个代码起始标记到最后一个非空行的内容
    code_start_patterns = [
        r'^import\s+\w+',              # import语句开头
        r'^from\s+\w+\s+import',       # from import语句开头
        r'^def\s+\w+',                 # def语句开头
        r'^class\s+\w+',               # class语句开头
        r'^#.*?coding',                # 编码声明
        r'^#.*?python',                # python注释
        r'^#.*?-\*-',                  # 编码声明格式
    ]
    
    for pattern in code_start_patterns:
        match = re.search(pattern, code, re.IGNORECASE | re.MULTILINE)
        if match:
            start_pos = match.start()
            # 从代码开始位置提取到末尾
            extracted = code[start_pos:].strip()
            if extracted:
                logger.debug(f"从文本中提取代码（找到代码起始标记: {pattern[:20]}...）")
                return extracted
    
    # 3. 如果都没有，检查是否包含Python关键字（可能是纯代码）
    python_keywords = ['import', 'from', 'def', 'class', 'if', 'for', 'while', 'with', 'try', 'except']
    has_python_keywords = any(keyword in code for keyword in python_keywords)
    if has_python_keywords:
        logger.debug("检测到Python关键字，返回原始内容（可能是纯代码）")
        return code
    
    # 4. 如果都没有，返回原始内容
    logger.debug("未找到代码标记，返回原始内容")
    return code


def clean_code(code: str) -> str:
    """
    清理代码，去除多余的空行和前后空白
    
    Args:
        code: 原始代码
    
    Returns:
        清理后的代码
    """
    if not code:
        return ""
    
    # 去除前后空白
    code = code.strip()
    
    # 去除开头的空行
    code = re.sub(r'^\n+', '', code)
    
    # 去除结尾的空行
    code = re.sub(r'\n+$', '', code)
    
    # 将多个连续空行压缩为最多两个空行
    code = re.sub(r'\n{3,}', '\n\n', code)
    
    return code
