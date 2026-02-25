# -*- coding:utf-8 -*-
"""
统一的PDF配置工具
从.env文件中读取PDF配置
"""

import os
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()


def is_pdf_advanced_enabled() -> bool:
    """
    检查是否启用高级PDF解析
    
    Returns:
        bool: 如果PDF_FLAG=True返回True，否则返回False
    """
    flag_str = os.getenv("PDF_FLAG", "False")
    return flag_str.lower() == "true"
