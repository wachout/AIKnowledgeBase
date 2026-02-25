import asyncio
import re
import json
from langgraph.graph import StateGraph, START, END
from Agent.ArticleThemeAgent.theme_agent import AgentState
from Agent.ArticleThemeAgent.theme_agent import preprocess_text
from Agent.ArticleThemeAgent.theme_agent import extract_title
from Agent.ArticleThemeAgent.theme_agent import extract_summary
from Agent.ArticleThemeAgent.theme_agent import extract_toc
from Agent.ArticleThemeAgent.theme_agent import extract_metadata
from Agent.ArticleThemeAgent.theme_agent import classify_doctype
from Agent.ArticleThemeAgent.theme_agent import extract_authors


# After all parallel nodes are done, end the graph
# We need a joining node to wait for all parallel tasks to complete.
# Let's add a simple collector node.
def collector_node(state: AgentState) -> AgentState:
    """
    A simple node that acts as a synchronization point for the parallel branches.
    
    Regarding state merging: LangGraph automatically merges the state updates from
    the parallel nodes. When each node updates a *different* key in the AgentState
    (e.g., one updates 'summary', another updates 'toc'), the updates are combined
    into the final state dictionary.
    
    If multiple nodes were to update the *same* key, we would need a special
    reducer function (like the `operator.add` we use for the 'error' key) to tell
    LangGraph how to combine the values.
    
    This node itself doesn't need to perform any merging logic; its purpose is
    simply to ensure that all parallel extraction tasks have completed before
    the graph proceeds to the END.
    """
    print("---(Node: Collector)---")
    print("   All extraction tasks complete. State has been merged.")
    return {}

async def run(sample_text):
    # --- 1. Define the Graph ---
    # Create a new graph
    workflow = StateGraph(AgentState)
    
    # Add the nodes to the graph
    workflow.add_node("preprocess", preprocess_text)
    workflow.add_node("extract_title", extract_title)
    workflow.add_node("extract_summary", extract_summary)
    workflow.add_node("extract_toc", extract_toc)
    workflow.add_node("extract_metadata", extract_metadata)
    workflow.add_node("classify_doctype", classify_doctype)
    workflow.add_node("extract_authors", extract_authors)
    
    # --- 2. Define the Edges ---
    # The graph starts with the preprocessing node
    workflow.add_edge(START, "preprocess")
    
    # After preprocessing, run all extraction nodes in parallel
    workflow.add_edge("preprocess", "extract_title")
    workflow.add_edge("preprocess", "extract_summary")
    workflow.add_edge("preprocess", "extract_toc")
    workflow.add_edge("preprocess", "extract_metadata")
    workflow.add_edge("preprocess", "classify_doctype")
    workflow.add_edge("preprocess", "extract_authors")
    
    workflow.add_node("collector", collector_node)
    workflow.add_edge("extract_title", "collector")
    workflow.add_edge("extract_summary", "collector")
    workflow.add_edge("extract_toc", "collector")
    workflow.add_edge("extract_metadata", "collector")
    workflow.add_edge("classify_doctype", "collector")
    workflow.add_edge("extract_authors", "collector")
    
    # The collector node transitions to the end
    workflow.add_edge("collector", END)
    
    # --- 3. Compile the Graph ---
    app = workflow.compile()
    
    initial_state = {"text": sample_text}
    
    final_state = app.invoke(initial_state)
    # return final_state  # Return the final state dictionary
    # Use json.dumps for pretty printing the dictionary
    # Ensure ensure_ascii=False to correctly display Chinese characters
    final_state_json = json.dumps(final_state, indent=2, ensure_ascii=False)
    return final_state_json

def clean_json_string(json_str: str) -> str:
    """
    清理 JSON 字符串，去除代码块标记和多余的空白
    
    Args:
        json_str: 可能包含代码块标记的 JSON 字符串
        
    Returns:
        str: 清理后的 JSON 字符串
    """
    if not json_str:
        return json_str
    
    # 去除首尾空白
    json_str = json_str.strip()
    
    # 使用正则表达式去除开头的 ```json 或 ``` 标记
    # 匹配开头的 ```json 或 ```（可能包含换行符和空白）
    json_str = re.sub(r'^```(?:json)?\s*\n?', '', json_str, flags=re.IGNORECASE | re.MULTILINE)
    
    # 使用正则表达式去除结尾的 ``` 标记（可能包含换行符和空白）
    json_str = re.sub(r'\n?\s*```\s*$', '', json_str, flags=re.MULTILINE)
    
    # 再次去除首尾空白和换行符
    json_str = json_str.strip()
    
    return json_str

def run_sync(sample_text):
    # result = asyncio.create_task(run(sample_text))
    # loop = asyncio.get_event_loop()
    # if loop.is_running():
    #     # If the event loop is already running, we need to run the async task in a different way
    #     result = loop.create_task(run(sample_text))
    # else:
    #     # If the event loop is not running, we can run the async task directly
    #     result = loop.run_until_complete(run(sample_text))   
    # print("Text length:", len(sample_text))
    # print("Result type:", type(result))
    # print("Result:", result)
    # return result  # Wait for the async task to complete and return the result
    res_j = asyncio.run(run(sample_text))
    # 清理 JSON 字符串，去除可能的代码块标记
    cleaned_json = clean_json_string(res_j)
    result = json.loads(cleaned_json)
    return result

# # --- 4. Define a Sample Input Text ---
# # A comprehensive sample document for testing
# sample_text = """
# # 城市大脑建设与运营管理标准
#
# **发布日期**: 2023-11-01
# **生效日期**: 2023-12-01
# **作废日期**: 2033-12-01
#
# **起草单位**: 未来城市研究中心
# **作者**: 张三, 李四
#
# **适用范围**: 本标准适用于中华人民共和国四川省成都市的城市大脑项目。
#
# ---
#
# ## **摘要**
#
# 本文档规定了城市大脑（City Brain）项目的建设、运营和管理的相关标准与要求，旨在确保项目的规范性、安全性和高效性。
#
# ---
#
# ## **目录**
#
# 1.  **引言**
#     1.1. 背景
#     1.2. 目的
# 2.  **核心技术要求**
#     2.1. 数据融合平台
#     2.2. AI算法引擎
#     2.3. 安全体系
# 3.  **运营管理规范**
#     3.1. 组织架构
#     3.2. 应急预案
# 4.  **附录**
#     4.1. 名词解释
#
# ---
#
# ## **1. 引言**
#
# ### **1.1. 背景**
#
# 随着信息技术的飞速发展，城市管理面临着前所未有的机遇与挑战。
#
# ### **1.2. 目的**
#
# 本标准的目的是为了统一和规范成都市城市大脑的建设与运营流程。
#
# ... (正文内容省略) ...
# """

# # --- 5. Run the Graph ---
# if __name__ == "__main__":
#     print("🚀 Starting the document analysis process...")
#
#     # The initial state for the graph
#     initial_state = {"text": sample_text}
#
#     # Invoke the graph with the initial state
#     # The `stream` method provides real-time updates from each node
#     final_state = app.invoke(initial_state)
#
#     # Print the final, structured output
#     print("\n\n✅ Document analysis complete!")
#     print("--- Final Result ---")
#
#     # Use json.dumps for pretty printing the dictionary
#     # Ensure ensure_ascii=False to correctly display Chinese characters
#     final_state_json = json.dumps(final_state, indent=2, ensure_ascii=False)
#     print(final_state_json)
#
#     # You can also access individual keys
#     # print("\n--- Extracted Summary ---")
#     # print(final_state.get('summary'))
