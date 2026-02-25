# -*- coding: utf-8 -*-
"""
报表代码生成智能体

功能：
1. 根据SQL语句和逻辑要求生成报表代码
2. 代码结构按照给定的模板格式
3. 支持MySQL和PostgreSQL数据库
"""

from typing import List, Dict, Any, Optional

try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_community.chat_models.tongyi import ChatTongyi
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
import logging
from Config import config

logger = logging.getLogger(__name__)


class ReportFormCodeAgent:
    """报表代码生成智能体"""
    
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
            
            # self.llm = ChatOpenAI(
            #     temperature=0.6,
            #     model=os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-reasoner"),
            #     api_key=os.getenv("DEEPSEEK_API_KEY"),
            #     base_url=os.getenv("DEEPSEEK_URL_BASE", "https://api.deepseek.com/v1"),
            # )
            
        else:
            self.llm = llm
    
    def generate_report_code(self,
                           base_prompt: str,
                           csv_name: str = None,
                           csv_description: str = None) -> str:
        """
        生成报表代码（基于CSV文件）
        
        Args:
            base_prompt: 已经替换了动态参数的prompt模板，包含：
                - [CSV_NAME]: CSV文件名
                - [csv描述]: CSV文件描述
                - [逻辑要求]: 逻辑计算要求
                - [TXT_NAME]: 输出文件名
            csv_name: CSV文件名（可选，如果base_prompt中已包含则不需要）
            csv_description: CSV文件描述（可选，如果base_prompt中已包含则不需要）
        
        Returns:
            生成的Python代码字符串
        """
        try:
            # 构建prompt
            prompt_template = ChatPromptTemplate.from_template(
                """你是一个专业的数据分析代码生成专家。请根据以下信息生成完整的Python代码。

**代码模板：**
{base_prompt}

**请完成以下任务：**

1. **理解CSV数据**：
   - 仔细阅读CSV描述，了解数据的结构、内容和类型
   - 如果数据为字符串、数值、日期时间等不同类型，请分别考虑相应的处理和分析方法
   - 根据数据的类型选择合适的统计分析方法
2. **理解逻辑要求**：深入理解逻辑要求部分，明确需要计算的统计指标和计算逻辑
   - 判断数据类型（数值型、分类型、时间序列、字符串等）
   - 选择合适的统计方法（描述性统计、分布分析、相关性分析、分组统计、趋势分析、频率分析、文本分析等）
   - 根据逻辑要求确定需要计算的具体指标和结果格式
   - 列之间的关系和依赖
3. **生成完整代码**：
   - 在"###一下是需要您完成的代码部分###"部分，编写完整的逻辑计算代码
   - 根据逻辑要求，选择合适的统计方法，计算各种统计指标并保存在result中
   - 作为数据分析师，重点关注根据不同的数据类型：
     * 描述性统计：总数、均值、中位数、众数、方差、标准差、四分位数、极值等
     * 分布分析：数据分布特征、偏度、峰度等
     * 相关性分析：变量间的相关关系
     * 分组统计：按不同维度进行分组统计
     * 趋势分析：时间序列趋势、变化率等
     * 频率分析：类别频率、出现次数等
     * 文本分析：关键词提取、情感分析等
     * 时间序列分析：周期性、季节性等
     * 字符串分析：频次统计、模式识别等
     * 其他高级统计分析：根据逻辑要求进行相应的统计计算
     * 关键点：是根据数据类型和逻辑要求选择合适的统计方法
     * 需要注意：这个分析结果要做为echarts图表的数据来源，所以要确保结果的格式清晰且易于前端处理
   - result的格式可以是：
     * 单一指标：字典格式 {{"key": "value"}}
     * 多个需要排序的指标：字典加列表格式 {{"key": ["value1", "value2", ...]}}
     * 需要排序和描述的指标：字典加列表加字典格式 {{"key": [{{"k_1": "v_1"}}, {{"k_2": "v_2"}}, ...]}}
   - 确保代码逻辑清晰，注释完整
   - 确保result变量最终包含所有计算结果，使用str转换为字符串格式以便写入文件

4. **代码要求**：
   - 代码必须完整可执行，严格按照模板结构生成
   - 使用pandas进行数据处理和统计分
   - 必须导入json库用于序列化result（模板中已包含）
   - 逻辑计算部分要详细，包含所有必要的统计计算步骤
   - 最后将result（强转换为字符串）写入文件并打印

**重要提示：**
- 代码模板中的这些占位符应该保持不变，它们会在运行时被替换
- 你只需要：
  1. 在逻辑计算部分编写完整的统计分析代码，不要返回无用信息，精简保留有价值的信息
  2. 分析给定的逻辑要求部分，如果提到的指标不在CSV数据中，尝试通过已有数据进行计算或推导，但是不能编造数据，不能随意添加不存在的列，必须基于已有数据进行计算
  3. 确保result使用str转换为字符串后再写入文件
  4. 不要修改代码模板的其他部分，保持代码结构完整

**CRITICAL OUTPUT REQUIREMENTS（关键输出要求）**:
- **MUST**: 只返回纯Python代码，不要包含任何markdown代码块标记（如 ```python 或 ```）
- **MUST**: 不要包含任何解释文字、注释说明或其他非代码内容
- **MUST**: 代码应该从第一行开始，直接是 import 语句或代码内容
- **FORBIDDEN**: 禁止使用 ```python 或 ``` 包裹代码
- **FORBIDDEN**: 禁止在代码前后添加任何说明文字

**输出示例（正确）**:
import pandas as pd
import json
df = pd.read_csv('file.csv')
...

**输出示例（错误 - 不要这样做）**:
```python
import pandas as pd
...
```

请严格按照要求，只输出纯Python代码，不要包含任何markdown标记。"""
            )
            
            chain = prompt_template | self.llm | StrOutputParser()
            result = chain.invoke({
                "base_prompt": base_prompt
            })
            
            logger.info("✅ 报表代码生成成功")
            return result
            
        except Exception as e:
            logger.error(f"❌ 报表代码生成失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
