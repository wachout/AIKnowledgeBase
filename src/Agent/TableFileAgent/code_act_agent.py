# -*- coding:utf-8 -*-
"""
OHCodeActAgent - 代码优先执行智能体
代码生成、复杂任务
基于CodeAct功能，创建代码智能体，检查代码，格式化代码，执行代码
代码运行环境在sandbox沙箱环境中
"""

import os
import subprocess
import tempfile
import logging
from typing import Dict, Any, Optional, List
from langchain_core.prompts import ChatPromptTemplate
from Config.llm_config import get_chat_tongyi

logger = logging.getLogger(__name__)


class OHCodeActAgent:
    """CodeAct智能体：代码生成和执行"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, enable_thinking=False)
        self.sandbox_dir = "conf/tmp/sandbox_files"
        os.makedirs(self.sandbox_dir, exist_ok=True)
        
        self.code_prompt = ChatPromptTemplate.from_template(
            """你是一个Python代码生成专家，擅长生成数据分析代码。

任务: {task}
数据信息: {data_info}
已有代码: {existing_code}

请生成Python代码来完成这个任务。代码应该：
1. 使用pandas进行数据处理
2. 使用numpy进行数值计算
3. 使用matplotlib/seaborn进行可视化（如需要）
4. 包含适当的错误处理
5. 输出结果到指定位置

请只返回Python代码，不要包含markdown格式或其他说明。
"""
        )
    
    def generate_and_execute(self, task: str, data_info: Dict[str, Any],
                            existing_code: str = "") -> Dict[str, Any]:
        """
        生成并执行代码
        
        Args:
            task: 任务描述
            data_info: 数据信息
            existing_code: 已有代码（可选）
            
        Returns:
            执行结果
        """
        try:
            # 1. 生成代码
            code = self._generate_code(task, data_info, existing_code)
            
            # 2. 检查代码
            check_result = self._check_code(code)
            if not check_result.get("valid", False):
                # 3. 修复代码
                code = self._fix_code(code, check_result.get("errors", []))
            
            # 4. 格式化代码
            code = self._format_code(code)
            
            # 5. 执行代码
            execution_result = self._execute_code(code, data_info)
            
            return {
                "success": execution_result.get("success", False),
                "code": code,
                "output": execution_result.get("output", ""),
                "error": execution_result.get("error"),
                "result_file": execution_result.get("result_file")
            }
            
        except Exception as e:
            logger.error(f"❌ CodeAct执行失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_code(self, task: str, data_info: Dict[str, Any], 
                      existing_code: str) -> str:
        """生成代码"""
        prompt = self.code_prompt.format(
            task=task,
            data_info=str(data_info),
            existing_code=existing_code
        )
        
        response = self.llm.invoke(prompt)
        code = response.content if hasattr(response, 'content') else str(response)
        
        # 清理代码（移除markdown格式）
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0].strip()
        elif "```" in code:
            code = code.split("```")[1].split("```")[0].strip()
        
        return code
    
    def _check_code(self, code: str) -> Dict[str, Any]:
        """检查代码语法"""
        try:
            compile(code, '<string>', 'exec')
            return {"valid": True}
        except SyntaxError as e:
            return {
                "valid": False,
                "errors": [{"type": "syntax", "message": str(e)}]
            }
    
    def _fix_code(self, code: str, errors: List[Dict[str, Any]]) -> str:
        """修复代码错误"""
        # 简化实现：实际应该调用LLM修复代码
        logger.warning(f"⚠️ 代码有错误，尝试修复: {errors}")
        return code  # 返回原代码，实际应该修复
    
    def _format_code(self, code: str) -> str:
        """格式化代码"""
        # 简化实现：可以使用autopep8或black
        return code
    
    def _execute_code(self, code: str, data_info: Dict[str, Any]) -> Dict[str, Any]:
        """在沙箱环境中执行代码"""
        try:
            # 创建临时Python文件
            temp_file = tempfile.NamedTemporaryFile(
                mode='w', suffix='.py', delete=False,
                dir=self.sandbox_dir
            )
            temp_file.write(code)
            temp_file.close()
            
            # 在subprocess中执行（沙箱隔离）
            result = subprocess.run(
                ['python', temp_file.name],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.sandbox_dir
            )
            
            # 清理临时文件
            os.unlink(temp_file.name)
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "output": result.stdout,
                    "result_file": None
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr,
                    "output": result.stdout
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "代码执行超时"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
