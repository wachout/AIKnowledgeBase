# -*- coding:utf-8 -*-
"""
自我反思智能体
根据文本冗余信息融合智能体获取的信息内容，结合用户的要求，反思自己还需要哪些信息
"""

import json
import re
from typing import Dict, Any, List, Optional
from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi
from langchain_core.prompts import ChatPromptTemplate


class ReflectionAgent:
    """自我反思智能体：动态生成System Prompt，反思还需要哪些信息"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)
        
    
    def reflect_and_generate_prompt(self, query: str, fused_content: Dict[str, Any],
                                   search_results: List[Dict[str, Any]],
                                   intent_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        自我反思：分析已有信息，判断还需要哪些信息，生成System Prompt
        
        Args:
            query: 用户查询
            fused_content: 文本冗余信息融合智能体的输出
            search_results: 当前搜索结果
            intent_analysis: 意图分析结果
            
        Returns:
            反思结果，包含：
            - needs_expansion: 是否需要扩展搜索
            - missing_information: 缺失的信息列表
            - suggested_queries: 建议的扩展查询
            - system_prompt: 动态生成的System Prompt
            - reasoning: 反思理由
        """
        try:
            # 构建系统提示词
            system_prompt = """你是一个自我反思智能体。你的任务是：
1. 分析当前已获取的信息
2. 结合用户查询要求，判断是否还需要更多信息
3. 如果需要，识别缺失的信息类型
4. 生成扩展搜索的建议查询
5. 动态生成精准的System Prompt，用于指导后续的查询

## 三层图结构（来自文本冗余信息融合）：
- sub句子层：背景、因果、举例等
- core句层：核心事实
- Topic层：文档"桥梁"，将段落联合一起

请基于这些信息进行反思。"""
            
            # 构建用户提示词
            fused_info = ""
            if fused_content:
                core_sentences = fused_content.get("core_sentences", [])
                topic_bridges = fused_content.get("topic_bridges", [])
                fused_info = f"""
## 文本冗余信息融合结果：
- 核心事实（core句层）：{len(core_sentences)} 个
- 主题桥梁（Topic层）：{len(topic_bridges)} 个
- 核心句子示例：{core_sentences[:3] if core_sentences else "无"}
"""
            
            search_info = f"""
## 当前搜索结果：
- 结果数量：{len(search_results)}
- 结果摘要：{search_results[0].get('content', '')[:200] if search_results else '无结果'}
"""
            
            intent_info = f"""
## 意图分析结果：
- 核心意图：{intent_analysis.get('core_intent', '')}
- 语义提纯查询：{intent_analysis.get('semantic_purified_query', query)}
- 实体：{intent_analysis.get('entities', [])}
- 逻辑关系：{intent_analysis.get('logical_relations', [])}
"""
            
            user_prompt = f"""请基于以下信息进行自我反思：

## 用户查询：
{query}

{intent_info}

{search_info}

{fused_info}

## 反思任务：

1. **信息充分性评估**：
   - 当前信息是否足够回答用户查询？
   - 如果不够，缺少哪些关键信息？

2. **缺失信息识别**：
   - 缺失的实体信息
   - 缺失的关系信息
   - 缺失的事实信息
   - 缺失的逻辑链条

3. **扩展搜索建议**：
   - 如果需要扩展搜索，建议2-3个扩展查询
   - 这些查询应该针对缺失的信息

4. **System Prompt生成**：
   - 生成一个精准的System Prompt
   - 这个Prompt应该指导后续查询，聚焦于缺失的信息
   - 应该包含查询重点、信息需求、回答要求等

请以JSON格式返回：
{{
    "needs_expansion": true/false,
    "missing_information": ["缺失信息1", "缺失信息2"],
    "suggested_queries": ["扩展查询1", "扩展查询2"],
    "system_prompt": "动态生成的System Prompt",
    "reasoning": "反思理由和判断依据"
}}"""
            
            # 调用LLM
            response = self.llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ])
            
            content = response.content.strip()
            
            # 提取JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                return {
                    "success": True,
                    "needs_expansion": result.get("needs_expansion", False),
                    "missing_information": result.get("missing_information", []),
                    "suggested_queries": result.get("suggested_queries", []),
                    "system_prompt": result.get("system_prompt", ""),
                    "reasoning": result.get("reasoning", ""),
                    "raw_response": result
                }
            else:
                return {
                    "success": False,
                    "error": "无法解析LLM返回的JSON",
                    "raw_response": content,
                    "needs_expansion": False,
                    "system_prompt": ""
                }
                
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON解析失败: {e}",
                "needs_expansion": False,
                "system_prompt": ""
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"反思失败: {str(e)}",
                "needs_expansion": False,
                "system_prompt": ""
            }
