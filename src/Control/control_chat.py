# -*- coding:utf-8 -*-

import os
import re
import json
import csv
import time
import logging
import copy
import uuid
import threading
import queue
import traceback
from typing import Dict, Any
from datetime import datetime

from bs4 import BeautifulSoup

from langchain_community.document_loaders import DirectoryLoader
from langchain_community.document_loaders import UnstructuredFileLoader

# from langchain_text_splitters import RecursiveCharacterTextSplitter

# from langchain_core.documents import Document

# from pbox import CodeSandBox  # 暂时注释掉，避免socket错误

from Control.control_milvus import CControl as ControlMilvus
from Control.control_file import CControl as CFileControl
from Control.control_graph import CControl as ControlGraph
from Control.control_search import CControl as ControlSearch
# from Control.control_graphiti import CControl as ControlGraphiti
# from Graphrag.light_rag import run as graph_run

# from Agent import article_theme_run
from Agent import entity_relation_split_run
# from Agent import text_to_cypher_run
from Agent import intent_recog_run
from Agent import file_analysis_run
# from Agent import analysis_code_run
# from Agent import report_form_code_run
from Agent import echarts_run
from Agent import agentic_rag_run
from Agent import agentic_sql_run
from Agent import agentic_query_run
from Agent import table_file_run
# from Agent.table_file_run import run_table_analysis_stream
# from Agent import intent_recog_sql_run
from Math.statistics import calculate_statistics
# from Agent.emb_query_run import run_agent
# table_file_run.run_table_analysis_stream
# 导入知识库数据库实例
from Db.sqlite_db import cSingleSqlite

from Config.embedding_config import get_embeddings
from Config.neo4j_config import is_neo4j_enabled
from Config.pdf_config import is_pdf_advanced_enabled
from Config.llm_config import get_chat_tongyi

# 导入圆桌讨论系统
from Roles import RoundtableDiscussion

from Utils import utils

from Control.control_sessions import CControl as ControlSessions
from Control.control_sql import CControl as ControlSql
from Control.control_discussion import DiscussionControl
# from Sql.vanna_manager import get_vanna_manager
from Sql.Graph.graph import Graph

# from pbox import CodeSandBox
# sandbox = CodeSandBox()

# 创建线程安全的logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 设置日志级别
logger_lock = threading.Lock()

def thread_safe_log(level_func, message, *args, **kwargs):
    """线程安全的日志记录函数"""
    with logger_lock:
        level_func(message, *args, **kwargs)


DOWNFILE = "conf/file"
URL_IMAGES = "http://192.168.35.125:8500/"
WORKING_DIR = "lightrag_data"

IAMGES_PATH = "/home/ubumtu/Downloads/Server/tmp_url"


class CControl():
    
    def __init__(self):
        self.file_obj = CFileControl()
        self.milvus_obj = ControlMilvus()
        self.graph_obj = ControlGraph()
        self.search_obj = ControlSearch()
        self.sess_obj = ControlSessions()
        self.sql_obj = ControlSql()
        self.discussion_obj = DiscussionControl()
    
    def content_list_to_json(self, content_list, file_id):
        _json = json.loads(content_list)
        _content = ""
        for item in _json:
            _type = item["type"]
            if(_type == "text"):
                _text = item["text"]
                _content = _content + _text+ "\n"
            elif(_type == "image"):
                if("img_path" in item.keys()):
                    url_image = URL_IMAGES + item["img_path"]
                else:
                    url_image = ""
                if("img_caption" in item.keys()):
                    img_caption = item["img_caption"]
                else:
                    img_caption = []
                if("img_footnote" in item.keys()):
                    img_footnote = item["img_footnote"]
                else:
                    img_footnote = []
                _tmpt_txt = ""
                if(img_caption):
                    _caption = "caption:\n"
                    for _cap in img_caption:
                        _caption = _caption + _cap + "\n"
                    _tmpt_txt = _tmpt_txt + _caption
                if(url_image):
                    _tmpt_txt = _tmpt_txt + "图片地址：" + url_image + "\n"
                if(img_footnote):
                    _footnote = "images footnote:\n"
                    for _foot in img_footnote:
                        _footnote = _footnote + _foot + "\n"
                    _tmpt_txt = _tmpt_txt + _footnote
                _content = _content + _tmpt_txt
                if(url_image):
                    caption = "\n".join(img_caption)
                    footnote = "\n".join(img_footnote)
                    upload_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    if(not file_id):
                        param = {"file_id":file_id, 
                                 "img_path":url_image,
                                 "caption":caption,
                                 "footnote":footnote,
                                 "upload_time":upload_time}
                        cSingleSqlite.insert_image_file(param)
                
            elif(_type == "table"):
                _tmpt_txt = ""
                if("text" in item.keys()):
                    _text = item["text"]
                    _tmpt_txt = _tmpt_txt + _text
                if("img_path" in item.keys()):
                    url_image = URL_IMAGES + item["img_path"]
                if("table_caption" in item.keys()):
                    table_caption = item["table_caption"]
                else:
                    table_caption = []
                if("table_footnote" in item.keys()):
                    table_footnote = item["table_footnote"]
                else:
                    table_footnote = []
                if(table_caption):
                    _caption = "caption:\n"
                    for _cap in table_caption:
                        _caption = _caption + _cap + "\n"
                    _tmpt_txt = _tmpt_txt + _caption
                modified_text = ""
                if("table_body" in item.keys()):
                    table_body = item["table_body"]
                    json_table = self.convert_xml_to_json(table_body)
                    modified_text = json_table["modified_text"]
                    _tmpt_txt = _tmpt_txt + "表格的Json格式：\n" + modified_text
                    _tmpt_txt = _tmpt_txt + "表格：\n" + table_body + "\n"
                    _tmpt_txt = _tmpt_txt + "表格的图片显示：\n" + url_image + "\n"
                if(table_footnote):
                    _footnote = "table footnote:\n"
                    for _foot in table_footnote:
                        _footnote = _footnote + _foot + "\n"
                    _tmpt_txt = _tmpt_txt + _footnote
                _content = _content + _tmpt_txt
                
                if(modified_text):
                    caption = "\n".join(table_caption)
                    footnote = "\n".join(table_footnote)
                    upload_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    if(not file_id):
                        param = {"file_id":file_id, 
                                 "table_data":modified_text,
                                 "caption":caption,
                                 "footnote":footnote,
                                 "upload_time":upload_time}
                        cSingleSqlite.insert_table_data(param)
                    
        return _content
    
    def load_files(self, _file):
        if(os.path.isfile(_file)):
            loader = UnstructuredFileLoader(_file)
            _loader = loader.load()
        else:
            _path = os.path.dirname(_file)
            loader = DirectoryLoader(_file)
            _loader = loader.load()
        return _loader
                    
    def convert_html_table_to_json(self, html):
        """
        Parses an HTML string, extracts the first table, and converts it to a JSON array of objects.
        The first row of the table is assumed to be the header.
        """
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table')
        if not table:
            # Return an empty list instead of a JSON string
            return []
    
        # Find all rows, then get the header from the first row
        rows = table.find_all('tr')
        if not rows:
            return []
        
        headers = [header.text.strip() for header in rows[0].find_all('td')]
        
        data = []
        # Process the rest of the rows
        for row in rows[1:]:
            cells = row.find_all('td')
            if len(cells) == len(headers):  # Ensure row is not malformed
                row_data = {headers[i]: cells[i].text.strip() for i in range(len(headers))}
                data.append(row_data)
        return data
    
    def convert_xml_to_json(self, content):
        all_tables_data = []
        
        def replacer(match):
            """
            This function is called for each <html>...</html> match.
            It converts the table to JSON, adds it to our master list,
            and returns the JSON string for replacement.
            """
            html_block = match.group(0)
            table_data = self.convert_html_table_to_json(html_block)
            if table_data:
                all_tables_data.extend(table_data)
                # Return a compact JSON string for in-place replacement
                return json.dumps(table_data, ensure_ascii=False)
            # If no table is found, return the original block
            return html_block
        
        modified_text = re.sub('<html>.*?</html>', replacer, content, flags=re.DOTALL)
        
        final_output = {
            "combined_json_tables": all_tables_data,
            "modified_text": modified_text
        }
        return final_output
    
    def query_milvus(self, param):
        """在 Milvus 中搜索向量数据（代理方法，实际实现在 control_search.py）"""
        return self.search_obj.query_milvus(param)
        
    def check_knowledge_and_user(self, knowledge_id, user_id):
        param = {"knowledge_id":knowledge_id, "user_id":user_id}
        result = cSingleSqlite.search_knowledge_base_by_id_and_user_id(param)
        return result
    
    def query_graph_neo4j(self, param, merge_result = False):
        """在 Neo4j 图数据库中搜索实体关系（代理方法，实际实现在 control_search.py）"""
        return self.search_obj.query_graph_neo4j(param, merge_result)
    
    def execute_all_query(self, param):
        query = param.get("query", "")
        if(not query or query.strip() == ""):
            return {"error_code":3, "error_msg":"Error, lack of query."}
        start_time = time.time()
        graph_data = self.query_graph_neo4j(param, merge_result=True)
        end_time = time.time()
        print(f"Graph query time: {end_time - start_time} seconds")
        
        milvus_data = self.query_milvus(param)
        end_time_2 = time.time()
        print(f"Milvus query time: {end_time_2 - end_time} seconds")
        
        result = self.search_obj.search_graph_emb(query, graph_data, milvus_data)
        
        # param = {"query":query, "graph_data":graph_data, "emb_data":milvus_data}
        # result = self.chat_obj.answer_question(param)
        
        res = {"error_code":0, "error_msg":"Success", "data": result}
        return res
    
    def chat_with_rag(self, param):
        """RAG Agentic智能体流式聊天"""
        knowledge_id = param.get("knowledge_id")
        user_id = param.get("user_id")
        flag = True
        # 检查知识库和用户权限，如果无权限，只能查询公共知识部分
        if(not self.check_knowledge_and_user(knowledge_id, user_id)):
            flag = False
        else:
            flag = True

        try:
            knowledge_id = param.get("knowledge_id")
            query = param.get("query", "")
            user_id = param.get("user_id")

            if not knowledge_id:
                yield {"error_code": 1, "error_msg": "缺少knowledge_id参数"}
                return

            if not query or query.strip() == "":
                yield {"error_code": 2, "error_msg": "查询内容不能为空"}
                return

            logger.info(f"开始RAG Agentic处理 - knowledge_id: {knowledge_id}, query: {query}")

            # 转换聊天历史格式（如果需要）
            chat_history = []  # 暂时为空，后续可以从 param 中提取
            
            # 获取流式结果，图数据通过三引擎搜索内部获取
            chunk_count = 0
            for chunk in agentic_rag_run.run_rag_agentic_stream(query, knowledge_id, user_id,
                                                                chat_history,
                                                                flag):
                chunk_count += 1
                yield chunk
            return
        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.error(f"RAG Agentic处理失败: {e}")
            logger.error(f"Traceback: {error_traceback}")

            yield {
                "error_code": 5,
                "error_msg": f"RAG Agentic处理失败: {str(e)}",
                "traceback": error_traceback
            }

    def execute_all_chat(self, param):
        
        logger.info(f"execute_all_chat called with param: {param}")
        
        query = param.get("query", "")
        logger.info(f"Extracted query: {query}")
        
        if(not query or query.strip() == ""):
            logger.warning("No query text provided")
            yield {"error_code":3, "error_msg":"Error, lack of query."}
            return
        try:
            logger.info("Calling query_graph_neo4j")
            graph_data = self.query_graph_neo4j(param, merge_result=True)
            if(graph_data):
                graph_data = copy.deepcopy(graph_data)
            logger.info(f"graph_data result: {graph_data}")
            graph_data = []
            logger.info("Calling query_milvus")
            milvus_data = self.query_milvus(param)
            logger.info(f"milvus_data result: {milvus_data}")
            
            # 直接返回流式结果
            logger.info("Calling search_obj.stream_openai_chat")
            stream_result = self.search_obj.stream_openai_chat(query, graph_data, milvus_data)
            logger.info(f"stream_openai_chat returned: {type(stream_result)}")
            
            # 确保正确yield数据
            has_data = False
            for item in stream_result:
                has_data = True
                logger.info(f"Yielding item from stream_openai_chat: {item}")
                yield item
            
            if not has_data:
                logger.warning("No data yielded from stream_openai_chat")
                yield {"message": "No data returned from chat processing"}
        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.error(f"Error in execute_all_chat: {str(e)}")
            logger.error(f"Traceback: {error_traceback}")
            yield {"error_code":5, "error_msg":f"Error processing stream query: {str(e)}", "traceback": error_traceback}

    def chat_with_discussion(self, user_id, session_id, query, file_path, chat_history=None, discussion_id=None):
        """
        圆桌讨论头脑风暴会议系统
        支持多智能体协作的深度讨论和决策
        支持状态持久化，可从断点恢复
        基于历史聊天记录智能识别用户意图，自动恢复已有会议
        
        优化版本：只返回任务创建成功信息，不流式返回中间信息。

        可选优化：第一/二/三层为不同智能体发言，可通过 AgentScope 统一消息与执行。
        安装 agentscope 后设置环境变量 USE_AGENTSCOPE=1 即可启用（见 Roles/roundtable/agentscope_bridge.py）。

        Args:
            user_id: 用户ID
            session_id: 会话ID
            query: 用户查询
            file_path: 文件路径
            chat_history: 历史聊天记录，用于意图识别
            discussion_id: 可选，指定任务ID。若传入（如前端「重启指定任务」），则沿用该ID与原文件夹，不创建新任务
        """
        # 生成唯一ID（用于创建chunk）
        _id = f"roundtable-{int(time.time())}"
        
        # 如果没有提供历史聊天记录，则自动获取
        if chat_history is None and session_id:
            chat_history = self.sess_obj.get_session_messages_by_id(session_id)

        # 使用智能体识别用户意图（四种意图）
        intent_result = self._identify_roundtable_intent(session_id, query)
        user_intent = intent_result.get('intent', 'start_new')
        target_discussion_id = intent_result.get('discussion_id')  # 可能是用户输入中提取的ID
        
        # 若调用方显式传入 discussion_id（如 API 重启指定任务），优先使用，确保用原任务ID与文件夹
        if discussion_id and str(discussion_id).strip():
            target_discussion_id = str(discussion_id).strip()
            logger.info(f"🎯 使用调用方指定的任务ID（重启指定任务）: {target_discussion_id}")
        
        logger.info(f"🎯 意图识别结果: intent={user_intent}, discussion_id={target_discussion_id}")
        
        # 意图1：其他聊天（非圆桌会议相关）
        if user_intent == 'other_chat':
            # 返回提示信息，引导用户使用圆桌会议功能
            yield self._create_chunk(_id,
                content="""💡 **圆桌会议系统提示**

您的输入看起来不是圆桌会议相关的请求。

**支持的操作：**
- 🚀 **创建新任务**: "帮我分析XX问题" / "讨论XX主题"
- 📊 **查询任务状态**: "任务进度怎么样" / "查看最新任务"
- 🔍 **查询指定任务**: "查询 discussion_xxx 的情况"

如果您想进行普通对话，请使用其他聊天模式。
""",
                chunk_type="text", finish_reason=""
            )

            time.sleep(1)
            yield self._create_chunk(_id,
                content="",
                chunk_type="text", finish_reason="stop"
            )

            return
        
        # 意图2：查询最新任务情况
        if user_intent == 'query_latest':
            # 流式返回任务信息
            yield from self._get_discussion_task_info(session_id, None)
            return
        
        # 意图3：查询指定任务情况（仅查看状态，不运行）
        if user_intent == 'query_specific' and target_discussion_id:
            # 流式返回任务信息
            yield from self._get_discussion_task_info(session_id, target_discussion_id)
            return

        # 意图5：修改指定任务中某智能体发言（需任务ID）
        if user_intent == 'modify_speech' and target_discussion_id:
            speaker = intent_result.get('speaker', '') or ''
            layer = intent_result.get('layer', 0)
            modification_content = intent_result.get('modification_content', '') or ''
            yield self._create_chunk(_id, content=f"✅ 收到修改发言请求\n\n**任务ID**: `{target_discussion_id}`\n**角色**: {speaker or '（将自动匹配）'}\n**层级**: {'第一层' if layer == 1 else '第二层' if layer == 2 else '自动'}\n正在后台执行修改并触发下游重发言…\n\n", chunk_type="text", finish_reason="")
            yield self._create_chunk(_id, content="", chunk_type="text", finish_reason="stop")
            try:
                self.discussion_obj.modify_agent_speech(
                    discussion_id=target_discussion_id,
                    speaker_name=speaker.strip() or None,
                    layer=layer if layer in (1, 2) else None,
                    user_content=modification_content.strip() or query,
                )
            except Exception as e:
                logger.error(f"修改发言执行失败: {e}", exc_info=True)
            return
        
        # 意图4：创建新任务 或 恢复/重启已有任务（resume 或 start_new 且带任务ID时用原ID）

        # 重启/恢复时沿用原任务ID与文件夹，不创建新ID
        discussion_id = target_discussion_id if target_discussion_id else f"discussion_{uuid.uuid4().hex[:8]}"
        
        # 返回任务创建成功信息
        task_type = "恢复" if target_discussion_id else "创建"
        yield self._create_chunk(_id,
            content=f"✅ 圆桌会议任务{task_type}成功\n\n"
                    f"**会议ID**: `{discussion_id}`\n"
                    f"会议已在后台异步执行。\n\n",
            chunk_type="text", finish_reason=""
        )
        
        yield self._create_chunk(_id,
            content="",
            chunk_type="text", finish_reason="stop"
        )

        logger.info(f"🚀 开始执行圆桌会议: {discussion_id} (task_type={task_type})")
        
        # 异步执行圆桌会议（不阻塞主流程）
        def run_discussion_async():
            """后台线程执行圆桌会议"""
            try:
                self.discussion_obj.chat_with_discussion(
                    user_id, session_id, query, file_path, discussion_id)
            except Exception as e:
                logger.error(f"❌ 圆桌会议执行失败: {discussion_id}, 错误: {e}")
        
        # 启动后台线程
        discussion_thread = threading.Thread(
            target=run_discussion_async,
            name=f"discussion_{discussion_id}",
            daemon=True  # 守护线程，主程序退出时自动结束
        )
        discussion_thread.start()
        logger.info(f"📤 圆桌会议已在后台线程启动: {discussion_thread.name}")
            

    def _identify_roundtable_intent(self, session_id: str, query: str) -> dict:
        """
        圆桌会议意图识别智能体
        
        通过 session_id 查询已有任务列表，结合LLM识别用户意图
        
        四种意图：
        1. start_new: 创建新任务
        2. query_latest: 咨询最新任务情况
        3. query_specific: 咨询指定任务（带任务ID）
        4. other_chat: 其他普通聊天
        
        Returns:
            dict: {'intent': 'start_new|query_latest|query_specific|other_chat', 'discussion_id': '可能的ID'}
        """
        try:
            import re
            
            # 步骤1: 提取用户输入中可能的任务ID
            id_pattern = r'(discussion_[a-f0-9]+)'
            id_match = re.search(id_pattern, query, re.IGNORECASE)
            extracted_id = id_match.group(1) if id_match else None
            
            # 步骤2: 通过 session_id 查询该会话下的所有任务
            task_summary = cSingleSqlite.count_discussion_tasks_by_session_id(session_id)
            tasks_list = task_summary.get('tasks', [])
            total_count = task_summary.get('total_count', 0)
            
            # 构建任务列表上下文（作为LLM参考）
            task_context = ""
            if tasks_list:
                task_lines = []
                for i, task in enumerate(tasks_list[:5]):  # 最多显礴5个
                    task_id = task.get('discussion_id', '')
                    status = task.get('task_status', '未知')
                    updated = task.get('updated_at', '')[:16] if task.get('updated_at') else ''
                    task_lines.append(f"  - {task_id} (状态: {status}, 更新: {updated})")
                task_context = f"""\n**当前会话已有{total_count}个任务：**
{chr(10).join(task_lines)}
"""
            else:
                task_context = "\n**当前会话暂无任务记录**\n"
            
            # 如果提取到任务ID，读取其主题信息
            specific_task_info = ""
            if extracted_id:
                topic_info = self._read_task_topic_from_file(extracted_id)
                if topic_info:
                    specific_task_info = f"\n**用户提到的任务ID {extracted_id} 的主题：**\n{topic_info}\n"
            
            # 步骤3: 使用LLM进行意图识别
            llm = get_chat_tongyi(temperature=0.1, enable_thinking=False)
            
            intent_prompt = f"""你是圆桌会议系统的意图识别智能体。请分析用户输入，判断用户意图。

**用户输入：**
{query}
{task_context}{specific_task_info}
**意图分类（严格从以下五种中选择一种）：**

1. **start_new** - 创建新任务
   - 用户想要发起新的讨论/分析/头脑风暴
   - 例如："帮我分析XX"、"讨论XX问题"、"研究一下XX"、"制定XX方案"

2. **query_latest** - 咨询最新任务
   - 用户想了解最近任务的进度或结果，但没有指定具体任务ID
   - 例如："任务进度怎么样"、"查看任务状态"、"完成了吗"、"结果是什么"

3. **query_specific** - 仅查询指定任务（只看状态，不运行）
   - 用户指定了任务ID且仅想查看该任务情况
   - 例如："查询 discussion_abc123 的情况"、"discussion_xxx 完成了吗"

4. **resume** - 恢复/重启指定任务（继续运行该任务，用原任务ID与文件夹）
   - 用户要继续运行或重启已有任务，且输入中包含任务ID
   - 例如："继续 discussion_xxx"、"重启 discussion_xxx"、"继续运行 discussion_xxx 任务"

5. **other_chat** - 其他普通聊天
   - 与圆桌会议无关的闲聊、问候、无意义输入
   - 例如："你好"、"谢谢"、"今天天气怎么样"、"嘿嘿"

6. **modify_speech** - 修改指定任务中某智能体发言
   - 用户指定了任务ID，并要求修改该任务中某一角色/智能体的发言内容
   - 例如："修改 discussion_xxx 里 专家_人机交互 的发言"、"把 discussion_abc 中 人机交互 的发言改成：..."、"修改任务 discussion_xxx 中 第二层 工业设计 的发言"

**请以JSON格式返回：**
{{
    "intent": "start_new|query_latest|query_specific|resume|other_chat|modify_speech",
    "confidence": 0.0-1.0,
    "reasoning": "简要判断理由",
    "speaker": "当 intent 为 modify_speech 时，从用户输入中识别的智能体名称，如 专家_人机交互、人机交互、工业设计 等，否则填空字符串",
    "layer": "当 intent 为 modify_speech 时填 1 或 2 表示第一层或第二层，无法判断填 0",
    "modification_content": "当 intent 为 modify_speech 且用户直接给出了修改后的内容时，提取该内容；否则填空字符串"
}}"""
            
            response = llm.invoke(intent_prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 解析JSON响应
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    json_text = json_match.group().strip()
                    json_text = re.sub(r'```json\s*', '', json_text)
                    json_text = re.sub(r'```\s*', '', json_text)
                    intent_result = json.loads(json_text)
                    
                    intent = intent_result.get('intent', 'start_new')
                    confidence = intent_result.get('confidence', 0.5)
                    reasoning = intent_result.get('reasoning', '')
                    
                    logger.info(f"🧠 意图识别智能体: intent={intent}, confidence={confidence}, reasoning={reasoning[:50]}")
                    
                    # 验证intent值
                    valid_intents = ['start_new', 'query_latest', 'query_specific', 'resume', 'other_chat', 'modify_speech']
                    if intent not in valid_intents:
                        intent = 'start_new'
                    
                    result = {'intent': intent, 'discussion_id': extracted_id}
                    if intent == 'modify_speech':
                        result['speaker'] = intent_result.get('speaker', '') or ''
                        result['layer'] = int(intent_result.get('layer', 0)) if str(intent_result.get('layer', '')).isdigit() else 0
                        result['modification_content'] = intent_result.get('modification_content', '') or ''
                    return result
                except json.JSONDecodeError as e:
                    logger.warning(f"意图识别JSON解析失败: {e}")
            
            # 回退策略：关键词匹配
            return self._fallback_roundtable_intent(query, extracted_id)
            
        except Exception as e:
            logger.warning(f"意图识别失败: {e}，使用回退策略")
            return self._fallback_roundtable_intent(query, None)
    
    def _fallback_roundtable_intent(self, query: str, extracted_id: str = None) -> dict:
        """
        回退的关键词意图识别（当LLM不可用时）
        """
        query_lower = query.lower().strip()
        
        # 若有任务ID且用户说继续/重启，则视为恢复指定任务（用原ID）
        resume_keywords = ['继续', '重启', '恢复', '接着', 'resume', 'restart', '继续运行']
        if extracted_id and any(kw in query_lower for kw in resume_keywords):
            return {'intent': 'resume', 'discussion_id': extracted_id}
        # 若有任务ID但仅查询类措辞，则仅查询
        if extracted_id:
            return {'intent': 'query_specific', 'discussion_id': extracted_id}
        
        # 查询任务的关键词
        query_keywords = ['查询', '查看', '任务情况', '任务状态', '进度', '怎么样了', 
                         '完成了吗', '结果', '进展', 'status', 'progress', 'result']
        if any(kw in query_lower for kw in query_keywords):
            return {'intent': 'query_latest', 'discussion_id': None}
        
        # 其他聊天的关键词（短无意义输入）
        other_keywords = ['你好', '嘿', '哈', '嘿嘿', '哈哈', '谢谢', '再见', 'hi', 'hello', 'thanks']
        if query_lower in other_keywords or len(query_lower) <= 2:
            return {'intent': 'other_chat', 'discussion_id': None}
        
        # 默认：创建新任务
        return {'intent': 'start_new', 'discussion_id': None}
    
    def _read_task_topic_from_file(self, discussion_id: str) -> str:
        """
        从文件中读取任务主题
        
        Args:
            discussion_id: 任务ID
            
        Returns:
            str: 任务主题，如果读取失败返回空字符串
        """
        try:
            state_file = os.path.join("discussion", discussion_id, "discussion_state.json")
            if not os.path.exists(state_file):
                return ""
            
            with open(state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            return state_data.get('topic', '')
        except Exception as e:
            logger.warning(f"读取任务主题失败: {e}")
            return ""
    
    def _get_discussion_task_info(self, session_id: str, discussion_id: str = None):
        """
        流式获取任务情况信息（生成器方法）
        
        Args:
            session_id: 会话ID
            discussion_id: 指定的任务ID，如果为None则查询最新任务
            
        Yields:
            dict: 流式chunk，包含文本信息和文件路径
        """
        _id = f"task-info-{int(time.time())}"
        
        try:
            discussion_base_dir = "discussion"
            
            # 如果没有指定ID，查找最新的任务
            if not discussion_id:
                task_summary = cSingleSqlite.count_discussion_tasks_by_session_id(session_id)
                tasks_list = task_summary.get('tasks', [])
                if tasks_list:
                    discussion_id = tasks_list[0].get('discussion_id')  # 最新的任务
            
            if not discussion_id:
                yield self._create_chunk(_id,
                    content="""ℹ️ **暂无任务记录**

当前会话中没有找到任何圆桌会议任务。

💡 **提示**: 您可以通过说"开始讨论XX问题"来启动新的圆桌会议。
""",
                    chunk_type="text", finish_reason=""
                )

                time.sleep(1)

                yield self._create_chunk(_id,
                    content="",
                    chunk_type="text", finish_reason="stop"
                ) 

                return
            
            # 读取任务状态文件
            state_file = os.path.join(discussion_base_dir, discussion_id, "discussion_state.json")
            
            if not os.path.exists(state_file):
                yield self._create_chunk(_id,
                    content=f"""⚠️ **任务不存在**

找不到任务ID: `{discussion_id}` 的记录文件。

💡 **提示**: 请确认任务ID是否正确，或启动新的圆桌会议。
""",
                    chunk_type="text", finish_reason=""
                )

                time.sleep(1)

                yield self._create_chunk(_id,
                    content="",
                    chunk_type="text", finish_reason="stop"
                ) 

                return
            
            # 读取状态文件
            with open(state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            # 构建基本信息
            status = state_data.get('status', '未知')
            status_emoji = {
                'active': '🟢 进行中',
                'paused': '⏸️ 已暂停',
                'completed': '✅ 已完成',
                'error': '❌ 出错'
            }.get(status, f'❓ {status}')
            
            topic = state_data.get('topic', '未指定')
            current_round = state_data.get('current_round', 0)
            max_rounds = state_data.get('max_rounds', 5)
            participants = state_data.get('participants', [])
            created_at = state_data.get('created_at', '未知')
            updated_at = state_data.get('updated_at', '未知')
            rounds_info = state_data.get('rounds', [])
            
            # 返回基本信息（文本格式）
            basic_info = f"""## 📊 任务情况报告

### 🎯 基本信息

| 项目 | 内容 |
|------|------|
| 任务ID | `{discussion_id}` |
| 状态 | {status_emoji} |
| 讨论主题 | {topic[:80]}{'...' if len(topic) > 80 else ''} |
| 当前轮次 | 第 {current_round} / {max_rounds} 轮 |
| 参与人数 | {len(participants)} 位专家 |
| 创建时间 | {created_at[:19] if created_at else '未知'} |
| 更新时间 | {updated_at[:19] if updated_at else '未知'} |

"""
            yield self._create_chunk(_id,
                content=basic_info,
                chunk_type="text", finish_reason=""
            )
            
            # 返回参与者列表
            if participants:
                participants_text = "### 👥 参与专家\n\n"
                for p in participants:
                    participants_text += f"- {p}\n"
                participants_text += "\n"
                yield self._create_chunk(_id,
                    content=participants_text,
                    chunk_type="text", finish_reason=""
                )
            
            # 返回轮次及发言文件信息
            if rounds_info:
                for round_data in rounds_info:
                    r_num = round_data.get('round_number', 0)
                    r_status = round_data.get('status', '未知')
                    speeches = round_data.get('speeches', [])
                    
                    # 轮次标题
                    round_header = f"### 🗣️ 第{r_num}轮讨论 ({r_status}) - 共{len(speeches)}条发言\n\n"
                    yield self._create_chunk(_id,
                        content=round_header,
                        chunk_type="text", finish_reason=""
                    )
                    
                    # 每个发言的文件信息
                    for speech in speeches:
                        speaker = speech.get('speaker', '未知')
                        file_path = speech.get('file_path', '')
                        timestamp = speech.get('timestamp', '')
                        is_skeptic = speech.get('is_skeptic', False)
                        
                        # 角色类型标记
                        role_tag = "🤔 质疑者" if is_skeptic else "💬 专家"
                        
                        # 返回发言信息文本
                        speech_info = f"**{role_tag}**: {speaker}\n"
                        yield self._create_chunk(_id,
                            content=speech_info,
                            chunk_type="text", finish_reason=""
                        )
                        
                        # 返回文件路径（chunk_type="file"）
                        if file_path:
                            yield self._create_chunk(_id,
                                content=file_path,
                                chunk_type="file", finish_reason=""
                            )
                        
                        # 添加换行
                        yield self._create_chunk(_id,
                            content="\n",
                            chunk_type="text", finish_reason=""
                        )
            else:
                yield self._create_chunk(_id,
                    content="### 📨 暂无轮次记录\n\n讨论尚未开始或暂无发言记录。\n",
                    chunk_type="text", finish_reason=""
                )
            
            # 第二层：实施讨论组（智能体与发言）
            layer2 = state_data.get('layer2', {})
            if layer2:
                layer2_header = "\n\n### 🛠️ 第二层 实施讨论组\n\n"
                yield self._create_chunk(_id, content=layer2_header, chunk_type="text", finish_reason="")
                if layer2.get('participants'):
                    parts_text = "#### 👥 参与专家\n\n" + "\n".join(f"- {p}" for p in layer2['participants']) + "\n\n"
                    yield self._create_chunk(_id, content=parts_text, chunk_type="text", finish_reason="")
                for sp in layer2.get('speeches', []):
                    speaker = sp.get('speaker', '专家')
                    yield self._create_chunk(_id, content=f"**实施专家**: {speaker}\n", chunk_type="text", finish_reason="")
                    rel_path = sp.get('relative_file_path', '')
                    if rel_path:
                        full_path = os.path.join(discussion_base_dir, discussion_id, rel_path)
                        yield self._create_chunk(_id, content=full_path, chunk_type="file", finish_reason="")
                    yield self._create_chunk(_id, content="\n", chunk_type="text", finish_reason="")

            # 第三层：具像化层（智能体发言/结果文件，可点击查看）
            conc_layer = state_data.get('concretization_layer', {})
            conc_dir = os.path.join(discussion_base_dir, discussion_id, "concretization")
            if conc_layer.get('status') == 'completed' or (os.path.isdir(conc_dir) and os.listdir(conc_dir)):
                layer3_header = "\n\n### 📐 第三层 具像化结果\n\n"
                yield self._create_chunk(_id, content=layer3_header, chunk_type="text", finish_reason="")
                # 展示 concretization/ 下所有结果文件（.md 为主、.json 可选）
                try:
                    for fname in sorted(os.listdir(conc_dir)):
                        if not fname.endswith('.md') and not fname.endswith('.json'):
                            continue
                        full_path = os.path.join(conc_dir, fname)
                        if not os.path.isfile(full_path):
                            continue
                        label = "具像化报告 (Markdown)" if fname.endswith('.md') else "具像化结果 (JSON)"
                        yield self._create_chunk(_id, content=f"**{label}**: `{fname}`\n", chunk_type="text", finish_reason="")
                        yield self._create_chunk(_id, content=full_path, chunk_type="file", finish_reason="")
                        yield self._create_chunk(_id, content="\n", chunk_type="text", finish_reason="")
                except OSError:
                    pass

            # 结束标记
            yield self._create_chunk(_id,
                content="",
                chunk_type="text", finish_reason="stop"
            )
            
        except Exception as e:
            logger.error(f"获取任务信息失败: {e}")
            yield self._create_chunk(_id,
                content=f"❌ 获取任务信息失败: {str(e)}",
                chunk_type="text", finish_reason="stop"
            )

    # 修改 chat 函数以支持同步调用
    def chat(self, user_id, session_id, query):
        """
        智能聊天函数，支持文件意图识别
        
        流程：
        1. 通过 session_id 获取该会话上传的文件列表
        2. 使用LLM识别用户意图，判断是否在咨询上传文件内容
        3. 如果是咨询文件，调用 chat_with_file 返回文件内容咨询
        4. 否则，使用常规的意图识别智能体进行对话
        """
        try:
            # 步骤1: 获取该会话上传的文件列表
            file_info_list = cSingleSqlite.search_file_basic_info_by_session_id(session_id)
            
            # 如果有上传的文件，进行意图识别
            if file_info_list and len(file_info_list) > 0:
                # 提取文件名列表
                file_names = [file_info.get("file_name", "") for file_info in file_info_list if file_info.get("file_name")]
                
                if file_names:
                    logger.info(f"📁 会话 {session_id} 有 {len(file_names)} 个上传文件: {file_names}")
                    
                    # 步骤2: 使用LLM识别用户意图
                    llm = get_chat_tongyi(temperature=0.3, enable_thinking=False)
                    
                    # 构建意图识别提示
                    file_list_text = "\n".join([f"- {name}" for name in file_names])
                    intent_prompt = f"""你是一个意图识别助手。请分析用户的问题，判断用户是否在咨询会话中上传的文件内容。

**会话中上传的文件列表：**
{file_list_text}

**用户问题：**
{query}

**判断标准：**
1. 用户是否明确提到了文件名或文件相关内容？
2. 用户是否在询问文件的内容、信息、数据等？
3. 用户是否在咨询文件中的具体信息？

**请以JSON格式返回：**
{{
    "is_file_consultation": true/false,
    "target_file_name": "如果is_file_consultation为true，返回匹配的文件名，否则返回空字符串",
    "confidence": 0.0-1.0之间的置信度,
    "reasoning": "判断理由"
}}"""
                    
                    try:
                        # 调用LLM进行意图识别
                        response = llm.invoke(intent_prompt)
                        response_text = response.content if hasattr(response, 'content') else str(response)
                        
                        # 解析JSON响应
                        # import re
                        # 尝试提取JSON对象（支持嵌套）
                        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                        if json_match:
                            try:
                                intent_result = json.loads(json_match.group())
                            except json.JSONDecodeError:
                                # 如果直接解析失败，尝试清理文本后再解析
                                json_text = json_match.group().strip()
                                # 移除可能的markdown代码块标记
                                json_text = re.sub(r'```json\s*', '', json_text)
                                json_text = re.sub(r'```\s*', '', json_text)
                                try:
                                    intent_result = json.loads(json_text)
                                except json.JSONDecodeError:
                                    logger.warning(f"⚠️ JSON解析失败，响应文本: {response_text[:200]}")
                                    intent_result = None
                        else:
                            intent_result = None
                        
                        if intent_result:
                            
                            is_file_consultation = intent_result.get("is_file_consultation", False)
                            target_file_name = intent_result.get("target_file_name", "")
                            confidence = intent_result.get("confidence", 0.0)
                            
                            logger.info(f"🔍 意图识别结果: is_file_consultation={is_file_consultation}, target_file={target_file_name}, confidence={confidence}")
                            
                            # 步骤3: 如果识别为文件咨询，调用 chat_with_file
                            if is_file_consultation and confidence > 0.5:
                                # 查找匹配的文件路径
                                target_file_path = None
                                
                                if target_file_name:
                                    # 精确匹配文件名
                                    for file_info in file_info_list:
                                        if file_info.get("file_name") == target_file_name:
                                            target_file_path = file_info.get("file_path")
                                            break
                                
                                # 如果精确匹配失败，尝试模糊匹配（文件名包含在查询中）
                                if not target_file_path:
                                    query_lower = query.lower()
                                    for file_info in file_info_list:
                                        file_name = file_info.get("file_name", "")
                                        file_name_lower = file_name.lower()
                                        # 检查文件名是否在查询中被提及
                                        if file_name_lower in query_lower or any(word in query_lower for word in file_name_lower.split('.')[0].split('_')):
                                            target_file_path = file_info.get("file_path")
                                            logger.info(f"🔍 通过模糊匹配找到文件: {file_name}")
                                            break
                                
                                # 如果只有一个文件，直接使用它
                                if not target_file_path and len(file_info_list) == 1:
                                    target_file_path = file_info_list[0].get("file_path")
                                    logger.info(f"🔍 只有一个文件，直接使用: {file_info_list[0].get('file_name')}")
                                
                                if target_file_path and os.path.exists(target_file_path):
                                    logger.info(f"✅ 识别为文件咨询，调用 chat_with_file: {target_file_path}")
                                    # 调用文件分析功能
                                    for chunk in self.chat_with_file(user_id, session_id, query, target_file_path):
                                        yield chunk
                                    return
                                else:
                                    logger.warning(f"⚠️ 无法找到匹配的文件，继续使用常规对话")
                        else:
                            logger.warning("⚠️ 无法解析LLM返回的JSON格式")
                    except Exception as e:
                        logger.error(f"❌ 意图识别失败: {e}", exc_info=True)
                        # 意图识别失败，继续使用常规对话
            else:
                logger.info(f"📁 会话 {session_id} 没有上传文件，使用常规对话")
            
            # 步骤4: 常规对话流程
            messages = self.sess_obj.get_session_messages_by_id(session_id)
            # 调用修改后的 run_sync 函数，现在它返回完整的响应
            result = intent_recog_run.run_sync_stream(query, messages)
            for chunk in result:
                yield chunk
                
        except Exception as e:
            logger.error(f"❌ chat 函数执行失败: {e}", exc_info=True)
            # 发生错误时，回退到常规对话
            try:
                messages = self.sess_obj.get_session_messages_by_id(session_id)
                result = intent_recog_run.run_sync_stream(query, messages)
                for chunk in result:
                    yield chunk
            except Exception as e2:
                logger.error(f"❌ 常规对话也失败: {e2}", exc_info=True)
                yield self._create_chunk("chatcmpl-error", f"对话处理失败: {str(e2)}", chunk_type="text", finish_reason="stop", model="chat-model")
        
    def chat_with_file(self, user_id, session_id, query, file_path):
        if(True):
        # try:
            print("chat_with_file: 开始读取文件")
            print(f"file_path: {file_path}")
            
            # 根据文件类型选择解析方式（参考 control.py 的逻辑）
            file_extension = os.path.splitext(file_path)[1].lower()
            is_pdf = file_extension == ".pdf"
            is_text_file = file_extension in [".md", ".txt"]
            is_table_file = file_extension in [".csv", ".xlsx", ".xls"]
            
            if is_table_file:
                # CSV、XLSX、XLS 文件: 使用表格文件分析智能体
                logger.info(f"使用表格文件分析智能体: {file_path}")
                
                # 定义步骤回调函数（可选，用于步骤通知）
                def step_callback(step_name: str, step_data: Dict[str, Any]):
                    """步骤回调函数"""
                    logger.info(f"📊 表格分析步骤: {step_name} - {step_data.get('message', '')}")
                
                # 直接流式返回分析结果
                try:
                    for chunk in table_file_run.run_table_analysis_stream(file_path, query=query, step_callback=step_callback):
                        yield chunk
                    # for chunk in run_table_analysis_stream(file_path, query=query, step_callback=step_callback):
                    #     yield chunk
                except Exception as e:
                    logger.error(f"❌ 表格分析流程执行失败: {e}")
                    traceback.print_exc()
                    yield self._create_chunk("chatcmpl-error", f"表格分析失败: {str(e)}", chunk_type="text", finish_reason="stop", model="file-analysis-model")
                return
            elif is_text_file:
                # md 或 txt 文件: 直接读取文本内容
                logger.info(f"使用文本文件读取: {file_path}")
                _txt = self.file_obj.read_txt(file_path)
                if _txt is None:
                    logger.error(f"文本文件读取失败: {file_path}")
                    # 返回错误信息的生成器
                    def error_generator():
                        yield self._create_chunk("chatcmpl-error", "文本文件读取失败", chunk_type="text", finish_reason="", model="file-analysis-model")
                        yield self._create_chunk("chatcmpl-error", "", chunk_type="text", finish_reason="stop", model="file-analysis-model")
                    return error_generator()
            elif is_pdf and not is_pdf_advanced_enabled():
                # PDF_FLAG=False: 使用初级PDF解析
                logger.info(f"使用初级PDF解析: {file_path}")
                _, content_list = self.file_obj.read_pdf_basic(file_path)
                if content_list is None:
                    logger.error(f"初级PDF解析失败: {file_path}")
                    # 返回错误信息的生成器
                    def error_generator():
                        yield self._create_chunk("chatcmpl-error", "PDF解析失败，请检查是否安装了PyMuPDF或PyPDF2", chunk_type="text", finish_reason="", model="file-analysis-model")
                        yield self._create_chunk("chatcmpl-error", "", chunk_type="text", finish_reason="stop", model="file-analysis-model")
                    return error_generator()
                _txt = content_list  # 初级解析直接返回文本内容
            else:
                # PDF_FLAG=True 或其他文件类型: 使用高级解析（调用API）
                logger.info(f"使用高级文件解析: {file_path}")
                _, content_list = self.file_obj.read_stream_file(file_path)
                if content_list is None:
                    logger.error(f"高级文件解析失败: {file_path}")
                    # 返回错误信息的生成器
                    def error_generator():
                        yield self._create_chunk("chatcmpl-error", "文件解析失败", chunk_type="text", finish_reason="", model="file-analysis-model")
                        yield self._create_chunk("chatcmpl-error", "", chunk_type="text", finish_reason="stop", model="file-analysis-model")
                    return error_generator()
                _txt = self.content_list_to_json(content_list, file_id="")
            
            # 生成 .md 文件路径并保存内容
            file_name = os.path.basename(file_path)
            txt, _ = os.path.splitext(file_name)
            file_md_path = file_path.replace(file_name, txt + ".md")
            with open(file_md_path, "w", encoding="utf-8") as f:
                f.write(_txt)

            # 使用文件分析智能体的流式结果
            # 传入文本读取的内容和用户的问题
            # 注意：直接传入 content 而不是 file_path，因为内容已经读取，避免再次读取文件
            input_data = {
                "file_path": file_path,  # 保留原始文件路径作为元数据
                "content": _txt,  # 文本读取的内容（MD格式）
                "query": query,   # 用户的问题
            }
            # 遍历生成器并 yield 每个 chunk，确保流式返回
            try:
                for chunk in file_analysis_run.run_file_analysis_sync_stream(input_data):
                    yield chunk
            except Exception as e:
                logger.error(f"❌ 文件分析流式处理失败: {e}", exc_info=True)
                yield self._create_chunk("chatcmpl-error", f"文件分析失败: {str(e)}", chunk_type="text", finish_reason="stop", model="file-analysis-model")
            return
        else:
            e = ""
        # except Exception as e:
            # 返回错误信息的生成器，与流式API兼容
            def error_generator():
                yield self._create_chunk("chatcmpl-error", f"Error during file upload: {str(e)}", chunk_type="text", finish_reason="", model="file-analysis-model")
                yield self._create_chunk("chatcmpl-error", "", chunk_type="text", finish_reason="stop", model="file-analysis-model")

            return error_generator()

    def chat_with_knowledge_and_sql(self, user_id, session_id, query, knowledge_id, sql_id):
        """
        结合知识库和SQL的智能问答功能（流式返回）
    
        功能：
        1. 通过knowledge_id进行milvus、elasticsearch、graph三个搜索引擎搜索业务数据
        2. 结合用户的问题，在搜索到的知识中，搜索与问题相关的指标实体
        3. 形成三层关联关系：
           - 第一层：用户咨询的业务问题中的实体
           - 第二层：业务问题中关联的指标实体
           - 第三层：指标实体需要的计算逻辑，该逻辑要标准明确的逻辑规范
    
        Args:
            user_id: 用户ID
            session_id: 会话ID
            query: 用户问题
            knowledge_id: 知识库ID
            sql_id: SQL数据库ID
        """
        # knowledge_id 知识库搜索 业务数据
        # sql_id SQL数据库搜索 业务数据
        
        _id = f"chatcmpl-{int(time.time())}"
        
        try:
            logger.info("🔍 执行Agentic Query智能体流程...")
            
            # 使用队列收集步骤结果
            step_queue = queue.Queue()
            final_query_result = None
            
            # 定义步骤回调函数
            def step_callback(step_name: str, step_data: Dict[str, Any]):
                """步骤回调函数，将每个步骤的结果放入队列"""
                try:
                    step_queue.put({
                        "step_name": step_name,
                        "step_data": step_data
                    })
                except Exception as e:
                    logger.error(f"⚠️ 步骤回调处理失败 ({step_name}): {e}")
                    traceback.print_exc()
            
            # 在后台线程中运行智能体流程
            def run_agentic_query_flow():
                """在后台线程中运行智能体流程"""
                nonlocal final_query_result
                try:
                    final_query_result = agentic_query_run.run_agentic_query(
                        knowledge_id=knowledge_id,
                        query=query,
                        sql_id=sql_id,
                        user_id=user_id,
                        step_callback=step_callback
                    )
                    # 发送完成信号
                    step_queue.put({"step_name": "query_completed", "step_data": {"success": True}})
                except Exception as e:
                    logger.error(f"❌ Agentic Query流程执行失败: {e}")
                    traceback.print_exc()
                    step_queue.put({"step_name": "query_completed", "step_data": {"success": False, "error": str(e)}})
            
            # 启动后台线程
            query_thread = threading.Thread(target=run_agentic_query_flow)
            query_thread.daemon = True
            query_thread.start()
            
            # 格式化步骤信息的映射
            step_messages = {
                "step_1_decision": "🔍 步骤1: 决策智能体 - 分析实体本源、指标、属性等",
                "step_2_search": "🔍 步骤2: 双引擎搜索 - 初步查询知识库",
                "step_3_evaluation": "📊 步骤3: 结果评估 - 分析搜索结果质量",
                "step_4_expanded_search": "🔍 步骤4: 扩展搜索",
                "step_5_artifact": "📋 步骤5: Artifact处理 - 分离清洗内容和原始内容",
                "step_6_dynamic_prompt": "📝 步骤6: 动态生成System Prompt",
                "step_7_query_enhancement": "✨ 步骤7: 查询增强 - 完善用户问题"
            }
            
            # 流式返回步骤信息
            while True:
                try:
                    item = step_queue.get(timeout=1)
                    step_name = item.get("step_name")
                    step_data = item.get("step_data", {})
                    
                    if step_name == "completed":
                        break
                    
                    # 显示步骤信息
                    if step_name in step_messages:
                        step_msg = step_messages[step_name]
                        if step_data.get("success"):
                            step_content = f"{step_msg}\n✅ 完成"
                            if step_name == "step_1_decision":
                                entity_analysis = step_data.get("entity_analysis", {})
                                entities_count = len(entity_analysis.get("entities", []))
                                metrics_count = len(entity_analysis.get("metrics", []))
                                attributes_count = len(entity_analysis.get("attributes", []))
                                step_content += f"\n- 识别到 {entities_count} 个实体、{metrics_count} 个指标、{attributes_count} 个属性"
                            elif step_name == "step_2_search":
                                step_content += f"\n- 共找到 {step_data.get('total_count', 0)} 个搜索结果"
                            elif step_name == "step_3_evaluation":
                                quality_score = step_data.get("quality_score", 0.0)
                                step_content += f"\n- 质量评分: {quality_score:.3f}"
                            elif step_name == "step_7_query_enhancement":
                                enhanced_query = step_data.get("enhanced_query", "")
                                if enhanced_query:
                                    step_content += f"\n- 增强后的查询: {enhanced_query}"
                            
                            chunk = self._create_chunk(_id, content=step_content, chunk_type="text", finish_reason="")
                            yield chunk
                        else:
                            error_msg = step_data.get("error", "未知错误")
                            step_content = f"{step_msg}\n❌ 失败: {error_msg}"
                            chunk = self._create_chunk(_id, content=step_content, chunk_type="text", finish_reason="")
                            yield chunk
                    
                except queue.Empty:
                    continue
            
            # 等待线程完成
            query_thread.join(timeout=30)
            
            # 检查Agentic Query结果
            if not final_query_result or not final_query_result.get("success"):
                error_msg = final_query_result.get("error", "未知错误") if final_query_result else "流程执行失败"
                chunk = self._create_chunk(_id, content=f"❌ Agentic Query流程失败: {error_msg}", chunk_type="text", finish_reason="stop")
                yield chunk
                return
            
            # 获取增强后的查询
            enhanced_query = final_query_result.get("enhanced_query", query)
            calculation_descriptions = final_query_result.get("calculation_descriptions", [])
            system_prompt = final_query_result.get("system_prompt", "")
            
            # 显示Agentic Query结果摘要
            result_content = "## 📊 Agentic Query结果\n\n"
            result_content += f"**原始查询：**\n{query}\n\n"
            result_content += f"**增强后的查询：**\n{enhanced_query}\n\n"
            
            if calculation_descriptions:
                result_content += "**计算描述：**\n"
                for i, calc_desc in enumerate(calculation_descriptions, 1):
                    if isinstance(calc_desc, dict):
                        attr = calc_desc.get("attribute", "")
                        calc = calc_desc.get("calculation", "")
                        desc = calc_desc.get("description", "")
                        result_content += f"{i}. **{attr}**: {calc}\n   {desc}\n\n"
                    else:
                        result_content += f"{i}. {calc_desc}\n\n"
            
            if system_prompt:
                result_content += f"**动态生成的System Prompt：**\n```\n{system_prompt}\n```\n\n"
            
            chunk = self._create_chunk(_id, content=result_content, chunk_type="text", finish_reason="")
            yield chunk
            logger.info(f"✅ Agentic Query流程完成，开始执行SQL查询...")
            
            # 如果没有sql_id，无法执行SQL查询
            if not sql_id:
                chunk = self._create_chunk(_id, content="\n⚠️ 未提供SQL数据库ID，无法执行SQL查询", chunk_type="text", finish_reason="stop")
                yield chunk
                return
            
            # 步骤2: 使用增强后的查询执行SQL查询
            logger.info(f"🔍 执行SQL查询，使用增强后的查询: {enhanced_query}")
            
            # 获取数据库信息
            db_info = self._get_database_info(sql_id)
        
            # 使用队列收集SQL步骤结果
            sql_step_queue = queue.Queue()
            final_sql_workflow_result = None
            
            # 定义SQL步骤回调函数
            def sql_step_callback(step_name: str, step_data: Dict[str, Any]):
                """SQL步骤回调函数"""
                try:
                    sql_step_queue.put({
                        "step_name": step_name,
                        "step_data": step_data
                    })
                except Exception as e:
                    logger.error(f"⚠️ SQL步骤回调处理失败 ({step_name}): {e}")
                    traceback.print_exc()
            
            # 在后台线程中运行SQL智能体流程
            def run_sql_agentic_search():
                """在后台线程中运行SQL智能体流程"""
                nonlocal final_sql_workflow_result
                try:
                    final_sql_workflow_result = agentic_sql_run.run_sql_agentic_search(
                        sql_id=sql_id,
                        query=enhanced_query,  # 使用增强后的查询
                user_id=user_id,
                        step_callback=sql_step_callback
                    )
                    # 发送完成信号
                    sql_step_queue.put({"step_name": "sql_completed", "step_data": {"success": True}})
                except Exception as e:
                    logger.error(f"❌ SQL智能体流程执行失败: {e}")
                    traceback.print_exc()
                    sql_step_queue.put({"step_name": "sql_completed", "step_data": {"success": False, "error": str(e)}})
            
            # 启动SQL后台线程
            sql_thread = threading.Thread(target=run_sql_agentic_search)
            sql_thread.daemon = True
            sql_thread.start()
            
            # 流式处理SQL步骤结果（跳过SQL生成流程的中间步骤）
            sql_completed = False
            while not sql_completed:
                try:
                    sql_item = sql_step_queue.get(timeout=1.0)
                    sql_step_name = sql_item.get("step_name")
                    sql_step_data = sql_item.get("step_data", {})
                    
                    if sql_step_name == "sql_completed":
                        sql_completed = True
                        if not sql_step_data.get("success"):
                            error_msg = sql_step_data.get("error", "SQL查询失败")
                            chunk = self._create_chunk(_id, content=f"\n## ❌ SQL查询失败\n\n**错误信息:** {error_msg}", chunk_type="text", finish_reason="stop")
                            yield chunk
                            return
                        
                    
                    # 跳过SQL生成流程的中间步骤，只输出最终结果
                    if sql_step_name in ["sql_flow_step_1_generation", "sql_flow_step_2_check_run", 
                                         "sql_flow_step_3_correction", "sql_flow_step_4_optimization",
                                         "sql_flow_step_5_recheck_run", "sql_flow_step_6_verification"]:
                        continue
                    
                    # 显示SQL步骤信息（简化显示）
                    if sql_step_name == "step_3_sql_generation":
                        if sql_step_data.get("success") and sql_step_data.get("sql"):
                            sql_content = sql_step_data.get("sql", "")
                            step_content = f"\n## 💻 SQL生成结果\n\n**生成的SQL：**\n```sql\n{sql_content}\n```\n"
                            execution_result = sql_step_data.get("execution_result", {})
                            if execution_result and execution_result.get("executed"):
                                row_count = execution_result.get("row_count", 0)
                                step_content += f"\n**执行结果：** ✅ 成功执行，返回 {row_count} 行数据\n"
                            chunk = self._create_chunk(_id, content=step_content, chunk_type="text", finish_reason="")
                            yield chunk
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"⚠️ 处理SQL步骤结果失败: {e}")
                    traceback.print_exc()
                    break
            
            # 等待SQL线程完成
            sql_thread.join(timeout=300)
            
            # 获取SQL查询结果
            sql_workflow_result = final_sql_workflow_result
            if not sql_workflow_result or not sql_workflow_result.get("success"):
                error_msg = sql_workflow_result.get("error", "SQL查询失败") if sql_workflow_result else "未获取到SQL查询结果"
                chunk = self._create_chunk(_id, content=f"\n## ❌ SQL查询失败\n\n**错误信息:** {error_msg}", chunk_type="text", finish_reason="stop")
                yield chunk
                return
            
            # 从sql_workflow_result中提取SQL和列信息
            sql = sql_workflow_result.get("sql", "")
            columns_with_description = sql_workflow_result.get("columns_with_description", [])
            columns_with_table_prefix = sql_workflow_result.get("columns_with_table_prefix", [])
            logical_calculations = sql_workflow_result.get("logical_calculations", [])
            execution_result = sql_workflow_result.get("execution_result", {})
            
            if not sql:
                logger.warning("⚠️ SQL为空，无法执行")
                chunk = self._create_chunk(_id, content="\n## ⚠️ 执行失败\n\n**错误:** SQL为空，无法执行查询", chunk_type="text", finish_reason="stop")
                yield chunk
                return
            
            logger.info(f"✅ 执行SQL: {sql[:100]}...")
            
            # 从columns_with_description中提取列信息（使用 table.col 格式）
            columns_desc = []
            columns_types = []
            columns_used = []
            
            # 优先使用 columns_with_table_prefix（如果存在）
            if columns_with_table_prefix:
                # 构建列名到描述的映射
                col_desc_map = {}
                col_type_map = {}
                for col in columns_with_description:
                    col_name_with_table = col.get("col_name_with_table", f"{col.get('table_name', '')}.{col.get('col_name', '')}")
                    col_desc_map[col_name_with_table] = col.get("col_description", col.get("col_name", ""))
                    col_type_map[col_name_with_table] = col.get("col_type", "unknown")
                
                # 使用 columns_with_table_prefix 中的列名
                for col_name_with_table in columns_with_table_prefix:
                    columns_used.append(col_name_with_table)
                    columns_types.append(col_type_map.get(col_name_with_table, "unknown"))
                    columns_desc.append(col_desc_map.get(col_name_with_table, col_name_with_table))
            else:
                # 如果没有 columns_with_table_prefix，从 columns_with_description 构建
                for col in columns_with_description:
                    col_name = col.get("col_name", "")
                    col_name_with_table = col.get("col_name_with_table", f"{col.get('table_name', '')}.{col_name}")
                    col_type = col.get("col_type", "")
                    col_description = col.get("col_description", col_name)
                    
                    if col_name:
                        columns_used.append(col_name_with_table)
                        columns_types.append(col_type or "unknown")
                        columns_desc.append(col_description)
            
            # 如果无法从columns_with_description获取列信息，尝试从SQL执行结果获取
            if not columns_used:
                logger.warning("⚠️ 无法从columns_with_description获取列信息，将从SQL执行结果中获取")
                try:
                    sql_url = db_info.get("db_host", "")
                    sql_port = str(db_info.get("db_port", ""))
                    sql_user = db_info.get("db_user", "")
                    sql_password = db_info.get("db_password", "")
                    sql_database = db_info.get("db_name", "")
                    sql_type = db_info.get("db_type")
                    conn, _ = self.sql_obj.connect_database(sql_url, sql_port, sql_type, sql_database, sql_user, sql_password)
                    cursor = conn.cursor()
                    cursor.execute(sql)
                    
                    if cursor.description:
                        col_name_mapping = {}
                        for col in columns_with_description:
                            orig_col = col.get("col_name", "")
                            col_with_table = col.get("col_name_with_table", f"{col.get('table_name', '')}.{orig_col}")
                            if orig_col:
                                col_name_mapping[orig_col.lower()] = col_with_table
                        
                        for desc in cursor.description:
                            orig_col_name = desc[0]
                            mapped_col_name = col_name_mapping.get(orig_col_name.lower(), orig_col_name)
                            columns_used.append(mapped_col_name)
                            columns_types.append(desc[1] or "unknown")
                            columns_desc.append(mapped_col_name)
                    
                    conn.close()
                except Exception as e:
                    logger.error(f"⚠️ 获取列信息失败: {e}")
                    columns_desc = ["列1", "列2"]
                    columns_types = ["unknown", "unknown"]
            
            logger.info(f"📊 提取到 {len(columns_used)} 个列")
            
            # 执行SQL并保存到CSV
            file_name = "conf/tmp/sandbox_files/" + uuid.uuid4().hex[:16]
            read_flag, max_num = self._read_data(sql, db_info, file_name, columns_desc, columns_types)
            
            if not read_flag or max_num == 0:
                logger.warning(f"⚠️ SQL执行失败或没有数据")
                error_msg = execution_result.get('error', '未知错误') if execution_result else '未知错误'
                chunk = self._create_chunk(_id, content=f"\n## ⚠️ SQL执行失败或没有数据\n\n**错误:** {error_msg}", chunk_type="text", finish_reason="stop")
                yield chunk
                return
            
            logger.info(f"✅ SQL执行成功，返回 {max_num} 行数据")
            
                    # 读取CSV文件并生成HTML表格
            csv_file_path = file_name + ".csv"
            html_table = self._csv_to_html_table(csv_file_path, max_num, max_rows=10)
            logger.info(f"📊 生成HTML表格: {'成功' if html_table else '失败'}")
            
            # 如果生成了HTML表格，流式返回
            if html_table: 
                chunk = self._create_chunk(_id, content=html_table, chunk_type="html_table", finish_reason="")
                yield chunk
            
            # 步骤3: 逻辑计算和解读
            if logical_calculations:
                logger.info(f"🔢 开始执行逻辑计算，共 {len(logical_calculations)} 个计算规则")
                try:
                    logic_result = agentic_sql_run.run_logic_calculation(
                        csv_file_path=csv_file_path,
                        query=enhanced_query,  # 使用增强后的查询
                        logical_calculations=logical_calculations,
                        columns_desc=columns_desc,
                        columns_types=columns_types,
                        sql=sql
                    )
                    print("logic_result:", logic_result)
                    if logic_result.get("success"):
                        calculation_summary = logic_result.get("calculation_summary", "")
                        calculation_result = logic_result.get("calculation_result", {})
                        tools_used = logic_result.get("tools_used", [])
                        interpretation = logic_result.get("interpretation", {})
                        final_interpretation = logic_result.get("final_interpretation", {})
                        
                        if calculation_result or calculation_summary or interpretation or final_interpretation:
                            # 构建逻辑计算结果的显示内容
                            logic_content = "\n\n## 🔢 逻辑计算结果\n\n"
                            
                            # 优先显示最终综合解读
                            if final_interpretation:
                                overall_summary = final_interpretation.get("overall_summary", "")
                                question_answer = final_interpretation.get("question_answer", "")
                                key_findings = final_interpretation.get("key_findings", [])
                                business_insights = final_interpretation.get("business_insights", [])
                                limitations = final_interpretation.get("limitations", "")
                                next_steps = final_interpretation.get("next_steps", "")
                                
                                if overall_summary:
                                    logic_content += f"**📊 整体总结：**\n{overall_summary}\n\n"
                                
                                if question_answer:
                                    logic_content += f"**❓ 问题回答：**\n{question_answer}\n\n"
                                
                                if key_findings:
                                    logic_content += "**🔍 关键发现：**\n"
                                    for i, finding in enumerate(key_findings, 1):
                                        logic_content += f"{i}. {finding}\n"
                                    logic_content += "\n"
                                
                                if business_insights:
                                    logic_content += "**💡 业务洞察：**\n"
                                    for i, insight in enumerate(business_insights, 1):
                                        logic_content += f"{i}. {insight}\n"
                                    logic_content += "\n"
                                
                                if limitations:
                                    logic_content += f"**⚠️ 局限性说明：**\n{limitations}\n\n"
                                
                                if next_steps:
                                    logic_content += f"**🚀 下一步建议：**\n{next_steps}\n\n"
                            
                            if calculation_summary:
                                logic_content += f"**计算摘要：** {calculation_summary}\n\n"
                            
                            if tools_used:
                                logic_content += f"**使用的统计工具：** {', '.join(tools_used)}\n\n"
                            
                            # 显示统计结果解读
                            if interpretation:
                                interpretation_summary = interpretation.get("interpretation_summary", "")
                                key_insights = interpretation.get("key_insights", [])
                                detailed_interpretation = interpretation.get("detailed_interpretation", "")
                                
                                if interpretation_summary:
                                    logic_content += f"**📈 统计结果解读摘要：**\n{interpretation_summary}\n\n"
                                
                                if key_insights:
                                    logic_content += "**关键洞察：**\n"
                                    for i, insight in enumerate(key_insights, 1):
                                        logic_content += f"{i}. {insight}\n"
                                    logic_content += "\n"
                                
                                if detailed_interpretation:
                                    logic_content += f"**详细解读：**\n{detailed_interpretation}\n\n"
                            
                            # 显示原始计算结果（作为补充信息）
                            if calculation_result:
                                logic_content += "**原始计算结果：**\n```json\n"
                                logic_content += json.dumps(calculation_result, ensure_ascii=False, indent=2)
                                logic_content += "\n```\n"
                            
                            chunk = self._create_chunk(_id, content=logic_content, chunk_type="text", finish_reason="")
                            yield chunk
                            logger.info(f"✅ 逻辑计算完成并返回结果（包含最终解读）")
                        else:
                            logger.warning("⚠️ 逻辑计算结果为空")
                    else:
                        error_msg = logic_result.get("error", "逻辑计算失败")
                        chunk = self._create_chunk(_id, content=f"\n## ⚠️ 逻辑计算失败\n\n**错误:** {error_msg}", chunk_type="text", finish_reason="")
                        yield chunk
                except Exception as e:
                    logger.error(f"❌ 逻辑计算执行失败: {e}")
                    traceback.print_exc()
                    chunk = self._create_chunk(_id, content=f"\n## ⚠️ 逻辑计算执行失败\n\n**错误:** {str(e)}", chunk_type="text", finish_reason="")
                    yield chunk
            
            # 清理CSV文件
            try:
                if os.path.exists(csv_file_path):
                    os.remove(csv_file_path)
            except Exception as e:
                logger.warning(f"⚠️ 清理CSV文件失败: {e}")
            
            # 返回完成信号
            chunk = self._create_chunk(_id, content="", chunk_type="text", finish_reason="stop")
            yield chunk
            logger.info(f"✅ 完整流程执行完成")
                
        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.error(f"❌ chat_with_knowledge_and_sql 执行失败: {e}")
            logger.error(f"Traceback: {error_traceback}")
            chunk = self._create_chunk(_id, content=f"❌ 执行失败: {str(e)}", chunk_type="text", finish_reason="stop")
            yield chunk
                
    def chat_with_sql(self, user_id, session_id, query, sql_id):
        """智能SQL问数：根据自然语言生成并执行 SQL，返回表格与逻辑计算解读。"""
        _id = f"chatcmpl-{int(time.time())}"
        db_info = self._get_database_info(sql_id)
        if not db_info or not db_info.get("db_host"):
            chunk = self._create_chunk(
                _id,
                content="## ❌ 智能问数失败\n\n**错误:** 未找到该数据源或数据库配置不完整，请检查 sql_id 或数据源连接。",
                chunk_type="text",
                finish_reason="stop",
            )
            yield chunk
            return

        try:
            # 调用公共的SQL生成工作流函数（支持异步流式返回）
            logger.info("🔍 执行SQL生成工作流...")
            
            # 使用队列收集步骤结果
            step_queue = queue.Queue()
            final_sql_workflow_result = None
            
            # 定义步骤回调函数，用于收集每个步骤的结果
            def step_callback(step_name: str, step_data: Dict[str, Any]):
                """步骤回调函数，将每个步骤的结果放入队列"""
                try:
                    step_queue.put({
                        "step_name": step_name,
                        "step_data": step_data
                    })
                except Exception as e:
                    logger.error(f"⚠️ 步骤回调处理失败 ({step_name}): {e}")
                    traceback.print_exc()
            
            # 在后台线程中运行智能体流程
            def run_agentic_search():
                """在后台线程中运行智能体流程"""
                nonlocal final_sql_workflow_result
                try:
                    final_sql_workflow_result = agentic_sql_run.run_sql_agentic_search(
                        sql_id=sql_id,
                        query=query,
                user_id=user_id,
                        step_callback=step_callback
                    )
                # 发送完成信号
                    step_queue.put({"step_name": "completed", "step_data": {"success": True}})
                except Exception as e:
                    logger.error(f"❌ 智能体流程执行失败: {e}")
                    traceback.print_exc()
                    step_queue.put({"step_name": "completed", "step_data": {"success": False, "error": str(e)}})
            
            agent_thread = threading.Thread(target=run_agentic_search)
            agent_thread.daemon = True
            agent_thread.start()

            step_messages = self._get_sql_step_display_titles()

            # 流式消费队列中的步骤结果并推送给前端
            completed = False
            while not completed:
                try:
                    # 从队列中获取步骤结果（设置超时避免无限等待）
                    step_result = step_queue.get(timeout=1.0)
                    step_name = step_result.get("step_name")
                    step_data = step_result.get("step_data", {})
                    
                    if step_name == "completed":
                        completed = True
                        if not step_data.get("success"):
                            error_msg = step_data.get("error", "智能问数失败")
                            chunk = self._create_chunk(_id, content=f"## ❌ 智能问数失败\n\n**错误信息:** {error_msg}", chunk_type="text", finish_reason="stop")
                            yield chunk
                            return
                        
                    
                    # 跳过SQL生成流程的中间步骤，只输出最终结果
                    if step_name in ["sql_flow_step_1_generation", "sql_flow_step_2_check_run", 
                                     "sql_flow_step_3_correction", "sql_flow_step_4_optimization",
                                     "sql_flow_step_5_recheck_run", "sql_flow_step_6_verification"]:
                        continue  # 跳过这些中间步骤的输出
                    
                    # 格式化步骤信息（Markdown格式）
                    step_title = step_messages.get(step_name, f"## 步骤: {step_name}")
                    content_parts = [f"{step_title}\n"]
                    
                    if step_data.get("success"):
                        # 根据步骤类型添加详细信息
                        if step_name == "step_1_database_info":
                            content_parts.append("**执行结果:**\n")
                            content_parts.append(f"- **数据库名称:** {step_data.get('database_name', '')}\n")
                            content_parts.append(f"- **数据库类型:** {step_data.get('database_type', '')}\n")
                        elif step_name == "step_1_2_metadata_query":
                            # 数据库元数据查询结果
                            if step_data.get("is_metadata_query"):
                                query_type = step_data.get("query_type", "")
                                result_data = step_data.get("result", {})
                                message = step_data.get("message", "")
                                
                                content_parts.append("**元数据查询结果:**\n")
                                content_parts.append(f"- **查询类型:** {query_type}\n")
                                
                                if message:
                                    content_parts.append(f"\n**查询结果:**\n{message}\n")
                                
                                # 根据查询类型显示详细信息
                                if query_type == "table_count":
                                    count = result_data.get("count", 0)
                                    content_parts.append(f"\n数据库中共有 **{count}** 个表\n")
                                elif query_type == "table_list":
                                    tables = result_data.get("tables", [])
                                    count = result_data.get("count", 0)
                                    content_parts.append(f"\n数据库中共有 **{count}** 个表：\n\n")
                                    for table in tables[:20]:  # 最多显示20个表
                                        table_name = table.get("table_name", "")
                                        table_desc = table.get("table_description", "")
                                        if table_desc:
                                            content_parts.append(f"- **{table_name}**: {table_desc}\n")
                                        else:
                                            content_parts.append(f"- **{table_name}**\n")
                                    if count > 20:
                                        content_parts.append(f"\n... 还有 {count - 20} 个表未显示\n")
                                elif query_type == "column_count":
                                    table_name = result_data.get("table_name", "")
                                    count = result_data.get("count", 0)
                                    content_parts.append(f"\n表 **{table_name}** 中共有 **{count}** 个列\n")
                                elif query_type == "column_list":
                                    table_name = result_data.get("table_name", "")
                                    columns = result_data.get("columns", [])
                                    count = result_data.get("count", 0)
                                    content_parts.append(f"\n表 **{table_name}** 中共有 **{count}** 个列：\n\n")
                                    for col in columns[:30]:  # 最多显示30个列
                                        col_name = col.get("column_name", "")
                                        col_type = col.get("column_type", "")
                                        col_comment = col.get("column_comment", "")
                                        if col_comment:
                                            content_parts.append(f"- **{col_name}** ({col_type}): {col_comment}\n")
                                        else:
                                            content_parts.append(f"- **{col_name}** ({col_type})\n")
                                    if count > 30:
                                        content_parts.append(f"\n... 还有 {count - 30} 个列未显示\n")
                                elif query_type == "table_description":
                                    table_name = result_data.get("table_name", "")
                                    table_desc = result_data.get("table_description", "")
                                    content_parts.append(f"\n表 **{table_name}** 的描述：\n{table_desc}\n")
                                elif query_type == "column_comment":
                                    table_name = result_data.get("table_name", "")
                                    column_name = result_data.get("column_name", "")
                                    column_type = result_data.get("column_type", "")
                                    column_comment = result_data.get("column_comment", "")
                                    content_parts.append(f"\n列 **{table_name}.{column_name}** ({column_type}) 的注释：\n{column_comment}\n")
                                else:
                                    # 查询失败（表名或列名错误）
                                    error_msg = step_data.get("error", "元数据查询失败")
                                    error_message = step_data.get("error_message", error_msg)
                                    available_tables = step_data.get("available_tables", [])
                                    available_columns = step_data.get("available_columns", [])
                                    
                                    content_parts.append("**元数据查询错误:**\n")
                                    content_parts.append(f"- **查询类型:** {query_type}\n")
                                    content_parts.append(f"- **错误信息:** {error_msg}\n\n")
                                    
                                    if error_message:
                                        content_parts.append(f"**详细错误说明:**\n{error_message}\n\n")
                                    
                                    if available_tables:
                                        content_parts.append(f"**可用的表名列表（共 {len(available_tables)} 个）:**\n")
                                        for i, table_name in enumerate(available_tables[:30], 1):
                                            content_parts.append(f"{i}. `{table_name}`\n")
                                        if len(available_tables) > 30:
                                            content_parts.append(f"\n... 还有 {len(available_tables) - 30} 个表未显示\n")
                                        content_parts.append("\n")
                                    
                                    if available_columns:
                                        content_parts.append(f"**可用的列名列表（共 {len(available_columns)} 个）:**\n")
                                        for i, col_name in enumerate(available_columns[:30], 1):
                                            content_parts.append(f"{i}. `{col_name}`\n")
                                        if len(available_columns) > 30:
                                            content_parts.append(f"\n... 还有 {len(available_columns) - 30} 个列未显示\n")
                                        content_parts.append("\n")
                            else:
                                content_parts.append("**检查结果:** 不是数据库元数据查询，继续后续流程\n")
                        elif step_name == "step_1_5_query_decomposition":
                            # 问题拆解与逻辑分析结果
                            content_parts.append("**拆解结果:**\n")
                            content_parts.append(f"- **实体:** {step_data.get('entities_count', 0)} 个\n")
                            content_parts.append(f"- **指标:** {step_data.get('metrics_count', 0)} 个\n")
                            content_parts.append(f"- **时间维度:** {step_data.get('time_dimensions_count', 0)} 个\n")
                            content_parts.append(f"- **关联关系:** {step_data.get('relationships_count', 0)} 个\n")
                            content_parts.append(f"- **逻辑计算:** {step_data.get('logical_calculations_count', 0)} 个\n")
                            content_parts.append(f"- **空间维度:** {step_data.get('spatial_dimensions_count', 0)} 个\n")
                            content_parts.append(f"- **集合论关系:** {step_data.get('set_theory_relations_count', 0)} 个\n")
                            content_parts.append(f"- **关系代数:** {step_data.get('relational_algebra_count', 0)} 个\n")
                            content_parts.append(f"- **图论关系:** {step_data.get('graph_theory_relations_count', 0)} 个\n")
                            content_parts.append(f"- **逻辑推理:** {step_data.get('logical_reasoning_count', 0)} 个\n")
                            content_parts.append(f"- **语义网络:** {step_data.get('semantic_network_count', 0)} 个\n")
                            content_parts.append(f"- **数学关系:** {step_data.get('mathematical_relations_count', 0)} 个\n")
                            
                            if step_data.get('analysis_summary'):
                                content_parts.append(f"\n**分析总结:**\n{step_data.get('analysis_summary')}\n")
                        elif step_name == "step_1_5_sql_intent_recognition":
                            # SQL意图识别结果
                            intent_type_message = step_data.get('intent_type_message', '')
                            if intent_type_message:
                                content_parts.append(f"{intent_type_message}\n\n")
                            content_parts.append("**识别结果:**\n")
                            content_parts.append(f"- **是否是SQL问数:** {'✅ 是' if step_data.get('is_sql_query', False) else '❌ 否'}\n")
                            content_parts.append(f"- **置信度:** `{step_data.get('confidence', 0):.2%}`\n")
                            if step_data.get('search_target'):
                                content_parts.append(f"- **搜索目标:** {step_data.get('search_target', '')}\n")
                        elif step_name == "step_1_5_sql_intent_recognition_warning":
                            # SQL意图识别警告
                            warning = step_data.get('warning', '')
                            if warning:
                                content_parts.append(f"> ⚠️ {warning}\n")
                        elif step_name == "step_1_5_sql_intent_recognition_final":
                            # SQL意图识别最终结果（不是SQL问数）
                            message = step_data.get('message', '')
                            if message:
                                content_parts.append(f"{message}\n")
                        elif step_name == "step_2_intent_recognition":
                            content_parts.append("**识别结果:**\n")
                            content_parts.append(f"- **查询类型:** `{step_data.get('query_type', '')}`\n")
                            content_parts.append(f"- **本源主体:** {step_data.get('primary_entities_count', 0)} 个\n")
                            content_parts.append(f"- **主体属性:** {step_data.get('entity_attributes_count', 0)} 个\n")
                            content_parts.append(f"- **主体指标:** {step_data.get('entity_metrics_count', 0)} 个\n")
                            content_parts.append(f"- **时间维度:** {step_data.get('time_dimensions_count', 0)} 个\n")
                            
                            # 显示相关表
                            relevant_tables = step_data.get('relevant_tables', [])
                            if relevant_tables:
                                table_names = [t.get('table_name', '') for t in relevant_tables if t.get('table_name')]
                                if table_names:
                                    content_parts.append(f"\n**相关表:** {len(relevant_tables)} 个\n")
                                    tables_str = ', '.join([f"`{name}`" for name in table_names[:10]])
                                    content_parts.append(f"- {tables_str}\n")
                            
                            # 显示相关列（按表分组）
                            relevant_columns = step_data.get('relevant_columns', [])
                            if relevant_columns:
                                columns_by_table = {}
                                for col in relevant_columns:
                                    table_name = col.get('table_name', '')
                                    col_name = col.get('col_name', '')
                                    if table_name and col_name:
                                        if table_name not in columns_by_table:
                                            columns_by_table[table_name] = []
                                        columns_by_table[table_name].append(col_name)
                                
                                if columns_by_table:
                                    content_parts.append(f"\n**相关列:** {len(relevant_columns)} 个\n")
                                    for table_name, cols in list(columns_by_table.items())[:5]:
                                        cols_str = ', '.join([f"`{c}`" for c in cols[:10]])
                                        content_parts.append(f"- `{table_name}`: {cols_str}\n")
                        elif step_name == "step_3_schema_search":
                            content_parts.append("**搜索结果:**\n")
                            content_parts.append(f"- **找到相关表:** **{step_data.get('results_count', 0)}** 个\n")
                            if step_data.get('relevant_tables'):
                                tables = step_data.get('relevant_tables', [])[:5]
                                tables_str = ', '.join([f"`{t.get('table_name', '')}`" for t in tables])
                                content_parts.append(f"- **相关表:** {tables_str}\n")
                            
                            # 显示验证结果
                            validation_result = step_data.get('validation_result', {})
                            is_sufficient = step_data.get('is_sufficient', True)
                            
                            if not is_sufficient:
                                content_parts.append("\n**⚠️ 验证结果:**\n")
                                content_parts.append("当前找到的表不足以完整描述用户查询需求。\n\n")
                                
                                missing_entities = validation_result.get('missing_entities', [])
                                missing_attributes = validation_result.get('missing_attributes', [])
                                missing_metrics = validation_result.get('missing_metrics', [])
                                missing_time_fields = validation_result.get('missing_time_fields', [])
                                
                                if missing_entities:
                                    entities_str = ', '.join(missing_entities)
                                    content_parts.append(f"- **缺失的实体:** {entities_str}\n")
                                
                                if missing_attributes:
                                    attrs_str = ', '.join([a.get('name', a.get('col_name', '')) for a in missing_attributes])
                                    content_parts.append(f"- **缺失的属性:** {attrs_str}\n")
                                
                                if missing_metrics:
                                    metrics_str = ', '.join([m.get('name', m.get('col_name', '')) for m in missing_metrics])
                                    content_parts.append(f"- **缺失的指标:** {metrics_str}\n")
                                
                                if missing_time_fields:
                                    time_str = ', '.join([t.get('name', t.get('col_name', '')) for t in missing_time_fields])
                                    content_parts.append(f"- **缺失的时间字段:** {time_str}\n")
                                
                                suggestion = validation_result.get('suggestion', '')
                                if suggestion:
                                    content_parts.append(f"\n**建议:**\n{suggestion}\n")
                            else:
                                content_parts.append("\n**✅ 验证结果:**\n")
                                content_parts.append("当前找到的表已经足够描述用户查询需求。\n")
                        elif step_name == "step_4_column_search":
                            content_parts.append("**列搜索结果:**\n")
                            content_parts.append(f"- **找到相关列:** **{step_data.get('total_columns_count', 0)}** 个\n")
                        elif step_name == "step_3_sql_generation":
                            content_parts.append("**SQL生成结果:**\n")
                            if step_data.get('sql'):
                                sql_content = step_data.get('sql', '')
                                content_parts.append("**生成的SQL:**\n")
                                content_parts.append(f"```sql\n{sql_content}\n```\n")
                            
                            execution_result = step_data.get('execution_result', {})
                            if execution_result:
                                if execution_result.get('executed'):
                                    row_count = execution_result.get('row_count', 0)
                                    content_parts.append(f"\n**执行结果:** ✅ 成功执行，返回 {row_count} 行数据\n")
                                else:
                                    error = execution_result.get('error', '')
                                    content_parts.append(f"\n**执行结果:** ❌ 执行失败 - {error}\n")
                            
                            # 显示列描述信息
                            columns_with_description = step_data.get('columns_with_description', [])
                            if columns_with_description:
                                content_parts.append(f"\n**使用的列及其描述:**\n")
                                # 按表分组显示
                                columns_by_table = {}
                                for col in columns_with_description:
                                    table_name = col.get('table_name', '')
                                    if table_name not in columns_by_table:
                                        columns_by_table[table_name] = []
                                    columns_by_table[table_name].append(col)
                                
                                for table_name, cols in columns_by_table.items():
                                    content_parts.append(f"\n**表 `{table_name}`:**\n")
                                    for col in cols:
                                        col_name = col.get('col_name', '')
                                        col_type = col.get('col_type', '')
                                        col_desc = col.get('col_description', col_name)
                                        content_parts.append(f"- `{col_name}` ({col_type}): {col_desc}\n")
                            
                            # 显示逻辑计算信息
                            logical_calculations = step_data.get('logical_calculations', [])
                            if logical_calculations:
                                content_parts.append(f"\n**需要的计算:**\n")
                                for lc in logical_calculations:
                                    operation = lc.get('logical_operation', '')
                                    operands = lc.get('operands', [])
                                    description = lc.get('description', '')
                                    if operation:
                                        operands_str = ', '.join([str(op) for op in operands]) if operands else ''
                                        content_parts.append(f"- **{operation}**")
                                        if operands_str:
                                            content_parts.append(f" ({operands_str})")
                                        if description:
                                            content_parts.append(f": {description}")
                                        content_parts.append("\n")
                            
                            is_satisfied = step_data.get('is_satisfied', True)
                            satisfaction_score = step_data.get('satisfaction_score', 1.0)
                            if satisfaction_score < 1.0 or not is_satisfied:
                                content_parts.append(f"\n**满足度:** {satisfaction_score:.2f} ({'✅ 满足' if is_satisfied else '❌ 不满足'}用户需求)\n")
                        elif step_name == "step_5_sql_check":
                            content_parts.append("**SQL检查结果:**\n")
                            is_valid = step_data.get('is_valid', False)
                            is_safe = step_data.get('is_safe', True)
                            content_parts.append(f"- **语法正确:** {'✅ 是' if is_valid else '❌ 否'}\n")
                            content_parts.append(f"- **安全性:** {'✅ 安全' if is_safe else '⚠️ 不安全'}\n")
                            if step_data.get('errors'):
                                errors = step_data.get('errors', [])
                                content_parts.append(f"\n**错误:**\n")
                                for err in errors:
                                    content_parts.append(f"- {err}\n")
                            if step_data.get('warnings'):
                                warnings = step_data.get('warnings', [])
                                content_parts.append(f"\n**警告:**\n")
                                for warn in warnings:
                                    content_parts.append(f"- {warn}\n")
                            if step_data.get('corrected_sql') and step_data.get('corrected_sql') != step_data.get('sql', ''):
                                corrected_sql = step_data.get('corrected_sql', '')
                                content_parts.append(f"\n**修正后的SQL:**\n")
                                content_parts.append(f"```sql\n{corrected_sql}\n```\n")
                        elif step_name == "step_final_result":
                            content_parts.append("**最终结果:**\n")
                            if step_data.get('sql'):
                                sql_content = step_data.get('sql', '')
                                content_parts.append("**最终SQL:**\n")
                                content_parts.append(f"```sql\n{sql_content}\n```\n")
                        elif step_name == "step_4_evaluation":
                            content_parts.append("**评估结果:**\n")
                            quality_score = step_data.get('quality_score', 0)
                            content_parts.append(f"- **质量评分:** `{quality_score:.2f}`\n")
                            is_satisfactory = step_data.get('is_satisfactory', False)
                            content_parts.append(f"- **是否满意:** {'✅ 是' if is_satisfactory else '❌ 否'}\n")
                        elif step_name == "step_5_expansion":
                            content_parts.append("**扩展结果:**\n")
                            content_parts.append(f"- **扩展轮数:** {step_data.get('expansion_rounds', 0)} 轮\n")
                            content_parts.append(f"- **合并结果:** **{step_data.get('merged_results_count', 0)}** 个表\n")
                        elif step_name == "step_6_rerank":
                            content_parts.append("**重排序结果:**\n")
                            if step_data.get('success'):
                                content_parts.append(f"- **重排序成功:** ✅\n")
                                if step_data.get('reranked_count'):
                                    content_parts.append(f"- **重排序后结果数:** **{step_data.get('reranked_count', 0)}** 个\n")
                            else:
                                content_parts.append(f"- **重排序状态:** ⚠️ {step_data.get('message', '重排序失败')}\n")
                        elif step_name == "step_7_artifact":
                            content_parts.append("**Artifact处理结果:**\n")
                            artifacts_count = step_data.get('artifacts_count', 0)
                            content_parts.append(f"- **Artifact数量:** **{artifacts_count}** 个\n")
                        elif step_name == "step_8_system_prompt":
                            content_parts.append("**System Prompt生成结果:**\n")
                            prompt_length = step_data.get('prompt_length', 0)
                            content_parts.append(f"- **Prompt长度:** **{prompt_length}** 字符\n")
                        elif step_name == "step_9_enhance_results":
                            content_parts.append("**增强搜索结果:**\n")
                            enhanced_count = step_data.get('enhanced_results_count', 0)
                            content_parts.append(f"- **增强结果数:** **{enhanced_count}** 个\n")
                        elif step_name == "step_10_schema_selection":
                            content_parts.append("**选择结果:**\n")
                            content_parts.append(f"- **选中表数量:** **{step_data.get('total_tables', 0)}** 个\n")
                            content_parts.append(f"- **选中列数量:** **{step_data.get('total_columns', 0)}** 个\n")
                            if step_data.get('selected_tables'):
                                tables_str = ', '.join(step_data.get('selected_tables', [])[:5])
                                content_parts.append(f"- **选中的表:** `{tables_str}`\n")
                        elif step_name == "step_11_validation":
                            content_parts.append("**校验结果:**\n")
                            is_valid = step_data.get('is_valid', False)
                            content_parts.append(f"- **校验通过:** {'✅ 是' if is_valid else '❌ 否'}\n")
                            validation_score = step_data.get('validation_score', 0)
                            content_parts.append(f"- **校验评分:** `{validation_score:.2f}`\n")
                            if step_data.get('missing_filter_columns'):
                                missing_filter = step_data.get('missing_filter_columns', {})
                                if missing_filter:
                                    content_parts.append("\n**⚠️ 缺失的查询条件列:**\n")
                                    for table_name, cols in missing_filter.items():
                                        if cols:
                                            content_parts.append(f"- `{table_name}`: {', '.join([f'`{c}`' for c in cols])}\n")
                        elif step_name == "step_12_sql_validation":
                            content_parts.append("**SQL生成结果:**\n")
                            if step_data.get('sql'):
                                sql_content = step_data.get('sql', '')
                                content_parts.append("**生成的SQL:**\n")
                                content_parts.append(f"```sql\n{sql_content}\n```\n")
                            if step_data.get('execution_result', {}).get('row_count', 0) > 0:
                                row_count = step_data.get('execution_result', {}).get('row_count', 0)
                                content_parts.append(f"\n**执行结果:** 返回 **{row_count}** 行数据\n")
                        elif step_name == "step_13_specified_sql":
                            content_parts.append("**指定SQL生成结果:**\n")
                            if step_data.get('sql'):
                                sql_content = step_data.get('sql', '')
                                content_parts.append("**指定SQL:**\n")
                                content_parts.append(f"```sql\n{sql_content}\n```\n")
                            if step_data.get('retry_count', 0) > 0:
                                retry_count = step_data.get('retry_count', 0)
                                content_parts.append(f"\n**重试次数:** {retry_count} 次\n")
                            if step_data.get('final_execution_result', {}).get('row_count', 0) > 0:
                                row_count = step_data.get('final_execution_result', {}).get('row_count', 0)
                                content_parts.append(f"\n**执行结果:** 返回 **{row_count}** 行数据\n")
                    else:
                        content_parts.append("**执行状态:** ❌ 执行失败\n")
                        if step_data.get("error"):
                            error_msg = str(step_data.get('error', ''))[:200]
                            content_parts.append(f"\n**错误信息:**\n```\n{error_msg}\n```\n")
                    
                    # 创建并yield步骤结果chunk（Markdown格式）
                    step_content = "".join(content_parts)
                    chunk = self._create_chunk(_id, content=step_content, chunk_type="text", finish_reason="")
                    yield chunk
                    
                except queue.Empty:
                    # 队列为空，继续等待
                    continue
                except Exception as e:
                    logger.error(f"⚠️ 处理步骤结果失败: {e}")
                    traceback.print_exc()
                    break
            
            # 等待后台线程完成
            agent_thread.join(timeout=300)  # 最多等待5分钟
            
            # 获取最终结果
            sql_workflow_result = final_sql_workflow_result
            if not sql_workflow_result:
                chunk = self._create_chunk(_id, content="## ❌ 智能问数失败\n\n**错误:** 未获取到结果", chunk_type="text", finish_reason="stop")
                yield chunk
                return
            if not sql_workflow_result.get("success"):
                error_msg = sql_workflow_result.get("error", "智能问数失败")
                chunk = self._create_chunk(_id, content=f"## ❌ 智能问数失败\n\n**错误信息:** {error_msg}", chunk_type="text", finish_reason="stop")
                yield chunk
                return
            
            # 检查是否是元数据查询
            if sql_workflow_result.get("is_metadata_query"):
                # 是元数据查询，直接显示结果并返回
                query_type = sql_workflow_result.get("query_type", "")
                
                if sql_workflow_result.get("success"):
                    # 查询成功
                    metadata_result = sql_workflow_result.get("metadata_result", {})
                    message = sql_workflow_result.get("message", "")
                    
                    result_content = f"\n## ✅ 数据库元数据查询结果\n\n"
                    result_content += f"**查询类型:** {query_type}\n\n"
                    result_content += f"**查询结果:**\n{message}\n"
                    
                    chunk = self._create_chunk(_id, content=result_content, chunk_type="text", finish_reason="stop")
                    yield chunk
                    return
                else:
                    # 查询失败（表名或列名错误）
                    error_msg = sql_workflow_result.get("error", "元数据查询失败")
                    error_message = sql_workflow_result.get("error_message", error_msg)
                    available_tables = sql_workflow_result.get("available_tables", [])
                    available_columns = sql_workflow_result.get("available_columns", [])
                    
                    result_content = f"\n## ⚠️ 数据库元数据查询错误\n\n"
                    result_content += f"**查询类型:** {query_type}\n\n"
                    result_content += f"**错误信息:** {error_msg}\n\n"
                    
                    if error_message:
                        result_content += f"**详细错误说明:**\n{error_message}\n\n"
                    
                    if available_tables:
                        result_content += f"**可用的表名列表（共 {len(available_tables)} 个）:**\n"
                        for i, table_name in enumerate(available_tables[:30], 1):
                            result_content += f"{i}. `{table_name}`\n"
                        if len(available_tables) > 30:
                            result_content += f"\n... 还有 {len(available_tables) - 30} 个表未显示\n"
                        result_content += "\n"
                    
                    if available_columns:
                        result_content += f"**可用的列名列表（共 {len(available_columns)} 个）:**\n"
                        for i, col_name in enumerate(available_columns[:30], 1):
                            result_content += f"{i}. `{col_name}`\n"
                        if len(available_columns) > 30:
                            result_content += f"\n... 还有 {len(available_columns) - 30} 个列未显示\n"
                        result_content += "\n"
                    
                    chunk = self._create_chunk(_id, content=result_content, chunk_type="text", finish_reason="stop")
                    yield chunk
                    return
            
            # 从sql_workflow_result中提取SQL和列信息
            sql = sql_workflow_result.get("sql", "")
            columns_with_description = sql_workflow_result.get("columns_with_description", [])
            columns_with_table_prefix = sql_workflow_result.get("columns_with_table_prefix", [])  # table.col 格式的列名列表
            logical_calculations = sql_workflow_result.get("logical_calculations", [])
            execution_result = sql_workflow_result.get("execution_result", {})
            
            if not sql:
                logger.warning("⚠️ SQL为空，无法执行")
                chunk = self._create_chunk(_id, content="## ⚠️ 执行失败\n\n**错误:** SQL为空，无法执行查询", chunk_type="text", finish_reason="stop")
                yield chunk
            else:
                logger.info(f"✅ 执行SQL: {sql[:100]}...")
                
                # 从columns_with_description中提取列信息（使用 table.col 格式）
                columns_desc = []  # 列描述（用于CSV表头，使用 table.col 格式）
                columns_types = []  # 列类型
                columns_used = []   # 列名（table.col 格式）
                
                # 优先使用 columns_with_table_prefix（如果存在）
                if columns_with_table_prefix:
                    # 构建列名到描述的映射
                    col_desc_map = {}
                    col_type_map = {}
                    for col in columns_with_description:
                        col_name_with_table = col.get("col_name_with_table", f"{col.get('table_name', '')}.{col.get('col_name', '')}")
                        col_desc_map[col_name_with_table] = col.get("col_description", col.get("col_name", ""))
                        col_type_map[col_name_with_table] = col.get("col_type", "unknown")
                    
                    # 使用 columns_with_table_prefix 中的列名
                    for col_name_with_table in columns_with_table_prefix:
                        columns_used.append(col_name_with_table)
                        columns_types.append(col_type_map.get(col_name_with_table, "unknown"))
                        columns_desc.append(col_desc_map.get(col_name_with_table, col_name_with_table))
                else:
                    # 如果没有 columns_with_table_prefix，从 columns_with_description 构建
                    for col in columns_with_description:
                        col_name = col.get("col_name", "")
                        col_name_with_table = col.get("col_name_with_table", f"{col.get('table_name', '')}.{col_name}")
                        col_type = col.get("col_type", "")
                        col_description = col.get("col_description", col_name)
                        
                        if col_name:
                            # 使用 table.col 格式的列名
                            columns_used.append(col_name_with_table)
                            columns_types.append(col_type or "unknown")
                            columns_desc.append(col_description)
                
                # 如果无法从columns_with_description获取列信息，尝试从SQL执行结果获取
                if not columns_used:
                    logger.warning("⚠️ 无法从columns_with_description获取列信息，将从SQL执行结果中获取")
                    # 先执行SQL获取列信息
                    try:
                        sql_url = db_info.get("db_host", "")
                        sql_port = str(db_info.get("db_port", ""))
                        sql_user = db_info.get("db_user", "")
                        sql_password = db_info.get("db_password", "")
                        sql_database = db_info.get("db_name", "")
                        sql_type = db_info.get("db_type")
                        conn, _ = self.sql_obj.connect_database(sql_url, sql_port, sql_type, sql_database, sql_user, sql_password)
                        cursor = conn.cursor()
                        cursor.execute(sql)
                        
                        # 从cursor.description获取列信息
                        # 尝试从columns_with_description中匹配列名，构建 table.col 格式
                        if cursor.description:
                            # 构建列名映射（原始列名 -> table.col）
                            col_name_mapping = {}
                            for col in columns_with_description:
                                orig_col = col.get("col_name", "")
                                col_with_table = col.get("col_name_with_table", f"{col.get('table_name', '')}.{orig_col}")
                                if orig_col:
                                    col_name_mapping[orig_col.lower()] = col_with_table
                            
                            for desc in cursor.description:
                                orig_col_name = desc[0]  # 原始列名
                                # 尝试映射到 table.col 格式
                                mapped_col_name = col_name_mapping.get(orig_col_name.lower(), orig_col_name)
                                columns_used.append(mapped_col_name)  # 使用 table.col 格式的列名
                                columns_types.append(desc[1] or "unknown")  # 列类型
                                columns_desc.append(mapped_col_name)  # 使用 table.col 格式作为描述
                        
                        conn.close()
                    except Exception as e:
                        logger.error(f"⚠️ 获取列信息失败: {e}")
                        # 如果失败，使用默认值
                        columns_desc = ["列1", "列2"]  # 默认列描述
                        columns_types = ["unknown", "unknown"]
                    
                logger.info(f"📊 提取到 {len(columns_used)} 个列")
                logger.info(f"   - 列名: {columns_used}")
                logger.info(f"   - 列类型: {columns_types}")
                
                # 执行SQL并保存到CSV
                file_name = "conf/tmp/sandbox_files/" + uuid.uuid4().hex[:16]
                read_flag, max_num = self._read_data(sql, db_info, file_name, columns_desc, columns_types)
                
                if not read_flag or max_num == 0:
                    logger.warning(f"⚠️ SQL执行失败或没有数据")
                    error_msg = execution_result.get('error', '未知错误') if execution_result else '未知错误'
                    chunk = self._create_chunk(_id, content=f"SQL执行失败或没有数据: {error_msg}", chunk_type="text", finish_reason="stop")
                    yield chunk
                else:
                    logger.info(f"✅ SQL执行成功，返回 {max_num} 行数据")
                    
                    # 读取CSV文件并生成HTML表格
                    csv_file_path = file_name + ".csv"
                    html_table = self._csv_to_html_table(csv_file_path, max_num, max_rows=10)
                    logger.info(f"📊 生成HTML表格: {'成功' if html_table else '失败'}")
                        
                    # 如果生成了HTML表格，流式返回
                    if html_table: 
                        chunk = self._create_chunk(_id, content=html_table, chunk_type="html_table", finish_reason="")
                        yield chunk

                    # 逻辑计算
                    if logical_calculations:
                        logger.info(f"🔢 开始执行逻辑计算，共 {len(logical_calculations)} 个计算规则")
                        try:
                            logic_result = agentic_sql_run.run_logic_calculation(
                                csv_file_path=csv_file_path,
                                query=query,
                                logical_calculations=logical_calculations,
                                columns_desc=columns_desc,
                                columns_types=columns_types,
                                sql=sql
                            )
                            if logic_result.get("success"):
                                calculation_summary = logic_result.get("calculation_summary", "")
                                calculation_result = logic_result.get("calculation_result", {})
                                tools_used = logic_result.get("tools_used", [])
                                interpretation = logic_result.get("interpretation", {})
                                final_interpretation = logic_result.get("final_interpretation", {})
                                
                                if calculation_result or calculation_summary or interpretation or final_interpretation:
                                    # 构建逻辑计算结果的显示内容
                                    logic_content = "\n\n## 🔢 逻辑计算结果\n\n"
                                    
                                    # 优先显示最终综合解读
                                    if final_interpretation:
                                        overall_summary = final_interpretation.get("overall_summary", "")
                                        question_answer = final_interpretation.get("question_answer", "")
                                        key_findings = final_interpretation.get("key_findings", [])
                                        business_insights = final_interpretation.get("business_insights", [])
                                        limitations = final_interpretation.get("limitations", "")
                                        next_steps = final_interpretation.get("next_steps", "")
                                        
                                        if overall_summary:
                                            logic_content += f"**📊 整体总结：**\n{overall_summary}\n\n"
                                        
                                        if question_answer:
                                            logic_content += f"**❓ 问题回答：**\n{question_answer}\n\n"
                                        
                                        if key_findings:
                                            logic_content += "**🔍 关键发现：**\n"
                                            for i, finding in enumerate(key_findings, 1):
                                                logic_content += f"{i}. {finding}\n"
                                            logic_content += "\n"
                                        
                                        if business_insights:
                                            logic_content += "**💡 业务洞察：**\n"
                                            for i, insight in enumerate(business_insights, 1):
                                                logic_content += f"{i}. {insight}\n"
                                            logic_content += "\n"
                                        
                                        if limitations:
                                            logic_content += f"**⚠️ 局限性说明：**\n{limitations}\n\n"
                                        
                                        if next_steps:
                                            logic_content += f"**🚀 下一步建议：**\n{next_steps}\n\n"
                                    
                                    if calculation_summary:
                                        logic_content += f"**计算摘要：** {calculation_summary}\n\n"
                                    
                                    if tools_used:
                                        logic_content += f"**使用的统计工具：** {', '.join(tools_used)}\n\n"
                                    
                                    # 显示统计结果解读
                                    if interpretation:
                                        interpretation_summary = interpretation.get("interpretation_summary", "")
                                        key_insights = interpretation.get("key_insights", [])
                                        detailed_interpretation = interpretation.get("detailed_interpretation", "")
                                        
                                        if interpretation_summary:
                                            logic_content += f"**📈 统计结果解读摘要：**\n{interpretation_summary}\n\n"
                                        
                                        if key_insights:
                                            logic_content += "**🔎 关键洞察：**\n"
                                            for i, insight in enumerate(key_insights, 1):
                                                logic_content += f"{i}. {insight}\n"
                                            logic_content += "\n"
                                        
                                        if detailed_interpretation:
                                            logic_content += f"**📊 详细解读：**\n{detailed_interpretation}\n\n"
                                    
                                    # if calculation_result:
                                    #     # 格式化统计结果（作为补充信息）
                                    #     logic_content += "**📋 统计结果详情：**\n\n"
                                    #     try:
                                    #         # 将统计结果转换为格式化的JSON字符串
                                    #         stats_json = json.dumps(calculation_result, ensure_ascii=False, indent=2)
                                    #         logic_content += f"```json\n{stats_json}\n```\n\n"
                                    #     except Exception as e:
                                    #         logger.warning(f"⚠️ 格式化统计结果失败: {e}")
                                    #         logic_content += f"{str(calculation_result)}\n\n"
                                    
                                    chunk = self._create_chunk(_id, content=logic_content, chunk_type="text", finish_reason="")
                                    yield chunk
                                    logger.info(f"✅ 逻辑计算完成并返回结果（包含最终解读）")
                                else:
                                    logger.info(f"ℹ️ 逻辑计算完成，但无结果返回")
                            else:
                                error_msg = logic_result.get("error", "未知错误")
                                logger.warning(f"⚠️ 逻辑计算失败: {error_msg}")
                                # 不返回错误，继续执行后续流程
                        except Exception as e:
                            logger.error(f"❌ 逻辑计算执行异常: {e}")
                            traceback.print_exc()
                            # 不返回错误，继续执行后续流程
                    else:
                        logger.info(f"ℹ️ 无需执行逻辑计算（未识别出逻辑计算规则）")
                    
                    # 清理临时文件
                    try:
                        if os.path.exists(csv_file_path):
                            os.remove(csv_file_path)
                        logger.info("✅ 临时文件已清理")
                    except Exception as e:
                        logger.warning(f"⚠️ 清理临时文件失败: {e}")

        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.error(f"❌ chat_with_sql 执行失败: {e}")
            logger.error(f"Traceback: {error_traceback}")
            
            # 流式返回错误消息
            content = f"智能问数执行失败: {str(e)}"
            _id = f"chatcmpl-error-{int(time.time())}"
            chunk = self._create_chunk(_id, content, chunk_type="text", finish_reason="stop")
            yield chunk

    def _get_sql_step_display_titles(self) -> Dict[str, str]:
        """智能问数流程中各步骤的展示标题（步骤名 -> Markdown 标题）。"""
        return {
            "step_1_database_info": "## 📚 步骤1: 获取数据库信息",
            "step_1_2_metadata_query": "## 🔍 步骤1.2: 数据库元数据查询",
            "step_1_5_sql_intent_recognition": "## 🔍 步骤1.5: SQL意图识别",
            "step_1_5_sql_intent_recognition_warning": "### ⚠️ SQL意图识别警告",
            "step_1_5_sql_intent_recognition_final": "### 💬 SQL意图识别结果",
            "step_2_intent_recognition": "## 🧠 步骤2: 意图识别",
            "step_3_sql_generation": "## 💻 步骤3: SQL生成结果",
            "step_final_result": "## ✅ 最终结果",
            "step_4_evaluation": "## 📈 步骤4: 结果评估",
            "step_5_expansion": "## 🚀 步骤5: 扩展搜索",
            "step_6_rerank": "## 🔄 步骤6: 结果重排序",
            "step_7_artifact": "## 🎨 步骤7: Artifact处理",
            "step_8_system_prompt": "## 📝 步骤8: 生成System Prompt",
            "step_9_enhance_results": "## 📊 步骤9: 增强搜索结果",
            "step_10_schema_selection": "## 🎯 步骤10: Schema精确选择",
            "step_11_validation": "## ✅ 步骤11: Schema校验",
            "step_12_sql_validation": "## 🔍 步骤12: SQL生成和校验",
            "step_13_specified_sql": "## 📋 步骤13: 生成指定SQL",
        }

    def _read_data(self, sql, db_info, file_name, columns_desc, columns_types=None):
        """
        读取数据库数据并计算统计指标
        
        Args:
            sql: SQL查询语句
            db_info: 数据库连接信息
            file_name: 输出文件名（不含扩展名）
            columns_desc: 列描述列表（用于CSV表头）
            columns_types: 列类型列表（用于统计计算，可选）
        
        Returns:
            tuple: (是否成功, 数据行数)
        """        
        sql_url = db_info.get("db_host", "")
        sql_port = str(db_info.get("db_port", ""))
        sql_user = db_info.get("db_user", "")
        sql_password = db_info.get("db_password", "")
        sql_database = db_info.get("db_name", "")
        sql_type = db_info.get("db_type")
        conn, _ = self.sql_obj.connect_database(sql_url, sql_port, sql_type, sql_database, sql_user, sql_password)      
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
        except Exception as e:
            logger.error(f"执行SQL失败: {e}")
            if cursor:
                cursor.close()
            return False, 0
        
        csv_f = file_name + ".csv"
        _len = 0
        with open(csv_f, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # 写入表头
            writer.writerow(columns_desc)
            # 写入数据行
            for row in cursor.fetchall():
                tmp_l = list(row)
                writer.writerow(tmp_l)
                _len = _len + 1
        return True, _len
    
    def statictics_data(self, csv_f, columns_desc, columns_types=None):
        """调用统计函数进行数据分析"""
        try:
            # 如果没有提供 columns_types，尝试从数据库获取
            if columns_types is None or len(columns_types) == 0:
                return {}
            # 确保 columns_types 长度与 columns_desc 一致
            if len(columns_types) < len(columns_desc):
                columns_types.extend(["unknown"] * (len(columns_desc) - len(columns_types)))
            elif len(columns_types) > len(columns_desc):
                columns_types = columns_types[:len(columns_desc)]
            
            statistics_result = calculate_statistics(csv_f, columns_types)
            if statistics_result:
                logger.info(f"✅ 统计计算完成，生成了 {len(statistics_result)} 类统计指标")
                # 可以将统计结果保存到文件或返回
                # statistics_file = file_name + "_statistics.json"
                # with open(statistics_file, 'w', encoding='utf-8') as f:
                #     json.dump(statistics_result, f, ensure_ascii=False, indent=2)
                return statistics_result
            else:
                return {}
        except Exception as e:
            logger.warning(f"⚠️ 统计计算失败: {e}")
            logger.error(traceback.format_exc())
            return {}
    
    def _csv_to_html_table(self, csv_file_path: str, max_num, max_rows: int = 50) -> str:
        """
        读取CSV文件并生成HTML表格格式
        
        Args:
            csv_file_path: CSV文件路径
            max_rows: 最大显示行数，默认50行
            max_num: CSV文件总行数
        Returns:
            HTML表格字符串，如果文件不存在或为空则返回空字符串
        """
        try:
            if not os.path.exists(csv_file_path):
                logger.warning(f"CSV文件不存在: {csv_file_path}")
                return ""
            
            total_rows = max_num
            
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                csv_reader = csv.reader(f)
                
                # 读取表头
                headers = next(csv_reader, None)
                if not headers:
                    logger.warning(f"CSV文件为空: {csv_file_path}")
                    return ""
                
                # 生成表头HTML
                header_html = "<thead><tr>"
                for header in headers:
                    header_html += f'<th style="border: 1px solid #ddd; padding: 8px; background-color: #f2f2f2; text-align: left;">{header}</th>'
                header_html += "</tr></thead>"
                # 读取数据行
                body_html = "<tbody>"
                for idx, row in enumerate(csv_reader):
                    if idx < max_rows:
                        body_html += "<tr>"
                        for cell in row:
                            # 转义HTML特殊字符
                            cell_str = str(cell) if cell is not None else ""
                            cell_str = cell_str.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
                            body_html += f'<td style="border: 1px solid #ddd; padding: 8px;">{cell_str}</td>'
                        body_html += "</tr>"
                    else:
                        break
                
                body_html += "</tbody>"
            
            # 构建完整的HTML表格
            html_table = f"""
<table style="border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; font-size: 14px;">
{header_html}
{body_html}
</table>
"""
            
            # 如果数据超过最大行数，添加提示信息
            if total_rows > max_rows:
                html_table += f'<p style="color: #666; font-size: 12px; margin-top: 10px;">注：数据共 {total_rows} 行，此处仅显示前 {max_rows} 行</p>'
            
            logger.info(f"✅ HTML表格生成成功: {csv_file_path}，共 {total_rows} 行，显示 {min(max_rows, total_rows)} 行")
            return html_table
            
        except Exception as e:
            logger.error(f"❌ 生成HTML表格失败: {e}")
            logger.error(traceback.format_exc())
            return ""
        
    def _get_database_info(self, sql_id: str) -> dict:
        """获取数据库基础信息"""
        try:
            # 从SQLite获取数据库连接信息
            base_sql_info = cSingleSqlite.query_base_sql_by_sql_id(sql_id)
            if not base_sql_info:
                logger.warning(f"未找到sql_id {sql_id} 的数据库信息")
                return {}
            # print(base_sql_info)
            # 获取表信息
            tables_info = cSingleSqlite.query_table_sql_by_sql_id(sql_id)
            tables = []
            for table in tables_info:
                table_id = table.get("table_id")
                # 获取列信息
                columns = cSingleSqlite.query_col_sql_by_table_id(table_id)
                tables.append({
                    "table_name": table.get("table_name"),
                    "table_description": table.get("table_description", ""),
                    "columns": [{
                        "col_name": col.get("col_name"),
                        "col_type": col.get("col_type"),
                        "is_nullable": col.get("col_info").get("is_nullable", True),
                        "column_default":col.get("col_info").get("column_default", None),
                        "comment":col.get("col_info").get("comment", None)
                    } for col in columns]
                })

            # 获取关系信息
            relations = cSingleSqlite.query_rel_sql_by_sql_id(sql_id)

            db_info = {
                "db_type": base_sql_info.get("sql_type", "mysql"),
                "db_name": base_sql_info.get("sql_name", ""),
                "db_host": base_sql_info.get("ip", ""),
                "db_port": base_sql_info.get("port", ""),
                "db_user": base_sql_info.get("sql_user_name", ""),
                "db_password": base_sql_info.get("sql_user_password", ""),
                "db_description": base_sql_info.get("sql_description", ""),
                "tables": tables,
                "relations": relations
            }

            return db_info

        except Exception as e:
            logger.error(f"获取数据库信息失败 (sql_id: {sql_id}): {e}")
            return {}

    def _create_chunk(self, _id, content, chunk_type="text", finish_reason="", model="emb-graph-chat-model"):
        """创建流式响应块的辅助函数"""
        # 对于file类型的chunk，确保content只包含文件路径，不包含其他文本
        if chunk_type == "file":
            # 清理content，确保只包含文件路径
            cleaned_content = str(content).strip()
            # 移除可能的换行符和其他空白字符
            cleaned_content = cleaned_content.replace('\n', '').replace('\r', '').strip()
            # 如果content包含多个路径（不应该发生），只取第一个
            if '\n' in cleaned_content or '\r' in cleaned_content:
                logger.warning(f"文件chunk的content包含换行符，已清理: {content}")
                cleaned_content = cleaned_content.split('\n')[0].split('\r')[0].strip()
            content = cleaned_content
            logger.debug(f"创建文件chunk，文件路径: {content}")
        
        # 如果提供了内容，即使finish_reason="stop"，也要包含在delta中
        # 如果content为空且finish_reason="stop"，则delta为空（纯finish chunk）
        if finish_reason == "stop" and not content:
            delta = {}
        else:
            delta = {
                "content": content,
                "type": chunk_type
            }
        
        return {
            "id": _id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": delta,
                    "finish_reason": finish_reason
                }
            ],
            "finish_reason": finish_reason
        }



