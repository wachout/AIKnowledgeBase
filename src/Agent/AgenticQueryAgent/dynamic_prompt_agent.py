# -*- coding:utf-8 -*-
"""
动态Prompt生成智能体
根据搜索结果和实体分析，动态生成System Prompt
"""

import json
import re
from typing import Dict, Any, List
from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi
from langchain_core.prompts import ChatPromptTemplate


class DynamicPromptAgent:
    """动态Prompt生成智能体：根据搜索结果动态生成System Prompt"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)
        
    
    def generate_prompt(self, query: str, entity_analysis: Dict[str, Any],
                       search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        动态生成System Prompt
        
        Args:
            query: 用户查询
            entity_analysis: 实体分析结果
            search_results: 搜索结果
            
        Returns:
            生成的Prompt，包含：
            - system_prompt: 系统提示
            - context_summary: 上下文摘要
            - key_information: 关键信息
        """
        try:
            # 提取关键信息
            entities = entity_analysis.get("entities", [])
            metrics = entity_analysis.get("metrics", [])
            attributes = entity_analysis.get("attributes", [])
            time_dimensions = entity_analysis.get("time_dimensions", [])
            relationships = entity_analysis.get("relationships", [])
            
            # 构建搜索结果摘要（只显示前5个）
            search_summary = []
            for i, result in enumerate(search_results[:5], 1):
                title = result.get("title", "无标题")
                content = result.get("content", "")[:300]  # 只取前300字符
                search_summary.append(f"知识片段{i}: {title}\n{content}...")
            search_summary_str = "\n\n".join(search_summary)
            
            # 转义花括号
            entities_str = json.dumps(entities, ensure_ascii=False, indent=2).replace("{", "{{").replace("}", "}}")
            metrics_str = json.dumps(metrics, ensure_ascii=False, indent=2).replace("{", "{{").replace("}", "}}")
            attributes_str = json.dumps(attributes, ensure_ascii=False, indent=2).replace("{", "{{").replace("}", "}}")
            
            system_prompt_template = """你是一个专业的数据分析助手。你的任务是根据用户查询和知识库搜索结果，提供准确、详细的回答。

**用户查询分析：**
- 实体本源: {entities}
- 指标: {metrics}
- 属性: {attributes}
- 时间维度: {time_dimensions}
- 关系: {relationships}

**知识库搜索结果：**
{search_results}

**重要提示：**
1. 基于知识库搜索结果回答问题
2. 如果知识库中有计算逻辑说明（如某属性需要两个指标相加），请在回答中明确说明
3. 如果知识库中提到了计算规则，请详细描述这些规则
4. 如果搜索结果不完整，请说明需要哪些额外信息
5. 用清晰、准确的语言回答用户的问题

请根据以上信息，回答用户的问题。"""

            user_prompt = f"""**用户查询：**
{query}

**识别的实体：**
{entities_str}

**识别的指标：**
{metrics_str}

**识别的属性：**
{attributes_str}

**知识库搜索结果：**
{search_summary_str}

请根据以上信息，生成一个详细的System Prompt，用于指导AI回答用户的问题。这个Prompt应该：
1. 明确说明需要回答的问题
2. 强调基于知识库搜索结果
3. 如果知识库中提到计算逻辑，要明确说明
4. 提供清晰的回答指导

请以JSON格式返回：
{{
    "system_prompt": "生成的System Prompt",
    "context_summary": "上下文摘要",
    "key_information": ["关键信息1", "关键信息2"]
}}"""

            prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个专业的Prompt生成专家。"),
                ("user", user_prompt)
            ])
            
            chain = prompt | self.llm
            response = chain.invoke({})
            
            # 解析响应
            response_text = response.content if hasattr(response, 'content') else str(response)
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    system_prompt = result.get("system_prompt", system_prompt_template.format(
                        entities=entities_str,
                        metrics=metrics_str,
                        attributes=attributes_str,
                        time_dimensions=json.dumps(time_dimensions, ensure_ascii=False),
                        relationships=json.dumps(relationships, ensure_ascii=False),
                        search_results=search_summary_str
                    ))
                    
                    return {
                        "success": True,
                        "system_prompt": system_prompt,
                        "context_summary": result.get("context_summary", ""),
                        "key_information": result.get("key_information", []),
                        "raw_response": response_text
                    }
                except json.JSONDecodeError:
                    pass
            
            # 如果解析失败，使用模板生成
            system_prompt = system_prompt_template.format(
                entities=entities_str,
                metrics=metrics_str,
                attributes=attributes_str,
                time_dimensions=json.dumps(time_dimensions, ensure_ascii=False),
                relationships=json.dumps(relationships, ensure_ascii=False),
                search_results=search_summary_str
            )
            
            return {
                "success": True,
                "system_prompt": system_prompt,
                "context_summary": f"基于{len(search_results)}个搜索结果和识别的{len(entities)}个实体、{len(metrics)}个指标生成",
                "key_information": [e.get("entity_name", "") for e in entities[:5]],
                "raw_response": response_text
            }
                
        except Exception as e:
            import logging
            import traceback
            logging.warning(f"⚠️ Prompt生成失败: {e}")
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "system_prompt": "你是一个专业的数据分析助手。请根据用户查询和知识库搜索结果回答问题。"
            }
