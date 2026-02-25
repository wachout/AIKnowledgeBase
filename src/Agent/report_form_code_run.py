# -*- coding: utf-8 -*-
"""
报表代码生成运行入口

功能：
1. 调用ReportFormCodeAgent生成报表代码
2. 代码检查、修复和格式化工作流
3. 处理SQL语句和prompt参数
"""

from typing import List, Dict, Any
import logging

from Agent.ReportFormCodeAgent.report_form_code_agent import ReportFormCodeAgent
from Agent.ReportFormCodeAgent.code_check_agent import CodeCheckAgent
from Agent.ReportFormCodeAgent.code_fix_agent import CodeFixAgent
from Agent.ReportFormCodeAgent.code_format_agent import CodeFormatAgent
from Agent.ReportFormCodeAgent.code_utils import extract_python_code, clean_code

logger = logging.getLogger(__name__)


def generate_report_code(base_prompt: str,
                         csv_name: str = None,
                         csv_description: str = None) -> str:
    """
    生成报表代码（基于CSV文件）- 包含代码检查、修复和格式化工作流
    
    Args:
        base_prompt: 已经替换了动态参数的prompt模板，包含：
            - [CSV_NAME]: CSV文件名
            - [csv描述]: CSV文件描述
            - [逻辑要求]: 逻辑计算要求
            - [TXT_NAME]: 输出文件名
        csv_name: CSV文件名（可选，如果base_prompt中已包含则不需要）
        csv_description: CSV文件描述（可选，如果base_prompt中已包含则不需要）
    
    Returns:
        生成的Python代码字符串（已检查和格式化）
    """
    try:
        # 初始化智能体
        code_gen_agent = ReportFormCodeAgent()
        code_check_agent = CodeCheckAgent()
        code_fix_agent = CodeFixAgent()
        code_format_agent = CodeFormatAgent()
        
        # 步骤1: 生成代码
        logger.info("📝 步骤1: 生成初始代码...")
        raw_code = code_gen_agent.generate_report_code(
            base_prompt=base_prompt,
            csv_name=csv_name,
            csv_description=csv_description
        )
        # 提取纯Python代码
        code = extract_python_code(raw_code)
        code = clean_code(code)
        logger.info("✅ 初始代码生成完成")
        
        # 步骤2-4: 代码检查、修复循环（最多6次）
        max_fix_attempts = 6
        for attempt in range(max_fix_attempts):
            logger.info(f"🔍 步骤2.{attempt + 1}: 检查代码（第 {attempt + 1} 次）...")
            check_result = code_check_agent.check_code(code, base_prompt)
            
            if check_result.get("is_valid", False):
                logger.info("✅ 代码检查通过，无需修复")
                break
            else:
                logger.warning(f"⚠️  代码检查发现问题: {check_result.get('error_summary', '')}")
                if attempt < max_fix_attempts - 1:
                    logger.info(f"🔧 步骤3.{attempt + 1}: 修复代码（第 {attempt + 1} 次）...")
                    fixed_raw_code = code_fix_agent.fix_code(code, check_result, base_prompt)
                    # 提取纯Python代码
                    code = extract_python_code(fixed_raw_code)
                    code = clean_code(code)
                    logger.info(f"✅ 代码修复完成（第 {attempt + 1} 次）")
                else:
                    logger.warning(f"⚠️  已达到最大修复次数（{max_fix_attempts}次），使用当前代码")
        
        # 步骤5: 格式化代码
        logger.info("✨ 步骤4: 格式化代码...")
        formatted_raw_code = code_format_agent.format_code(code)
        # 提取纯Python代码
        code = extract_python_code(formatted_raw_code)
        code = clean_code(code)
        logger.info("✅ 代码格式化完成")
        
        logger.info("🎉 代码生成工作流完成")
        return code
        
    except Exception as e:
        logger.error(f"报表代码生成失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
