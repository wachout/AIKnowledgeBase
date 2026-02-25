import os
import json # Added for json.dumps
import re # For regex pattern matching
import logging
# from dotenv import load_dotenv # For environment variables
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from typing import Dict, Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# 使用统一的LLM配置
from Config.llm_config import get_chat_openai
from .data_extractor import StatisticsDataExtractor

# Using unified LLM configuration
llm = get_chat_openai(temperature=0.7, streaming=False)


class EchartsAgent:
    def __init__(self, llm_instance=None):
        # 🎯 统一管理：使用传入的llm_instance，如果没有则使用默认配置
        if llm_instance is None:
            from Config.llm_config import get_chat_openai
            llm_instance = get_chat_openai(temperature=0.7, streaming=False)
        self.llm = llm_instance
        self.data_to_echarts_prompt = ChatPromptTemplate.from_template(
            """
            You are an expert in Echarts data visualization.
            Your task is to generate appropriate Echarts visualization configurations based on statistical indicators and user requirements.

            User Query: {query}
            Statistics Data: {data}

            Instructions:
            1. **Focus on User Requirements**:
               - Carefully analyze the user query to understand what type of report/chart format they want
               - Identify keywords indicating chart types (e.g., "柱状图", "折线图", "饼图", "散点图", "趋势", "分布", "对比", etc.)
               - Understand the user's intent: do they want to see trends, distributions, comparisons, correlations, etc.?
            
            2. **Analyze Statistics Indicators**:
               - The input data contains comprehensive statistical indicators including:
                 * descriptive_statistics: mean, median, mode, variance, std, min, max, quartiles, etc.
                 * distribution_analysis: skewness, kurtosis, distribution type
                 * correlation_analysis: correlation matrix, strong correlations
                 * frequency_analysis: value frequencies, top values
                 * grouped_statistics: statistics by groups
                 * trend_analysis: trends over time
                 * time_series_analysis: seasonal patterns, periodic patterns
                 * column_joint_analysis: pairwise correlations, cross-tabulation, joint frequencies
               - Extract relevant statistical indicators based on user requirements
               - Use the statistical values to generate appropriate chart data
            
            3. **Chart Type Selection**:
               - Based on user query and available statistics, choose the most suitable chart type:
                 * Bar chart (柱状图): for comparisons, distributions, frequency counts
                 * Line chart (折线图): for trends, time series, changes over time
                 * Pie chart (饼图): for proportions, frequency distributions
                 * Scatter plot (散点图): for correlations, relationships between variables
                 * Box plot (箱线图): for distributions, quartiles
                 * Heatmap (热力图): for correlation matrices, cross-tabulation
               - Consider multiple series if comparing different groups or indicators
            
            4. **Data Extraction from Statistics**:
               - 🎯 优先使用预提取的图表数据（extracted_chart）：
                 * 使用 extracted_chart.xAxis_data 作为 xAxis.data
                 * 使用 extracted_chart.series_data 作为 series[].data
                 * 这些数据是从统计指标中自动提取的数值数据
               - 如果预提取数据不足，从 statistics_result 中提取：
                 * For descriptive statistics: use mean, median, min, max, quartiles
                 * For frequency analysis: use frequency counts as chart data
                 * For correlation analysis: extract correlation values for scatter plots or heatmaps
                 * For grouped statistics: extract group means/medians for grouped bar charts
                 * For trend analysis: extract trend values over time for line charts
            
            5. **Echarts Configuration Requirements**:
               - Generate complete and valid Echarts JSON configuration
               - Include all necessary components: title, tooltip, legend, xAxis, yAxis, series
               - Use meaningful titles based on user query and statistics type
               - Set appropriate axis labels based on the statistical indicators being visualized
               - Ensure data types are correct (numbers as numbers, strings as strings)
               - Handle None/NULL values: convert to appropriate defaults (string to "", number to 0)
               - Use boolean values as true/false (not True/False)
            
            6. **Output Format**:
               - Your response MUST be only the JSON configuration, with no additional text, explanations, or markdown formatting (e.g. no ```json ... ```)
               - The output must be a valid JSON object with "echarts_config" field
            
            **Output Format**:
            {{
              "echarts_config": {{
                "title": {{ "text": "Chart Title Based on User Query" }},
              "tooltip": {{}},
                "legend": {{ "data": ["Series Names"] }},
                "xAxis": {{ "type": "category", "data": [...] }},
                "yAxis": {{ "type": "value" }},
                "series": [{{ "name": "Series Name", "type": "bar/line/pie/scatter", "data": [...] }}]
              }}
            }}
            
            Example - Bar chart for frequency analysis:
            {{
              "echarts_config": {{
                "title": {{ "text": "类别频率分布" }},
                "tooltip": {{ "trigger": "axis" }},
                "legend": {{ "data": ["频率"] }},
                "xAxis": {{ "type": "category", "data": ["类别A", "类别B", "类别C"] }},
                "yAxis": {{ "type": "value", "name": "频率" }},
                "series": [{{ "name": "频率", "type": "bar", "data": [100, 200, 150] }}]
              }}
            }}

            ⚠️ 重要提醒：
            - xAxis.type 必须是有效的值："category", "value", "time" 等，不能为 null
            - xAxis.data 和 series[].data 不能为空数组，必须包含实际数据
            - series[].type 必须是有效的 ECharts 类型："bar", "line", "pie", "scatter" 等，不能使用中文描述

            JSON Configuration (strictly JSON, no other text):
            """
        )

        self.validation_prompt = ChatPromptTemplate.from_template(
            """
            You are an Echarts configuration validator.
            Review the following JSON configuration.

            JSON Configuration:
            {echarts_json}

            Validation Checklist:
            1. Is the JSON valid?
            2. Does it contain "echarts_config" field?
            3. Does the "echarts_config" adhere to the Echarts schema?
            4. Are all necessary components for a basic chart present in "echarts_config" (e.g., series, axis if applicable)?
            5. Does the chart type seem appropriate for the kind of data usually represented in such a structure?
            6. Are there any obvious errors or omissions?
            7. Are there any "None" or "NULL" data?
            
            Note: If echarts_config is an empty object {{}}, it is still valid (used for large datasets shown as tables).
            
            Your Feedback:
            If the JSON is valid, complete, and adheres to the structure (with echarts_config), respond with the single word "VALID" and nothing else.
            Otherwise, provide a concise list of issues, each on a new line, starting with "INVALID:". Example:
            INVALID:
            - Missing yAxis configuration in echarts_config.
            - Series data for 'sales' is empty.
            - echarts_config field is missing.
            """
        )

        self.echarts_chain = (
            {"data": RunnablePassthrough(), "query": RunnablePassthrough()}
            | self.data_to_echarts_prompt
            | self.llm
            | StrOutputParser()
        )

        self.validation_chain = (
            self.validation_prompt
            | self.llm
            | StrOutputParser()
        )

    def generate_echarts_config(self, data: str, query: str) -> dict:
        """
        Generates an Echarts configuration from statistics data and a query.
        Includes a self-correction step and data extraction preprocessing.
        Returns a dictionary containing echarts_config.

        Args:
            data: JSON string containing statistics_result (statistical indicators)
            query: User query (for understanding report format requirements)
        """
        try:
            # 🎯 预处理步骤：使用 StatisticsDataExtractor 提取实际数值数据
            parsed_data = json.loads(data) if isinstance(data, str) else data

            # 提取图表数据（xAxis.data 和 series.data）
            extracted_chart = StatisticsDataExtractor.extract_chart_data(parsed_data)

            # 检查是否有实际提取到的数据
            has_actual_data = (extracted_chart.get("xAxis_data") and len(extracted_chart["xAxis_data"]) > 0 and
                             extracted_chart.get("series_data") and len(extracted_chart["series_data"]) > 0)

            if has_actual_data:
                # 将提取的数据添加到查询中
                extracted_data_str = json.dumps(extracted_chart, ensure_ascii=False, indent=2)

                enhanced_query = f"""{query}

📊 预提取的图表数据（请优先使用这些数据）：
{extracted_data_str}

请根据预提取的数据生成 ECharts 配置：
1. 使用 extracted_chart.xAxis_data 作为 xAxis.data
2. 使用 extracted_chart.series_data 作为 series[].data
3. 选择合适的图表类型（line, bar, pie, scatter 等）
4. 确保 xAxis.type 不是 null（使用 'category' 或 'value'）

统计指标说明：
- 完整的统计指标数据已提供在输入数据中
- 请根据用户查询意图，从统计指标中选择合适的数据来生成图表
- 重点关注用户查询中提到的指标类型和展示方式"""
            else:
                # 如果没有提取到实际数据，使用原始查询方式
                logger.info("⚠️ 未提取到实际图表数据，使用原始查询方式")
                enhanced_query = f"""{query}

请根据用户查询，理解用户要求的报表展示格式：
1. 用户希望看到什么类型的图表（柱状图、折线图、饼图、散点图等）？
2. 用户关注哪些统计指标（趋势、分布、对比、相关性等）？
3. 如何从提供的统计指标中提取数据来生成图表？

统计指标说明：
- 统计指标数据已提供在输入数据中
- 请根据用户查询意图，从统计指标中选择合适的数据来生成图表
- 重点关注用户查询中提到的指标类型和展示方式"""

        except Exception as e:
            logger.warning(f"⚠️ 数据预处理失败，使用原始数据: {e}")
            enhanced_query = f"""{query}

请根据用户查询，理解用户要求的报表展示格式：
1. 用户希望看到什么类型的图表（柱状图、折线图、饼图、散点图等）？
2. 用户关注哪些统计指标（趋势、分布、对比、相关性等）？
3. 如何从提供的统计指标中提取数据来生成图表？

统计指标说明：
- 统计指标数据已提供在输入数据中
- 请根据用户查询意图，从统计指标中选择合适的数据来生成图表
- 重点关注用户查询中提到的指标类型和展示方式"""

        max_retries = 3

        # 定义基础查询，用于重试时的错误处理
        base_query = f"""{query}

请根据用户查询，理解用户要求的报表展示格式：
1. 用户希望看到什么类型的图表（柱状图、折线图、饼图、散点图等）？
2. 用户关注哪些统计指标（趋势、分布、对比、相关性等）？
3. 如何从提供的统计指标中提取数据来生成图表？

统计指标说明：
- 统计指标数据已提供在输入数据中
- 请根据用户查询意图，从统计指标中选择合适的数据来生成图表
- 重点关注用户查询中提到的指标类型和展示方式"""
        
        for attempt in range(max_retries):
            try:
                # Step 2: Generate Echarts JSON
                # 使用原始数据和增强查询（包含预提取的数据）
                generated_json_str = self.echarts_chain.invoke({"data": data, "query": enhanced_query})
                
                # Basic check if the output is likely JSON (starts with { and ends with })
                json_start = generated_json_str.find('{')
                json_end = generated_json_str.rfind('}')
                if json_start != -1 and json_end != -1 and json_start < json_end:
                    generated_json_str = generated_json_str[json_start : json_end+1]
                else:
                    print(f"Attempt {attempt+1}: LLM did not return a JSON-like structure. Output: {generated_json_str}")
                    if attempt == max_retries - 1:
                        raise ValueError("LLM failed to generate a JSON-like structure after multiple attempts.")
                    enhanced_query = base_query + f"\nPrevious attempt failed to produce valid JSON. Please ensure the output is strictly a JSON object with 'echarts_config' field. Previous output: {generated_json_str}"
                    continue

                # Convert Python-style boolean values (True/False) to JSON-style (true/false)
                generated_json_str = re.sub(r'\bTrue\b', 'true', generated_json_str)
                generated_json_str = re.sub(r'\bFalse\b', 'false', generated_json_str)

                # Step 3: Validate the generated JSON
                validation_feedback = self.validation_chain.invoke({"echarts_json": generated_json_str})

                if "VALID" in validation_feedback.upper():
                    # Parse JSON
                    parsed_json = json.loads(generated_json_str)
                    
                    # Ensure echarts_config exists
                    if "echarts_config" not in parsed_json:
                        # If root level has echarts fields, wrap them
                        if any(key in parsed_json for key in ["title", "series", "xAxis", "yAxis", "legend", "tooltip"]):
                            parsed_json = {
                                "echarts_config": parsed_json
                            }
                        else:
                            parsed_json = {
                                "echarts_config": {}
                            }
                    
                    # 校验：检查 echarts_config 是否为空或无效
                    echarts_config = parsed_json.get("echarts_config", {})
                    if not echarts_config or not isinstance(echarts_config, dict):
                        # 如果 echarts_config 为空或不是字典，返回空对象
                        return {"echarts_config": {}}
                    
                    # 检查是否有必要的图表组件（至少要有 series 或 title）
                    has_series = "series" in echarts_config and echarts_config.get("series")
                    has_title = "title" in echarts_config and echarts_config.get("title")
                    
                    # 如果既没有 series 也没有 title，或者 series 为空列表，返回空对象
                    if not has_series and not has_title:
                        return {"echarts_config": {}}
                    
                    # 如果 series 存在但是空列表，返回空对象
                    if has_series and isinstance(echarts_config.get("series"), list) and len(echarts_config.get("series", [])) == 0:
                        return {"echarts_config": {}}
                    
                    return parsed_json
                else:
                    # If not valid, refine the query for the next attempt
                    enhanced_query = base_query + f"\nReview Feedback: {validation_feedback}. Please address these issues in the next generation. Ensure the output has 'echarts_config' field."
                    print(f"Attempt {attempt+1} failed validation. Refining query and retrying.")
            
            except json.JSONDecodeError as e:
                enhanced_query = base_query + f"\nPrevious attempt resulted in a JSONDecodeError: {e}. Ensure the output is valid JSON with 'echarts_config' field."
                if attempt == max_retries - 1:
                    raise ValueError(f"Failed to generate valid JSON after {max_retries} attempts. Last error: {e}")
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                enhanced_query = base_query + f"\nAn error occurred: {str(e)}. Please try to fix this in the next attempt."

        raise ValueError(f"Failed to generate a valid Echarts configuration after {max_retries} attempts.")
    
    

# The __main__ block has been moved to examples/run_agent.py
# You can run that script to see the agent in action.
