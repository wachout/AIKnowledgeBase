"""
用户意图识别和搜索智能体

功能特性：
1. 用户意图识别和query分析
2. 基于意图进行双引擎搜索（Milvus + Elasticsearch）
3. 语义实体扩展和额外搜索
4. 结果合并和返回

工作流程：
1. 意图识别和query分析 → 2. 初始双引擎搜索 → 3. 实体扩展 → 4. 扩展搜索 → 5. 结果合并
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from re import S
from typing import List, Dict, Any, TypedDict, Optional

# LangChain 核心组件
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers.json import JsonOutputParser
from langchain_core.tools import tool
# from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_community.chat_models.tongyi import ChatTongyi
from Config.llm_config import get_chat_tongyi

# 项目内部模块
from Config.embedding_config import get_embeddings
from Control.control_search import CControl as ControlSearch
from Db.sqlite_db import cSingleSqlite

# ============================================================================
# 大模型配置
# ============================================================================

llm = get_chat_tongyi(temperature=0.7, streaming=False, enable_thinking=False)

# ============================================================================
# 工具定义
# ============================================================================

def file_statistics_impl(knowledge_id: str) -> Dict[str, Any]:
    """知识库的文件统计信息

    Args:
        knowledge_id: 知识库ID

    Returns:
        文件统计信息
    """
    try:
        # 获取知识库文件数量
        file_count = cSingleSqlite.search_file_num_by_knowledge_id(knowledge_id)
        knowledge_dict = cSingleSqlite.query_knowledge_by_knowledge_id(knowledge_id)
        knowledge_name = knowledge_dict.get("name", "未知知识库")

        # 检查是否有数据
        if file_count == 0:
            return {
                "knowledge_name": knowledge_name,
                "file_count": 0,
                "description": f"知识库 {knowledge_name} 目前还没有上传任何文件，请先上传文件后再查询。",
                "tool_result": True,
                "empty_data": True
            }

        return {
            "knowledge_name": knowledge_name,
            "file_count": file_count,
            "description": f"知识库 {knowledge_name} 包含 {file_count} 个文件",
            "tool_result": True
        }
    except Exception as e:
        return {"error": f"获取文件统计失败: {str(e)}", "tool_result": False}

def file_list_impl(knowledge_id: str) -> Dict[str, Any]:
    """获取知识库的文件列表

    Args:
        knowledge_id: 知识库ID

    Returns:
        文件列表信息
    """
    try:
        # 获取知识库文件列表
        files = cSingleSqlite.search_file_name_by_knowledge_id(knowledge_id)
        knowledge_dict = cSingleSqlite.query_knowledge_by_knowledge_id(knowledge_id)
        knowledge_name = knowledge_dict.get("name", "未知知识库")

        # 检查是否有数据
        if not files or len(files) == 0:
            return {
                "knowledge_name": knowledge_name,
                "files": [],
                "file_count": 0,
                "description": f"知识库 {knowledge_name} 目前还没有上传任何文件，请先上传文件后再查看文件列表。",
                "tool_result": True,
                "empty_data": True
            }

        return {
            "knowledge_name": knowledge_name,
            "files": files,
            "file_count": len(files),
            "description": f"知识库 {knowledge_name} 的文件列表，最多显示前 {len(files)} 个文件",
            "tool_result": True
        }
    except Exception as e:
        return {"error": f"获取文件列表失败: {str(e)}", "tool_result": False}

def file_summary_impl(file_name: str) -> Dict[str, Any]:
    """获取文件的详细主旨信息

    Args:
        file_name: 文件名

    Returns:
        文件详细信息
    """
    try:
        # 获取文件详细信息
        file_info = cSingleSqlite.search_file_detail_info_by_file_name(file_name)

        # 检查是否有数据
        if not file_info:
            return {
                "file_name": file_name,
                "file_info": None,
                "description": f"未找到文件 {file_name} 的详细信息，请确认文件名是否正确。",
                "tool_result": True,
                "empty_data": True
            }

        return {
            "file_name": file_name,
            "file_info": file_info,
            "description": f"文件 {file_name} 的详细信息",
            "tool_result": True
        }
    except Exception as e:
        return {
            "file_name": file_name,
            "file_info": None,
            "description": f"查询文件 {file_name} 时发生错误：{str(e)}",
            "tool_result": True,
            "empty_data": True
        }

# 创建工具对象
file_statistics_tool = tool("file_statistics")(file_statistics_impl)
file_list_tool = tool("file_list")(file_list_impl)
file_summary_tool = tool("file_summary")(file_summary_impl)

# ============================================================================
# 数据结构定义
# ============================================================================

class IntentSearchState(TypedDict):
    """意图识别和搜索的状态"""
    question: str                           # 用户原始问题
    knowledge_id: str                       # 知识库ID
    user_id: str                            # 用户ID
    intent_analysis: Dict[str, Any]         # 意图分析结果
    search_results: List[Dict[str, Any]]    # 搜索结果
    expanded_queries: List[str]             # 扩展查询
    flag: bool                              # 权限标志

# ============================================================================
# 用户意图识别和搜索智能体
# ============================================================================

class IntentRecognitionAgent:
    """用户意图识别和智能搜索智能体

    功能流程：
    1. 用户意图识别和query分析
    2. 基于意图进行双引擎搜索（Milvus + Elasticsearch）
    3. 语义实体扩展和额外搜索
    4. 结果合并和返回
    """

    def __init__(self):
        self.llm = llm  # 使用配置的大模型
        self.search_obj = ControlSearch()  # 统一搜索控制器

    def simple_tool_judgment(self, query: str, intent_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """基于关键词的简单工具判断

        Args:
            query: 用户查询
            intent_analysis: 意图分析结果

        Returns:
            工具判断结果
        """
        query_lower = query.lower()
        keywords = intent_analysis.get("keywords", [])

        # 文件统计相关的关键词
        file_stats_keywords = ["多少", "几个", "数量", "统计", "总数", "总共", "count", "number"]
        # 文件列表相关的关键词
        file_list_keywords = ["列出", "列表", "清单", "有哪些", "显示", "查看", "list", "show"]
        # 文件摘要相关的关键词 (这些关键词出现时通常不应该使用工具，因为需要具体内容)
        file_content_keywords = ["内容", "摘要", "总结", "分析", "解释", "content", "summary", "analyze"]

        # 检查是否包含文件内容相关的关键词，如果有则不使用工具
        for keyword in file_content_keywords:
            if keyword in query_lower:
                return {
                    "can_answer_directly": False,
                    "tool_to_use": "none",
                    "tool_params": {},
                    "reasoning": f"查询包含内容分析关键词'{keyword}'，需要搜索而不是直接使用工具"
                }

        # 检查文件统计关键词
        for keyword in file_stats_keywords:
            if keyword in query_lower or any(k.lower() == keyword for k in keywords):
                return {
                    "can_answer_directly": True,
                    "tool_to_use": "file_statistics",
                    "tool_params": {},
                    "reasoning": f"检测到统计相关关键词'{keyword}'，建议使用file_statistics工具"
                }

        # 检查文件列表关键词
        for keyword in file_list_keywords:
            if keyword in query_lower or any(k.lower() == keyword for k in keywords):
                return {
                    "can_answer_directly": True,
                    "tool_to_use": "file_list",
                    "tool_params": {},
                    "reasoning": f"检测到列表相关关键词'{keyword}'，建议使用file_list工具"
                }

        # 检查是否询问特定文件
        # 如果查询中包含文件名相关的模式，可能需要file_summary
        # 但这个比较复杂，暂时交给LLM判断

        return {
            "can_answer_directly": False,
            "tool_to_use": "none",
            "tool_params": {},
            "reasoning": "未检测到明确的工具使用关键词"
        }

    def can_answer_with_tools(self, query: str, intent_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """判断是否可以通过工具直接回答问题

        Args:
            query: 用户查询
            intent_analysis: 意图分析结果

        Returns:
            包含是否能回答和工具结果的字典
        """
        try:
            # 分析查询是否可以直接通过工具回答（基于语义理解）
            analysis_prompt = ChatPromptTemplate.from_template(
                """你是一个智能助手，需要通过**语义理解**来判断用户查询是否可以通过特定工具直接回答。

**重要原则：**
- 必须通过理解用户查询的**真实意图和语义**来判断，而不是简单的关键词匹配
- 仔细分析用户问题的核心诉求，判断是否真的只需要工具提供的信息就能回答
- 如果用户问题涉及文件内容分析、知识检索、信息提取等，则不应该使用工具

**可用工具详细说明：**

1. **file_statistics** - 获取知识库的文件统计信息
   - **语义特征**：用户询问的是知识库的**文件数量统计**，不涉及文件内容
   - **适用场景**：询问"有多少文件"、"文件总数"、"文件数量统计"等纯数量问题
   - **不适用场景**：虽然包含"多少"、"统计"等词，但实际是在询问文件内容、质量、类型等需要搜索的问题
   - 示例查询（适用）："知识库有多少文件？", "文件总数是多少？", "统计一下文件数量"
   - 示例查询（不适用）："统计一下文件中的关键信息", "有多少文件提到了XXX", "文件内容统计"
   - 参数：{{"knowledge_id": "知识库ID"}}

2. **file_list** - 获取知识库的完整文件列表
   - **语义特征**：用户想查看知识库包含的**文件名称列表**，不涉及文件内容
   - **适用场景**：询问"有哪些文件"、"文件清单"、"列出文件"等纯列表问题
   - **不适用场景**：虽然包含"列出"、"有哪些"等词，但实际是在询问文件内容、文件中的信息等需要搜索的问题
   - 示例查询（适用）："列出所有文件", "知识库有哪些文件？", "显示文件列表", "文件清单"
   - 示例查询（不适用）："列出包含XXX的文件", "有哪些文件提到了YYY", "列出文件中的关键信息"
   - 参数：{{"knowledge_id": "知识库ID"}}

3. **file_summary** - 获取特定文件的详细信息和摘要
   - **语义特征**：用户询问的是**已知文件名**的元数据信息（如创建时间、大小等），而不是文件的具体内容
   - **适用场景**：用户明确提到文件名，且询问的是文件的基本信息、元数据
   - **不适用场景**：询问文件内容、文件中的具体信息、需要搜索文件内容的问题
   - 示例查询（适用）："文件XXX的基本信息是什么？", "XXX文件的元数据", "XXX文件什么时候创建的？"
   - 示例查询（不适用）："文件XXX的内容是什么？", "XXX文件讲了什么？", "总结XXX文件的内容"
   - 参数：{{"file_name": "具体的文件名"}}

**用户查询：** {query}

**意图分析：**
- 主要意图：{main_intent}
- 查询类型：{query_type}
- 关键词：{keywords}

**语义理解判断规则：**
1. **仔细分析用户真实意图**：
   - 用户是在询问文件/知识库的元数据（数量、列表、基本信息）？
   - 还是需要搜索、分析、提取文件内容中的信息？

2. **区分工具适用场景**：
   - ✅ 适用：纯元数据查询（文件数量、文件列表、文件基本信息）
   - ❌ 不适用：内容查询（文件内容、文件中的信息、需要搜索的问题）

3. **常见误判情况**：
   - 包含"统计"但实际是"统计文件内容" → 不使用工具
   - 包含"列出"但实际是"列出文件中的信息" → 不使用工具
   - 包含"多少"但实际是"文件中有多少相关信息" → 不使用工具

**请基于语义理解进行判断：**
1. 深入理解用户查询的真实意图
2. 判断是否可以通过上述工具直接回答问题 (can_answer_directly)
3. 如果可以，具体使用哪个工具 (tool_to_use)
4. 工具的参数是什么 (tool_params)
5. 提供详细的语义理解判断理由 (reasoning)

**返回JSON格式：**
{{
    "can_answer_directly": true/false,
    "tool_to_use": "file_statistics/file_list/file_summary/none",
    "tool_params": {{"knowledge_id": "xxx"}} 或 {{"file_name": "xxx"}},
    "reasoning": "基于语义理解的详细判断理由，说明为什么适用或不适用工具"
}}"""
            )

            try:
                chain = analysis_prompt | self.llm | JsonOutputParser()
                analysis_result = chain.invoke({
                    "query": query,
                    "main_intent": intent_analysis.get("main_intent", ""),
                    "query_type": intent_analysis.get("query_type", ""),
                    "keywords": intent_analysis.get("keywords", [])
                })
                return analysis_result
            except Exception as json_error:
                print(f"❌ JSON解析失败: {json_error}")
                # 返回保守的默认值
                return {
                    "can_answer_directly": False,
                    "tool_to_use": "none",
                    "tool_params": {},
                    "reasoning": f"JSON解析失败，使用默认分析: {str(json_error)}"
                }

        except Exception as e:
            print(f"❌ 工具判断失败: {e}")
            return {
                "can_answer_directly": False,
                "tool_to_use": "none",
                "tool_params": {},
                "reasoning": f"分析失败: {str(e)}"
            }

    def execute_tool(self, tool_name: str, tool_params: Dict[str, Any]) -> Dict[str, Any]:
        """执行指定的工具

        Args:
            tool_name: 工具名称
            tool_params: 工具参数

        Returns:
            工具执行结果
        """
        try:
            if tool_name == "file_statistics":
                knowledge_id = tool_params.get("knowledge_id", "")
                return file_statistics_impl(knowledge_id)
            elif tool_name == "file_list":
                knowledge_id = tool_params.get("knowledge_id", "")
                return file_list_impl(knowledge_id)
            elif tool_name == "file_summary":
                file_name = tool_params.get("file_name", "")
                return file_summary_impl(file_name)
            else:
                return {"error": f"未知工具: {tool_name}", "tool_result": False}

        except Exception as e:
            print(f"❌ 工具执行失败: {e}")
            return {"error": f"工具执行失败: {str(e)}", "tool_result": False}

    def _convert_enhanced_intent_to_search_intent(self, enhanced_intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """将增强的意图识别结果转换为搜索所需的意图分析格式
        
        Args:
            enhanced_intent_result: 增强的意图识别结果（来自 EnhancedIntentAgent）
            query: 原始查询
            
        Returns:
            搜索所需的意图分析格式
        """
        # 提取语义提纯后的查询
        semantic_purified_query = enhanced_intent_result.get("semantic_purified_query", query)
        core_intent = enhanced_intent_result.get("core_intent", "")
        entities = enhanced_intent_result.get("entities", [])
        relationships = enhanced_intent_result.get("relationships", [])
        
        # 构建搜索所需的意图分析格式
        intent_analysis = {
            "main_intent": core_intent or semantic_purified_query or query,
            "query_type": "factual",  # 默认类型，可以根据需要调整
            "keywords": entities + [semantic_purified_query] if semantic_purified_query != query else entities,
            "entities": entities,
            "relationships": relationships,
            "search_strategy": "基于语义提纯的智能搜索",
            "complexity": "medium",  # 默认复杂度
            # 保留增强意图识别的其他信息
            "semantic_purified_query": semantic_purified_query,
            "core_intent": core_intent,
            "attributes": enhanced_intent_result.get("attributes", []),
            "mathematical_logic": enhanced_intent_result.get("mathematical_logic", []),
            "logical_relations": enhanced_intent_result.get("logical_relations", []),
            "set_theory_relations": enhanced_intent_result.get("set_theory_relations", []),
            "relational_algebra": enhanced_intent_result.get("relational_algebra", []),
            "graph_theory_relations": enhanced_intent_result.get("graph_theory_relations", []),
        }
        
        return intent_analysis
    
    def analyze_intent(self, query: str) -> Dict[str, Any]:
        """分析用户意图和query拆解

        Args:
            query: 用户查询

        Returns:
            意图分析结果
        """
        prompt = ChatPromptTemplate.from_template(
            """你是一个专业的需求分析专家。请对用户的查询进行深入分析。

用户查询：{query}

请从以下维度进行分析并严格按照JSON格式返回结果：
1. 主要意图 (main_intent)：用户想要做什么
2. 查询类型 (query_type)：factual(事实), explanatory(解释), comparative(比较), procedural(过程)
3. 关键词列表 (keywords)：重要的关键词
4. 可能的实体 (entities)：人名、地名、组织名、技术名词等（如果没有则为空数组）
5. 搜索策略建议 (search_strategy)：需要什么类型的搜索
6. 复杂度评估 (complexity)：simple, medium, complex

重要：请确保返回有效的JSON格式，不要添加多余的字段或值。

返回格式示例：
{{
    "main_intent": "获取知识库文件数量",
    "query_type": "factual",
    "keywords": ["知识库", "文件", "数量"],
    "entities": [],
    "search_strategy": "查询元数据",
    "complexity": "simple"
}}"""
        )

        try:
            chain = prompt | self.llm | JsonOutputParser()
            result = chain.invoke({"query": query})
            return result
        except Exception as e:
            print(f"❌ JSON解析失败: {e}")
            # 返回默认分析结果
            return {
                "main_intent": f"分析查询：{query}",
                "query_type": "factual",
                "keywords": [query.split()[0] if query.split() else "查询"],
                "entities": [],
                "search_strategy": "通用搜索",
                "complexity": "medium"
            }

    def expand_entities(self, intent_analysis: Dict[str, Any], num_expansions: int = 3) -> List[str]:
        """基于意图分析进行语义实体扩展

        Args:
            intent_analysis: 意图分析结果
            num_expansions: 扩展查询数量

        Returns:
            扩展查询列表
        """
        entities = intent_analysis.get("entities", [])
        keywords = intent_analysis.get("keywords", [])
        query_type = intent_analysis.get("query_type", "factual")

        prompt = ChatPromptTemplate.from_template(
            """基于用户的意图分析，进行语义实体扩展，生成多个相关的搜索查询。
            
原始意图分析：
- 主要意图：{main_intent}
- 查询类型：{query_type}
- 关键词：{keywords}
- 实体：{entities}
- 搜索策略：{search_strategy}
- 复杂度：{complexity}

请生成{num_expansions}个不同的扩展查询，这些查询应该：
1. 包含语义相关的实体和关键词
2. 覆盖不同的搜索角度
3. 适合双引擎搜索（Milvus + Elasticsearch）
4. 每个查询都以字符串形式返回

返回JSON格式：
{{
    "expanded_queries": [
        "扩展查询1",
        "扩展查询2",
        "扩展查询3"
    ]
}}"""
        )

        chain = prompt | self.llm | JsonOutputParser()
        result = chain.invoke({
            "main_intent": intent_analysis.get("main_intent", ""),
            "query_type": query_type,
            "keywords": keywords,
            "entities": entities,
            "search_strategy": intent_analysis.get("search_strategy", ""),
            "complexity": intent_analysis.get("complexity", "medium"),
            "num_expansions": num_expansions
        })

        return result.get("expanded_queries", [])

    def search_milvus(self, state: IntentSearchState, query_text: str) -> List[Dict[str, Any]]:
        """在Milvus中搜索相关内容（代理方法，实际实现在 control_search.py）

        Args:
            state: 智能体状态
            query_text: 搜索查询文本

        Returns:
            搜索结果列表
        """
        param = {
            "query": query_text,
            "knowledge_id": state["knowledge_id"],
            "user_id": state.get("user_id", ""),
            "top_k": 10
        }
        return self.search_obj.search_milvus_formatted(param)

    def search_elasticsearch(self, state: IntentSearchState, query_text: str) -> List[Dict[str, Any]]:
        """在Elasticsearch中搜索相关内容（代理方法，实际实现在 control_search.py）

        Args:
            state: 智能体状态
            query_text: 搜索查询文本

        Returns:
            搜索结果列表
        """
        param = {
            "query": query_text,
            "knowledge_id": state["knowledge_id"],
            "user_id": state.get("user_id", ""),
            "flag": state["flag"],
            "size": 10
        }
        return self.search_obj.query_elasticsearch(param)

    def search_graph_data(self, state: IntentSearchState, query_text: str) -> List[Dict[str, Any]]:
        """在图数据中搜索相关内容（代理方法，实际实现在 control_search.py）

        Args:
            state: 智能体状态
            query_text: 搜索查询文本

        Returns:
            图数据搜索结果列表
        """
        param = {
            "query": query_text,
            "knowledge_id": state["knowledge_id"],
            "user_id": state.get("user_id", "")
        }
        return self.search_obj.search_graph_data(param)

    def search_triple_engines_with_graph(self, state: IntentSearchState, query_text: str) -> List[Dict[str, Any]]:
        """同时使用 Milvus、Elasticsearch、图数据和CSV/Excel进行四引擎搜索

        Args:
            state: 智能体状态
            query_text: 搜索查询文本

        Returns:
            合并的搜索结果列表
        """
        try:
            print("🔍 执行四引擎并行搜索（Milvus + Elasticsearch + Graph + CSV/Excel）...")

            # 使用 ThreadPoolExecutor 并行执行四个搜索引擎
            with ThreadPoolExecutor(max_workers=4) as executor:
                milvus_future = executor.submit(self.search_milvus, state, query_text)
                elastic_future = executor.submit(self.search_elasticsearch, state, query_text)
                graph_future = executor.submit(self.search_graph_data, state, query_text)
                csv_excel_future = executor.submit(self.search_csv_excel_data, state, query_text)

                # 等待结果
                milvus_results = milvus_future.result()
                elastic_results = elastic_future.result()
                graph_results = graph_future.result()
                csv_excel_results = csv_excel_future.result()

            # 合并结果
            combined_results = milvus_results + elastic_results + graph_results + csv_excel_results

            # 统一得分处理
            for result in combined_results:
                if result.get("search_engine") == "elasticsearch":
                    result["combined_score"] = result.get("_score", 0) * 10  # 文本搜索权重最高
                elif result.get("search_engine") == "graph_data":
                    result["combined_score"] = result.get("score", 0) * 12  # 图数据权重最高，因为包含关系信息
                elif result.get("search_engine") == "csv_excel":
                    result["combined_score"] = result.get("score", 0) * 15  # CSV/Excel表格数据权重最高
                else:
                    result["combined_score"] = result.get("score", 0)  # Milvus保持原权重

            # 按组合得分排序
            combined_results.sort(key=lambda x: x.get("combined_score", 0), reverse=True)

            # 限制结果数量
            max_results = 15  # 增加结果数量以适应四引擎
            combined_results = combined_results[:max_results]

            print(f"✅ 四引擎搜索完成，获得 {len(combined_results)} 个结果")
            print(f"   - Milvus: {len(milvus_results)} 个结果")
            print(f"   - Elasticsearch: {len(elastic_results)} 个结果")
            print(f"   - 图数据: {len(graph_results)} 个结果")
            print(f"   - CSV/Excel: {len(csv_excel_results)} 个结果")

            return combined_results

        except Exception as e:
            print(f"❌ 四引擎搜索失败: {e}，回退到三引擎搜索")
            # 回退到三引擎搜索
            try:
                with ThreadPoolExecutor(max_workers=3) as executor:
                    milvus_future = executor.submit(self.search_milvus, state, query_text)
                    elastic_future = executor.submit(self.search_elasticsearch, state, query_text)
                    graph_future = executor.submit(self.search_graph_data, state, query_text)

                    milvus_results = milvus_future.result()
                    elastic_results = elastic_future.result()
                    graph_results = graph_future.result()

                combined_results = milvus_results + elastic_results + graph_results
                for result in combined_results:
                    if result.get("search_engine") == "elasticsearch":
                        result["combined_score"] = result.get("_score", 0) * 10
                    elif result.get("search_engine") == "graph_data":
                        result["combined_score"] = result.get("score", 0) * 12
                    else:
                        result["combined_score"] = result.get("score", 0)

                combined_results.sort(key=lambda x: x.get("combined_score", 0), reverse=True)
                return combined_results[:30]

            except Exception as fallback_e:
                print(f"❌ 回退搜索也失败: {fallback_e}，使用Milvus单引擎")
                return self.search_milvus(state, query_text)

    def search_csv_excel_data(self, state: IntentSearchState, query_text: str) -> List[Dict[str, Any]]:
        """在CSV/Excel表格数据中进行智能问数查询（第四数据源）
        
        通过智能问数智能体流程：
        1. 查找 file/file_id 目录下的目录文件（_catalog.md）和 SQLite 数据库（_data.db）
        2. 意图分析智能体：分析用户问题 + 目录内容，找到对应的 SQLite 表
        3. SQL 生成智能体：根据列描述生成 SQL、语法检查、校验、修改
        4. 运行 SQL 查询
        5. 数据分析智能体：对文本数据统计，对数值数据基础分析

        Args:
            state: 智能体状态
            query_text: 搜索查询文本

        Returns:
            CSV/Excel搜索结果列表，包含表格数据和分析结果
        """
        import os
        from pathlib import Path
        
        results = []
        
        try:
            knowledge_id = state.get("knowledge_id", "")
            if not knowledge_id:
                return results
            
            # 获取知识库下的所有文件
            files = cSingleSqlite.search_file_by_knowledge_id(knowledge_id)
            if not files:
                return results
            
            processed_files = set()
            
            for file_info in files:
                file_id = file_info.get("file_id", "")
                file_name = file_info.get("file_name", "")
                
                if not file_id or file_id in processed_files:
                    continue
                
                # 检查文件类型
                file_ext = Path(file_name).suffix.lower() if file_name else ""
                if file_ext not in [".csv", ".xlsx", ".xls"]:
                    continue
                
                processed_files.add(file_id)
                
                # 构建文件目录路径
                file_dir = os.path.join("conf", "file", file_id)
                if not os.path.exists(file_dir):
                    continue
                
                # 使用智能问数智能体进行查询
                smart_query_result = self._smart_table_query(file_dir, file_id, file_name, query_text)
                if smart_query_result:
                    results.append(smart_query_result)
            
            print(f"📊 智能问数查询完成: {len(results)} 个结果")
            
        except Exception as e:
            print(f"⚠️ 智能问数查询失败: {e}")
            
        return results
    
    def _smart_table_query(self, file_dir: str, file_id: str, file_name: str, query: str) -> Optional[Dict[str, Any]]:
        """智能问数智能体主流程
        
        Args:
            file_dir: 文件目录路径（file/file_id）
            file_id: 文件ID
            file_name: 文件名
            query: 用户查询问题
            
        Returns:
            智能问数结果，包含SQL查询结果和数据分析
        """
        import os
        import glob
        
        try:
            # 步骤1: 查找目录文件和 SQLite 数据库
            catalog_files = glob.glob(os.path.join(file_dir, "*_catalog.md"))
            sqlite_files = glob.glob(os.path.join(file_dir, "*_data.db"))
            
            if not sqlite_files:
                print(f"⚠️ 未找到 SQLite 数据库: {file_dir}")
                return None
            
            sqlite_path = sqlite_files[0]  # 使用第一个找到的数据库
            
            # 读取目录文件内容（用于意图分析）
            catalog_content = ""
            if catalog_files:
                try:
                    with open(catalog_files[0], "r", encoding="utf-8") as f:
                        catalog_content = f.read()
                except Exception:
                    pass
            
            # 步骤2: 意图分析智能体 - 分析用户问题，找到对应表
            intent_result = self._analyze_table_intent(sqlite_path, catalog_content, query)
            if not intent_result:
                return None
            
            target_table = intent_result.get("target_table", "")
            column_descriptions = intent_result.get("column_descriptions", [])
            
            # 步骤3: SQL 生成智能体 - 生成、检查、校验 SQL
            sql_result = self._generate_and_validate_sql(
                sqlite_path, target_table, column_descriptions, query
            )
            if not sql_result or not sql_result.get("sql"):
                return None
            
            # 步骤4: 运行 SQL 查询
            query_result = self._execute_sql_query(sqlite_path, sql_result.get("sql"))
            if not query_result:
                return None
            
            # 步骤5: 数据分析智能体 - 对结果进行分析
            analysis_result = self._analyze_query_result(query_result, query)
            
            # 构建最终结果
            result = {
                "title": f"📊 智能问数: {file_name}",
                "content": analysis_result.get("summary", ""),
                "score": 15,  # 高权重
                "source": sqlite_path,
                "search_engine": "smart_table_query",
                "file_id": file_id,
                "file_name": file_name,
                "is_table_data": True,
                "table_data": {
                    "headers": query_result.get("headers", []),
                    "rows": query_result.get("rows", []),
                    "total_rows": len(query_result.get("rows", [])),
                    "total_columns": len(query_result.get("headers", [])),
                    "markdown_table": self._generate_markdown_table(
                        query_result.get("headers", []),
                        query_result.get("rows", [])
                    )
                },
                "metadata": {
                    "analysis_type": "smart_table_query",
                    "query": query,
                    "target_table": target_table,
                    "generated_sql": sql_result.get("sql", ""),
                    "intent_analysis": intent_result,
                    "data_analysis": analysis_result
                }
            }
            
            return result
            
        except Exception as e:
            print(f"⚠️ 智能问数失败 ({file_name}): {e}")
            return None
    
    def _analyze_table_intent(self, sqlite_path: str, catalog_content: str, query: str) -> Optional[Dict[str, Any]]:
        """意图分析智能体：分析用户问题，找到对应的 SQLite 表
        
        Args:
            sqlite_path: SQLite 数据库路径
            catalog_content: 目录文件内容
            query: 用户查询问题
            
        Returns:
            意图分析结果，包含目标表和列描述
        """
        import sqlite3
        import json
        
        try:
            conn = sqlite3.connect(sqlite_path)
            cursor = conn.cursor()
            
            # 获取所有表的元数据
            cursor.execute("SELECT table_name, sheet_name, description FROM _table_metadata")
            tables = cursor.fetchall()
            
            # 获取所有列的元数据
            cursor.execute("SELECT table_name, column_name, description, sample_values FROM _column_metadata")
            columns = cursor.fetchall()
            
            conn.close()
            
            if not tables:
                return None
            
            # 构建表和列信息
            table_info = {}
            for table_name, sheet_name, description in tables:
                table_info[table_name] = {
                    "sheet_name": sheet_name,
                    "description": description,
                    "columns": []
                }
            
            for table_name, column_name, description, sample_values in columns:
                if table_name in table_info:
                    table_info[table_name]["columns"].append({
                        "name": column_name,
                        "description": description,
                        "sample_values": sample_values
                    })
            
            # 使用 LLM 进行意图分析
            from Config.llm_config import get_chat_tongyi
            
            llm = get_chat_tongyi(temperature=0.1, streaming=False, enable_thinking=False)
            
            prompt = f"""你是一个数据分析意图识别专家。根据用户的问题和可用的表格信息，分析用户想查询哪个表。

## 用户问题
{query}

## 可用表格信息
{json.dumps(table_info, ensure_ascii=False, indent=2)}

## 目录信息（如有）
{catalog_content if catalog_content else "无"}

## 输出要求
请分析用户意图，返回 JSON 格式：
```json
{{
    "target_table": "最相关的表名",
    "confidence": 0.9,
    "reason": "选择该表的原因",
    "relevant_columns": ["与查询相关的列名列表"]
}}
```

只返回 JSON，不要其他内容。"""

            response = llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 解析 JSON 响应
            import re
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                intent_data = json.loads(json_match.group())
                target_table = intent_data.get("target_table", "")
                
                if target_table and target_table in table_info:
                    return {
                        "target_table": target_table,
                        "confidence": intent_data.get("confidence", 0.5),
                        "reason": intent_data.get("reason", ""),
                        "relevant_columns": intent_data.get("relevant_columns", []),
                        "column_descriptions": table_info[target_table]["columns"]
                    }
            
            # 如果 LLM 分析失败，使用第一个表
            first_table = list(table_info.keys())[0]
            return {
                "target_table": first_table,
                "confidence": 0.3,
                "reason": "默认选择第一个表",
                "relevant_columns": [],
                "column_descriptions": table_info[first_table]["columns"]
            }
            
        except Exception as e:
            print(f"⚠️ 意图分析失败: {e}")
            return None
    
    def _generate_and_validate_sql(self, sqlite_path: str, table_name: str, 
                                    column_descriptions: List[Dict], query: str) -> Optional[Dict[str, Any]]:
        """SQL 生成智能体：生成 SQL、语法检查、校验、修改
        
        Args:
            sqlite_path: SQLite 数据库路径
            table_name: 目标表名
            column_descriptions: 列描述信息
            query: 用户查询问题
            
        Returns:
            SQL 生成结果，包含最终 SQL 语句
        """
        import sqlite3
        import json
        
        try:
            from Config.llm_config import get_chat_tongyi
            
            llm = get_chat_tongyi(temperature=0.1, streaming=False, enable_thinking=False)
            
            # 构建列信息
            columns_info = "\n".join([
                f"- {col['name']}: {col.get('description', '无描述')}"
                for col in column_descriptions
            ])
            
            prompt = f"""你是一个 SQLite SQL 生成专家。根据用户问题生成 SQL 查询语句。

## 用户问题
{query}

## 目标表
表名: {table_name}

## 列信息
{columns_info}

## 要求
1. 生成符合 SQLite 语法的 SQL
2. 只返回 SELECT 查询语句，禁止 INSERT/UPDATE/DELETE
3. 如果是统计类问题，使用 COUNT/SUM/AVG/MAX/MIN 等聚合函数
4. 如果是筛选问题，使用 WHERE 条件
5. 限制返回行数不超过 100 行（使用 LIMIT）

## 输出格式
```json
{{
    "sql": "SELECT ... FROM {table_name} ...",
    "explanation": "SQL 解释"
}}
```

只返回 JSON，不要其他内容。"""

            response = llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 解析 JSON 响应
            import re
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                sql_data = json.loads(json_match.group())
                sql = sql_data.get("sql", "")
                
                if sql:
                    # 语法检查和校验
                    validated_sql = self._validate_sql(sqlite_path, sql, table_name)
                    if validated_sql:
                        return {
                            "sql": validated_sql,
                            "original_sql": sql,
                            "explanation": sql_data.get("explanation", ""),
                            "validated": True
                        }
            
            # 如果生成失败，返回简单的全表查询
            fallback_sql = f'SELECT * FROM "{table_name}" LIMIT 50'
            return {
                "sql": fallback_sql,
                "original_sql": fallback_sql,
                "explanation": "使用默认全表查询",
                "validated": False
            }
            
        except Exception as e:
            print(f"⚠️ SQL 生成失败: {e}")
            return None
    
    def _validate_sql(self, sqlite_path: str, sql: str, table_name: str) -> Optional[str]:
        """校验和修正 SQL 语句
        
        Args:
            sqlite_path: SQLite 数据库路径
            sql: 待校验的 SQL
            table_name: 目标表名
            
        Returns:
            校验后的 SQL，失败返回 None
        """
        import sqlite3
        
        try:
            # 安全检查：只允许 SELECT
            sql_upper = sql.upper().strip()
            if not sql_upper.startswith("SELECT"):
                return None
            
            # 禁止危险操作
            dangerous_keywords = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE"]
            for keyword in dangerous_keywords:
                if keyword in sql_upper:
                    return None
            
            # 确保有 LIMIT 限制
            if "LIMIT" not in sql_upper:
                sql = sql.rstrip(";") + " LIMIT 100"
            
            # 尝试执行 EXPLAIN 检查语法
            conn = sqlite3.connect(sqlite_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute(f"EXPLAIN {sql}")
                conn.close()
                return sql
            except sqlite3.OperationalError as e:
                conn.close()
                print(f"⚠️ SQL 语法错误: {e}")
                # 返回简单的全表查询作为回退
                return f'SELECT * FROM "{table_name}" LIMIT 50'
                
        except Exception as e:
            print(f"⚠️ SQL 校验失败: {e}")
            return None
    
    def _execute_sql_query(self, sqlite_path: str, sql: str) -> Optional[Dict[str, Any]]:
        """执行 SQL 查询
        
        Args:
            sqlite_path: SQLite 数据库路径
            sql: SQL 查询语句
            
        Returns:
            查询结果，包含 headers 和 rows
        """
        import sqlite3
        
        try:
            conn = sqlite3.connect(sqlite_path)
            cursor = conn.cursor()
            
            cursor.execute(sql)
            
            # 获取列名
            headers = [description[0] for description in cursor.description]
            
            # 获取数据
            rows = cursor.fetchall()
            
            conn.close()
            
            # 转换为字符串列表
            rows = [[str(cell) if cell is not None else "" for cell in row] for row in rows]
            
            return {
                "headers": headers,
                "rows": rows,
                "row_count": len(rows),
                "sql": sql
            }
            
        except Exception as e:
            print(f"⚠️ SQL 执行失败: {e}")
            return None
    
    def _analyze_query_result(self, query_result: Dict[str, Any], original_query: str) -> Dict[str, Any]:
        """数据分析智能体：对查询结果进行分析
        
        对文本数据进行统计，对数值数据进行基础分析。
        
        Args:
            query_result: SQL 查询结果
            original_query: 原始用户查询
            
        Returns:
            分析结果
        """
        try:
            headers = query_result.get("headers", [])
            rows = query_result.get("rows", [])
            
            if not headers or not rows:
                return {"summary": "查询结果为空", "statistics": {}}
            
            analysis = {
                "summary": "",
                "statistics": {},
                "text_analysis": {},
                "numeric_analysis": {}
            }
            
            # 对每列进行分析
            for col_idx, header in enumerate(headers):
                col_values = [row[col_idx] for row in rows if col_idx < len(row)]
                
                # 尝试转换为数值
                numeric_values = []
                text_values = []
                
                for val in col_values:
                    if val and val != "":
                        try:
                            numeric_values.append(float(val))
                        except ValueError:
                            text_values.append(str(val))
                
                # 数值列分析
                if numeric_values and len(numeric_values) > len(text_values):
                    analysis["numeric_analysis"][header] = {
                        "count": len(numeric_values),
                        "sum": round(sum(numeric_values), 2),
                        "avg": round(sum(numeric_values) / len(numeric_values), 2),
                        "min": round(min(numeric_values), 2),
                        "max": round(max(numeric_values), 2)
                    }
                # 文本列分析
                elif text_values:
                    value_counts = {}
                    for v in text_values:
                        value_counts[v] = value_counts.get(v, 0) + 1
                    
                    # 取前5个最常见的值
                    top_values = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                    
                    analysis["text_analysis"][header] = {
                        "unique_count": len(value_counts),
                        "total_count": len(text_values),
                        "top_values": dict(top_values)
                    }
            
            # 生成摘要
            summary_parts = [f"查询返回 {len(rows)} 行数据"]
            
            if analysis["numeric_analysis"]:
                for col, stats in analysis["numeric_analysis"].items():
                    summary_parts.append(f"{col}: 平均值={stats['avg']}, 总和={stats['sum']}, 范围=[{stats['min']}, {stats['max']}]")
            
            if analysis["text_analysis"]:
                for col, stats in analysis["text_analysis"].items():
                    summary_parts.append(f"{col}: {stats['unique_count']}个唯一值")
            
            analysis["summary"] = "；".join(summary_parts)
            analysis["statistics"] = {
                "row_count": len(rows),
                "column_count": len(headers)
            }
            
            return analysis
            
        except Exception as e:
            print(f"⚠️ 数据分析失败: {e}")
            return {"summary": f"数据分析出错: {e}", "statistics": {}}
    
    def _read_csv_as_table(self, csv_path: str, max_rows: int = 20) -> Dict[str, Any]:
        """读取CSV文件为表格格式数据
        
        Args:
            csv_path: CSV文件路径
            max_rows: 最大读取行数
            
        Returns:
            表格数据字典，包含headers和rows
        """
        try:
            import pandas as pd
            
            df = pd.read_csv(csv_path, nrows=max_rows, encoding="utf-8-sig")
            
            # 转换为表格格式
            headers = df.columns.tolist()
            rows = df.values.tolist()
            
            # 处理NaN值
            rows = [[("" if pd.isna(cell) else str(cell)) for cell in row] for row in rows]
            
            # 生成Markdown表格
            markdown_table = self._generate_markdown_table(headers, rows)
            
            return {
                "headers": headers,
                "rows": rows,
                "total_rows": len(rows),
                "total_columns": len(headers),
                "markdown_table": markdown_table
            }
            
        except Exception as e:
            print(f"⚠️ 读取CSV表格失败: {e}")
            return {"headers": [], "rows": [], "total_rows": 0, "total_columns": 0, "markdown_table": ""}
    
    def _generate_markdown_table(self, headers: List[str], rows: List[List[str]], max_rows: int = 10) -> str:
        """生成Markdown格式的表格
        
        Args:
            headers: 表头列表
            rows: 数据行列表
            max_rows: 最大显示行数
            
        Returns:
            Markdown格式的表格字符串
        """
        if not headers:
            return ""
        
        lines = []
        
        # 表头
        lines.append("| " + " | ".join(str(h) for h in headers) + " |")
        # 分隔线
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        # 数据行（限制显示行数）
        display_rows = rows[:max_rows]
        for row in display_rows:
            # 确保每行的列数与表头一致
            padded_row = row + [""] * (len(headers) - len(row)) if len(row) < len(headers) else row[:len(headers)]
            lines.append("| " + " | ".join(str(cell) for cell in padded_row) + " |")
        
        # 如果有更多行，添加提示
        if len(rows) > max_rows:
            lines.append(f"\n*（共 {len(rows)} 行数据，仅显示前 {max_rows} 行）*")
        
        return "\n".join(lines)

    def merge_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并和去重搜索结果

        Args:
            results: 搜索结果列表

        Returns:
            去重并排序后的结果列表
        """
        if not results:
            return []

        seen = set()
        unique_results = []

        for result in results:
            # 创建唯一标识符，基于内容和标题
            content_hash = hash((result.get("content", "") + result.get("title", "")).strip())
            if content_hash not in seen:
                seen.add(content_hash)
                unique_results.append(result)

        # 按得分排序
        unique_results.sort(key=lambda x: x.get("score", x.get("_score", 0)), reverse=True)
        return unique_results

    def search_only(self, query: str, knowledge_id: str, user_id: str = "", flag: bool = True, 
                   intent_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """纯搜索功能：只进行搜索，不进行意图识别和工具判断
        
        注意：意图识别和工具判断已在外部完成（enhanced_intent_agent 和 tool_agent）
        图数据通过三引擎搜索内部获取，无需外部传入

        Args:
            query: 用户查询
            knowledge_id: 知识库ID
            user_id: 用户ID
            flag: 权限标志
            intent_result: 意图识别结果，用于指导搜索

        Returns:
            搜索结果和意图分析
        """
        try:
            # 初始化状态
            state: IntentSearchState = {
                "question": query,
                "knowledge_id": knowledge_id,
                "user_id": user_id,
                "intent_analysis": {},
                "search_results": [],
                "expanded_queries": [],
                "flag": flag
            }

            # 步骤1: 意图整理（将传入的意图结果转换为搜索所需的格式）
            if intent_result:
                print("📋 步骤1: 整理意图识别结果用于搜索")
                # 将增强的意图识别结果转换为搜索所需的格式
                intent_analysis = self._convert_enhanced_intent_to_search_intent(intent_result, query)
                state["intent_analysis"] = intent_analysis
                print(f"✅ 意图整理完成: {intent_analysis.get('main_intent', '未知意图')}")
                print(f"✅ 语义提纯查询: {intent_result.get('semantic_purified_query', query)}")
            else:
                # 如果没有提供意图结果，创建基本的意图分析
                print("📋 步骤1: 创建基本意图分析")
                intent_analysis = {
                    "main_intent": query,
                    "query_type": "factual",
                    "keywords": query.split(),
                    "entities": [],
                    "relationships": [],
                    "search_strategy": "通用搜索",
                    "complexity": "medium",
                    "semantic_purified_query": query
                }
                state["intent_analysis"] = intent_analysis

            # 步骤2: 基于意图进行初始四引擎搜索（Milvus + Elasticsearch + Graph + CSV/Excel）
            print("🔎 步骤2: 执行初始四引擎搜索（Milvus + Elasticsearch + Graph + CSV/Excel）")
            # 如果提供了意图识别结果，优先使用语义提纯后的查询
            search_query = query
            if intent_result:
                semantic_purified_query = intent_result.get("semantic_purified_query", query)
                if semantic_purified_query and semantic_purified_query != query:
                    search_query = semantic_purified_query
                    print(f"🔍 使用语义提纯后的查询进行搜索: {search_query}")
            
            initial_results = self.search_triple_engines_with_graph(state, search_query)
            print(f"📊 初始搜索获得 {len(initial_results)} 个结果")

            # 步骤3: 基于意图分析进行扩展搜索
            print("🚀 步骤3: 执行扩展搜索")
            expanded_results = []
            expanded_queries = []
            
            # 根据意图分析的复杂度决定是否进行扩展搜索
            complexity = intent_analysis.get("complexity", "medium")
            entities = intent_analysis.get("entities", [])
            
            # 如果有实体或复杂度不是simple，进行扩展搜索
            if entities or complexity != "simple":
                try:
                    # 生成扩展查询（生成1-2个扩展查询）
                    num_expansions = 1 if complexity == "medium" else 2
                    expanded_queries = self.expand_entities(intent_analysis, num_expansions=num_expansions)
                    state["expanded_queries"] = expanded_queries
                    print(f"⚡ 生成 {len(expanded_queries)} 个扩展查询")
                    
                    # 对每个扩展查询进行三引擎搜索
                    for i, expanded_query in enumerate(expanded_queries):
                        print(f"  - 扩展搜索 {i+1}: {expanded_query[:50]}...")
                        results = self.search_triple_engines_with_graph(state, expanded_query)
                        expanded_results.extend(results)
                    
                    print(f"📈 扩展搜索获得 {len(expanded_results)} 个结果")
                except Exception as e:
                    print(f"⚠️ 扩展搜索失败: {e}，继续使用初始搜索结果")
                    expanded_queries = []
                    expanded_results = []
            else:
                print("ℹ️ 查询复杂度为simple且无实体，跳过扩展搜索")

            # 步骤4: 合并所有搜索结果
            print("🔀 步骤4: 合并搜索结果")
            all_results = initial_results + expanded_results

            # 去重和排序
            all_results = self.merge_search_results(all_results)
            print(f"🎉 最终获得 {len(all_results)} 个去重后的结果")

            return {
                "success": True,
                "intent_analysis": intent_analysis,
                "search_results": all_results,
                "initial_results_count": len(initial_results),
                "expanded_results_count": len(expanded_results),
                "total_results_count": len(all_results),
                "query": query,
                "knowledge_id": knowledge_id,
                "expanded_queries": expanded_queries
            }

        except Exception as e:
            print(f"❌ 搜索失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "knowledge_id": knowledge_id,
                "search_results": []
            }
    
    def search_with_intent(self, query: str, knowledge_id: str, user_id: str = "", flag: bool = True, 
                          graph_data: List[List[Dict[str, Any]]] = None, 
                          intent_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """基于用户意图的智能搜索（保留原方法以兼容旧代码）

        Args:
            query: 用户查询
            knowledge_id: 知识库ID
            user_id: 用户ID
            flag: 权限标志
            graph_data: 图数据，包含节点关系信息
            intent_result: 可选的意图识别结果，如果提供则使用它而不是重新分析

        Returns:
            搜索结果和意图分析
        """
        # 直接调用 search_only，因为意图识别和工具判断已在外部完成
        return self.search_only(query, knowledge_id, user_id, flag, graph_data, intent_result)

# ============================================================================
# IntentRecognitionAgent 实例化函数
# ============================================================================

def create_intent_recognition_agent() -> IntentRecognitionAgent:
    """创建用户意图识别和搜索智能体实例

    Returns:
        IntentRecognitionAgent实例
    """
    return IntentRecognitionAgent()

def run_intent_based_search(query: str, knowledge_id: str, user_id: str = "", flag: bool = True, 
                            intent_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """运行基于用户意图的智能搜索
    
    注意：此函数只进行搜索，不进行意图识别和工具判断。
    意图识别和工具判断已在外部完成（enhanced_intent_agent 和 tool_agent）。
    图数据通过三引擎搜索内部获取，无需外部传入。

    Args:
        query: 用户查询
        knowledge_id: 知识库ID
        user_id: 用户ID
        flag: 权限标志
        intent_result: 可选的意图识别结果，用于指导搜索

    Returns:
        搜索结果和意图分析
    """
    agent = create_intent_recognition_agent()
    return agent.search_only(query, knowledge_id, user_id, flag, intent_result)
