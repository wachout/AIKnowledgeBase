import os
import re
from typing import Dict, Any, List, Generator, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi

# ============================================================================
# 大模型配置
# ============================================================================

llm_stream = get_chat_tongyi(temperature=0.7, streaming=True, enable_thinking=False)

def rag_stream(query, intent_analysis, search_results, search_content, system_prompt=None):
    # 步骤3: 分析搜索结果统计信息
    engine_stats = {}
    milvus_docs = []
    elastic_docs = []
    graph_docs = []

    for result in search_results:
        engine = result.get("search_engine", "unknown")
        engine_stats[engine] = engine_stats.get(engine, 0) + 1

        # 分类存储不同引擎的结果
        if engine == "milvus":
            milvus_docs.append(result)
        elif engine == "elasticsearch":
            elastic_docs.append(result)
        elif engine == "graph_data":
            graph_docs.append(result)

    # 构建增强的搜索结果统计信息（不显示具体搜索引擎）
    search_stats = f"""
搜索结果统计：
- 总结果数：{len(search_results)} 个
- 从多个搜索引擎搜到的知识
"""

    # 步骤4: 构建RAG提示
    # 如果提供了动态 System Prompt，使用它；否则使用默认模板
    if system_prompt:
        # 使用动态 System Prompt
        prompt_template = system_prompt + """

## 搜索结果统计
{search_stats}

## 搜索结果内容（从多个搜索引擎搜到的知识）
{search_results}

## 意图分析
- 主要意图：{main_intent}
- 查询类型：{query_type}
- 关键词：{keywords}
- 实体：{entities}
- 搜索策略：{search_strategy}

请基于以上信息提供准确、全面、有帮助的回答。回答要：

内容处理原则：
1. **直接针对用户问题**，充分利用从多个搜索引擎搜到的知识
2. **优先考虑实体关系信息**，这些往往包含关键的上下文和关联
3. **媒体内容展示**：
   - 如果搜索结果中包含图片URL，直接显示图片URL（每行一个URL）
   - 如果搜索结果中包含表格数据，请说明"相关内容包含表格数据"
   - 对于图片，直接输出URL，不需要添加额外的提示信息
   - 对于表格，总结表格中的关键信息

回答结构：
4. **实体关系优先**：首先基于实体关系建立答案框架
5. **多源信息整合**：结合从多个搜索引擎搜到的知识的互补优势
6. **媒体内容集成**：在相关位置自然融入图片URL和表格信息的描述
7. **逻辑清晰合理**：如果信息不足明确说明，引导用户提供更多信息

回答："""
    else:
        # 使用默认模板
        prompt_template = """你是一个专业的智能助手，请基于多引擎搜索结果（包括图数据）回答用户的问题。

用户问题：{query}

意图分析：
- 主要意图：{main_intent}
- 查询类型：{query_type}
- 关键词：{keywords}
- 实体：{entities}
- 搜索策略：{search_strategy}

{search_stats}

搜索结果（从多个搜索引擎搜到的知识）：
{search_results}

重要说明：
- 图数据包含实体间的关系信息，这对于理解复杂概念非常有价值
- 如果搜索结果提到包含图片或表格，请在回答中适当提及
- 实体关系可以提供更深的上下文理解

请基于以上信息提供准确、全面、有帮助的回答。回答要：

内容处理原则：
1. **直接针对用户问题**，充分利用从多个搜索引擎搜到的知识
2. **优先考虑实体关系信息**，这些往往包含关键的上下文和关联
3. **媒体内容展示**：
   - 如果搜索结果中包含图片URL，直接显示图片URL（每行一个URL）
   - 如果搜索结果中包含表格数据，请说明"相关内容包含表格数据"
   - 对于图片，直接输出URL，不需要添加额外的提示信息
   - 对于表格，总结表格中的关键信息

回答结构：
4. **实体关系优先**：首先基于实体关系建立答案框架
5. **多源信息整合**：结合从多个搜索引擎搜到的知识的互补优势
6. **媒体内容集成**：在相关位置自然融入图片URL和表格信息的描述
7. **逻辑清晰合理**：如果信息不足明确说明，引导用户提供更多信息

回答："""
    
    prompt = ChatPromptTemplate.from_template(prompt_template)

    # 步骤4: 使用流式模型生成回答
    print("🎯 开始生成流式回答...")

    chain = prompt | llm_stream
    stream_response = chain.stream({
        "query": query,
        "main_intent": intent_analysis.get("main_intent", "未知"),
        "query_type": intent_analysis.get("query_type", "未知"),
        "keywords": ", ".join(intent_analysis.get("keywords", [])),
        "entities": ", ".join(intent_analysis.get("entities", [])),
        "search_strategy": intent_analysis.get("search_strategy", "未知"),
        "search_stats": search_stats,
        "search_results": search_content if search_content else "暂无相关搜索结果"
    })

    # 步骤5: 流式输出结果
    chunk_index = 0
    for chunk in stream_response:
        chunk_index += 1

        # 处理chunk内容
        if hasattr(chunk, 'content'):
            content = chunk.content
        else:
            content = str(chunk)

        if content.strip():  # 只输出非空内容
            # 提取图数据中的图片和表格信息
            media_info = extract_images_and_tables_from_graph(graph_docs) if graph_docs else {"images": [], "tables": []}

            yield {
                "id": f"rag_chunk_{hash(query)}_{chunk_index}",
                "object": "chat.completion.chunk",
                "created": int(os.times()[4]),
                "model": "rag-agentic-model",
                "choices": [{
                    "index": 0,
                    "delta": {
                        "content": content,
                        "type": "text",
                        "intent_analysis": intent_analysis,
                        "search_results_count": len(search_results),
                        "search_engine_stats": engine_stats,
                        "milvus_results_count": len(milvus_docs),
                        "elasticsearch_results_count": len(elastic_docs),
                        "graph_results_count": len(graph_docs),
                        "media_info": media_info
                    },
                    "finish_reason": None
                }]
            }

    # 发送结束标记
    yield {
        "id": f"rag_end_{hash(query)}",
        "object": "chat.completion.chunk",
        "created": int(os.times()[4]),
        "model": "rag-agentic-model",
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": "stop"
        }]
    }


def format_graph_data_for_display(graph_result: Dict[str, Any]) -> str:
    """格式化图数据结果用于显示

    Args:
        graph_result: 图数据搜索结果

    Returns:
        格式化的显示文本
    """
    try:
        graph_relation = graph_result.get("graph_relation", {})
        metadata = graph_result.get("metadata", {})

        formatted_text = f"🕸️ 图关系信息：\n"

        # 关系信息
        relation = graph_relation.get("relation", {})
        if relation:
            formatted_text += f"📋 关系描述：{relation.get('description', '无描述')}\n"
            if relation.get('keywords'):
                formatted_text += f"🏷️ 关键词：{relation.get('keywords')}\n"
            if relation.get('weight'):
                formatted_text += f"⚖️ 权重：{relation.get('weight')}\n"

        # 起始节点
        start_node = graph_relation.get("start_node", {})
        if start_node:
            formatted_text += f"\n🔵 起始节点：{start_node.get('entity_id', '未知')} ({start_node.get('entity_type', '未知类型')})\n"
            desc = start_node.get('description', '')
            if desc:
                formatted_text += f"📝 描述：{desc[:300]}{'...' if len(desc) > 300 else ''}\n"

            # 处理chunks中的图片和表格
            chunks = start_node.get('chunks', [])
            titles = start_node.get('titles', [])

            for j, chunk in enumerate(chunks[:3]):  # 只显示前3个chunk
                if isinstance(chunk, str):
                    # 提取图片URL并直接输出
                    img_urls = []
                    # 提取<img>标签中的URL
                    img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', chunk, re.IGNORECASE)
                    img_urls.extend(img_matches)
                    # 提取HTTP图片链接
                    http_matches = re.findall(r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp|bmp|svg)(?:\?[^\s]*)?', chunk, re.IGNORECASE)
                    img_urls.extend(http_matches)
                    
                    if img_urls:
                        # 直接输出图片URL，每行一个，不添加提示信息
                        for img_url in img_urls:
                            formatted_text += f"{img_url}\n"
                    # 检查是否包含表格
                    elif '<table' in chunk or '<tr' in chunk:
                        formatted_text += f"📊 包含表格数据\n"
                    else:
                        # 显示文本内容摘要
                        clean_chunk = re.sub(r'<[^>]+>', '', chunk)  # 移除HTML标签
                        if len(clean_chunk.strip()) > 50:
                            formatted_text += f"📄 内容：{clean_chunk.strip()[:200]}...\n"

                    # 显示对应标题
                    if j < len(titles) and titles[j]:
                        formatted_text += f"📖 标题：{titles[j]}\n"

        # 结束节点
        end_node = graph_relation.get("end_node", {})
        if end_node:
            formatted_text += f"\n🔴 结束节点：{end_node.get('entity_id', '未知')} ({end_node.get('entity_type', '未知类型')})\n"
            desc = end_node.get('description', '')
            if desc:
                formatted_text += f"📝 描述：{desc[:300]}{'...' if len(desc) > 300 else ''}\n"

            # 处理chunks中的图片和表格（类似起始节点处理）
            chunks = end_node.get('chunks', [])
            titles = end_node.get('titles', [])

            for j, chunk in enumerate(chunks[:3]):  # 只显示前3个chunk
                if isinstance(chunk, str):
                    # 提取图片URL并直接输出
                    img_urls = []
                    # 提取<img>标签中的URL
                    img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', chunk, re.IGNORECASE)
                    img_urls.extend(img_matches)
                    # 提取HTTP图片链接
                    http_matches = re.findall(r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp|bmp|svg)(?:\?[^\s]*)?', chunk, re.IGNORECASE)
                    img_urls.extend(http_matches)
                    
                    if img_urls:
                        # 直接输出图片URL，每行一个，不添加提示信息
                        for img_url in img_urls:
                            formatted_text += f"{img_url}\n"
                    # 检查是否包含表格
                    elif '<table' in chunk or '<tr' in chunk:
                        formatted_text += f"📊 包含表格数据\n"
                    else:
                        # 显示文本内容摘要
                        clean_chunk = re.sub(r'<[^>]+>', '', chunk)  # 移除HTML标签
                        if len(clean_chunk.strip()) > 50:
                            formatted_text += f"📄 内容：{clean_chunk.strip()[:200]}...\n"

                    # 显示对应标题
                    if j < len(titles) and titles[j]:
                        formatted_text += f"📖 标题：{titles[j]}\n"

        return formatted_text

    except Exception as e:
        return f"❌ 图数据格式化失败: {str(e)}"


def generate_graph_data_summary(graph_results: List[Dict[str, Any]], query: str) -> str:
    """生成图数据搜索结果的汇总信息

    Args:
        graph_results: 图数据搜索结果列表
        query: 用户查询

    Returns:
        汇总信息字符串
    """
    if not graph_results:
        return "未找到相关的图数据信息。"

    summary = f"📊 基于查询 '{query}' 找到的图数据信息：\n\n"

    # 统计信息
    total_relations = len(graph_results)
    entities = set()
    relations_found = []

    for result in graph_results:
        metadata = result.get("metadata", {})
        graph_relation = result.get("graph_relation", {})

        start_entity = metadata.get("start_entity", "")
        end_entity = metadata.get("end_entity", "")
        relation_desc = graph_relation.get("relation", {}).get("description", "")

        entities.add(start_entity)
        entities.add(end_entity)
        relations_found.append(f"{start_entity} → {end_entity}")

    summary += f"🔗 发现 {total_relations} 个相关关系\n"
    summary += f"🏷️ 涉及 {len(entities)} 个实体: {', '.join(list(entities)[:10])}{'...' if len(entities) > 10 else ''}\n\n"

    # 媒体内容统计
    media_info = extract_images_and_tables_from_graph(graph_results)
    if media_info["image_count"] > 0:
        summary += f"🖼️ 包含 {media_info['image_count']} 张相关图片\n"
    if media_info["table_count"] > 0:
        summary += f"📊 包含 {media_info['table_count']} 个相关表格\n"

    if media_info["image_count"] > 0 or media_info["table_count"] > 0:
        summary += "\n"

    # 主要关系展示
    summary += "📋 主要关系概览：\n"
    for i, relation in enumerate(relations_found[:5]):  # 只显示前5个
        summary += f"{i+1}. {relation}\n"
    if len(relations_found) > 5:
        summary += f"... 还有 {len(relations_found) - 5} 个关系\n"

    return summary


def extract_images_and_tables_from_graph(graph_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """从图数据结果中提取图片和表格信息

    Args:
        graph_results: 图数据搜索结果列表

    Returns:
        包含图片URLs、表格信息和统计数据的字典
        图片URL直接返回，不添加来源信息
    """
    images = []
    tables = []

    for result in graph_results:
        if result.get("search_engine") == "graph_data":
            media_content = result.get("media_content", {})
            graph_relation = result.get("graph_relation", {})

            # 从预处理的media_content中获取信息
            result_images = media_content.get("images", [])
            result_tables = media_content.get("tables", [])

            # 直接添加图片URL，不添加来源信息
            images.extend(result_images)

            # 添加表格信息
            tables.extend(result_tables)
            
            # 从graph_relation的chunks中提取图片URL
            for node_key in ["start_node", "end_node"]:
                node = graph_relation.get(node_key, {})
                chunks = node.get("chunks", [])
                for chunk in chunks:
                    if isinstance(chunk, str):
                        # 提取<img>标签中的URL
                        img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', chunk, re.IGNORECASE)
                        images.extend(img_matches)
                        
                        # 提取HTTP图片链接
                        http_matches = re.findall(r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp|bmp|svg)(?:\?[^\s]*)?', chunk, re.IGNORECASE)
                        images.extend(http_matches)

    # 对表格进行去重（基于内容）
    unique_tables = []
    seen_table_contents = set()
    for table in tables:
        content = table.get("content", "")
        if content not in seen_table_contents:
            seen_table_contents.add(content)
            unique_tables.append(table)

    # 图片URL去重并直接返回
    unique_images = list(set(images))

    return {
        "images": unique_images,  # 直接返回URL列表，不添加来源信息
        "tables": unique_tables,  # 基于内容去重
        "image_count": len(unique_images),
        "table_count": len(unique_tables)
    }


