# -*- coding:utf-8 -*-
"""
意图识别智能体
根据用户问题和数据库描述，判断用户的问题该怎么搜索
"""

import json
import re
from typing import Dict, Any, List
from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi
from langchain_core.prompts import ChatPromptTemplate


class IntentRecognitionAgent:
    """意图识别智能体：分析用户查询意图，拆解为本源实体、属性、指标、关联关系"""
    
    def __init__(self):
        from Config.llm_config import get_chat_tongyi
        self.llm = get_chat_tongyi(temperature=0.7, streaming=False, enable_thinking=False)
        
    
    def analyze_intent(self, decomposition_result: Dict[str, Any], database_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析用户查询意图
        
        根据逻辑规则识别结果（decomposition_result）来匹配数据库信息，识别相关的实体、属性、指标等。
        
        Args:
            decomposition_result: 问题拆解与逻辑分析结果，包含：
                - query: 原始用户查询
                - entities: 实体列表
                - metrics: 指标列表
                - time_dimensions: 时间维度列表
                - relationships: 关联关系列表
                - logical_calculations: 逻辑计算列表
                - mathematical_relations: 数学关系列表
                - 等等
            database_info: 数据库信息（包含sql_description、sql_name、tables等）
                          tables格式: [{
                              'table_id': '...',
                              'table_name': '...',
                              'table_description': '...',
                              'attributes': ['属性1', '属性2', ...],
                              'attributes_description': ['属性描述1', ...],
                              'datetime': ['时间字段1', ...],
                              'datetime_description': ['时间字段描述1', ...],
                              'numerics': ['指标1', '指标2', ...],
                              'numerics_description': ['指标描述1', ...]
                          }]
            
        Returns:
            意图分析结果，包含：
            - primary_entities: 本源实体列表
            - entity_attributes: 实体属性列表
            - entity_metrics: 实体指标列表
            - relationships: 关联关系列表
            - search_strategy: 搜索策略
        """
        try:
            # 从decomposition_result中提取信息
            if not decomposition_result.get("success"):
                # 如果拆解失败，使用原始query
                original_query = decomposition_result.get("query", "")
            else:
                original_query = decomposition_result.get("query", "")
                entities_from_decomp = decomposition_result.get("entities", [])
                metrics_from_decomp = decomposition_result.get("metrics", [])
                time_dims_from_decomp = decomposition_result.get("time_dimensions", [])
                relationships_from_decomp = decomposition_result.get("relationships", [])
                logical_calcs_from_decomp = decomposition_result.get("logical_calculations", [])
                math_relations_from_decomp = decomposition_result.get("mathematical_relations", [])
                set_theory_from_decomp = decomposition_result.get("set_theory_relations", [])
                relational_algebra_from_decomp = decomposition_result.get("relational_algebra", [])
            
            # 构建数据库上下文
            db_description = database_info.get("sql_description", "")
            db_name = database_info.get("sql_name", "")
            tables_info = database_info.get("tables", [])
            
            system_prompt = """你是一个专业的数据库查询分析专家。你的任务是根据逻辑规则识别结果，匹配数据库表结构信息，识别相关的实体、属性、指标等。

重要提示：
1. 你已经收到了问题拆解与逻辑分析的结果，其中包含了识别出的实体、指标、时间维度、关联关系、逻辑计算、数学关系等信息
2. 你的任务是将这些识别结果与数据库表结构信息进行匹配，找出：
   - 哪些实体对应数据库中的哪些表
   - 哪些指标对应数据库中的哪些numerics字段
   - 哪些时间维度对应数据库中的哪些datetime字段
   - 哪些属性对应数据库中的哪些attributes字段
3. 匹配时要考虑语义相似性、同义词、相关概念等
4. 如果逻辑规则识别结果中的实体、指标等在数据库中没有完全匹配的字段，可以寻找语义相近的字段

请根据逻辑规则识别结果和数据库表结构信息，以JSON格式返回匹配结果：
1. 本源实体（primary_entities）：从逻辑规则识别结果中的entities匹配到数据库表
2. 实体属性（entity_attributes）：从逻辑规则识别结果匹配到数据库中的attributes字段
3. 实体指标（entity_metrics）：从逻辑规则识别结果中的metrics匹配到数据库中的numerics字段
4. 时间维度（time_dimensions）：从逻辑规则识别结果中的time_dimensions匹配到数据库中的datetime字段
5. 关联关系（relationships）：从逻辑规则识别结果中的relationships匹配到数据库表之间的关系
6. 相关表（relevant_tables）：根据匹配结果，识别出相关的表名
7. 相关列（relevant_columns）：根据匹配结果，识别出相关的列名（需要指定所属的表名）

数据库表结构信息格式说明：
- 每个表包含：表名、表描述、属性列表、时间字段列表、指标列表
- 属性（attributes）：格式为"列名(描述)"，如"gender(性别)"，表示描述性字段
- 时间字段（datetime）：格式为"列名(描述)"，如"create_time(创建时间)"，表示时间相关字段
- 指标（numerics）：格式为"列名(描述)"，如"age(年龄)"，表示数值型字段

在匹配时，请参考列的描述信息（括号中的内容），同时也要记录对应的列名，以便后续生成SQL时使用。"""

            # 构建表结构信息字符串
            tables_context = ""
            if tables_info:
                tables_context = "\n\n数据库表结构信息：\n"
                for table in tables_info[:50]:  # 限制表数量，避免上下文过长
                    table_id = table.get("table_id", "")
                    table_name = table.get("table_name", "")
                    table_description = table.get("table_description", "")
                    
                    # 获取属性信息（列名和描述）
                    attributes_col = table.get("attributes", [])
                    attributes_des = table.get("attributes_description", [])
                    
                    # 获取时间字段信息（列名和描述）
                    datetime_col = table.get("datetime", [])
                    datetime_des = table.get("datetime_description", [])
                    
                    # 获取指标信息（列名和描述）
                    numerics_col = table.get("numerics", [])
                    numerics_des = table.get("numerics_description", [])
                    
                    tables_context += f"\n表名：{table_name}\n"
                    if table_id:
                        tables_context += f"表ID：{table_id}\n"
                    if table_description:
                        tables_context += f"表描述：{table_description}\n"
                    
                    # 格式化属性信息：列名(描述) 或 列名
                    if attributes_col:
                        attributes_list = []
                        for i, col_name in enumerate(attributes_col):
                            if i < len(attributes_des) and attributes_des[i]:
                                attributes_list.append(f"{col_name}({attributes_des[i]})")
                            else:
                                attributes_list.append(col_name)
                        tables_context += f"属性（attributes）：{', '.join(attributes_list)}\n"
                    
                    # 格式化时间字段信息：列名(描述) 或 列名
                    if datetime_col:
                        datetime_list = []
                        for i, col_name in enumerate(datetime_col):
                            if i < len(datetime_des) and datetime_des[i]:
                                datetime_list.append(f"{col_name}({datetime_des[i]})")
                            else:
                                datetime_list.append(col_name)
                        tables_context += f"时间字段（datetime）：{', '.join(datetime_list)}\n"
                    
                    # 格式化指标信息：列名(描述) 或 列名
                    if numerics_col:
                        numerics_list = []
                        for i, col_name in enumerate(numerics_col):
                            if i < len(numerics_des) and numerics_des[i]:
                                numerics_list.append(f"{col_name}({numerics_des[i]})")
                            else:
                                numerics_list.append(col_name)
                        tables_context += f"指标（numerics）：{', '.join(numerics_list)}\n"
                    
                    tables_context += "\n"
            
            # 构建逻辑规则识别结果摘要
            decomposition_summary = ""
            if decomposition_result.get("success"):
                decomp_data = decomposition_result
                decomp_summary_parts = []
                
                if decomp_data.get("entities"):
                    entities_list = [e.get("entity_name", "") for e in decomp_data.get("entities", []) if e.get("entity_name")]
                    if entities_list:
                        decomp_summary_parts.append(f"识别出的实体：{', '.join(entities_list)}")
                
                if decomp_data.get("metrics"):
                    metrics_list = [m.get("metric_name", "") for m in decomp_data.get("metrics", []) if m.get("metric_name")]
                    if metrics_list:
                        decomp_summary_parts.append(f"识别出的指标：{', '.join(metrics_list)}")
                
                if decomp_data.get("time_dimensions"):
                    time_list = [t.get("time_concept", "") for t in decomp_data.get("time_dimensions", []) if t.get("time_concept")]
                    if time_list:
                        decomp_summary_parts.append(f"识别出的时间维度：{', '.join(time_list)}")
                
                if decomp_data.get("relationships"):
                    rel_list = [f"{r.get('from_entity', '')}-{r.get('to_entity', '')}" for r in decomp_data.get("relationships", []) if r.get("from_entity") and r.get("to_entity")]
                    if rel_list:
                        decomp_summary_parts.append(f"识别出的关联关系：{', '.join(rel_list)}")
                
                if decomp_data.get("mathematical_relations"):
                    math_list = [m.get("math_type", "") for m in decomp_data.get("mathematical_relations", []) if m.get("math_type")]
                    if math_list:
                        decomp_summary_parts.append(f"识别出的数学关系类型：{', '.join(set(math_list))}")
                
                if decomp_data.get("logical_calculations"):
                    logic_list = [l.get("logical_operation", "") for l in decomp_data.get("logical_calculations", []) if l.get("logical_operation")]
                    if logic_list:
                        decomp_summary_parts.append(f"识别出的逻辑运算：{', '.join(set(logic_list))}")
                
                if decomp_summary_parts:
                    decomposition_summary = "\n".join(decomp_summary_parts)
                else:
                    decomposition_summary = "逻辑规则识别结果为空"
            else:
                decomposition_summary = "逻辑规则识别失败，使用原始查询进行分析"
            
            user_prompt = f"""数据库信息：
- 数据库名称：{db_name}
- 数据库描述：{db_description}
{tables_context}

原始用户查询：{original_query}

逻辑规则识别结果摘要：
{decomposition_summary}

请根据逻辑规则识别结果，匹配数据库表结构信息，以JSON格式返回匹配结果：
{{
    "primary_entities": [
        {{
            "entity_name": "实体名称",
            "entity_type": "实体类型",
            "description": "实体描述",
            "confidence": 0.9
        }}
    ],
    "entity_attributes": [
        {{
            "attribute_name": "属性名称（从表结构中的attributes描述中提取）",
            "attribute_col_name": "对应的列名（从表结构中的attributes列名中提取）",
            "attribute_type": "属性类型",
            "description": "属性描述（对应表结构中的描述信息）",
            "confidence": 0.8
        }}
    ],
    "entity_metrics": [
        {{
            "metric_name": "指标名称（从表结构中的numerics描述中提取）",
            "metric_col_name": "对应的列名（从表结构中的numerics列名中提取）",
            "metric_type": "指标类型（如count、sum、avg、max、min等）",
            "description": "指标描述（对应表结构中的描述信息）",
            "confidence": 0.8
        }}
    ],
    "time_dimensions": [
        {{
            "time_field": "时间字段名称（从表结构中的datetime描述中提取）",
            "time_col_name": "对应的列名（从表结构中的datetime列名中提取）",
            "time_type": "时间类型（如date、datetime、timestamp等）",
            "description": "时间字段描述（对应表结构中的描述信息）",
            "confidence": 0.8
        }}
    ],
    "relationships": [
        {{
            "from_entity": "源实体",
            "to_entity": "目标实体",
            "relationship_type": "关系类型",
            "description": "关系描述",
            "confidence": 0.7
        }}
    ],
    "relevant_tables": [
        {{
            "table_name": "表名",
            "relevance_reason": "相关性原因",
            "confidence": 0.9
        }}
    ],
    "relevant_columns": [
        {{
            "table_name": "表名",
            "col_name": "列名",
            "relevance_reason": "相关性原因",
            "usage": "用途说明（如：SELECT、WHERE、GROUP BY等）",
            "confidence": 0.8
        }}
    ],
    "search_strategy": "搜索策略说明"
}}

请确保返回有效的JSON格式。"""

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
                    "query": original_query,
                    "primary_entities": result.get("primary_entities", []),
                    "entity_attributes": result.get("entity_attributes", []),
                    "entity_metrics": result.get("entity_metrics", []),
                    "time_dimensions": result.get("time_dimensions", []),
                    "relationships": result.get("relationships", []),
                    "relevant_tables": result.get("relevant_tables", []),
                    "relevant_columns": result.get("relevant_columns", []),
                    "search_strategy": result.get("search_strategy", ""),
                    "decomposition_result": decomposition_result,
                    "raw_analysis": result
                }
            else:
                return {
                    "success": False,
                    "error": "无法解析大模型返回的JSON",
                    "raw_response": content
                }
                
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON解析失败: {e}",
                "raw_response": content if 'content' in locals() else ""
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"意图识别失败: {str(e)}"
            }
