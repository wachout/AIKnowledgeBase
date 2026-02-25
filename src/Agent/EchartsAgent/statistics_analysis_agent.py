# -*- coding: utf-8 -*-
"""
统计分析汇总智能体 - 专门负责对统计指标进行深入分析和汇总
"""

import os
import json
import re
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Make sure to have the required API key and model settings in your .env file
# api_key = os.getenv("QWEN_API_KEY")
# base_url = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
# model_name = os.getenv("THEME_MODEL", "deepseek3.2")
#
# if not api_key:
#     raise ValueError("QWEN_API_KEY not found in environment variables. Please set it in the .env file.")
#
# # Using model as configured
# llm = ChatOpenAI(
#     temperature=0.7,
#     model=model_name,
#     api_key=api_key,
#     base_url=base_url,
# )


class StatisticsAnalysisAgent:
    """统计分析汇总智能体 - 专门负责统计指标的分析和汇总"""
    
    def __init__(self, llm_instance=None):
        # 如果没有提供llm_instance，使用默认配置创建
        if llm_instance is None:
            from Config.llm_config import get_chat_openai
            self.llm = get_chat_openai(temperature=0.7, streaming=False)
        else:
            self.llm = llm_instance
        
        self.analysis_prompt = ChatPromptTemplate.from_template(
            """
            You are an expert statistician specializing in comprehensive statistical analysis and summary.
            Your task is to analyze the given statistical indicators and provide detailed insights and summaries.

            User Query: {query}
            Statistics Data: {data}

            Statistics Data Structure:
            The input data contains comprehensive statistical indicators including:
            1. **descriptive_statistics**: mean, median, mode, variance, std, min, max, quartiles (q25, q50, q75), range, count
            2. **distribution_analysis**: skewness, kurtosis, distribution type
            3. **correlation_analysis**: correlation matrix, strong correlations (|r| > 0.7)
            4. **frequency_analysis**: unique_count, total_count, frequency distribution, top_10 values
            5. **text_analysis**: total_words, unique_words, top_keywords, avg_text_length
            6. **string_analysis**: length_stats (mean, min, max, std), patterns (email, numeric, mixed), unique_ratio
            7. **grouped_statistics**: statistics by groups (count, mean, median, std, min, max per group)
            8. **trend_analysis**: trend direction (increasing/decreasing/stable), change_rate, first_value, last_value
            9. **time_series_analysis**: monthly_pattern, weekly_pattern, time_range
            10. **column_joint_analysis**: 
                - pairwise_correlation: pearson_correlation, spearman_correlation, correlation_strength, correlation_direction
                - cross_analysis: cross_table, chi_square, p_value, cramers_v, is_independent
                - joint_frequency: joint_frequency, conditional_frequency, most_common_combination
                - conditional_statistics: conditional_statistics, group_comparison

            Instructions:
            1. **Comprehensive Statistical Analysis**: 
               - Analyze all available statistical indicators thoroughly
               - Identify key patterns, trends, and relationships in the data
               - Extract meaningful insights from descriptive statistics, distributions, correlations, etc.
               - Pay special attention to:
                 * Extreme values (min, max) and their significance
                 * Distribution characteristics (skewness, kurtosis, distribution type)
                 * Strong correlations and their implications
                 * Frequency patterns and top values
                 * Trend directions and change rates
                 * Group differences and conditional statistics
            
            2. **Statistical Summary**: Generate comprehensive summary including:
               - **Summary**: Overall summary of the statistical findings and main characteristics
               - **Key Insights**: Important statistical discoveries (3-7 insights):
                 * Key statistical patterns found
                 * Significant correlations or relationships
                 * Distribution characteristics
                 * Trend patterns
                 * Group differences or conditional patterns
               - **Statistical Characteristics**:
                 * **Distribution**: Data distribution characteristics (normal, skewed, etc.)
                 * **Central Tendency**: Mean, median, mode patterns
                 * **Variability**: Variance, standard deviation, range patterns
                 * **Correlations**: Key correlations and relationships between variables
                 * **Trends**: Trend patterns over time (if applicable)
                 * **Group Patterns**: Patterns across different groups (if applicable)
               - **Anomalies**: Outliers, unusual patterns, or special cases (if any)
               - **Statistical Summary**: Key statistical metrics summary (mean, median, extremes, correlations, etc.)
            
            3. **Business/Statistical Significance**: 
               - Explain the statistical significance of the findings
               - Highlight important relationships and patterns
               - Provide context for the statistical results
            
            4. Your response MUST be only the JSON configuration, with no additional text, explanations, or markdown formatting (e.g. no ```json ... ```).
            
            **Output Format**:
            {{
              "statistics_summary": {{
                "summary": "统计指标整体概述（简要描述统计数据的核心特征和主要发现）",
                "key_insights": [
                  "关键洞察1（从统计指标中发现的重要模式或关系）",
                  "关键洞察2",
                  "关键洞察3",
                  "关键洞察4"
                ],
                "statistical_characteristics": {{
                  "distribution": "数据分布特征描述（基于分布分析指标）",
                  "central_tendency": "集中趋势特征（均值、中位数、众数模式）",
                  "variability": "变异性特征（方差、标准差、极差模式）",
                  "correlations": "相关性特征（关键变量间的相关关系）",
                  "trends": "趋势特征（时间序列趋势模式，如适用）",
                  "group_patterns": "分组模式（不同组间的统计差异，如适用）"
                }},
                "anomalies": "异常值或特殊模式描述（如有）",
                "statistical_summary": "统计摘要（关键统计指标汇总：均值、中位数、极值、相关性等）"
              }}
            }}
            
            Example:
            {{
              "statistics_summary": {{
                "summary": "统计数据显示，数值型变量呈现近似正态分布，存在多个强相关关系，文本型变量呈现明显的频率集中特征",
                "key_insights": [
                  "年龄与收入呈现中等正相关（r=0.65），表明年龄增长与收入增加相关",
                  "数据分布呈现右偏特征（偏度=1.2），说明存在较多高值异常点",
                  "类别A的频率最高，占总数的45%，呈现明显的集中分布",
                  "时间序列数据显示明显的季节性模式，12月份数值显著高于其他月份",
                  "分组统计显示，不同地区的均值差异显著，最大差异达到30%"
                ],
                "statistical_characteristics": {{
                  "distribution": "主要数值变量呈现右偏分布（偏度>0），峰度接近3，接近正态分布",
                  "central_tendency": "均值与中位数接近，表明数据分布相对对称；众数集中在特定区间",
                  "variability": "标准差较大，变异系数>0.3，表明数据变异性较高",
                  "correlations": "发现3对变量存在强相关关系（|r|>0.7），其中变量A与变量B的相关性最强（r=0.85）",
                  "trends": "时间序列显示明显的上升趋势，年均增长率约15%，存在季节性波动",
                  "group_patterns": "按地区分组后，东部地区均值显著高于西部地区，差异达25%"
                }},
                "anomalies": "发现2个异常值点，数值超过3倍标准差，可能影响整体统计结果",
                "statistical_summary": "样本量1000，均值50.2，中位数48.5，标准差12.3，最小值20，最大值95，四分位距25.8；发现5对强相关变量；频率最高的类别占比45%"
              }}
            }}

            JSON Output (strictly JSON, no other text):
            """
        )
        
        self.analysis_chain = (
            {"data": RunnablePassthrough(), "query": RunnablePassthrough()}
            | self.analysis_prompt
            | self.llm
            | StrOutputParser()
        )
    
    def generate_statistics_summary(self, data: str, query: str) -> dict:
        """
        生成统计指标分析汇总
        
        Args:
            data: 统计指标数据字符串（JSON格式）
            query: 用户查询
        
        Returns:
            包含statistics_summary的字典
        """
        max_retries = 3
        base_query = query
        for attempt in range(max_retries):
            try:
                # 生成统计分析汇总
                generated_json_str = self.analysis_chain.invoke({"data": data, "query": base_query})
                
                # 提取JSON部分
                json_start = generated_json_str.find('{')
                json_end = generated_json_str.rfind('}')
                if json_start != -1 and json_end != -1 and json_start < json_end:
                    generated_json_str = generated_json_str[json_start : json_end+1]
                else:
                    print(f"Attempt {attempt+1}: LLM did not return a JSON-like structure.")
                    if attempt == max_retries - 1:
                        raise ValueError("LLM failed to generate a JSON-like structure after multiple attempts.")
                    base_query = query + f"\nPrevious attempt failed to produce valid JSON. Please ensure the output is strictly a JSON object with 'statistics_summary' field."
                    continue
                
                # 转换Python布尔值为JSON布尔值
                generated_json_str = re.sub(r'\bTrue\b', 'true', generated_json_str)
                generated_json_str = re.sub(r'\bFalse\b', 'false', generated_json_str)
                
                # 解析JSON
                parsed_json = json.loads(generated_json_str)
                
                # 确保有statistics_summary字段
                if "statistics_summary" not in parsed_json:
                    parsed_json["statistics_summary"] = {
                        "summary": "统计指标分析汇总",
                        "key_insights": [],
                        "statistical_characteristics": {
                            "distribution": "",
                            "central_tendency": "",
                            "variability": "",
                            "correlations": "",
                            "trends": "",
                            "group_patterns": ""
                        },
                        "anomalies": "",
                        "statistical_summary": ""
                    }
                
                return parsed_json
                
            except json.JSONDecodeError as e:
                print(f"Attempt {attempt+1}: Generated analysis is not valid JSON: {e}")
                base_query = query + f"\nPrevious attempt resulted in a JSONDecodeError: {e}. Ensure the output is valid JSON with 'statistics_summary' field."
                if attempt == max_retries - 1:
                    raise ValueError(f"Failed to generate valid JSON after {max_retries} attempts. Last error: {e}")
            except Exception as e:
                print(f"An unexpected error occurred during statistics analysis: {e}")
                if attempt == max_retries - 1:
                    raise e
                base_query = query + f"\nAn error occurred: {str(e)}. Please try to fix this in the next attempt."
        
        raise ValueError(f"Failed to generate a valid statistics summary after {max_retries} attempts.")
