# -*- coding:utf-8 -*-

'''
Created on 2025年9月10日

@author: 
'''

import os
import re
import json
# import subprocess
import urllib
import time
import logging
import threading
import copy
import threading
import datetime
# from multiprocessing import Process, Pipe

from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

# from langchain.document_loaders import DirectoryLoader
from langchain_community.document_loaders import DirectoryLoader
from langchain_community.document_loaders import UnstructuredFileLoader

# from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_text_splitters import RecursiveCharacterTextSplitter

# from langchain.text_splitter import CharacterTextSplitter 

from langchain_core.documents import Document

from Control.control_milvus import CControl as ControlMilvus
from Control.control_file import CControl as CFileControl
from Control.control_graph import CControl as ControlGraph
from Control.control_search import CControl as ControlSearch
from Control.control_sessions import CControl as ControlSessions
from Control.control_elastic import CControl as ElasticSearchController
# from Control.control_chat import CControl as ControlChat
# from Control.control_graphiti import CControl as ControlGraphiti
from Graphrag.light_rag import run as graph_run

from Agent import article_theme_run
# from Agent import entity_relation_split_run
# from Agent import text_to_cypher_run

# from Agent.emb_query_run import run_agent

# 导入知识库数据库实例
from Db.sqlite_db import cSingleSqlite

from Config.embedding_config import get_embeddings
from Config.elasticsearch_config import is_elasticsearch_enabled
from Config.milvus_config import is_milvus_enabled
from Config.neo4j_config import is_neo4j_enabled
from Config.pdf_config import is_pdf_advanced_enabled

# 导入 Elasticsearch 控制器
# from Control.control_elastic import get_elastic_controller

from Utils import utils

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

THREAD_LIST = []
# thread_list = []

class CControl():
    
    def __init__(self):
        self.file_obj = CFileControl()
        self.milvus_obj = ControlMilvus()
        self.graph_obj = ControlGraph()
        self.search_obj = ControlSearch()
        self.session_obj = ControlSessions()
        self.elasticsearch_obj = ElasticSearchController()
        # self.graphiti_obj = ControlGraphiti()
    
    def add_file(self, param):        
        _url = ""
        if("url" in param.keys()):
            _url = param["url"]
        # _path = ""
        # if("path" in param.keys()):
        #     _path = param["path"]
        
        file_id = param.get("file_id", "")
        user_name = param.get("user_name", "")
        
        if("permission_level" not in param.keys()):
            permission_level = "public"
        else:
            permission_level = param["permission_level"]
        
        # 获取用户ID
        user_id = param.get("user_id", "")
        
        knowledge_id = param.get("knowledge_id", "")
        
        if not user_id:
            return {"error_code": 5, "error_msg": "用户ID不能为空"}
        
        for t in THREAD_LIST:
            if t.is_alive():
                return {"error_code":4, "error_msg":"The rag process is running, please try again later."}
            else:
                THREAD_LIST.remove(t)
        
        search_param = {"knowledge_id": knowledge_id, "user_id": user_id}
        res_kb = cSingleSqlite.search_knowledge_base_by_id_and_user_id(search_param)
        if(not res_kb):
            return {"error_code":3, "error_msg":"Knowledge base does not exist"}
        
        if(_url):
            _txt, file_name, file_path, file_flag = self.get_txt(_url, user_id, file_id)
            if(file_flag):
                return {"error_code":0, "error_msg":"File already exists"}
            if(_txt is None):
                return {"error_code":1, "error_msg":"Url error"}
        else:
            file_path = param.get("path", "")
            if(not file_path or file_path.strip() == ""):
                return {"error_code":2, "error_msg":"File path is empty"}
            
        # param = {"file_source": file, "text":_txt}
        # content = utils.request_text(param, "/documents/text")
        # res = eval(content)
        # track_id = res.get("track_id", "")
        # if(track_id and track_id.strip() != ""):
       
        file_name = os.path.basename(file_path)
        _lt = cSingleSqlite.search_file_from_name_userid(file_name, user_id)
        if(_lt and len(_lt) > 0):
            return {"error_code":0, "error_msg":"File already exists"}
        res = self.file_path_analysis(knowledge_id, user_id, user_name, file_id, file_path, permission_level, _url)
        return res
    
    def file_path_analysis(self, knowledge_id, user_id, user_name, file_id, file_path, permission_level, _url=""):
        
        # 根据文件类型选择解析方式
        file_extension = os.path.splitext(file_path)[1].lower()
        is_pdf = file_extension == ".pdf"
        is_text_file = file_extension in [".md", ".txt"]
        
        if is_text_file:
            # md 或 txt 文件: 直接读取文本内容
            logger.info(f"使用文本文件读取: {file_path}")
            _txt = self.file_obj.read_txt(file_path)
            if _txt is None:
                logger.error(f"文本文件读取失败: {file_path}")
                return {"error_code": 1, "error_msg": "文本文件读取失败"}
        elif is_pdf and not is_pdf_advanced_enabled():
            # PDF_FLAG=False: 使用初级PDF解析
            logger.info(f"使用初级PDF解析: {file_path}")
            _, content_list = self.file_obj.read_pdf_basic(file_path)
            if content_list is None:
                logger.error(f"初级PDF解析失败: {file_path}")
                return {"error_code": 1, "error_msg": "PDF解析失败，请检查是否安装了PyMuPDF或PyPDF2"}
            _txt = content_list  # 初级解析直接返回文本内容
        else:
            # PDF_FLAG=True 或其他文件类型: 使用高级解析（调用API）
            logger.info(f"使用高级文件解析: {file_path}")
            _, content_list = self.file_obj.read_stream_file(file_path)
            if content_list is None:
                logger.error(f"高级文件解析失败: {file_path}")
                return {"error_code": 1, "error_msg": "文件解析失败"}
            _txt = self.content_list_to_json(content_list, file_id="")
        file_name = os.path.basename(file_path)
        txt, _ = os.path.splitext(file_name)
        file_md_path = file_path.replace(file_name, txt + ".md")
        with open(file_md_path, "w", encoding="utf-8") as f:
            f.write(_txt)
            
        for t in THREAD_LIST:
            if t.is_alive():
                return {"error_code":4, "error_msg":"The rag process is running, please try again later."}
            else:
                THREAD_LIST.remove(t)
        
        # file_id = "file_" + utils.generate_secure_string(length=16)
        _dict = self.get_file_info(_txt, file_name)
        title = _dict["title"]
        authors = _dict["authors"]
        doc_type = _dict["doc_type"]
        summary = _dict["summary"]
        toc_json = _dict["toc"]
        
        upload_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        
        file_info_dict = {"knowledge_id": knowledge_id, "file_id": file_id,
                          "file_name": file_name, "file_path": file_path, 
                          "file_size": os.path.getsize(file_path), "upload_user_id": user_id, 
                          "permission_level": permission_level, "url":_url, 
                          "upload_time":upload_time}
        
        cSingleSqlite.insert_file_basic_info(file_info_dict)
        
        detail_info_dict = {"file_id":file_id,"file_name":file_name,"recognized_title":title,
                            "overview":summary,"authors":authors, "category":doc_type,
                            "create_time":"", "catalog":toc_json}

        cSingleSqlite.insert_file_detail_info(detail_info_dict)

        # 保存 Markdown 内容到 Elasticsearch
        # from Config.elasticsearch_config import is_elasticsearch_enabled
        if is_elasticsearch_enabled():
            elastic_save_success = self.elasticsearch_obj.save_markdown_content(
                knowledge_id=knowledge_id,
                file_id=file_id,
                user_id=user_id,
                permission_level=permission_level,
                file_name=file_name,
                markdown_content=_txt,
                summary=summary,  # 可以后续添加摘要提取
                authors=authors,  # 可以后续添加作者提取
                category=doc_type if 'doc_type' in locals() else ""
            )
            if elastic_save_success:
                logger.info(f"文件 {file_name} 成功保存到 Elasticsearch")
            else:
                logger.warning(f"文件 {file_name} 保存到 Elasticsearch 失败")
        else:
            e = ""
        # except Exception as e:
        #     logger.error(f"保存文件到 Elasticsearch 时出错: {e}")
        
        embedding = get_embeddings()
        index_params = {
            "index_type": "HNSW",
            "metric_type": "IP",
            "params": {}
        }
        # 保存到Milvus（如果启用）
        # from Config.milvus_config import is_milvus_enabled
        if is_milvus_enabled():
            if(len(_txt) < 1000):
                param = {"knowledge_partition": file_id,
                         "knowledge_collection":knowledge_id,
                         "title": title,
                         "data": _txt,
                         "permission_level": permission_level}
            
                self.milvus_obj.add_text(param, embedding, index_params)
                res = {"error_code":0, "error_msg":"Success"}
                return res
            
            # 启动异步线程执行 save_milvus，不阻塞流式响应
            th_milvus = threading.Thread(target=self.save_milvus, args=(file_id, file_md_path, knowledge_id, 
                                                                        title, toc_json, permission_level,
                                                                        embedding, index_params,))
            THREAD_LIST.append(th_milvus)
            th_milvus.start()
        else:
            res = {"error_code":0, "error_msg":"Success"}
            return res
        if is_neo4j_enabled():
            th_graph = threading.Thread(target=self.check_graph, args=(file_md_path, knowledge_id, file_id,
                                                                       title, file_name, permission_level,))
            THREAD_LIST.append(th_graph)
            th_graph.start()
        else:
            res = {"error_code":0, "error_msg":"Success"}
            return res

        # th_graph = threading.Thread(target=self.check_graph, args=(file_md_path, knowledge_id, file_id,
        #                                                            title, file_name, permission_level,))
        # THREAD_LIST.append(th_graph)
        # th_graph.start()
        
        return {"error_code":0, "error_msg":"Success", "file_id":file_id}
    
    def save_milvus(self, file_id, md_path, knowledge_id, title, toc_json, 
                    permission_level, embedding, index_params):
        
        self.save_toc_info(toc_json, file_id, knowledge_id,
                            title, embedding, index_params,
                            permission_level)
        
        self.save_text_vector(md_path, file_id, knowledge_id, 
                              title, embedding, index_params,
                              permission_level)
    
    
    def save_text_vector(self, md_path, partition_core, database_core,
                         title, embedding, index_params, permission_level):
        final_list = self.split_data(md_path)
        for _chunk in final_list:
            modified_text = _chunk
            param = {"knowledge_partition": partition_core,
                     "knowledge_collection":database_core,
                     "title": title,
                     "data": modified_text,
                     "permission_level":permission_level}
        
            self.milvus_obj.add_text(param, embedding, index_params)
        
            # self.graphiti_obj.save_graph(knowledge_id=database_core, file_id=partition_core, title=title, _txt=modified_text, permission_level=permission_level)
    
    def save_toc_info(self, toc_json, partition_core, database_core,
                      title, embedding, index_params, permission_level):
        if(toc_json and len(toc_json) > 0):
            param = {"knowledge_partition": partition_core,
                     "knowledge_collection":database_core,
                     "title": title,
                     "data": str(toc_json),
                     "permission_level":permission_level}

            self.milvus_obj.add_text(param, embedding, index_params)
        
    def save_base_vector(self, partition_core, database_core, title, 
                         summary, embedding, index_params, permission_level):
        param = {"knowledge_partition": partition_core,
                 "knowledge_collection":database_core,
                 "title": title,
                 "data": summary,
                 "permission_level":permission_level}
        
        self.milvus_obj.add_text(param, embedding, index_params)
    
    def get_file_info(self, _txt, file):
        if(len(_txt) > 10000):
            _sub_txt = _txt[0:10000]
            theme_json = article_theme_run.run_sync(_sub_txt)
        else:
            theme_json = article_theme_run.run_sync(_txt)
        
        title = theme_json.get("title", "")
        summary = theme_json.get("summary", "")
        metadata = theme_json.get("metadata", {})
        doc_type = metadata.get("document_type", "Unknown")
        authors = metadata.get("authors", [])
        toc_json = theme_json.get("toc", {})
        
        if(not title or title.strip() == ""):
            if(summary and summary.strip() != ""):
                title = summary
            else:
                title = os.path.basename(file)
        
        _tmp_d = {}
        _tmp_d["title"] = title
        _tmp_d["summary"] = summary
        _tmp_d["doc_type"] = doc_type
        _tmp_d["authors"] = authors
        _tmp_d["toc"] = str(toc_json)
        _tmp_d["file"] = file
        
        return _tmp_d
    
    def get_txt(self, _url, user_id, file_id):
        if(_url):
            path = urlparse(_url).path
            filename = unquote(os.path.basename(path))
            
            file_path = '{}/{}/{}'.format(DOWNFILE, file_id, filename)  # 拼接文件名。
            
            _lt = cSingleSqlite.search_file_from_name_userid(filename, user_id)
            if(_lt and len(_lt) > 0):
                return None, None, None, True
            
            # try:
            res = self.file_obj.down_file(_url, file_path)
            if(res["success"]):
                file_path = res["file_path"]
                # file_size = res["file_size"]
                file_name = unquote(os.path.basename(file_path))
            else:
                return None, None, None, False
            
            file_extension = os.path.splitext(file_path)[1].lower()
            if(file_extension == ".txt"):
                _txt = self.file_obj.read_txt(file_path)
                json_table = self.convert_xml_to_json(_txt)
                _txt = json_table["modified_text"]
            else:
            
                _, content_list = self.file_obj.read_url(_url)
                _txt = self.content_list_to_json(content_list, file_id)
            
            return _txt, file_name, file_path, False
        else:
            return None, None, None, False
    
    def check_graph(self, md_file, database_core, partition_core, 
                    title, file, permission_level):
        graph_path = graph_run(md_file, partition_core)
        # graph_path = os.path.join("lightrag_data", "graph_WWVtiSspiCfwAIsW")
        if(graph_path):
            self.graph_obj.save_graph(graph_path,  
                                      database_core, 
                                      partition_core,
                                      file, permission_level)
        
            self.graph_obj.save_graph_info(graph_path, database_core, 
                                           partition_core, file, title)
        else:
            self.delete_file_by_file_id(database_core, partition_core)
            # self.delete_graph_by_file_id(partition_core)
            self.delete_milvus_by_file_id(database_core, partition_core)
            self.delete_graph_db_by_file_id(partition_core)
            self.delete_graph_file_id(partition_core)
            
    def delete_user(self, param):
        for t in THREAD_LIST:
            if t.is_alive():
                return {"error_code":4, "success": False, "error_msg":"The rag process is running, please try again later."}
            else:
                THREAD_LIST.remove(t)
        user_id = param.get("user_id")
        if not user_id:
            return {"error_code": 3, "success": False, "message": "用户ID不能为空"}

        # 1. 查询用户的所有知识库
        knowledge_bases = cSingleSqlite.query_knowledge_base_by_user_id({"user_id": user_id})
        for kb in knowledge_bases:
            knowledge_id = kb["knowledge_id"]
            # 2. 删除知识库下的所有文件
            file_info = cSingleSqlite.query_file_basic_info_by_knowledge_id(knowledge_id)
            for item in file_info:
                file_id = item["file_id"]
                # 删除文件相关数据
                self.delete_file_by_file_id(knowledge_id, file_id)
                self.delete_milvus_by_file_id(knowledge_id, file_id)
                self.delete_graph_db_by_file_id(file_id)
                self.delete_graph_file_id(file_id)

            # 3. 删除知识库本身
            self.delete_knowledge_base_by_id({"knowledge_id": knowledge_id})
        
        # 4. 删除用户在SQL数据库中的所有自定义SQL
        database_lft = cSingleSqlite.query_base_sql_by_user_id(user_id)
        for db in database_lft:
            sql_id = db["sql_id"]
            cSingleSqlite.delete_base_sql(sql_id)

        # 5. 删除用户在图数据库中的全局数据
        # self.graph_obj.delete_all_graph_by_user(user_id)
        
        # 6. 删除用户聊天记录
        self.session_obj.delete_session_by_id(user_id)

        # 7. 最后删除用户记录
        res = cSingleSqlite.delete_user_by_user_id(param)
        if res:
            return {"error_code": 0, "success": True, "message": "用户及其所有数据删除成功"}
        else:
            return {"error_code": 1, "success": False, "message": "用户删除失败"}
            
    def delete_knowledge(self, param):
        knowledge_id = param["knowledge_id"]
        file_info = cSingleSqlite.query_file_basic_info_by_knowledge_id(knowledge_id)
        for item in file_info:
            file_id = item["file_id"]
            
            self.delete_file_by_file_id(knowledge_id, file_id)
            self.delete_milvus_by_file_id(knowledge_id, file_id)
            self.delete_graph_db_by_file_id(file_id)
            self.delete_graph_file_id(file_id)
            
        self.delete_knowledge_base_by_id(param)
        return True
            
    def delete_milvus_by_file_id(self, knowledge_id, file_id):
        if(is_milvus_enabled()):
            if(self.milvus_obj.milvus_service.has_collection(knowledge_id)):
                if(self.milvus_obj.milvus_service.has_partition(knowledge_id, file_id)):
                    self.milvus_obj.milvus_service.drop_partition(knowledge_id, file_id)
        return True
        
    def delete_graph_db_by_file_id(self, file_id):
        cSingleSqlite.delete_graph_chunk_table(file_id)
        cSingleSqlite.delete_graph_node_table(file_id)
        cSingleSqlite.delete_graph_relation_table(file_id)
        return True
    
    def delete_graph_file_id(self, file_id):
        chunk_lt = cSingleSqlite.query_graph_chunk_by_file_id(file_id)
        for chunk in chunk_lt: 
            chunk_id = chunk["chunk_id"]
            self.graph_obj.delete_node(chunk_id)

    def delete_knowledge_base_by_id(self, param):
        cSingleSqlite.delete_graph_relation_by_knowledge_id(param)
        cSingleSqlite.delete_graph_node_by_knowledge_id(param)
        cSingleSqlite.delete_graph_chunk_by_knowledge_id(param)
        knowledge_id = param["knowledge_id"]
        cSingleSqlite.delete_knowledge_base_by_id(knowledge_id)
        
    def delete_file_by_file_id(self, knowledge_id, file_id):
        param = {"file_id":file_id}
        # cSingleSqlite.delete_vector_file_by_file_id(param)
        _path = os.path.join(WORKING_DIR, file_id)

        file_path = os.path.join("conf/file", file_id)
        utils.remove_path(file_path)

        utils.remove_path(_path)
        file_info = cSingleSqlite.search_file_basic_info_by_file_id(file_id)
        if(file_info):
            file_name = file_info["file_name"]
            upload_user_id = file_info["upload_user_id"]
            _path = os.path.join("conf/file", upload_user_id, file_name)
            utils.remove_path(_path)

        img_file = cSingleSqlite.search_images_by_file_id(file_id)
        for _img in img_file:
            _path = _img["img_path"]
            path = urlparse(_path).path
            img_path = os.path.join(IAMGES_PATH, path)
            utils.remove_path(img_path)

        cSingleSqlite.delete_image_file(param)
        cSingleSqlite.delete_table_data(param)
        cSingleSqlite.delete_file_basic_info(file_id)
        cSingleSqlite.delete_file_detail_info(file_id)

        # 删除 Elasticsearch 中的相关数据
        try:
            # elastic_controller = get_elastic_controller()
            elastic_delete_success = self.elasticsearch_obj.delete_file_elasticsearch_data(file_id)
            if elastic_delete_success:
                logger.info(f"文件 {file_id} 的 Elasticsearch 数据删除成功")
            else:
                logger.warning(f"文件 {file_id} 的 Elasticsearch 数据删除失败")
        except Exception as e:
            logger.error(f"删除文件 {file_id} 的 Elasticsearch 数据时出错: {e}")

        # self.graphiti_obj.delete_graphiti(knowledge_id, file_id)

        return True

    def delete_all_data(self):
        for t in THREAD_LIST:
            if t.is_alive():
                return {"error_code":4, "error_msg":"The rag process is running, please try again later."}
            else:
                THREAD_LIST.remove(t)
        self.delete_all_graph()
        self.delete_all_milvus()
        self.delete_all_elasticsearch()
        # self.graphiti_obj.delete_all_graphiti()
        return {"error_code":0, "error_msg":"SUCCESS"}
    
    def delete_sql_data(self):
        """删除所有SQL数据"""
        user_id_lt = cSingleSqlite.search_user_id()
        for user_id in user_id_lt:
            _d = cSingleSqlite.query_base_sql_by_user_id(user_id)
            for db in _d:
                sql_id = db["sql_id"]
                cSingleSqlite.delete_base_sql(sql_id)
        return {"error_code":0, "error_msg":"SUCCESS"}

    def delete_all_graph(self):
        """删除所有图数据"""
        for t in THREAD_LIST:
            if t.is_alive():
                return {"error_code":4, "error_msg":"The rag process is running, please try again later."}
            else:
                THREAD_LIST.remove(t)
        self.graph_obj.delete_all_graph()
        return {"error_code":0, "error_msg":"SUCCESS"}

    def delete_all_milvus(self):
        """删除所有milvus数据"""
        self.milvus_obj.delete_all_collection()
        return {"error_code":0, "error_msg":"SUCCESS"}
    
    def delete_all_elasticsearch(self):
        """删除所有elasticsearch数据"""
        try:
            # 使用新的删除方法
            # elastic_controller = get_elastic_controller()
            delete_success = self.elasticsearch_obj.delete_all_elasticsearch()

            if delete_success:
                logger.info("✅ 成功删除所有 Elasticsearch 索引和数据")
                return {"error_code": 0, "error_msg": "SUCCESS"}
            else:
                logger.error("❌ 删除所有 Elasticsearch 数据失败")
                return {"error_code": 1, "error_msg": "删除 Elasticsearch 数据失败"}

        except Exception as e:
            logger.error(f"删除所有 Elasticsearch 数据时出错: {e}")
            return {"error_code": 1, "error_msg": f"删除出错: {str(e)}"}
    
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
                    param = {"file_id":file_id, 
                             "table_data":modified_text,
                             "caption":caption,
                             "footnote":footnote,
                             "upload_time":upload_time}
                    cSingleSqlite.insert_table_data(param)
                    
        return _content
                
    def delete_file(self, param):
        for t in THREAD_LIST:
            if t.is_alive():
                return {"error_code":4, "error_msg":"The rag process is running, please try again later."}
            else:
                THREAD_LIST.remove(t)
        if("file_id" not in param.keys()):
            return {"error_code":3, "error_msg":"Error, lack of file."}
        file_id = param["file_id"]
        user_id = param["user_id"]
        #search_param = {"file_id":file_id, "user_id":user_id}
        file_dict = cSingleSqlite.search_file_basic_info_by_file_id(file_id)
        if(not file_dict):
            return {"error_code":4, "error_msg":"Error, the file info is not exist."}
        if(file_dict["upload_user_id"] != user_id):
            return {"error_code":5, "error_msg":"Error, the file is not belong to the user."}
        # database_code = base_info["knowledge_id"]
        partition_core = file_dict["file_id"]
        knowledge_id = file_dict["knowledge_id"]
        paragraph_list = cSingleSqlite.query_graph_chunk_by_file_id(partition_core)
        for _paragraph in paragraph_list:
            paragraph_code = _paragraph["chunk_id"]
            self.graph_obj.delete_node(paragraph_code)
        
        # _path = os.path.join(WORKING_DIR, partition_core)
        # utils.remove_path(_path)
        
        self.delete_graph_db_by_file_id(partition_core)
        self.delete_file_by_file_id(knowledge_id, partition_core)
        
        return {"error_code":0, "error_msg":"Success"}
            
    def post_process_splits(self, splits):
        # Pass 1: Merge HTML blocks
        html_merged_splits = []
        i = 0
        while i < len(splits):
            current_split = splits[i]
            content = current_split.page_content
    
            # A simple heuristic for a split HTML block
            if "<html>" in content and "</html>" not in content:
                merged_content = content
                # Look ahead to find the closing tag
                for j in range(i + 1, len(splits)):
                    next_content = splits[j].page_content
                    merged_content += next_content
                    if "</html>" in next_content:
                        html_merged_splits.append(Document(page_content=merged_content))
                        i = j # Move index past the merged splits
                        break
                else: # If loop finishes without finding a closing tag
                    html_merged_splits.append(Document(page_content=merged_content))
            else:
                html_merged_splits.append(current_split)
            i += 1
    
        return html_merged_splits
    
    
    def split_data(self, _file, chunk_size=512, chunk_overlap=128):
        docs = self.load_files(_file)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, 
                                                       chunk_overlap=chunk_overlap)
        
        all_splits = text_splitter.split_documents(docs)
        processed_splits = self.post_process_splits(all_splits)
        page_list = [split.page_content for split in processed_splits]
        return page_list
    
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
    