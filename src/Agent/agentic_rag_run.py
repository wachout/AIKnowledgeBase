"""
RAG Agentic 智能体运行模块（增强版）

采用自适应框架，关注核心思考序列，需要多种假设生成，同时系统性的验证

智能体流程：
1. 意图识别智能体：判断是调用工具还是检索知识库，识别用户核心意图
   a. 语义提纯消除歧义
   b. 逻辑和规则的提纯，数理逻辑
2. 如果是工具：直接执行工具并返回结果
3. 如果是检索：
   a. 初步查询知识库
   b. 结果评估：分析搜索结果质量
   c. 如果不满意：扩展搜索
   d. 文本冗余信息融合智能体（不用大模型）
   e. 自我反思智能体：动态生成System Prompt
   f. 调度智能体：判断是否扩展搜索（最多2次）
   g. Artifact 处理：分离清洗内容和原始内容
   h. 流式生成回答
"""

import os
from typing import Dict, Any, Optional, List, Generator
from langchain_core.messages import BaseMessage

from Agent.AgenticRagAgent import rag_agentic_agent
from Agent.AgenticRagAgent.intent_recognition_agent import run_intent_based_search
from Agent.AgenticRagAgent.enhanced_intent_agent import EnhancedIntentAgent
from Agent.AgenticRagAgent.tool_agent import ToolAgent
from Agent.AgenticRagAgent.redundancy_fusion_agent import RedundancyFusionAgent
from Agent.AgenticRagAgent.reflection_agent import ReflectionAgent
from Agent.AgenticRagAgent.orchestrator_agent import OrchestratorAgent
from Agent.AgenticRagAgent.result_evaluator_agent import ResultEvaluatorAgent
from Agent.AgenticRagAgent.artifact_handler import ArtifactHandler
from Db.sqlite_db import cSingleSqlite


def run_rag_agentic_stream(query: str, knowledge_id: str, user_id: str, 
                          chat_history: Optional[List[BaseMessage]] = None,
                          flag: bool = True) -> Generator[Dict[str, Any], None, None]:
    """
    运行RAG Agentic智能体（增强版），采用自适应框架进行流式回答生成。

    工作流程：
    1. 意图识别智能体：判断是调用工具还是检索知识库，识别用户核心意图
       a. 语义提纯消除歧义
       b. 逻辑和规则的提纯，数理逻辑
    2. 如果是工具：直接执行工具并返回结果
    3. 如果是检索：
       a. 初步查询知识库（三引擎并行搜索：Milvus + Elasticsearch + Graph）
       b. 结果评估：分析搜索结果质量
       c. 文本冗余信息融合智能体（不用大模型）
       d. 自我反思智能体：动态生成System Prompt
       e. 调度智能体：判断是否扩展搜索（最多2次）
       f. Artifact 处理：分离清洗内容和原始内容
       g. 流式生成回答

    参数:
        query (str): 用户的查询内容。
        knowledge_id (str): 知识库ID。
        user_id (str): 用户ID。
        chat_history (Optional[List[BaseMessage]]): 聊天历史（可选）。
        flag (bool): 权限标志，指示是否进行意图识别。

    返回:
        Generator[Dict[str, Any], None, None]: 响应流生成器。
    """
    
    # 初始化组件
    enhanced_intent_agent = EnhancedIntentAgent()
    tool_agent = ToolAgent()
    redundancy_fusion_agent = RedundancyFusionAgent()
    reflection_agent = ReflectionAgent()
    orchestrator_agent = OrchestratorAgent(max_expansions=2)
    evaluator_agent = ResultEvaluatorAgent()
    artifact_handler = ArtifactHandler()
    
    # 步骤1: 获取知识库元数据
    print("📚 步骤1: 获取知识库元数据...")
    knowledge_description_d = cSingleSqlite.search_knowledge_base_by_knowledge_id(knowledge_id)
    knowledge_description = knowledge_description_d.get("description", "知识库未描述")
    
    # 转换聊天历史格式
    history_list = None
    if chat_history:
        history_list = [
            {"role": "user" if hasattr(msg, "type") and msg.type == "human" else "assistant",
             "content": msg.content if hasattr(msg, "content") else str(msg)}
            for msg in chat_history[-5:]  # 只使用最近5轮
        ]
    
    # 步骤2: 增强的意图识别智能体
    print("🎯 步骤2: 增强的意图识别（语义提纯 + 逻辑提纯）...")
    intent_result = enhanced_intent_agent.analyze_intent(
        query=query,
        knowledge_description=knowledge_description,
        chat_history=history_list
    )
    
    action = intent_result.get("action", "retrieve")
    core_intent = intent_result.get("core_intent", "")
    semantic_purified_query = intent_result.get("semantic_purified_query", query)
    
    # 咨询本源识别结果
    consultation_root_cause = intent_result.get("consultation_root_cause", "")
    consultation_essence = intent_result.get("consultation_essence", "")
    consultation_core_issue = intent_result.get("consultation_core_issue", "")
    consultation_source = intent_result.get("consultation_source", "")
    
    print(f"✅ 意图识别结果: {action}")
    print(f"✅ 核心意图: {core_intent}")
    print(f"✅ 语义提纯查询: {semantic_purified_query}")
    print(f"🔍 咨询本源识别:")
    print(f"   - 根本原因: {consultation_root_cause}")
    print(f"   - 本质意图: {consultation_essence}")
    print(f"   - 核心问题: {consultation_core_issue}")
    print(f"   - 咨询根源: {consultation_source}")
    
    # 步骤3: 根据决策执行相应行动
    if action == "tool":
        # 工具调用路径
        print("🔧 执行工具调用...")
        tool_name = intent_result.get("tool_name", "")
        print(f"🛠️ 工具名称: {tool_name}")
        
        # 使用工具智能体根据 intent_result 执行工具
        tool_execution_result = tool_agent.execute_tool_by_intent(
            intent_result=intent_result,
            query=query,
            knowledge_id=knowledge_id
        )
        
        if tool_execution_result.get("success", False):
            # 工具执行成功，流式输出结果
            formatted_content = tool_execution_result.get("formatted_content", "")
            tool_name_executed = tool_execution_result.get("tool_name", tool_name)
            
            print(f"✅ 工具 {tool_name_executed} 执行成功")
            
            # 流式输出工具结果
            chunk = create_chunk(f"tool_result_{hash(query)}", int(os.times()[4]), 
                               default_content=formatted_content, _type="text", 
                               intent_analysis=intent_result, search_results="", finish_reason=None)
            yield chunk
            
            # 发送结束标记
            chunk = create_chunk(f"tool_end_{hash(query)}", int(os.times()[4]), 
                               default_content="", _type="text", 
                               intent_analysis=intent_result, search_results="", finish_reason="stop")
            yield chunk
            return
        else:
            # 工具执行失败，转为检索模式
            error_msg = tool_execution_result.get("error", "未知错误")
            print(f"❌ 工具执行失败: {error_msg}，转为检索模式")
            action = "retrieve"
    
    # 检索路径：初步查询知识库
    print("🔍 步骤3: 初步查询知识库...")
    # 使用query和intent_result进行语义搜索
    print(f"🔍 原始查询: {query}")
    print(f"🔍 语义提纯查询: {semantic_purified_query}")
    intent_search_result = run_intent_based_search(
        query=query, 
        knowledge_id=knowledge_id, 
        user_id=user_id, 
        flag=flag, 
        intent_result=intent_result  # 传入增强的意图识别结果
    )
    
    initial_results = intent_search_result.get("search_results", [])
    # 合并增强意图识别的结果
    intent_analysis = {
        **intent_result,
        **intent_search_result.get("intent_analysis", {})
    }
    
    print(f"📊 初步搜索获得 {len(initial_results)} 个结果")
    
    # 步骤4: 结果评估
    print("📈 步骤4: 评估搜索结果质量...")
    evaluation = evaluator_agent.evaluate_results(
        query=query,
        search_results=initial_results,
        intent_analysis=intent_analysis
    )
    
    print(f"✅ 质量评分: {evaluation.get('quality_score', 0):.2f}")
    print(f"✅ 是否满意: {evaluation.get('is_satisfactory', False)}")
    
    # 步骤5: 文本冗余信息融合智能体（不用大模型）
    print("🔗 步骤5: 文本冗余信息融合（拆句、找关系、架桥梁）...")
    fused_result = redundancy_fusion_agent.fuse_redundant_information(initial_results)
    
    if fused_result.get("success"):
        print(f"✅ 融合完成：{len(fused_result.get('core_sentences', []))} 个核心句子")
        print(f"✅ 主题桥梁：{len(fused_result.get('topic_bridges', []))} 个")
    
    # 步骤6: 自我反思智能体 + 调度智能体（循环最多2次）
    print("🤔 步骤6: 自我反思 + 调度扩展搜索...")
    final_results = initial_results
    expansion_count = 0
    system_prompt = ""
    
    while expansion_count < 2:
        # 自我反思
        reflection_result = reflection_agent.reflect_and_generate_prompt(
            query=query,
            fused_content=fused_result,
            search_results=final_results,
            intent_analysis=intent_analysis
        )
        
        if reflection_result.get("success"):
            system_prompt = reflection_result.get("system_prompt", "")
            print(f"✅ 反思完成，生成System Prompt: {len(system_prompt)} 字符")
        
        # 调度智能体判断是否扩展
        expansion_decision = orchestrator_agent.should_expand_search(
            reflection_result=reflection_result,
            expansion_count=expansion_count
        )
        
        if not expansion_decision.get("should_expand", False):
            print(f"✅ 调度决策：不需要扩展搜索（{expansion_decision.get('reason', '')}）")
            break
        
        # 执行扩展搜索
        expansion_count += 1
        print(f"🚀 执行第 {expansion_count} 次扩展搜索...")
        
        suggested_queries = expansion_decision.get("suggested_queries", [])
        expanded_results = []
        
        # 将 reflection_result 转换为意图识别结果格式，用于指导扩展搜索
        reflection_intent_result = None
        if reflection_result.get("success"):
            # 从 reflection_result 中提取信息构建意图识别结果
            missing_info = reflection_result.get("missing_information", [])
            reasoning = reflection_result.get("reasoning", "")
            
            # 将缺失信息转换为实体列表（用于搜索）
            entities = []
            if isinstance(missing_info, list):
                entities = [str(item) for item in missing_info if item]
            
            reflection_intent_result = {
                "semantic_purified_query": reflection_result.get("suggested_queries", [""])[0] if reflection_result.get("suggested_queries") else query,
                "core_intent": f"扩展搜索: {reasoning[:100] if reasoning else '基于反思结果进行扩展搜索'}",
                "entities": entities,  # 使用缺失信息作为实体
                "relationships": [],
                "attributes": [],
                "missing_information": missing_info,
                "reasoning": reasoning,
                "needs_expansion": reflection_result.get("needs_expansion", True)
            }
            print(f"🔍 使用反思结果指导扩展搜索:")
            print(f"   - 反思理由: {reasoning[:100] if reasoning else '无'}")
            print(f"   - 缺失信息: {missing_info[:3] if missing_info else '无'}")
            print(f"   - 实体提取: {entities[:3] if entities else '无'}")
        
        for expanded_query in suggested_queries:
            print(f"  - 扩展搜索: {expanded_query[:50]}...")
            # 为每个扩展查询构建特定的意图结果
            expanded_intent_result = None
            if reflection_intent_result:
                expanded_intent_result = {
                    **reflection_intent_result,
                    "semantic_purified_query": expanded_query,  # 使用扩展查询作为语义提纯查询
                    "core_intent": f"扩展搜索: {expanded_query}"
                }
            
            # 使用 expanded_query 和 reflection_result 进行知识库搜索
            expanded_result = run_intent_based_search(
                query=expanded_query,
                knowledge_id=knowledge_id,
                user_id=user_id,
                flag=flag,
                intent_result=expanded_intent_result  # 传入基于反思结果的意图识别结果
            )
            expanded_results.extend(expanded_result.get("search_results", []))
        
        # 合并结果
        final_results = final_results + expanded_results
        print(f"📈 扩展后共获得 {len(final_results)} 个结果")
        
        # 重新融合信息
        fused_result = redundancy_fusion_agent.fuse_redundant_information(final_results)
    
    # 步骤7: Artifact 处理
    print("🎨 步骤7: 处理 Artifact...")
    artifact_data = artifact_handler.process_search_results(final_results)
    cleaned_content = artifact_data["cleaned_content"]
    artifacts = artifact_data["artifacts"]
    
    # 如果没有生成System Prompt，使用融合后的内容
    if not system_prompt:
        system_prompt = f"""你是一个专业的AI助手。请基于以下信息回答用户的问题。

用户查询：{query}
核心意图：{core_intent}

请使用以下信息回答问题：
{cleaned_content}

要求：
1. 准确理解用户的核心意图
2. 基于提供的信息进行回答
3. 如果信息不足，请说明"""
    
    # 步骤8: 构建搜索结果文本（用于RAG）
    # 优先使用融合后的内容
    search_content = fused_result.get("fused_content", cleaned_content) if fused_result.get("success") else cleaned_content
    
    # 步骤9: 调用RAG流式处理（传入动态System Prompt）
    print("🎯 步骤9: 流式生成回答...")
    chunk_count = 0
    
    # 先发送 Artifact 信息（给用户看）
    artifacts_chunk = create_chunk(
        f"artifacts_{hash(query)}",
        int(os.times()[4]),
        default_content="",
        _type="artifacts",
        intent_analysis=intent_analysis,
        search_results=artifact_handler.format_artifacts_for_frontend(artifacts),
        finish_reason=None
    )
    yield artifacts_chunk
    
    # 然后流式生成回答
    for chunk in rag_agentic_agent.rag_stream(
        query=query,
        intent_analysis=intent_analysis,
        search_results=final_results,
        search_content=search_content,
        system_prompt=system_prompt  # 传入动态生成的System Prompt
    ):
        chunk_count += 1
        yield chunk
    
    # 如果没有收到任何chunk，生成默认响应
    if chunk_count == 0:
        print("⚠️ RAG流式处理没有产生任何chunk，生成默认响应")
        default_content = ""
        if not final_results:
            default_content = "抱歉，基于您的查询没有找到相关信息。请尝试重新表述您的问题，或者检查知识库中是否有相关内容。"
        else:
            default_content = f"已找到 {len(final_results)} 条相关信息，但生成回答时出现问题。请稍后重试。"
        
        _id = f"rag_default_{hash(query)}"
        chunk = create_chunk(_id, int(os.times()[4]), default_content, 
                           intent_analysis=intent_analysis, 
                           search_results=final_results,
                           finish_reason="stop")
        yield chunk


def create_chunk(_id, _time, default_content="", _type="text", 
                 intent_analysis="", search_results="",
                 finish_reason="stop"):
    """创建chunk对象"""
    chunk_data = {
        "id": _id,
        "object": "chat.completion.chunk",
        "created": int(os.times()[4]),
        "model": "rag-agentic-model",
        "choices": [{
            "index": 0,
            "delta": {
                "content": default_content,
                "type": _type,
            },
            "finish_reason": finish_reason
        }]
    }
    
    # 添加额外字段
    if intent_analysis:
        chunk_data["choices"][0]["delta"]["intent_analysis"] = intent_analysis
    if search_results:
        if isinstance(search_results, list):
            chunk_data["choices"][0]["delta"]["search_results_count"] = len(search_results)
            chunk_data["choices"][0]["delta"]["artifacts"] = search_results
        else:
            chunk_data["choices"][0]["delta"]["search_results"] = search_results
    
    return chunk_data
