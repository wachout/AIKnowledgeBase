# -*- coding:utf-8 -*-
"""
增强的意图识别智能体
包含语义提纯消除歧义和逻辑规则提纯（数理逻辑）
"""

import json
import re
from typing import Dict, Any, Optional, List
from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi
from langchain_core.prompts import ChatPromptTemplate


class EnhancedIntentAgent:
    """增强的意图识别智能体：语义提纯 + 逻辑提纯"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)
        
    
    def analyze_intent(self, query: str, knowledge_description: str = "", 
                     chat_history: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        增强的意图识别：包含语义提纯和逻辑提纯
        
        Args:
            query: 用户查询
            knowledge_description: 知识库描述
            chat_history: 聊天历史
            
        Returns:
            意图分析结果，包含：
            - action: "tool" 或 "retrieve"
            - tool_name: 工具名称（如果是工具）
            - core_intent: 核心意图
            - semantic_purified_query: 语义提纯后的查询
            - logical_rules: 逻辑规则和数理逻辑
            - entities: 实体列表
            - relationships: 关系列表
            - mathematical_logic: 数学逻辑
        """
        try:
            # 构建系统提示词
            system_prompt = """你是一个专业的意图识别和语义分析专家。你的任务是：
1. 判断用户查询是调用工具还是检索知识库
2. 进行语义提纯，消除歧义
3. 提取逻辑规则和数理逻辑
4. 识别咨询的本源（咨询的根本原因、本质意图、核心问题）

## 工具类型：
- file_statistics: 获取知识库的文件统计信息（文件数量等）
- file_list: 获取知识库的文件列表
- file_summary: 获取文件的详细主旨信息

## 语义提纯要求：
- 识别并消除查询中的歧义
- 提取核心意图和关键概念
- 识别实体、属性、关系

## 咨询本源识别要求：
- 识别咨询的根本原因（为什么会有这个咨询）
- 识别咨询的本质意图（用户真正想要了解什么）
- 识别咨询的核心问题（问题的本质是什么）
- 识别咨询的根源（问题的来源、背景）

## 逻辑规则提纯要求：
- 识别数理逻辑（算术、统计、代数、几何等）
- 识别逻辑关系（因果、条件、并列、转折等）
- 识别集合论关系、关系代数、图论关系等

请以JSON格式返回分析结果。"""
            
            # 构建用户提示词
            history_context = ""
            if chat_history:
                history_context = "\n\n## 聊天历史：\n"
                for msg in chat_history[-3:]:  # 只使用最近3轮
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    history_context += f"- {role}: {content}\n"
            
            knowledge_context = f"\n知识库描述: {knowledge_description}" if knowledge_description else ""
            
            user_prompt = f"""请分析以下用户查询：

## 用户查询：
{query}
{knowledge_context}
{history_context}

请完成以下分析：

1. **判断行动类型**：是调用工具还是检索知识库？
   - 如果查询明确要求获取文件统计、文件列表、文件摘要等元数据信息，选择"tool"
   - 如果查询需要从知识库内容中检索信息，选择"retrieve"

2. **语义提纯**：
   - 识别并消除歧义
   - 提取核心意图（core_intent）
   - 生成语义提纯后的查询（semantic_purified_query）
   - 识别实体（entities）、属性（attributes）、关系（relationships）

3. **咨询本源识别**：
   - 识别咨询的根本原因（consultation_root_cause）：为什么用户会有这个咨询
   - 识别咨询的本质意图（consultation_essence）：用户真正想要了解什么
   - 识别咨询的核心问题（consultation_core_issue）：问题的本质是什么
   - 识别咨询的根源（consultation_source）：问题的来源、背景、触发因素

4. **逻辑规则提纯**：
   - 识别数理逻辑（mathematical_logic）：算术、统计、代数、几何、微积分等
   - 识别逻辑关系（logical_relations）：因果、条件、并列、转折、递进等
   - 识别集合论关系（set_theory_relations）
   - 识别关系代数（relational_algebra）
   - 识别图论关系（graph_theory_relations）

请以JSON格式返回：
{{
    "action": "tool" 或 "retrieve",
    "tool_name": "工具名称（如果是tool）",
    "confidence": 0.0-1.0,
    "core_intent": "核心意图描述",
    "semantic_purified_query": "语义提纯后的查询",
    "entities": ["实体1", "实体2"],
    "attributes": ["属性1", "属性2"],
    "relationships": ["关系1", "关系2"],
    "consultation_root_cause": "咨询的根本原因",
    "consultation_essence": "咨询的本质意图",
    "consultation_core_issue": "咨询的核心问题",
    "consultation_source": "咨询的根源",
    "mathematical_logic": ["数学逻辑1", "数学逻辑2"],
    "logical_relations": ["逻辑关系1", "逻辑关系2"],
    "set_theory_relations": ["集合论关系1"],
    "relational_algebra": ["关系代数1"],
    "graph_theory_relations": ["图论关系1"],
    "reasoning": "分析理由"
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
                    "action": result.get("action", "retrieve"),
                    "tool_name": result.get("tool_name", ""),
                    "confidence": result.get("confidence", 0.5),
                    "core_intent": result.get("core_intent", ""),
                    "semantic_purified_query": result.get("semantic_purified_query", query),
                    "entities": result.get("entities", []),
                    "attributes": result.get("attributes", []),
                    "relationships": result.get("relationships", []),
                    "consultation_root_cause": result.get("consultation_root_cause", ""),
                    "consultation_essence": result.get("consultation_essence", ""),
                    "consultation_core_issue": result.get("consultation_core_issue", ""),
                    "consultation_source": result.get("consultation_source", ""),
                    "mathematical_logic": result.get("mathematical_logic", []),
                    "logical_relations": result.get("logical_relations", []),
                    "set_theory_relations": result.get("set_theory_relations", []),
                    "relational_algebra": result.get("relational_algebra", []),
                    "graph_theory_relations": result.get("graph_theory_relations", []),
                    "reasoning": result.get("reasoning", ""),
                    "raw_response": result
                }
            else:
                return {
                    "success": False,
                    "error": "无法解析LLM返回的JSON",
                    "raw_response": content,
                    "action": "retrieve",  # 默认返回检索
                    "semantic_purified_query": query
                }
                
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON解析失败: {e}",
                "action": "retrieve",
                "semantic_purified_query": query
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"意图识别失败: {str(e)}",
                "action": "retrieve",
                "semantic_purified_query": query
            }
