import datetime

from Db.redis_db import cRedisDB
from Db.sqlite_db import cSingleSqlite

class CControl():

    def __init__(self):
        self.client = cRedisDB.client

    def get_sessions_by_user_id(self, user_id):
        """
        从会话中获取用户信息
        """
        session_id_lt = cSingleSqlite.search_session_by_user_id(user_id)
        user_sessions = {}
        for session_info in session_id_lt:
            session_id = session_info["session_id"]
            session_name = session_info["session_name"]
            session = cRedisDB.get_chat_history_by_session_id(session_id)
            if session:
                tmp_d = {}
                tmp_d["session"] = session
                tmp_d["session_name"] = session_name
                user_sessions[session_id] = tmp_d
                
        return user_sessions
    
    def delete_session_by_id(self, user_id):
        session_id_lt = cSingleSqlite.search_session_by_user_id(user_id)
        for session_info in session_id_lt:
            session_id = session_info["session_id"]
            cRedisDB.delete_user_session(session_id)
        cSingleSqlite.delete_sessions_by_user_id(user_id)
            
    def delete_session_messages_by_id(self, session_id):
        """
        删除会话消息
        :param session_id: 会话ID
        :return: 删除结果
        """
        return cRedisDB.delete_user_session(session_id)

    def get_session_messages_by_id(self, session_id):
        """
        获取会话消息
        :param session_id: 会话ID
        :return: 会话消息列表
            格式: [{'timestamp': 1763462855.612966, 'query': [{"type":"text", "content":"..."}], 'response': [{"type":"text", "content":"..."}]}, ...]
        """
        message = cRedisDB.get_chat_history_by_session_id(session_id)
        #按时间排序
        if message:
            message = sorted(message, key=lambda x: x['timestamp'])
        #将对话改成问答形式{"role": "user/assistant", "content": "内容"}
        # 注意：现在 query 和 response 都是列表格式 [{"type":"", "content":""}]
        formatted_messages = []
        for msg in message:
            # 处理 query：如果是旧格式（字符串），转换为新格式
            query = msg.get("query", [])
            if isinstance(query, str):
                query = [{"type":"text", "content":query}]
            elif not isinstance(query, list):
                query = [{"type":"text", "content":str(query)}]
            
            # 处理 response：如果是旧格式（字符串），转换为新格式
            response = msg.get("response", [])
            if isinstance(response, str):
                response = [{"type":"text", "content":response}]
            elif not isinstance(response, list):
                response = [{"type":"text", "content":str(response)}]
            
            formatted_messages.append({"role": "user", "content": query})
            formatted_messages.append({"role": "assistant", "content": response})
        return formatted_messages

    # 添加保存用户会话到Redis的功能
    def save_user_session(self, session_id, user_info):
        """
        保存用户会话到Redis数据库
        :param session_id: 会话ID
        :param user_info: 用户信息
        :return: 保存结果
        """
        # 同时保存到Redis和本地字典以确保兼容性
        return cRedisDB.save_user_session(session_id, user_info)

    # 添加保存聊天记录到Redis的功能
    def save_chat_history(self, user_id, session_id, session_name, query, response):
        """
        保存聊天记录到Redis数据库
        :param user_id: 用户ID
        :param session_id: 会话ID
        :param session_name: 会话名称
        :param query: 用户查询，格式为 [{"type":"text", "content":"..."}] 或字符串（兼容旧格式）
        :param response: 系统回复，格式为 [{"type":"text/echarts/html_table", "content":"..."}] 或字符串（兼容旧格式）
        :return: 保存结果
        """
        session = cSingleSqlite.search_session_by_session_id(session_id)
        if session:
            session_name = session["session_name"]
        else:
            param = {"user_id":user_id, "session_id": session_id, "session_name": session_name}
            cSingleSqlite.save_session_info(param)
        
        # 处理 query 参数：如果是字符串，转换为列表格式；如果是列表，直接使用
        if isinstance(query, str):
            query_formatted = [{"type":"text", "content":query}]
        elif isinstance(query, list):
            query_formatted = query
        else:
            query_formatted = [{"type":"text", "content":str(query)}]
        
        # 处理 response 参数：如果是字符串，转换为列表格式；如果是列表，直接使用
        if isinstance(response, str):
            response_formatted = [{"type":"text", "content":response}]
        elif isinstance(response, list):
            response_formatted = response
        else:
            response_formatted = [{"type":"text", "content":str(response)}]
        
        chat_record = {
            "timestamp": datetime.datetime.now().timestamp(),
            "query": query_formatted,
            "response": response_formatted
        }
        return cRedisDB.save_chat_history(session_id, chat_record)

    def delete_user_session(self, session_id):
        """
        删除用户会话
        :param session_id: 会话ID
        :return: 删除结果
        """
        return cRedisDB.delete_user_session(session_id)

    def clear_chat_history(self, user_id):
        """
        清除用户聊天历史记录
        :param user_id: 用户ID
        :return: 清除结果
        """
        return cRedisDB.clear_chat_history(user_id)

    def create_session_info(self, user_id, session_id, session_name, knowledge_name):
        """
        创建会话信息
        :param user_id: 用户ID
        :param session_id: 会话ID
        :param session_name: 会话名称
        :param knowledge_name: 知识库名称
        :return: 保存结果
        """
        param = {"user_id":user_id, "session_id": session_id, "session_name": session_name, "knowledge_name": knowledge_name}
        return cSingleSqlite.save_session_info(param)

    def update_last_chat_record(self, session_id, updated_query=None, updated_response=None):
        """
        更新最后一条聊天记录
        :param session_id: 会话ID
        :param updated_query: 更新后的用户查询，格式为 [{"type":"text", "content":"..."}] 或字符串（兼容旧格式）
        :param updated_response: 更新后的系统回复，格式为 [{"type":"text/echarts/html_table", "content":"..."}] 或字符串（兼容旧格式）
        :return: 更新结果
        """
        # 获取最后一条记录
        last_record = cRedisDB.get_last_chat_history(session_id)
        if not last_record:
            return False

        # 如果没有提供更新的内容，保持原有内容
        if updated_query is not None:
            # 处理 query 参数：如果是字符串，转换为列表格式；如果是列表，直接使用
            if isinstance(updated_query, str):
                query_formatted = [{"type":"text", "content":updated_query}]
            elif isinstance(updated_query, list):
                query_formatted = updated_query
            else:
                query_formatted = [{"type":"text", "content":str(updated_query)}]
        else:
            query_formatted = last_record.get("query", [])

        if updated_response is not None:
            # 处理 response 参数：如果是字符串，转换为列表格式；如果是列表，直接使用
            if isinstance(updated_response, str):
                response_formatted = [{"type":"text", "content":updated_response}]
            elif isinstance(updated_response, list):
                response_formatted = updated_response
            else:
                response_formatted = [{"type":"text", "content":str(updated_response)}]
        else:
            response_formatted = last_record.get("response", [])

        # 构建更新后的记录
        updated_record = {
            "timestamp": last_record.get("timestamp", datetime.datetime.now().timestamp()),
            "query": query_formatted,
            "response": response_formatted
        }

        return cRedisDB.update_last_chat_history(session_id, updated_record)

    def get_last_chat_record(self, session_id):
        """
        获取最后一条聊天记录
        :param session_id: 会话ID
        :return: 最后一条聊天记录，格式为 {'timestamp': timestamp, 'query': [...], 'response': [...]}
        """
        last_record = cRedisDB.get_last_chat_history(session_id)
        if last_record:
            # 格式化返回结果，与get_session_messages_by_id保持一致的格式
            query = last_record.get("query", [])
            response = last_record.get("response", [])

            # 确保query和response是列表格式
            if isinstance(query, str):
                query = [{"type":"text", "content":query}]
            elif not isinstance(query, list):
                query = [{"type":"text", "content":str(query)}]

            if isinstance(response, str):
                response = [{"type":"text", "content":response}]
            elif not isinstance(response, list):
                response = [{"type":"text", "content":str(response)}]

            return {
                "timestamp": last_record.get("timestamp"),
                "query": query,
                "response": response
            }
        return None
        





