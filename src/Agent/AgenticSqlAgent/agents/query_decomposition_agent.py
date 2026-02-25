# -*- coding:utf-8 -*-
"""
问题拆解与逻辑分析智能体
对用户问题进行拆解，识别实体、指标、时间维度、关联关系、逻辑计算等
并分析各种逻辑关系和数学关系
"""

import json
import re
from typing import Dict, Any, List
from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi


class QueryDecompositionAgent:
    """问题拆解与逻辑分析智能体：拆解用户问题，识别各种逻辑和数学关系"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)
    
    def decompose_query(self, query: str, table_info_list: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        拆解用户问题，识别实体、指标、时间维度、关联关系、逻辑计算等
        如果提供了table_info_list，会进行语义核对，确保识别出的实体、指标等与数据库表信息匹配
        
        Args:
            query: 用户查询问题
            table_info_list: 表信息列表（可选），格式为：
                [
                    {
                        "table_id": "表ID",
                        "table_name": "表名",
                        "table_description": "表描述",
                        "columns": [
                            {
                                "col_name": "列名",
                                "col_type": "列类型",
                                "comment": "列注释"
                            }
                        ]
                    }
                ]
            
        Returns:
            拆解结果，包含：
            - entities: 实体列表
            - metrics: 指标列表
            - time_dimensions: 时间维度列表
            - relationships: 关联关系列表
            - logical_calculations: 逻辑计算列表
            - spatial_dimensions: 空间维度列表
            - set_theory_relations: 集合论关系
            - relational_algebra: 关系代数
            - graph_theory_relations: 图论关系
            - logical_reasoning: 逻辑推理
            - semantic_network: 语义网络
            - mathematical_relations: 数学关系（逻辑、算数、统计、代数、几何等）
            - matched_tables: 匹配的表信息（如果提供了table_info_list）
        """
        try:
            system_prompt = """你是一个专业的数据分析师，擅长从业务问题中抽象出数据分析和计算逻辑。

**你的核心能力：**
1. **抽象任务目标**：从用户的业务问题中提炼出核心的分析目标和任务目标
2. **抽象事物本源**：识别问题中涉及的实体类别（实体本源），而不是具体的实体实例
   - 实体本源是通用的类别概念，如：人、企业、学生、订单、产品等
   - 不是具体实例，如："张三"、"某某公司"、"订单12345"等
3. **抽象计算逻辑**：识别问题中需要执行的数理逻辑和计算规则
   - 包括统计计算、数学运算、逻辑运算等
   - 这些计算将在数据抽取完成后执行
4. **抽象事物联系**：识别实体之间的关联关系、业务关系、数据关系

**分析原则：**
- 以数据分析师的视角，专注于抽象和逻辑分析
- 识别问题中明确提到的计算逻辑，不要做过度扩展
- 提炼出问题的本质，而不是表面现象
- 关注数据维度和计算维度，而非具体的数据值

请从以下维度进行专业的数据分析抽象：

1. **任务目标抽象**：提炼出用户问题的核心分析目标和任务目标
   - 用户想要解决什么业务问题？
   - 需要分析什么维度的数据？
   - 最终要得到什么结论或洞察？

2. **实体本源抽象**：识别问题中涉及的**实体类别**（实体本源），而不是具体的实体实例
   - **实体本源**是实体的类别/类型，如：人、企业、学生、订单、产品、客户等通用类别
   - **不是**具体实例，如："张三"、"某某公司"、"订单12345"等
   - 从具体问题中抽象出通用的实体类别概念
   - 示例：
     * ✅ 正确：人、企业、学生、订单、产品
     * ❌ 错误：张三、某某公司、订单12345

3. **指标抽象**：识别问题中涉及的数值型指标和度量维度
   - 需要统计什么指标？（如总数、平均值、最大值、最小值、增长率、占比等）
   - 这些指标反映了什么业务含义？

4. **时间维度抽象**：识别问题中涉及的时间相关概念
   - 需要分析哪个时间维度？（如日期、时间段、时间范围、时间序列等）
   - 时间维度在分析中的作用是什么？

5. **事物联系抽象**：识别实体之间的关联关系、业务关系、数据关系
   - 实体之间是什么关系？（如一对多、多对多、包含、属于、关联等）
   - 这些关系如何影响数据分析？

6. **计算逻辑抽象**：识别问题中需要执行的数理逻辑和计算规则
   - **逻辑运算**：AND、OR、NOT、IF-THEN、比较运算等
   - **数学运算**：加减乘除、幂运算、开方等
   - **统计计算**：均值、方差、标准差、相关系数、回归分析、频率分析等
   - **聚合计算**：求和、计数、分组统计等
   - 这些计算将在数据抽取完成后执行
   - 只提取问题中明确提到的计算逻辑，不要过度扩展

7. **空间维度抽象**：识别问题中涉及的空间相关概念（如地理位置、区域、坐标等）

8. **集合论关系抽象**：识别问题中涉及的集合关系（如并集、交集、差集、子集、补集等）

9. **关系代数抽象**：识别问题中涉及的关系代数操作（如选择、投影、连接、并、差、交等）

10. **图论关系抽象**：识别问题中涉及的图论概念（如节点、边、路径、连通性、最短路径等）

11. **逻辑推理抽象**：识别问题中涉及的逻辑推理模式（如演绎推理、归纳推理、类比推理等）

12. **语义网络抽象**：识别问题中涉及的语义关系（如上下位关系、同义关系、反义关系等）

13. **数学关系抽象**：识别问题中涉及的数学关系类型：
    - 逻辑：逻辑运算、布尔代数
    - 算数：加减乘除、幂运算、开方等
    - 统计：均值、方差、标准差、相关系数、回归分析等
    - 代数：方程、不等式、函数、矩阵运算等
    - 几何：距离、角度、面积、体积等
    - 微积分：导数、积分、极限等
    - 离散数学：组合、排列、图论等
    - 符号数学：符号计算、公式推导等
    - 优化：最优化问题、线性规划、非线性规划等
    - 算法复杂：时间复杂度、空间复杂度等

**分析要求：**
- 以数据分析师的视角，从业务问题中抽象出数据分析和计算逻辑
- 关注问题的本质和核心，而非表面现象
- 识别明确提到的计算逻辑，避免过度扩展
- 提炼出清晰的任务目标和计算逻辑

请仔细分析用户问题，从数据分析师的角度抽象出任务目标、实体本源、计算逻辑和事物联系，并以JSON格式返回分析结果。"""

            # 构建表信息上下文（如果提供了表信息）
            table_context = ""
            if table_info_list:
                table_context = "\n\n## 数据库表信息（用于语义核对）：\n"
                for table_info in table_info_list[:10]:  # 最多显示10个表
                    table_name = table_info.get("table_name", "")
                    table_desc = table_info.get("table_description", "")
                    columns = table_info.get("columns", [])
                    
                    table_context += f"\n**表：{table_name}**\n"
                    if table_desc:
                        table_context += f"- 描述：{table_desc}\n"
                    if columns:
                        table_context += "- 列信息：\n"
                        for col in columns[:5]:  # 每个表最多显示5个列
                            col_name = col.get("col_name", "")
                            col_type = col.get("col_type", "")
                            col_comment = col.get("comment", "")
                            if col_comment:
                                table_context += f"  - {col_name} ({col_type}): {col_comment}\n"
                            else:
                                table_context += f"  - {col_name} ({col_type})\n"
                
                table_context += "\n**语义核对要求：**\n"
                table_context += "- 识别出的实体、指标、时间维度等应该与上述表信息进行语义匹配\n"
                table_context += "- 如果识别出的概念在表信息中有对应的表或列，请在结果中标注匹配的表和列\n"
                table_context += "- 优先匹配表描述和列注释中包含的概念\n"
            
            user_prompt = f"""用户查询：{query}
{table_context}

请以专业数据分析师的视角，对这个问题进行深度抽象和分析，以JSON格式返回分析结果。

**分析要求：**
1. **抽象任务目标**：提炼出用户问题的核心分析目标和任务目标
2. **抽象实体本源**：只识别**实体类别**（实体本源），如"人"、"企业"、"学生"、"订单"等，不要识别具体的实体实例，如"张三"、"某某公司"、"订单12345"等
3. **抽象计算逻辑**：识别问题中需要执行的数理逻辑和计算规则
   - 逻辑计算（logical_calculations）和数学关系（mathematical_relations）只提取问题中**明确提到**的计算
   - 这些计算将在数据抽取完成后执行，用于对抽取的数据进行逻辑数理计算
   - 不要过度扩展，只提取问题中明确提到的内容
4. **抽象事物联系**：识别实体之间的关联关系、业务关系、数据关系

**重要原则：**
- 以数据分析师的视角，专注于抽象和逻辑分析
- 关注问题的本质和核心，而非表面现象
- 如果问题中没有明确提到某种计算，则返回空数组

JSON格式：
{{
    "task_objective": "任务目标（从用户问题中抽象出的核心分析目标和任务目标）",
    "entities": [
        {{
            "entity_name": "实体类别名称（实体本源，如：人、企业、学生、订单等，不是具体实例如'张三'、'某某公司'）",
            "entity_type": "实体类型",
            "description": "实体描述（说明这是实体类别，不是具体实例）",
            "confidence": 0.9
        }}
    ],
    "metrics": [
        {{
            "metric_name": "指标名称",
            "metric_type": "指标类型（如count、sum、avg、max、min、growth_rate等）",
            "description": "指标描述",
            "confidence": 0.8
        }}
    ],
    "time_dimensions": [
        {{
            "time_concept": "时间概念（如日期、时间段、时间范围等）",
            "time_type": "时间类型（如date、datetime、period、range等）",
            "description": "时间维度描述",
            "confidence": 0.8
        }}
    ],
    "relationships": [
        {{
            "from_entity": "源实体",
            "to_entity": "目标实体",
            "relationship_type": "关系类型（如one_to_many、many_to_many、contains、belongs_to等）",
            "description": "关系描述",
            "confidence": 0.7
        }}
    ],
    "logical_calculations": [
        {{
            "logical_operation": "逻辑运算（如AND、OR、NOT、IF-THEN、比较运算等，只提取问题中明确提到的）",
            "operands": ["操作数列表（问题中明确提到的操作数）"],
            "description": "逻辑计算描述（说明这个计算将在数据抽取后执行）",
            "confidence": 0.8
        }}
    ],
    "spatial_dimensions": [
        {{
            "spatial_concept": "空间概念（如地理位置、区域、坐标等）",
            "spatial_type": "空间类型（如location、region、coordinate等）",
            "description": "空间维度描述",
            "confidence": 0.7
        }}
    ],
    "set_theory_relations": [
        {{
            "set_operation": "集合操作（如union、intersection、difference、subset、complement等）",
            "sets": ["涉及的集合"],
            "description": "集合论关系描述",
            "confidence": 0.7
        }}
    ],
    "relational_algebra": [
        {{
            "operation": "关系代数操作（如select、project、join、union、difference、intersection等）",
            "tables": ["涉及的表"],
            "description": "关系代数操作描述",
            "confidence": 0.7
        }}
    ],
    "graph_theory_relations": [
        {{
            "graph_concept": "图论概念（如node、edge、path、connectivity、shortest_path等）",
            "nodes": ["节点列表"],
            "edges": ["边列表"],
            "description": "图论关系描述",
            "confidence": 0.6
        }}
    ],
    "logical_reasoning": [
        {{
            "reasoning_type": "推理类型（如deductive、inductive、analogical等）",
            "premises": ["前提列表"],
            "conclusion": "结论",
            "description": "逻辑推理描述",
            "confidence": 0.7
        }}
    ],
    "semantic_network": [
        {{
            "semantic_relation": "语义关系（如hyponymy、synonymy、antonymy等）",
            "concepts": ["相关概念列表"],
            "description": "语义网络关系描述",
            "confidence": 0.6
        }}
    ],
    "mathematical_relations": [
        {{
            "math_type": "数学类型（如logic、arithmetic、statistics、algebra、geometry、calculus、discrete、symbolic、optimization、complexity等，只提取问题中明确提到的）",
            "operation": "数学运算（问题中明确提到的运算）",
            "formula": "公式（如果问题中明确提到）",
            "description": "数学关系描述（说明这个计算将在数据抽取后执行）",
            "confidence": 0.8
        }}
    ],
    "analysis_summary": "问题拆解和分析的总结（从数据分析师视角，说明问题的核心目标、实体本源、计算逻辑和事物联系）"
}}

请确保返回有效的JSON格式。记住：
- 以数据分析师的视角，抽象出任务目标、实体本源、计算逻辑和事物联系
- 只提取问题中明确提到的逻辑数理计算，不要过度扩展
- 关注问题的本质和核心，而非表面现象"""

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
                
                # 如果提供了表信息，添加匹配信息
                matched_tables = []
                if table_info_list:
                    # 简单的语义匹配：检查实体、指标等是否在表信息中出现
                    entities = result.get("entities", [])
                    metrics = result.get("metrics", [])
                    
                    for table_info in table_info_list:
                        table_name = table_info.get("table_name", "")
                        table_desc = table_info.get("table_description", "")
                        columns = table_info.get("columns", [])
                        
                        # 检查实体是否匹配
                        matched_entities = []
                        for entity in entities:
                            entity_name = entity.get("entity_name", "")
                            if entity_name.lower() in table_desc.lower() or entity_name.lower() in table_name.lower():
                                matched_entities.append(entity_name)
                        
                        # 检查指标是否匹配列
                        matched_metrics = []
                        for metric in metrics:
                            metric_name = metric.get("metric_name", "")
                            for col in columns:
                                col_comment = col.get("comment", "")
                                if metric_name.lower() in col_comment.lower():
                                    matched_metrics.append({
                                        "metric": metric_name,
                                        "column": col.get("col_name", "")
                                    })
                        
                        if matched_entities or matched_metrics:
                            matched_tables.append({
                                "table_id": table_info.get("table_id", ""),
                                "table_name": table_name,
                                "matched_entities": matched_entities,
                                "matched_metrics": matched_metrics
                            })
                
                return {
                    "success": True,
                    "query": query,
                    "task_objective": result.get("task_objective", ""),
                    "entities": result.get("entities", []),
                    "metrics": result.get("metrics", []),
                    "time_dimensions": result.get("time_dimensions", []),
                    "relationships": result.get("relationships", []),
                    "logical_calculations": result.get("logical_calculations", []),
                    "spatial_dimensions": result.get("spatial_dimensions", []),
                    "set_theory_relations": result.get("set_theory_relations", []),
                    "relational_algebra": result.get("relational_algebra", []),
                    "graph_theory_relations": result.get("graph_theory_relations", []),
                    "logical_reasoning": result.get("logical_reasoning", []),
                    "semantic_network": result.get("semantic_network", []),
                    "mathematical_relations": result.get("mathematical_relations", []),
                    "analysis_summary": result.get("analysis_summary", ""),
                    "matched_tables": matched_tables if table_info_list else [],
                    "raw_analysis": result
                }
            else:
                return {
                    "success": False,
                    "query": query,
                    "error": "无法解析大模型返回的JSON",
                    "raw_response": content
                }
                
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "query": query,
                "error": f"JSON解析失败: {e}",
                "raw_response": content if 'content' in locals() else ""
            }
        except Exception as e:
            return {
                "success": False,
                "query": query,
                "error": f"问题拆解失败: {str(e)}"
            }
