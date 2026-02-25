# -*- coding:utf-8 -*-

import redis
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from Config.redis_config import get_redis_connection_params

class RedisDB():
    """
    Redis数据库服务类
    提供对Redis数据库的基本操作封装，包括会话管理和聊天记录存储等功能
    """
    
    def __init__(self, host=None, port=None, db=None, password=None, username=None):
        """
        初始化Redis连接
        
        Args:
            host: Redis服务器地址（可选，默认从.env读取）
            port: Redis服务器端口（可选，默认从.env读取）
            db: 数据库编号（可选，默认从.env读取）
            password: 密码（可选，默认从.env读取）
            username: 用户名（可选，默认从.env读取）
        """
        # 如果未提供参数，从.env文件读取配置
        if host is None or port is None:
            config = get_redis_connection_params()
            self.host = host or config["host"]
            self.port = port or config["port"]
            self.db = db if db is not None else config.get("db", 0)
            self.password = password if password is not None else config.get("password")
            self.username = username if username is not None else config.get("username")
        else:
            self.host = host
            self.port = port
            self.db = db if db is not None else 0
            self.password = password
            self.username = username
        
        # 构建连接参数
        connection_params = {
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "decode_responses": True
        }
        
        if self.password:
            connection_params["password"] = self.password
        
        if self.username:
            connection_params["username"] = self.username
        
        # 建立连接
        self.client = redis.Redis(**connection_params)
    
    def save_user_session(self, session_id: str, user_info: Dict[str, Any]) -> bool:
        """
        保存用户会话信息
        
        Args:
            session_id: 会话ID
            user_info: 用户信息字典
            
        Returns:
            bool: 保存成功返回True，否则返回False
        """
        try:
            key = f"session:{session_id}"
            value = json.dumps(user_info)
            # 设置会话过期时间为1小时
            self.client.setex(key, 3600, value)
            return True
        except Exception as e:
            print(f"保存用户会话失败: {e}")
            return False
    
    def get_user_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户会话信息
        
        Args:
            session_id: 会话ID
            
        Returns:
            Dict: 用户信息字典，不存在或过期返回None
        """
        try:
            key = f"session:{session_id}"
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"获取用户会话失败: {e}")
            return None
    
    def delete_user_session(self, session_id: str) -> bool:
        """
        删除用户会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 删除成功返回True，否则返回False
        """
        try:
            key = f"session:{session_id}"
            self.client.delete(key)
            return True
        except Exception as e:
            print(f"删除用户会话失败: {e}")
            return False
    
    def save_chat_history(self, session_id: str, chat_record: Dict[str, Any]) -> bool:
        """
        保存用户聊天记录（按session_id保存）
        
        Args:
            session_id: 会话ID
            chat_record: 聊天记录字典，应包含timestamp, query, response等字段
            
        Returns:
            bool: 保存成功返回True，否则返回False
        """
        try:
            key = f"chat_history:{session_id}"
            # 添加时间戳作为排序分数
            timestamp = chat_record.get('timestamp', datetime.now().timestamp())
            value = json.dumps(chat_record)
            self.client.zadd(key, {value: timestamp})
            # 保留最近100条记录
            self.client.zremrangebyrank(key, 0, -101)
            return True
        except Exception as e:
            print(f"保存聊天记录失败: {e}")
            return False
    
    def get_chat_history_by_session_id(self, session_id: str) -> List[Dict[str, Any]]:
        """
        通过session_id获取聊天记录
        
        Args:
            session_id: 会话ID
        
        Returns:
            List[Dict]: 聊天记录列表，如果session_id无效或无记录则返回空列表
        """
        try:
            # 使用session_id直接获取聊天记录
            chat_history_key = f"chat_history:{session_id}"
            records = self.client.zrevrange(chat_history_key, 0, -1)  # 获取所有记录
            return [json.loads(record) for record in records]
        except Exception as e:
            print(f"通过session_id获取聊天记录失败: {e}")
            return []

    def update_last_chat_history(self, session_id: str, updated_record: Dict[str, Any]) -> bool:
        """
        更新最后一条聊天记录

        Args:
            session_id: 会话ID
            updated_record: 更新后的聊天记录字典，应包含timestamp, query, response等字段

        Returns:
            bool: 更新成功返回True，否则返回False
        """
        try:
            key = f"chat_history:{session_id}"
            # 获取最后一条记录（分数最高的，即最新的）
            last_records = self.client.zrevrange(key, 0, 0, withscores=True)

            if not last_records:
                print(f"没有找到session_id为{session_id}的聊天记录")
                return False

            # 解析最后一条记录
            last_record_json, last_score = last_records[0]

            # 保留原有的时间戳，如果新记录没有指定时间戳
            if 'timestamp' not in updated_record:
                updated_record['timestamp'] = last_score

            # 删除旧记录
            self.client.zrem(key, last_record_json)

            # 添加更新后的记录
            updated_value = json.dumps(updated_record)
            self.client.zadd(key, {updated_value: updated_record['timestamp']})

            return True
        except Exception as e:
            print(f"更新最后一条聊天记录失败: {e}")
            return False

    def get_last_chat_history(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取最后一条聊天记录

        Args:
            session_id: 会话ID

        Returns:
            Dict: 最后一条聊天记录字典，不存在返回None
        """
        try:
            key = f"chat_history:{session_id}"
            # 获取最后一条记录（分数最高的，即最新的）
            last_records = self.client.zrevrange(key, 0, 0)

            if not last_records:
                return None

            # 解析最后一条记录
            last_record_json = last_records[0]
            return json.loads(last_record_json)
        except Exception as e:
            print(f"获取最后一条聊天记录失败: {e}")
            return None

    def clear_chat_history(self, user_id: str) -> bool:
        """
        清除用户聊天历史记录

        Args:
            user_id: 用户ID

        Returns:
            bool: 清除成功返回True，否则返回False
        """
        try:
            key = f"chat_history:{user_id}"
            self.client.delete(key)
            return True
        except Exception as e:
            print(f"清除聊天记录失败: {e}")
            return False
    
    def close(self):
        """
        关闭Redis连接
        """
        if self.client:
            self.client.close()


# 全局单例实例
cRedisDB = RedisDB()

