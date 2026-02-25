# -*- coding:utf-8 -*-
"""
Agentic Query智能体主入口
结合知识库和SQL的智能问答功能
"""

from typing import Dict, Any, Optional
from Agent.AgenticQueryAgent import (
    DecisionAgent,
    HybridSearchAgent,
    ResultEvaluatorAgent,
    ExpandedSearchAgent,
    DynamicPromptAgent,
    ArtifactHandler,
    QueryEnhancementAgent
)


def run_agentic_query(knowledge_id: str, query: str, sql_id: str = None,
                     user_id: str = None, step_callback: Optional[callable] = None) -> Dict[str, Any]:
    """
    运行Agentic Query智能体流程
    
    工作流程：
    1. 决策智能体：判断用户问题中提到的实体本源、指标、属性、时间、关系等
    2. 通过milvus和Elasticsearch双引擎搜索：
       a. 初步查询知识库
       b. 结果评估：分析搜索结果质量
       c. 如果不满意：扩展搜索
       d. 动态生成 System Prompt
       e. Artifact 处理：分离清洗内容和原始内容
       f. 目标是完善用户的问题，生成更详细的查询和计算
    
    Args:
        knowledge_id: 知识库ID
        query: 用户查询问题
        sql_id: SQL数据库ID（可选）
        user_id: 用户ID（可选）
        step_callback: 步骤回调函数，用于流式返回步骤信息
        
    Returns:
        完整的查询结果，包含：
        - success: 是否成功
        - enhanced_query: 增强后的查询
        - system_prompt: 动态生成的System Prompt
        - search_results: 搜索结果
        - calculation_descriptions: 计算描述
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
        print(f"🚀 开始Agentic Query智能体流程")
        print(f"   知识库ID: {knowledge_id}")
        print(f"   用户查询: {query}")
        if sql_id:
            print(f"   SQL数据库ID: {sql_id}")
        
        # 步骤1: 决策智能体 - 分析实体本源、指标、属性、时间、关系等
        print("\n🔍 步骤1: 决策智能体 - 分析实体本源、指标、属性等...")
        decision_agent = DecisionAgent()
        entity_analysis = decision_agent.analyze_entities(query)
        
        if not entity_analysis.get("success"):
            error_msg = f"实体分析失败: {entity_analysis.get('error', '未知错误')}"
            _notify_step("step_1_decision", {
                "success": False,
                "error": error_msg
            })
            return {
                "success": False,
                "error": error_msg
            }
        
        _notify_step("step_1_decision", {
            "success": True,
            "entity_analysis": entity_analysis
        })
        
        print(f"   ✅ 识别到 {len(entity_analysis.get('entities', []))} 个实体")
        print(f"   ✅ 识别到 {len(entity_analysis.get('metrics', []))} 个指标")
        print(f"   ✅ 识别到 {len(entity_analysis.get('attributes', []))} 个属性")
        
        # 步骤2: 双引擎搜索 - 初步查询知识库
        print("\n🔍 步骤2: 双引擎搜索 - 初步查询知识库...")
        hybrid_search_agent = HybridSearchAgent()
        search_result = hybrid_search_agent.search(
            knowledge_id=knowledge_id,
            query=query,
            user_id=user_id,
            top_k=10,
            permission_flag=True
        )
        
        if not search_result.get("success"):
            error_msg = f"搜索失败: {search_result.get('error', '未知错误')}"
            _notify_step("step_2_search", {
                "success": False,
                "error": error_msg
            })
            return {
                "success": False,
                "error": error_msg,
                "entity_analysis": entity_analysis
            }
        
        initial_results = search_result.get("combined_results", [])
        print(f"   ✅ Milvus搜索结果: {len(search_result.get('milvus_results', []))} 个")
        print(f"   ✅ Elasticsearch搜索结果: {len(search_result.get('elasticsearch_results', []))} 个")
        print(f"   ✅ 合并后结果: {len(initial_results)} 个")
        
        _notify_step("step_2_search", {
            "success": True,
            "milvus_count": len(search_result.get('milvus_results', [])),
            "elasticsearch_count": len(search_result.get('elasticsearch_results', [])),
            "total_count": len(initial_results)
        })
        
        # 步骤3: 结果评估 - 分析搜索结果质量
        print("\n📊 步骤3: 结果评估 - 分析搜索结果质量...")
        evaluator_agent = ResultEvaluatorAgent()
        evaluation_result = evaluator_agent.evaluate_results(
            query=query,
            search_results=initial_results,
            entity_analysis=entity_analysis
        )
        
        quality_score = evaluation_result.get("quality_score", 0.0)
        is_satisfied = evaluation_result.get("is_satisfied", False)
        should_expand = evaluation_result.get("should_expand", False)
        
        print(f"   ✅ 质量评分: {quality_score:.3f}")
        print(f"   ✅ 是否满意: {is_satisfied}")
        print(f"   ✅ 是否需要扩展: {should_expand}")
        
        _notify_step("step_3_evaluation", {
            "success": True,
            "quality_score": quality_score,
            "is_satisfied": is_satisfied,
            "should_expand": should_expand
        })
        
        # 步骤4: 扩展搜索（如果不满意）
        final_results = initial_results
        if should_expand:
            print("\n🔍 步骤4: 扩展搜索...")
            expanded_search_agent = ExpandedSearchAgent()
            expanded_result = expanded_search_agent.expand_search(
                knowledge_id=knowledge_id,
                query=query,
                evaluation_result=evaluation_result,
                initial_results=initial_results,
                user_id=user_id,
                permission_flag=True
            )
            
            if expanded_result.get("success"):
                final_results = expanded_result.get("all_results", initial_results)
                print(f"   ✅ 扩展搜索完成，共 {len(final_results)} 个结果")
            else:
                print(f"   ⚠️ 扩展搜索失败，使用初始结果")
            
            _notify_step("step_4_expanded_search", {
                "success": expanded_result.get("success", False),
                "expanded_count": len(expanded_result.get("expanded_results", [])),
                "total_count": len(final_results)
            })
        else:
            print("\n⏭️  步骤4: 跳过扩展搜索（结果已满足要求）")
            _notify_step("step_4_expanded_search", {
                "success": True,
                "skipped": True,
                "reason": "结果已满足要求"
            })
        
        # 步骤5: Artifact处理 - 分离清洗内容和原始内容
        print("\n📋 步骤5: Artifact处理 - 分离清洗内容和原始内容...")
        artifact_handler = ArtifactHandler()
        artifact_result = artifact_handler.process_for_query(final_results)
        
        cleaned_content = artifact_result.get("cleaned_content", "")
        artifacts = artifact_result.get("artifacts", [])
        
        print(f"   ✅ 处理完成，共 {len(artifacts)} 个Artifact")
        
        _notify_step("step_5_artifact", {
            "success": True,
            "artifacts_count": len(artifacts),
            "cleaned_content_length": len(cleaned_content)
        })
        
        # 步骤6: 动态生成System Prompt
        print("\n📝 步骤6: 动态生成System Prompt...")
        prompt_agent = DynamicPromptAgent()
        prompt_result = prompt_agent.generate_prompt(
            query=query,
            entity_analysis=entity_analysis,
            search_results=final_results
        )
        
        system_prompt = prompt_result.get("system_prompt", "")
        print(f"   ✅ System Prompt生成完成（长度: {len(system_prompt)} 字符）")
        
        _notify_step("step_6_dynamic_prompt", {
            "success": True,
            "prompt_length": len(system_prompt)
        })
        
        # 步骤7: 查询增强 - 完善用户问题，生成更详细的查询和计算
        print("\n✨ 步骤7: 查询增强 - 完善用户问题...")
        enhancement_agent = QueryEnhancementAgent()
        enhancement_result = enhancement_agent.enhance_query(
            original_query=query,
            entity_analysis=entity_analysis,
            search_results=final_results,
            artifact_content=cleaned_content
        )
        
        enhanced_query = enhancement_result.get("enhanced_query", query)
        calculation_descriptions = enhancement_result.get("calculation_descriptions", [])
        
        print(f"   ✅ 查询增强完成")
        print(f"   ✅ 识别到 {len(calculation_descriptions)} 个计算描述")
        
        _notify_step("step_7_query_enhancement", {
            "success": True,
            "enhanced_query": enhanced_query,
            "calculation_descriptions_count": len(calculation_descriptions)
        })
        
        print("\n✅ Agentic Query智能体流程完成")
        
        # 构建返回结果
        return {
            "success": True,
            "original_query": query,
            "enhanced_query": enhanced_query,
            "system_prompt": system_prompt,
            "entity_analysis": entity_analysis,
            "search_results": final_results,
            "artifacts": artifacts,
            "cleaned_content": cleaned_content,
            "calculation_descriptions": calculation_descriptions,
            "detailed_requirements": enhancement_result.get("detailed_requirements", ""),
            "quality_score": quality_score,
            "evaluation_result": evaluation_result
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Agentic Query流程执行失败: {str(e)}"
        }
