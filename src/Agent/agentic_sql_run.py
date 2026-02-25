# -*- coding:utf-8 -*-
"""
Agentic SQL智能体主入口
根据用户查询和数据库信息，生成SQL查询语句
"""

import traceback

from typing import Dict, Any, Optional, List
from Agent.AgenticSqlAgent.tools.database_tools import (
    query_database_info, 
    query_tables_by_sql_id, 
    query_columns_by_table_id
)
from Agent.AgenticSqlAgent.database_metadata_agent import DatabaseMetadataAgent
from Agent.AgenticSqlAgent.AnalysisSql.database_analysis_agent import DatabaseAnalysisAgent
from Agent.AgenticSqlAgent.agents.query_decomposition_agent import QueryDecompositionAgent
from Agent.AgenticSqlAgent.agents.intent_recognition_agent import IntentRecognitionAgent
# from Agent.AgenticSqlAgent.agents.database_check_agent import DatabaseCheckAgent
from Agent.AgenticSqlAgent.SqlGeneration.sql_generation_flow import SqlGenerationFlow
from Agent.AgenticSqlAgent.RuleLogic.logic_calculation_agent import LogicCalculationAgent
from Sql.schema_vector import SqlSchemaVectorAgent
import json
from Db.sqlite_db import cSingleSqlite


def run_sql_agentic_search(sql_id: str, query: str, user_id: str = None, 
                           step_callback: Optional[callable] = None) -> Dict[str, Any]:
    """
    运行Agentic SQL智能体搜索流程
    
    Args:
        sql_id: 数据库连接ID
        query: 用户查询问题
        user_id: 用户ID（可选）
        step_callback: 步骤回调函数，用于流式返回步骤信息
                       callback(step_name: str, step_data: Dict[str, Any])
        
    Returns:
        完整的搜索结果，包含：
        - success: 是否成功
        - sql: 生成的SQL语句
        - intent_analysis: 意图分析结果
        - relevant_tables: 相关表列表
        - relevant_columns: 相关列列表（按表分组）
        - sql_check: SQL检查结果
        - error: 错误信息（如果有）
    """
    
    def _notify_step(step_name: str, step_data: Dict[str, Any]):
        """通知步骤完成"""
        if step_callback:
            try:
                step_callback(step_name, step_data)
            except Exception as e:
                print(f"⚠️ 步骤回调失败 ({step_name}): {e}")
    
    try:
        print(f"🚀 开始Agentic SQL智能体搜索流程")
        print(f"   SQL ID: {sql_id}")
        print(f"   用户查询: {query}")
        
        # 步骤1: 获取数据库信息（包括表结构和列信息）
        print("\n📊 步骤1: 获取数据库信息...")
        database_info = query_database_info(sql_id)
        if not database_info:
            error_msg = f"未找到数据库信息 (sql_id: {sql_id})"
            _notify_step("step_1_database_info", {
                "success": False,
                "error": error_msg
            })
            return {
                "success": False,
                "error": error_msg
            }
        
        db_name = database_info.get('sql_name', '')
        db_type = database_info.get('sql_type', '')
        print(f"   ✅ 数据库: {db_name} ({db_type})")
        
        # 获取所有表信息
        print("   📋 获取表结构信息...")
        all_tables = query_tables_by_sql_id(sql_id)
        tables_info = []
        
        for table in all_tables:
            table_id = table.get("table_id", "")
            table_name = table.get("table_name", "")
            table_description = table.get("table_description", "")
            
            if not table_id:
                continue
            
            # 获取表的列信息
            columns = query_columns_by_table_id(table_id)
            attributes_des_lt = []
            attributes_col_lt = []
            numerics_des_lt = []
            numerics_col_lt = []
            datetime_des_lt = []
            datetime_col_lt = []
            for col in columns:
                col_name = col.get("col_name", "")
                col_info = col.get("col_info", {})
                # 解析 col_info（可能是JSON字符串）
                if isinstance(col_info, str):
                    try:
                        col_info = json.loads(col_info)
                    except:
                        col_info = {}
                        
                col_comment = col_info.get("comment", "") if isinstance(col_info, dict) else ""
                
                col_type_ana = col_info.get("ana_type", "")
                if(col_type_ana == "numeric"):
                    numerics_des_lt.append(col_comment)
                    numerics_col_lt.append(col_name)
                elif(col_type_ana == "attribute"):
                    attributes_des_lt.append(col_comment)
                    attributes_col_lt.append(col_name)
                elif(col_type_ana == "datetime"):
                    datetime_des_lt.append(col_comment)
                    datetime_col_lt.append(col_name)
                    
            
            tables_info.append({
                # "table_id": table_id,
                "table_name": table_name,
                "table_description": table_description,
                "attributes_description": attributes_des_lt,
                "attributes":attributes_col_lt,
                "datetime_description": datetime_des_lt,
                "datetime": datetime_col_lt,
                "numerics_description": numerics_des_lt,
                "numerics": numerics_col_lt
            })
        
        # 将表结构信息添加到 database_info 中
        database_info["tables"] = tables_info
        database_info["tables_count"] = len(tables_info)
        
        print(f"   ✅ 获取到 {len(tables_info)} 个表的结构信息")
        
        _notify_step("step_1_database_info", {
            "success": True,
            "database_name": db_name,
            "database_type": db_type,
            "tables_count": len(tables_info),
            "database_info": database_info
        })
        
        # 步骤1.2: 数据库元数据查询检查
        print("\n🔍 步骤1.2: 检查是否是数据库元数据查询...")
        metadata_agent = DatabaseMetadataAgent()
        metadata_result = metadata_agent.process_metadata_query(sql_id, query)
        
        if metadata_result.get("success") and metadata_result.get("is_metadata_query"):
            # 是元数据查询，直接返回结果
            metadata_query_result = metadata_result.get("metadata_result", {})
            query_type = metadata_result.get("query_type", "")
            
            print(f"   ✅ 识别为数据库元数据查询: {query_type}")
            
            if metadata_query_result.get("success"):
                # 构建返回结果
                result_data = metadata_query_result.get("data", {})
                result_message = result_data.get("message", "查询成功")
                
                _notify_step("step_1_2_metadata_query", {
                    "success": True,
                    "is_metadata_query": True,
                    "query_type": query_type,
                    "result": result_data,
                    "message": result_message
                })
                
                return {
                    "success": True,
                    "is_metadata_query": True,
                    "query_type": query_type,
                    "metadata_result": metadata_query_result,
                    "message": result_message
                }
            else:
                # 元数据查询执行失败（表名或列名错误等）
                error_msg = metadata_query_result.get("error", "元数据查询执行失败")
                error_message = metadata_query_result.get("error_message", error_msg)
                available_tables = metadata_query_result.get("available_tables", [])
                available_columns = metadata_query_result.get("available_columns", [])
                
                print(f"   ⚠️ 元数据查询执行失败: {error_msg}")
                
                # 构建详细的错误信息
                error_result = {
                    "error": error_msg,
                    "error_message": error_message,
                    "query_type": query_type,
                    "table_name": metadata_result.get("table_name", ""),
                    "column_name": metadata_result.get("column_name", "")
                }
                
                if available_tables:
                    error_result["available_tables"] = available_tables
                    error_result["available_tables_count"] = len(available_tables)
                
                if available_columns:
                    error_result["available_columns"] = available_columns
                    error_result["available_columns_count"] = len(available_columns)
                
                _notify_step("step_1_2_metadata_query", {
                    "success": False,
                    "is_metadata_query": True,
                    "error": error_msg,
                    "error_message": error_message,
                    "available_tables": available_tables,
                    "available_columns": available_columns
                })
                
                # 元数据查询失败时，返回错误信息和详细查询信息，不继续后续流程
                return {
                    "success": False,
                    "is_metadata_query": True,
                    "query_type": query_type,
                    "error": error_msg,
                    "error_message": error_message,
                    "available_tables": available_tables,
                    "available_columns": available_columns,
                    "metadata_result": metadata_query_result
                }
        else:
            # 不是元数据查询，继续后续流程
            print(f"   ✅ 不是数据库元数据查询，继续后续流程")
            _notify_step("step_1_2_metadata_query", {
                "success": True,
                "is_metadata_query": False,
                "should_continue": True
            })
        
        # 步骤1.3: Milvus向量搜索（通过sql_id作为partition查询相关表）
        print("\n🔍 步骤1.3: Milvus向量搜索相关表...")
        table_info_list = []
        try:
            schema_vector_agent = SqlSchemaVectorAgent(sql_id=sql_id)
            # 通过sql_id作为partition进行语义搜索
            search_result = schema_vector_agent.search_graph_nodes(
                query=query,
                sql_id=sql_id,
                limit=10  # 最多返回10个相关表
            )
            
            if search_result.get("success"):
                results = search_result.get("results", [])
                print(f"   ✅ Milvus搜索完成，找到 {len(results)} 个相关表节点")
                
                # 提取唯一的table_id
                table_ids = set()
                for result in results:
                    table_id = result.get("table_id", "")
                    if table_id:
                        table_ids.add(table_id)
                
                print(f"   📋 提取到 {len(table_ids)} 个唯一的表ID")
                
                # 通过table_id获取表信息
                # 先获取所有表信息，然后匹配table_id
                all_tables = query_tables_by_sql_id(sql_id)
                table_id_to_table = {t.get("table_id"): t for t in all_tables}
                
                for table_id in table_ids:
                    try:
                        # 从已查询的表信息中获取
                        table_info = table_id_to_table.get(table_id)
                        if not table_info:
                            print(f"   ⚠️ 未找到表ID {table_id} 的信息")
                            continue
                        
                        # 获取列信息
                        columns = query_columns_by_table_id(table_id)
                        
                        # 构建表信息
                        table_data = {
                            "table_id": table_id,
                            "table_name": table_info.get("table_name", ""),
                            "table_description": table_info.get("table_description", ""),
                            "columns": []
                        }
                        
                        # 添加列信息
                        for col in columns:
                            col_info = col.get("col_info", {})
                            table_data["columns"].append({
                                "col_name": col.get("col_name", ""),
                                "col_type": col.get("col_type", ""),
                                "comment": col_info.get("comment", "")
                            })
                        
                        table_info_list.append(table_data)
                        print(f"   ✅ 获取表信息: {table_data['table_name']} ({len(table_data['columns'])} 列)")
                        
                    except Exception as e:
                        print(f"   ⚠️ 获取表 {table_id} 信息失败: {e}")
                        continue
                
                _notify_step("step_1_3_milvus_search", {
                    "success": True,
                    "search_results_count": len(results),
                    "table_ids_found": len(table_ids),
                    "table_info_count": len(table_info_list)
                })
            else:
                print(f"   ⚠️ Milvus搜索失败: {search_result.get('message', '未知错误')}")
                _notify_step("step_1_3_milvus_search", {
                    "success": False,
                    "error": search_result.get("message", "Milvus搜索失败")
                })
        except Exception as e:
            print(f"   ⚠️ Milvus搜索异常: {e}")
            traceback.print_exc()
            _notify_step("step_1_3_milvus_search", {
                "success": False,
                "error": f"Milvus搜索异常: {str(e)}"
            })
        
        # 步骤1.5: 问题拆解与逻辑分析（带表信息语义核对）
        print("\n🔍 步骤1.5: 问题拆解与逻辑分析（语义核对）...")
        decomposition_agent = QueryDecompositionAgent()
        # 如果找到了相关表信息，传入进行语义核对
        if table_info_list:
            print(f"   📋 使用 {len(table_info_list)} 个表信息进行语义核对")
            decomposition_result = decomposition_agent.decompose_query(query, table_info_list=table_info_list)
        else:
            print(f"   ⚠️ 未找到相关表信息，仅进行问题拆解")
            decomposition_result = decomposition_agent.decompose_query(query)
        
        if not decomposition_result.get("success"):
            error_msg = f"问题拆解失败: {decomposition_result.get('error', '未知错误')}"
            # 确保decomposition_result包含query字段，以便后续步骤使用
            if "query" not in decomposition_result:
                decomposition_result["query"] = query
            _notify_step("step_1_5_query_decomposition", {
                "success": False,
                "error": error_msg
            })
            # 问题拆解失败不影响后续流程，继续执行
            print(f"   ⚠️ {error_msg}，继续执行后续步骤")
            return {
                "success": False,
                "error": error_msg
            }
        else:
            entities = decomposition_result.get('entities', [])
            metrics = decomposition_result.get('metrics', [])
            time_dims = decomposition_result.get('time_dimensions', [])
            relationships = decomposition_result.get('relationships', [])
            logical_calcs = decomposition_result.get('logical_calculations', [])
            spatial_dims = decomposition_result.get('spatial_dimensions', [])
            set_theory = decomposition_result.get('set_theory_relations', [])
            relational_algebra = decomposition_result.get('relational_algebra', [])
            graph_theory = decomposition_result.get('graph_theory_relations', [])
            logical_reasoning = decomposition_result.get('logical_reasoning', [])
            semantic_network = decomposition_result.get('semantic_network', [])
            math_relations = decomposition_result.get('mathematical_relations', [])
            
            print(f"   ✅ 拆解结果:")
            print(f"      - 实体: {len(entities)} 个")
            print(f"      - 指标: {len(metrics)} 个")
            print(f"      - 时间维度: {len(time_dims)} 个")
            print(f"      - 关联关系: {len(relationships)} 个")
            print(f"      - 逻辑计算: {len(logical_calcs)} 个")
            print(f"      - 空间维度: {len(spatial_dims)} 个")
            print(f"      - 集合论关系: {len(set_theory)} 个")
            print(f"      - 关系代数: {len(relational_algebra)} 个")
            print(f"      - 图论关系: {len(graph_theory)} 个")
            print(f"      - 逻辑推理: {len(logical_reasoning)} 个")
            print(f"      - 语义网络: {len(semantic_network)} 个")
            print(f"      - 数学关系: {len(math_relations)} 个")
            
            _notify_step("step_1_5_query_decomposition", {
                "success": True,
                "entities_count": len(entities),
                "metrics_count": len(metrics),
                "time_dimensions_count": len(time_dims),
                "relationships_count": len(relationships),
                "logical_calculations_count": len(logical_calcs),
                "spatial_dimensions_count": len(spatial_dims),
                "set_theory_relations_count": len(set_theory),
                "relational_algebra_count": len(relational_algebra),
                "graph_theory_relations_count": len(graph_theory),
                "logical_reasoning_count": len(logical_reasoning),
                "semantic_network_count": len(semantic_network),
                "mathematical_relations_count": len(math_relations),
                "entities": entities,
                "metrics": metrics,
                "time_dimensions": time_dims,
                "relationships": relationships,
                "logical_calculations": logical_calcs,
                "spatial_dimensions": spatial_dims,
                "set_theory_relations": set_theory,
                "relational_algebra": relational_algebra,
                "graph_theory_relations": graph_theory,
                "logical_reasoning": logical_reasoning,
                "semantic_network": semantic_network,
                "mathematical_relations": math_relations,
                "analysis_summary": decomposition_result.get("analysis_summary", ""),
                "decomposition_result": decomposition_result
            })
        # 筛选出需要核对的表
        print("\n🔍 筛选相关表...")
        matched_tables = set()  # 使用set避免重复
        
        # 1. 通过entities在sqlite中LIKE搜索相关表格的描述
        if entities:
            for entity in entities:
                entity_name = entity.get('entity_name', '') if isinstance(entity, dict) else str(entity)
                if entity_name:
                    # 在表描述中搜索
                    tables_by_desc = cSingleSqlite.query_tables_by_description_like(sql_id, entity_name)
                    for table in tables_by_desc:
                        table_id = table.get('table_id', '')
                        if table_id:
                            matched_tables.add(table_id)
                    print(f"   - 实体 '{entity_name}' 匹配到 {len(tables_by_desc)} 个表")
        
        # 2. 通过metrics在sqlite中LIKE搜索相关列的描述
        if metrics:
            for metric in metrics:
                metric_name = metric.get('metric_name', '') if isinstance(metric, dict) else str(metric)
                if metric_name:
                    # 在列描述中搜索
                    columns_by_desc = cSingleSqlite.query_columns_by_description_like(sql_id, metric_name)
                    for col in columns_by_desc:
                        table_id = col.get('table_id', '')
                        if table_id:
                            matched_tables.add(table_id)
                    print(f"   - 指标 '{metric_name}' 匹配到 {len(columns_by_desc)} 个列（涉及 {len(set(c.get('table_id') for c in columns_by_desc))} 个表）")
        
        # 获取匹配的表信息
        filtered_tables = []
        if matched_tables:
            all_tables = query_tables_by_sql_id(sql_id)
            for table in all_tables:
                if table.get('table_id', '') in matched_tables:
                    filtered_tables.append(table)
            print(f"   ✅ 筛选出 {len(filtered_tables)} 个相关表")
        else:
            # 如果没有匹配的表，使用所有表
            filtered_tables = query_tables_by_sql_id(sql_id)
            print(f"   ⚠️ 未找到匹配的表，使用所有表（{len(filtered_tables)} 个）")
        
        # 更新database_info中的tables，只包含筛选出的表
        if filtered_tables:
            # 重新构建tables_info，只包含筛选出的表
            filtered_tables_info = []
            for table in filtered_tables:
                table_id = table.get('table_id', '')
                table_name = table.get('table_name', '')
                table_description = table.get('table_description', '')
                
                # 获取表的列信息
                columns = query_columns_by_table_id(table_id)
                attributes = []
                attributes_description = []
                datetime_cols = []
                datetime_description = []
                numerics = []
                numerics_description = []
                
                for col in columns:
                    col_name = col.get('col_name', '')
                    col_type = col.get('col_type', '')
                    col_info = col.get('col_info', {})
                    
                    if isinstance(col_info, str):
                        try:
                            col_info = json.loads(col_info)
                        except:
                            col_info = {}
                    
                    col_comment = col_info.get('comment', '') if isinstance(col_info, dict) else ''
                    col_type_ana = col_info.get('ana_type', '')
                    
                    if col_type_ana == 'numeric':
                        numerics.append(col_name)
                        numerics_description.append(col_comment if col_comment else col_name)
                    elif col_type_ana == 'attribute':
                        attributes.append(col_name)
                        attributes_description.append(col_comment if col_comment else col_name)
                    elif col_type_ana == 'datetime':
                        datetime_cols.append(col_name)
                        datetime_description.append(col_comment if col_comment else col_name)
                
                filtered_tables_info.append({
                    'table_id': table_id,
                    'table_name': table_name,
                    'table_description': table_description,
                    'attributes': attributes,
                    'attributes_description': attributes_description,
                    'datetime': datetime_cols,
                    'datetime_description': datetime_description,
                    'numerics': numerics,
                    'numerics_description': numerics_description
                })
            
            # 更新database_info
            database_info['tables'] = filtered_tables_info
        
        # 步骤2: 意图识别
        print("\n🧠 步骤2: 意图识别...")
        intent_agent = IntentRecognitionAgent()
        intent_analysis = intent_agent.analyze_intent(decomposition_result, database_info)
        
        if not intent_analysis.get("success"):
            error_msg = f"意图识别失败: {intent_analysis.get('error', '未知错误')}"
            _notify_step("step_2_intent_recognition", {
                "success": False,
                "error": error_msg
            })
            return {
                "success": False,
                "error": error_msg,
                "intent_analysis": intent_analysis
            }
        
        primary_entities = intent_analysis.get('primary_entities', [])
        entity_attributes = intent_analysis.get('entity_attributes', [])
        entity_metrics = intent_analysis.get('entity_metrics', [])
        time_dimensions = intent_analysis.get('time_dimensions', [])
        relationships = intent_analysis.get('relationships', [])
        relevant_tables = intent_analysis.get('relevant_tables', [])
        relevant_columns = intent_analysis.get('relevant_columns', [])
        
        print(f"   ✅ 识别到:")
        print(f"      - 本源实体: {len(primary_entities)} 个")
        print(f"      - 实体属性: {len(entity_attributes)} 个")
        print(f"      - 实体指标: {len(entity_metrics)} 个")
        print(f"      - 时间维度: {len(time_dimensions)} 个")
        print(f"      - 关联关系: {len(relationships)} 个")
        print(f"      - 相关表: {len(relevant_tables)} 个")
        print(f"      - 相关列: {len(relevant_columns)} 个")
        
        # 打印相关表名
        if relevant_tables:
            table_names = [t.get('table_name', '') for t in relevant_tables]
            print(f"      - 表名: {', '.join(table_names[:5])}")
        
        # 打印相关列名（按表分组）
        if relevant_columns:
            columns_by_table = {}
            for col in relevant_columns:
                table_name = col.get('table_name', '')
                col_name = col.get('col_name', '')
                if table_name and col_name:
                    if table_name not in columns_by_table:
                        columns_by_table[table_name] = []
                    columns_by_table[table_name].append(col_name)
            
            for table_name, cols in list(columns_by_table.items())[:3]:
                print(f"      - {table_name} 表的列: {', '.join(cols[:5])}")
        
        _notify_step("step_2_intent_recognition", {
            "success": True,
            "query_type": intent_analysis.get('search_strategy', ''),
            "primary_entities_count": len(primary_entities),
            "entity_attributes_count": len(entity_attributes),
            "entity_metrics_count": len(entity_metrics),
            "time_dimensions_count": len(time_dimensions),
            "relationships_count": len(relationships),
            "relevant_tables_count": len(relevant_tables),
            "relevant_columns_count": len(relevant_columns),
            "primary_entities": primary_entities,
            "entity_attributes": entity_attributes,
            "entity_metrics": entity_metrics,
            "time_dimensions": time_dimensions,
            "relationships": relationships,
            "relevant_tables": relevant_tables,
            "relevant_columns": relevant_columns,
            "intent_analysis": intent_analysis
        })
        
        # 步骤3: SQL生成流程（包含生成、检测、纠错、优化、再检测、核对）
        # 注意：已取消表核对步骤，直接使用意图识别步骤中找到的相关表
        print("\n💻 步骤3: SQL生成流程...")
        
        # 检查是否有相关表
        if not relevant_tables:
            return {
                "success": False,
                "error": "未找到相关表，无法生成SQL",
                "intent_analysis": intent_analysis
            }
        
        sql_flow = SqlGenerationFlow(max_retries=3)
        sql_flow_result = sql_flow.run_flow(
            query, intent_analysis, relevant_tables, sql_id, database_info, None,
            step_callback=lambda step_name, step_data: _notify_step(step_name, step_data)
        )
        
        if not sql_flow_result.get("success"):
            error_msg = f"SQL生成流程失败: {sql_flow_result.get('error', '未知错误')}"
            _notify_step("step_3_sql_generation", {
                "success": False,
                "error": error_msg
            })
            return {
                "success": False,
                "error": error_msg,
                "intent_analysis": intent_analysis,
                "relevant_tables": relevant_tables,
                "sql_flow_result": sql_flow_result
            }
        
        generated_sql = sql_flow_result.get("sql", "")
        final_execution_result = sql_flow_result.get("final_execution_result", {})
        is_satisfied = sql_flow_result.get("is_satisfied", True)
        generation_columns_used = sql_flow_result.get("generation_columns_used", [])  # SQL生成智能体返回的列信息
        
        print(f"   ✅ 最终SQL: {generated_sql}")
        print(f"   ✅ 执行结果: {'成功' if final_execution_result.get('executed', False) else '失败'}")
        print(f"   ✅ 满足度: {sql_flow_result.get('satisfaction_score', 1.0):.2f}")
        
        # 从SQL生成智能体返回的列信息中构建 columns_with_description
        columns_with_description = []
        tables_used_in_sql = set()  # 使用set避免重复
        
        # 构建表名到表ID的映射，用于获取列类型
        table_name_to_id = {}
        table_name_to_info = {}
        for table in relevant_tables:
            table_id = table.get("table_id", "")
            table_name = table.get("table_name", "")
            if table_name:
                table_name_to_id[table_name] = table_id
                table_name_to_info[table_name] = table
        
        # 从generation_columns_used中提取列信息
        for col_info in generation_columns_used:
            table_name = col_info.get("table_name", "")
            col_name = col_info.get("col_name", "")
            col_description = col_info.get("col_description", col_name)
            
            if table_name:
                tables_used_in_sql.add(table_name)
            
            # 获取列类型（从表信息中查找）
            col_type = "unknown"
            if table_name and table_name in table_name_to_id:
                table_id = table_name_to_id[table_name]
                columns = query_columns_by_table_id(table_id)
                for col in columns:
                    if col.get("col_name", "") == col_name:
                        col_type = col.get("col_type", "unknown")
                        break
            
            # 构建 table.col 格式的列名
            col_name_with_table = f"{table_name}.{col_name}" if table_name else col_name
            
            columns_with_description.append({
                "table_name": table_name,
                                "col_name": col_name,
                "col_name_with_table": col_name_with_table,
                "col_type": col_type,
                "col_description": col_description,
                "col_comment": col_description
            })
        
        # 如果generation_columns_used为空，回退到原来的方法（通过SQL字符串匹配）
        if not columns_with_description:
            print("   ⚠️ SQL生成智能体未返回列信息，使用字符串匹配方法")
            for table in relevant_tables:
                table_id = table.get("table_id", "")
                table_name = table.get("table_name", "")
                
                if table_name:
                    tables_used_in_sql.add(table_name)
                
                # 获取该表的所有列信息
                columns = query_columns_by_table_id(table_id)
                for col in columns:
                    col_name = col.get("col_name", "")
                    col_info = col.get("col_info", {})
                    
                    if isinstance(col_info, str):
                        try:
                            col_info = json.loads(col_info)
                        except:
                            col_info = {}
                    
                    col_comment = col_info.get("comment", "") if isinstance(col_info, dict) else ""
                    col_type = col.get("col_type", "")
                    
                    # 检查该列是否在SQL中被使用（通过检查列名是否在SQL中）
                    if col_name and col_name.lower() in generated_sql.lower():
                        # 构建 table.col 格式的列名
                        col_name_with_table = f"{table_name}.{col_name}"
                        columns_with_description.append({
                            "table_name": table_name,
                            "col_name": col_name,
                            "col_name_with_table": col_name_with_table,
                            "col_type": col_type,
                            "col_description": col_comment if col_comment else col_name,
                            "col_comment": col_comment
                        })
        
        tables_used_in_sql = list(tables_used_in_sql)
        
        # 从decomposition_result中获取逻辑计算信息
        logical_calculations = []
        if decomposition_result and decomposition_result.get("success"):
            logical_calcs = decomposition_result.get("logical_calculations", [])
            for lc in logical_calcs:
                logical_calculations.append({
                    "logical_operation": lc.get("logical_operation", ""),
                    "operands": lc.get("operands", []),
                    "description": lc.get("description", "")
                })
        
        _notify_step("step_3_sql_generation", {
            "success": True,
            "sql": generated_sql,
            "sql_type": sql_flow_result.get("sql_type", database_info.get("sql_type", "mysql")),
            "execution_result": final_execution_result,
            "is_satisfied": is_satisfied,
            "satisfaction_score": sql_flow_result.get("satisfaction_score", 1.0),
            "columns_with_description": columns_with_description,
            "logical_calculations": logical_calculations
        })
        
        # 构建 table.col 格式的列名列表（用于返回数据）
        columns_with_table_prefix = []
        for col in columns_with_description:
            col_name_with_table = col.get("col_name_with_table", f"{col.get('table_name', '')}.{col.get('col_name', '')}")
            columns_with_table_prefix.append(col_name_with_table)
        
        # 更新 execution_result 中的列名，使用 table.col 格式
        if final_execution_result and final_execution_result.get("executed"):
            original_columns = final_execution_result.get("columns", [])
            # 将原始列名映射到 table.col 格式
            updated_columns = []
            column_mapping = {}  # 原始列名 -> table.col 格式的映射
            
            for col in columns_with_description:
                original_col_name = col.get("col_name", "")
                col_name_with_table = col.get("col_name_with_table", "")
                if original_col_name and col_name_with_table:
                    column_mapping[original_col_name.lower()] = col_name_with_table
            
            # 更新列名列表
            for orig_col in original_columns:
                mapped_col = column_mapping.get(orig_col.lower(), orig_col)
                updated_columns.append(mapped_col)
            
            # 更新数据字典中的键名
            updated_data = []
            if final_execution_result.get("data"):
                for row in final_execution_result.get("data", []):
                    updated_row = {}
                    for i, orig_col in enumerate(original_columns):
                        mapped_col = column_mapping.get(orig_col.lower(), orig_col)
                        # 从原始行中获取值
                        if isinstance(row, dict):
                            value = row.get(orig_col)
                        else:
                            value = row[i] if i < len(row) else None
                        updated_row[mapped_col] = value
                    updated_data.append(updated_row)
            
            # 更新 execution_result
            final_execution_result["columns"] = updated_columns
            final_execution_result["data"] = updated_data
        
        # 返回最终结果（包含列描述和计算信息）
        result = {
            "success": True,
            "sql": generated_sql,
            "sql_type": database_info.get("sql_type", "mysql"),
            "execution_result": final_execution_result,
            "is_satisfied": is_satisfied,
            "satisfaction_score": sql_flow_result.get("satisfaction_score", 1.0),
            "columns_with_description": columns_with_description,  # 生成SQL使用的列及其描述
            "columns_with_table_prefix": columns_with_table_prefix,  # table.col 格式的列名列表
            "logical_calculations": logical_calculations,  # 分析用户意图时需要的计算
            "tables_used": tables_used_in_sql,  # 使用的表名列表
            "database_info": {
                "sql_id": sql_id,
                "sql_name": database_info.get("sql_name", ""),
                "sql_type": database_info.get("sql_type", "")
            }
        }
        
        print("\n✅ Agentic SQL智能体搜索流程完成")
        
        # 通知最终结果
        _notify_step("step_final_result", {
            "success": True,
            "sql": generated_sql,
            "sql_type": database_info.get("sql_type", "mysql")
        })
        
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"流程执行失败: {str(e)}"
        }


def run_logic_calculation(csv_file_path: str, query: str, logical_calculations: list,
                          columns_desc: list, columns_types: list, sql: str) -> Dict[str, Any]:
    """
    执行逻辑计算
    
    Args:
        csv_file_path: CSV文件路径
        query: 用户查询问题
        logical_calculations: 逻辑计算规则列表
        columns_desc: 列描述列表（table.col 格式）
        columns_types: 列类型列表
        sql: 原始SQL语句
        
    Returns:
        逻辑计算结果，包含最终解读
    """
    try:
        agent = LogicCalculationAgent()
        result = agent.calculate_logic(
            csv_file_path=csv_file_path,
            query=query,
            logical_calculations=logical_calculations,
            columns_desc=columns_desc,
            columns_types=columns_types,
            sql=sql
        )
        
        # 如果计算成功，添加最终综合解读
        if result.get("success"):
            final_interpretation = agent.interpret_final_result(
                query=query,
                logical_calculations=logical_calculations,
                calculation_result=result.get("calculation_result", {}),
                interpretation=result.get("interpretation", {}),
                tools_used=result.get("tools_used", []),
                columns_desc=columns_desc
            )
            result["final_interpretation"] = final_interpretation
        
        return result
    except Exception as e:
        traceback.print_exc()
        return {
            "success": False,
            "error": f"逻辑计算执行失败: {str(e)}"
        }


def analyze_database_descriptions(des_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    分析数据库描述文本，进行分类

    Args:
        des_list: 描述列表，格式为:
            [{"table_id": "", "title": "", "content": ""}]

    Returns:
        分类分析结果
    """
    try:
        agent = DatabaseAnalysisAgent()
        result = agent.analyze_database_descriptions(des_list)

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "数据库描述分析失败")
            }

        return result

    except Exception as e:
        traceback.print_exc()
        return {
            "success": False,
            "error": f"数据库描述分析执行失败: {str(e)}"
        }
