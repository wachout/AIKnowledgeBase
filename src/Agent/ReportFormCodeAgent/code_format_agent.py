# -*- coding: utf-8 -*-
"""
代码格式标准化智能体

功能：
1. 标准化代码格式
2. 统一代码风格
3. 优化代码可读性
"""

from typing import Dict, Any
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


class CodeFormatAgent:
    """代码格式标准化智能体"""
    
    def __init__(self, llm=None):
        """
        初始化智能体
        
        Args:
            llm: 大语言模型实例，如果为None则使用默认配置
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain相关库未安装，请安装必要的依赖")
        
        if llm is None:
            temperature = 0.3  # 格式化任务使用较低温度，更稳定
            api_key = config.config.GetSysConfig().get("agent_key", "sk-0270be722a48439e9ed73001e8e2524b")
            model_name = config.config.GetSysConfig().get("agent_code_name", "qwen3-coder-plus")
            base_url = config.config.GetSysConfig().get("agent_base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
            
            self.llm = ChatTongyi(
                temperature=temperature,
                model=model_name,
                api_key=api_key,
                base_url=base_url,
                streaming=False,
            )
            
        else:
            self.llm = llm
    
    def format_code(self, code: str) -> str:
        """
        标准化代码格式
        
        Args:
            code: 要格式化的代码
        
        Returns:
            格式化后的代码
        """
        try:
            prompt_template = ChatPromptTemplate.from_template(
                """你是一个Python代码格式标准化专家。请将以下代码格式化为标准的Python代码风格。

代码：
```python
{code}
```

请按照以下标准格式化代码：
1. 遵循PEP 8代码风格规范
2. 统一缩进（使用4个空格）
3. 统一导入顺序（标准库 -> 第三方库 -> 本地库）
4. 添加适当的空行分隔代码块
5. 确保注释格式规范
6. 统一变量命名风格
7. 优化代码可读性

**重要：只修改格式，不要改变代码的逻辑和功能。**

**CRITICAL OUTPUT REQUIREMENTS（关键输出要求）**:
- **MUST**: 只返回纯Python代码，不要包含任何markdown代码块标记（如 ```python 或 ```）
- **MUST**: 不要包含任何解释文字、注释说明或其他非代码内容
- **MUST**: 代码应该从第一行开始，直接是 import 语句或代码内容
- **FORBIDDEN**: 禁止使用 ```python 或 ``` 包裹代码
- **FORBIDDEN**: 禁止在代码前后添加任何说明文字

请严格按照要求，只输出格式化后的纯Python代码，不要包含任何markdown标记。"""
            )
            
            chain = prompt_template | self.llm | StrOutputParser()
            formatted_code = chain.invoke({
                "code": code
            })
            
            logger.info("✅ 代码格式化完成")
            return formatted_code
            
        except Exception as e:
            logger.error(f"❌ 代码格式化失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # 格式化失败时返回原代码
            return code
