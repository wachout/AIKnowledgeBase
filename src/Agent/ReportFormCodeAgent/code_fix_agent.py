# -*- coding: utf-8 -*-
"""
代码修改智能体

功能：
1. 根据检查结果修改代码
2. 修复语法错误、结构错误和逻辑错误
"""

from typing import Dict, Any
import logging

try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_community.chat_models.tongyi import ChatTongyi
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

from Config import config

logger = logging.getLogger(__name__)


class CodeFixAgent:
    """代码修改智能体"""
    
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
            from Config.llm_config import get_chat_tongyi
            self.llm = get_chat_tongyi(temperature=0.7, streaming=False, enable_thinking=False)
            self.llm = self.llm.bind(enable_thinking=False)
        else:
            self.llm = llm
    
    def fix_code(self, code: str, check_result: Dict[str, Any], base_prompt: str = None) -> str:
        """
        修复代码
        
        Args:
            code: 原始代码
            check_result: 代码检查结果
            base_prompt: 原始prompt（可选，用于上下文）
        
        Returns:
            修复后的代码
        """
        try:
            # 收集所有错误和建议
            all_errors = []
            all_errors.extend(check_result.get("syntax_errors", []))
            all_errors.extend(check_result.get("structure_errors", []))
            all_errors.extend(check_result.get("logic_errors", []))
            all_suggestions = check_result.get("suggestions", [])
            
            if not all_errors and not all_suggestions:
                logger.info("✅ 代码无需修复")
                return code
            
            prompt_template = ChatPromptTemplate.from_template(
                """你是一个Python代码修复专家。请根据错误信息和建议修复以下代码。

原始代码：
```python
{code}
```

原始要求：
{base_prompt}

发现的错误：
{errors}

建议：
{suggestions}

请修复代码中的所有错误，确保：
1. 修复所有语法错误
2. 修复所有结构错误（确保包含必要的导入、变量、文件写入等）
3. 修复所有逻辑错误（确保result变量正确生成、使用json.dumps等）
4. 保持代码的完整性和可执行性
5. 不要改变代码的核心逻辑，只修复错误

**CRITICAL OUTPUT REQUIREMENTS（关键输出要求）**:
- **MUST**: 只返回纯Python代码，不要包含任何markdown代码块标记（如 ```python 或 ```）
- **MUST**: 不要包含任何解释文字、注释说明或其他非代码内容
- **MUST**: 代码应该从第一行开始，直接是 import 语句或代码内容
- **FORBIDDEN**: 禁止使用 ```python 或 ``` 包裹代码
- **FORBIDDEN**: 禁止在代码前后添加任何说明文字

请严格按照要求，只输出修复后的纯Python代码，不要包含任何markdown标记。"""
            )
            
            errors_text = "\n".join([f"- {e}" for e in all_errors]) if all_errors else "无"
            suggestions_text = "\n".join([f"- {s}" for s in all_suggestions]) if all_suggestions else "无"
            
            chain = prompt_template | self.llm | StrOutputParser()
            fixed_code = chain.invoke({
                "code": code,
                "base_prompt": base_prompt or "无特殊要求",
                "errors": errors_text,
                "suggestions": suggestions_text
            })
            
            logger.info("✅ 代码修复完成")
            return fixed_code
            
        except Exception as e:
            logger.error(f"❌ 代码修复失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # 修复失败时返回原代码
            return code
