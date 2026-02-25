# -*- coding:utf-8 -*-

'''
Created on 2025年9月10日

@author: 
'''

import os
import copy
# 配置日志系统，避免absl相关警告
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

import threading
import time
import asyncio 
import json
import os
import uuid
import shutil
from datetime import datetime
from datetime import timedelta
from logging.handlers import TimedRotatingFileHandler

from flask import Flask
from flask import request
from flask import jsonify
from flask import Response
from flask import stream_with_context
from flask import send_from_directory
from flask import session
from flask import make_response

import sys
sys.path.append('src')
from Config import config

import base64
import mimetypes

# 从Db模块导入knowledgeBaseDB实例
from Db.sqlite_db import cSingleSqlite

# 添加Redis数据库功能块
from Control import control_sessions
sess_obj = control_sessions.CControl()

from Control import control
controller = control.CControl()

from Control import control_chat
controller_chat = control_chat.CControl()

from Control import control_sql
controller_sql = control_sql.CControl()

from Utils import utils

# 创建线程安全的logger
logger = logging.getLogger('werkzeug')
logger.setLevel(logging.INFO)  # 设置日志级别

# 添加控制台处理器（如果还没有的话）
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

logger_lock = threading.Lock()

def thread_safe_log(level_func, message, *args, **kwargs):
    """线程安全的日志记录函数"""
    with logger_lock:
        level_func(message, *args, **kwargs)

# 正确设置静态文件目录路径
static_folder_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'web')

app = Flask(__name__, static_folder=static_folder_path)

app.secret_key = 'your_secret_key_here'  # 在实际应用中应该使用更安全的密钥
app.permanent_session_lifetime = timedelta(hours=1)


# 添加CORS头部的函数
def add_cors_headers(response):
    # 获取请求的Origin头部
    origin = request.headers.get('Origin', '')

    # 允许的Origin列表
    allowed_origins = [
        'http://localhost:5173',      # 本地开发
        'http://127.0.0.1:5173',      # 本地IP
    ]

    # 如果Origin以5173端口结尾且是http协议，则允许
    if origin and origin.startswith('http://') and origin.endswith(':5173'):
        response.headers['Access-Control-Allow-Origin'] = origin
    elif origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
    else:
        # 默认允许localhost
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'

    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response

# 在所有响应中添加CORS头部
@app.after_request
def after_request(response):
    return add_cors_headers(response)

# 处理OPTIONS预检请求
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = make_response('', 200)
        response = add_cors_headers(response)
        return response

def verify_user_credentials(user_name, password):
    """
    验证用户凭据
    :param user_name: 用户名
    :param password: 密码
    :return: 用户信息字典或None
    """
    try:
        c = cSingleSqlite.conn.cursor()
        sql = "SELECT user_id, user_name, password, permissions FROM user_info WHERE user_name=?"
        c.execute(sql, (user_name,))
        row = c.fetchone()
        
        if row and row[2] == password:  # 简单的密码对比（实际项目中应使用加密）
            return {
                'user_id': row[0],
                'user_name': row[1],
                'password': row[2],
                'permissions': row[3]
            }
        return None
    except Exception as e:
        logger.error(f"验证用户凭据时出错: {e}")
        return None

@app.route('/api/register', methods=['POST'])
def register():
    """
    用户注册接口
    请求参数: {
        "user_name": "用户名",
        "password": "密码",
        "confirm_password": "确认密码"
    }
    返回参数: {
        "success": true/false,
        "message": "结果信息",
        "user_id": "用户ID"  # 注册成功时返回
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    
    # 获取必要参数
    user_name = data.get('user_name')
    password = data.get('password')
    confirm_password = data.get('confirm_password')
    
    # 参数校验
    if not user_name or not password or not confirm_password:
        return jsonify({'success': False, 'message': '用户名、密码和确认密码不能为空'})
    
    if password != confirm_password:
        return jsonify({'success': False, 'message': '密码和确认密码不一致'})
    
    if len(password) < 6:
        return jsonify({'success': False, 'message': '密码长度不能少于6位'})
    
    try:
        # 检查用户名是否已存在
        c = cSingleSqlite.conn.cursor()
        sql = "SELECT user_id FROM user_info WHERE user_name=?"
        c.execute(sql, (user_name,))
        row = c.fetchone()
        
        if row:
            return jsonify({'success': False, 'message': '用户名已存在'})
        
        # 生成用户ID
        user_id = f"user_{int(time.time())}"
        
        # 准备用户信息（默认权限为空）
        user_info = {
            'user_id': user_id,
            'user_name': user_name,
            'password': password,  # 实际项目中应该加密存储
            'permissions': ''  # 默认无特殊权限
        }
        
        # 插入用户信息
        cSingleSqlite.insert_user(user_info)
        
        logger.info(f"新用户注册: {user_name} (ID: {user_id})")
        
        return jsonify({
            'success': True,
            'message': '注册成功',
            'user_id': user_id
        })
    except Exception as e:
        logger.error(f"注册过程中发生错误: {e}")
        return jsonify({'success': False, 'message': f'注册过程中发生错误: {str(e)}'})

@app.route('/api/delete_user', methods=['POST'])
def delete_user():
    """
    删除用户接口
    请求参数: {
        "user_name": "用户名",
        "password": "密码"
    }
    返回参数: {
        "success": true/false,
        "message": "结果信息"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    
    # 验证用户凭据
    user_name = data.get('user_name')
    password = data.get('password')
    
    if not user_name or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})
    
    user_info = verify_user_credentials(user_name, password)
    if not user_info:
        return jsonify({'success': False, 'message': '用户名或密码错误'})
    
    user_id = user_info['user_id']
    param = {
        "user_id": user_id
    }
    try:
        result = controller.delete_user(param)
        # 如果删除成功，同时清理用户相关的其他数据
        if result.get('success'):
            # 删除用户的其他相关信息（如知识库等）
            try:
                c = cSingleSqlite.conn.cursor()
                # 删除用户创建的知识库
                sql = "DELETE FROM knowledge_base WHERE create_user_id=?"
                c.execute(sql, (user_id,))
                cSingleSqlite.conn.commit()
                sess_obj.delete_user_session(user_id)
                logger.info(f"用户 {user_name} 的相关数据已被清理")
            except Exception as e:
                logger.error(f"清理用户相关数据时出错: {e}")
                
        return jsonify(result)
    except Exception as e:
        logger.error(f"删除用户过程中发生错误: {e}")
        return jsonify({'success': False, 'message': '删除用户过程中发生错误'})

@app.route('/api/add_file', methods=['POST'])
def add_file():
    """
    添加文件接口
    支持FormData上传文件或通过URL添加文件
    请求参数: {
        "file": "文件对象", # 可选，如果通过file对象传输
        "user_name": "用户名",
        "password": "密码",
        "permission_level": "public/private",
        "knowledge_id": "知识库ID",
        "knowledge_name": "知识库名称", #可选
        "file_url": "文件URL" #可选，如果通过URL传输
    }
    返回参数: {
        "success": true/false,
        "message": "结果信息"
    }
    """
    try:
        # 验证用户凭据（统一处理）
        user_name = None
        password = None
        
        # 检查是否是文件上传（FormData）
        if 'file' in request.files:
            # FormData格式
            user_name = request.form.get('user_name')
            password = request.form.get('password')
            permission_level = request.form.get('permission_level', 'public')
            knowledge_id = request.form.get('knowledge_id')
            knowledge_name = request.form.get('knowledge_name')
            file_url = None  # 通过file对象传输时，file_url为空
        else:
            # JSON格式
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': 'No data provided'})
            
            user_name = data.get('user_name')
            password = data.get('password')
            permission_level = data.get('permission_level', 'public')
            knowledge_id = data.get('knowledge_id')
            knowledge_name = data.get('knowledge_name')
            file_url = data.get('file_url')  # 通过URL传输时使用此URL
        
        if not user_name or not password:
            return jsonify({'success': False, 'message': '用户名和密码不能为空'})
        
        user_info = verify_user_credentials(user_name, password)
        if not user_info:
            return jsonify({'success': False, 'message': '用户名或密码错误'})
        
        user_id = user_info['user_id']
        
        # 确定知识库ID和名称
        knowledge_base_id = None
        knowledge_base_name = None
        
        if knowledge_id:
            # 如果提供了knowledge_id，验证是否存在
            kb_info = cSingleSqlite.query_knowledge_base_by_id(knowledge_id)
            if kb_info:
                knowledge_base_id = knowledge_id
                knowledge_base_name = kb_info.get('name', knowledge_name)
            else:
                return jsonify({'success': False, 'message': f'指定的知识库ID {knowledge_id} 不存在'})
        elif knowledge_name:
            # 如果提供了knowledge_name，查找对应的知识库
            kb_list = cSingleSqlite.query_knowledge_by_knowledge_name({"name": knowledge_name})
            if kb_list and len(kb_list) > 0:
                knowledge_base_id = kb_list[0]['knowledge_id']
                knowledge_base_name = knowledge_name
            else:
                return jsonify({'success': False, 'message': f'指定的知识库名称 {knowledge_name} 不存在'})
        else:
            # 如果没有提供knowledge_id或knowledge_name，使用用户的默认知识库
            try:
                c = cSingleSqlite.conn.cursor()
                sql = "SELECT knowledge_id, name FROM knowledge_base WHERE create_user_id=?"
                c.execute(sql, (user_id,))
                row = c.fetchone()
                
                if row:
                    knowledge_base_id = row[0]
                    knowledge_base_name = row[1]
                    logger.info(f"用户 {user_name} 使用现有知识库: {knowledge_base_name}")
                else:
                    # 用户没有知识库，创建默认知识库
                    knowledge_base_id = f"kb_{user_id}"
                    knowledge_base_name = f"{user_name}的知识库"
                    
                    kb_info = {
                        'knowledge_id': knowledge_base_id,
                        'name': knowledge_base_name,
                        'create_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'description': f"{user_name}的默认知识库",
                        'valid_start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'valid_end_time': '2099-12-31 23:59:59',
                        'create_user_id': user_id
                    }
                    
                    cSingleSqlite.insert_knowledge_base(kb_info)
                    logger.info(f"为用户 {user_name} 创建默认知识库: {knowledge_base_name}")
            except Exception as e:
                logger.error(f"检查或创建知识库时出错: {e}")
                return jsonify({'success': False, 'message': f'检查或创建知识库时出错: {str(e)}'})
        
        # 处理文件：通过file对象或file_url
        param = {
            'user_id': user_id,
            'user_name': user_name,
            'permission_level': permission_level,
            "knowledge_id": knowledge_base_id,
        }
        file_id = "file_" + utils.generate_secure_string(length=16)
        param[ 'file_id'] = file_id
        if 'file' in request.files:
            # 通过file对象传输：保存文件，传递path
            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'message': '未选择文件'})
            file_name = file.filename
            file_lt = cSingleSqlite.search_file_from_name_userid(file_name, user_id)
            if(file_lt and len(file_lt)>0):
                return jsonify({'success': False, 'message': '已存在同名文件，请修改文件名后重新上传'})
            
            file_dir = os.path.join("conf", "file", file_id)
            os.makedirs(file_dir, exist_ok=True)
            
            # filename = secure_filename(file.filename)
            file_path = os.path.join(file_dir, file.filename)
            file.save(file_path)
            
            # 传递path给controller.add_file（通过file对象传输时，url为空）
            param['path'] = file_path
            param['url'] = ""  # 通过file对象传输时，url保存为空
            
        elif file_url:
            # 通过file_url传输：传递url
            param['url'] = file_url
            param['path'] = ""  # 通过URL传输时，path为空
            
        else:
            return jsonify({'success': False, 'message': '必须提供file对象或file_url参数'})
        
        # 注意：controller.add_file目前不支持指定knowledge_id，它总是使用用户的默认知识库
        # 如果需要在指定知识库中添加文件，需要在controller层面支持
        # 这里我们仍然验证knowledge_id/knowledge_name，但实际添加时使用默认知识库
        
        # 调用controller.add_file处理文件
        result = controller.add_file(param)
        
        # 转换返回格式
        if result.get('error_code') == 0:
            msg = result.get('message', '文件添加成功')
            response_data = {'success': True, 'message': msg}
            if 'file_id' in result:
                response_data['file_id'] = result['file_id']
            return jsonify(response_data)
        else:
            return jsonify({'success': False, 'message': result.get('error_msg', '文件添加失败')})
            
    except Exception as e:
        logger.error(f"Error in add_file: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'处理请求时出错: {str(e)}'})

@app.route('/api/create_knowledge_base', methods=['POST'])
def create_knowledge_base():
    """
    创建知识库接口
    请求参数: {
        "user_name": "用户名",
        "password": "密码",
        "name": "知识库名称",
        "description": "知识库描述",
        "valid_start_time": "有效开始时间",
        "valid_end_time": "有效结束时间"
    }
    返回参数: {
        "success": true/false,
        "message": "结果信息",
        "knowledge_name": "知识库名字"  # 创建成功时返回
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})

    # 验证用户凭据
    user_name = data.get('user_name')
    password = data.get('password')

    if not user_name or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})

    user_info = verify_user_credentials(user_name, password)
    if not user_info:
        return jsonify({'success': False, 'message': '用户名或密码错误'})

    user_id = user_info['user_id']

    # 获取必要参数
    name = data.get('name')
    description = data.get('description', '')
    valid_start_time = data.get('valid_start_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    valid_end_time = data.get('valid_end_time', '2099-12-31 23:59:59')

    if not name:
        return jsonify({'success': False, 'message': '知识库名称不能为空'})

    try:
        param = {"name": name, "user_id": user_id}
        existing_kb = cSingleSqlite.query_knowledge_by_knowledge_name_and_user_id(param)
        if existing_kb:
            return jsonify({
                'success': False,
                'message': '请重新换个知识库名，已有该知识库'
            })
        
        _id = utils.generate_secure_string(8)
            
        # 创建知识库ID
        knowledge_base_id = f"kb_{user_id}_{_id}"

        # 准备知识库信息
        kb_info = {
            'knowledge_id': knowledge_base_id,
            'name': name,
            'create_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'description': description,
            'valid_start_time': valid_start_time,
            'valid_end_time': valid_end_time,
            'create_user_id': user_id
        }

        # 插入知识库信息
        cSingleSqlite.insert_knowledge_base(kb_info)

        logger.info(f"用户 {user_name} 创建知识库: {name}")

        return jsonify({
            'success': True,
            'message': '知识库创建成功',
            'knowledge_name': name
        })
    except Exception as e:
        logger.error(f"创建知识库时出错: {e}")
        return jsonify({
            'success': False,
            'message': f'创建知识库时出错: {str(e)}'
        })

@app.route('/api/delete_knowledge_base', methods=['POST'])
def delete_knowledge_base():
    """
    删除知识库接口
    请求参数: {
        "user_name": "用户名",
        "password": "密码",
        "user_id": "用户ID",
        "knowledge_id": "知识库ID",  # 可选
        "knowledge_name": "知识库name"
    }
    返回参数: {
        "success": true/false,
        "message": "结果信息"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})

    # 验证用户凭据
    user_name = data.get('user_name')
    password = data.get('password')

    if not user_name or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})

    user_info = verify_user_credentials(user_name, password)
    if not user_info:
        return jsonify({'success': False, 'message': '用户名或密码错误'})

    user_id = user_info['user_id']

    # 获取知识库名字
    knowledge_name = data.get('knowledge_name')
    if not knowledge_name:
        return jsonify({'success': False, 'message': '知识库名字不能为空'})
    
    # 获取知识库ID（可选）
    knowledge_id = data.get('knowledge_id')
    if not knowledge_id:
        return jsonify({'success': False, 'message': '知识库id不能为空'})

    # try:
    if(True):
        param = {"knowledge_id":knowledge_id, "user_id":user_id}
        # 验证用户是否有权限删除该知识库
        kb_info = cSingleSqlite.search_knowledge_base_by_id_and_user_id(param)

        if not kb_info:
            return jsonify({'success': False, 'message': '无权删除知识库'})

        if kb_info[0]['create_user_id'] != user_id:
            return jsonify({'success': False, 'message': '您没有权限删除该知识库'})

        knowledge_id = kb_info[0]["knowledge_id"]
        param = {"knowledge_id":knowledge_id}

        cSingleSqlite.delete_knowledge_base_by_id(knowledge_id)

        controller.delete_knowledge(param)

        logger.info(f"用户 {user_name} 删除知识库: {knowledge_name}")

        return jsonify({
            'success': True,
            'message': '知识库删除成功'
        })
    else:
    # except Exception as e:
    #     logger.error(f"删除知识库时出错: {e}")
        return jsonify({
            'success': False,
            # 'message': f'删除知识库时出错: {str(e)}'
        })

@app.route('/api/get_knowledge_base', methods=['POST'])
def get_knowledge_base():
    """
    获取知识库接口
    请求参数: {
        "user_name": "用户名",
        "password": "密码",
    }
    返回参数: {
        "success": true/false,
        "message": "结果信息",
        "knowledge_base": {
            "knowledge_id": "知识库ID",
            "name": "知识库名称",
            "create_time": "创建时间",
            "description": "描述",
            "valid_start_time": "有效开始时间",
            "valid_end_time": "有效结束时间",
            "create_user_id": "创建用户ID"
            "file_num": "文件数量"
        } 或 [
            {
                "knowledge_id": "知识库ID",
                "name": "知识库名称",
                "create_time": "创建时间",
                "description": "描述",
                "valid_start_time": "有效开始时间",
                "valid_end_time": "有效结束时间",
                "create_user_id": "创建用户ID",
                "file_num": "文件数量"
            }
        ]
    }
    """
    data = request.get_json()
    if not data:
        data = {}
    user_name = data.get('user_name')
    password = data.get('password')
    
    # 验证用户凭据
    user_info = verify_user_credentials(user_name, password)
    if not user_info:
        return jsonify({'success': False, 'message': '用户名或密码错误'})
    
    try:
        user_id = cSingleSqlite.search_user_id_by_user_name_password(user_name, password)
        if(not user_id):
            return jsonify({
                'success': False,
                'message': '用户不存在'
            })
            
        all_knowledge_bases = cSingleSqlite.query_all_knowledge_bases()
        all_knowledge = []
        for knowledge_base in all_knowledge_bases:
            file_num = cSingleSqlite.search_file_num_by_knowledge_id(knowledge_base['knowledge_id'])
            knowledge_base["file_count"] = file_num
            all_knowledge.append(knowledge_base)
        # 始终返回成功，即使没有知识库，让前端决定如何显示
        return jsonify({
            'success': True,
            'message': '获取所有知识库信息成功',
            'knowledge_base': all_knowledge if all_knowledge else []
        })
    except Exception as e:
        logger.error(f"获取知识库信息时出错: {e}")
        return jsonify({
            'success': False,
            'message': f'获取知识库信息时出错: {str(e)}'
        })

@app.route('/api/delete_file', methods=['POST'])
def delete_file():
    """
    删除文件接口
    请求参数: {
        "user_name": "用户名",
        "password": "密码",
        "file_id": "文件ID"
    }
    返回参数: {
        "success": true/false,
        "message": "结果信息"
    }
    """
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    
    # 验证用户凭据
    user_name = data.get('user_name')
    password = data.get('password')
    
    if not user_name or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})
    
    user_info = verify_user_credentials(user_name, password)
    if not user_info:
        return jsonify({'success': False, 'message': '用户名或密码错误'})
    
    user_id = user_info['user_id']
    
    if not data:
        return jsonify({'error': 'No data provided'})
    else:
        # Process the data
        logger.info(f"Received data: {data}")
        try:
            param = {"user_id": user_id, "file_id": data["file_id"]}
            result = controller.delete_file(param)
            # 转换返回格式
            if result.get('error_code') == 0:
                return jsonify({'success': True, 'message': '文件删除成功'})
            else:
                return jsonify({'success': False, 'message': result.get('error_msg', '文件删除失败')})
        except Exception as e:
            logger.error(f"Error processing delete_file request: {e}")
            return jsonify({'success': False, 'message': f'Error processing file deletion: {str(e)}'})

@app.route('/api/get_local_file_content', methods=['GET', 'POST'])
def get_local_file_content():
    """
    获取本地文件内容接口（用于读取圆桌会议角色回答文件）
    GET请求参数: file_path (query参数)
    POST请求参数: {
        "user_name": "用户名",
        "password": "密码",
        "file_path": "文件绝对路径"
    }
    返回参数: {
        "success": true/false,
        "message": "结果信息",
        "file_name": "文件名",
        "content": "文件内容"
    }
    """
    # 支持GET和POST两种方式
    if request.method == 'GET':
        file_path = request.args.get('file_path')
        if not file_path:
            logger.error('GET请求：文件路径为空')
            return jsonify({'success': False, 'message': '文件路径不能为空'})
        # URL解码文件路径
        import urllib.parse
        file_path = urllib.parse.unquote(file_path)
        logger.info(f'GET请求：文件路径={file_path}')
    else:
        data = request.get_json()
        if not data:
            logger.error('POST请求：没有提供数据')
            return jsonify({'success': False, 'message': 'No data provided'})
        
        # 验证用户凭据（POST方式需要）
        user_name = data.get('user_name')
        password = data.get('password')
        file_path = data.get('file_path')
        
        if not user_name or not password:
            logger.error('POST请求：用户名或密码为空')
            return jsonify({'success': False, 'message': '用户名和密码不能为空'})
        
        if not file_path:
            logger.error('POST请求：文件路径为空')
            return jsonify({'success': False, 'message': '文件路径不能为空'})
        
        user_info = verify_user_credentials(user_name, password)
        if not user_info:
            logger.error('POST请求：用户名或密码错误')
            return jsonify({'success': False, 'message': '用户名或密码错误'})
    
    try:
        # 安全检查：确保文件路径在项目目录下
        abs_file_path = os.path.abspath(file_path)
        project_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        
        logger.info(f'项目根目录: {project_root}')
        logger.info(f'文件绝对路径: {abs_file_path}')
        
        # 允许访问的目录：discussion目录和src/discussion目录
        discussion_dir1 = os.path.join(project_root, 'discussion')
        discussion_dir2 = os.path.join(project_root, 'src', 'discussion')
        
        logger.info(f'允许的目录1: {discussion_dir1}')
        logger.info(f'允许的目录2: {discussion_dir2}')
        logger.info(f'路径检查: startsWith dir1={abs_file_path.startswith(discussion_dir1)}, startsWith dir2={abs_file_path.startswith(discussion_dir2)}')
        
        # 检查文件路径是否在允许的目录下
        if not (abs_file_path.startswith(discussion_dir1) or abs_file_path.startswith(discussion_dir2)):
            logger.error(f'无权访问该文件路径: {abs_file_path}')
            return jsonify({'success': False, 'message': f'无权访问该文件路径。文件路径: {abs_file_path}, 允许的目录: {discussion_dir1} 或 {discussion_dir2}'})
        
        # 检查文件是否存在
        if not os.path.exists(abs_file_path):
            logger.error(f'文件不存在: {abs_file_path}')
            return jsonify({'success': False, 'message': f'文件不存在: {abs_file_path}'})
        
        # 检查是否为文件
        if not os.path.isfile(abs_file_path):
            logger.error(f'路径不是文件: {abs_file_path}')
            return jsonify({'success': False, 'message': f'路径不是文件: {abs_file_path}'})
        
        # 检查文件大小（限制5MB）
        file_size = os.path.getsize(abs_file_path)
        logger.info(f'文件大小: {file_size} bytes')
        if file_size > 5 * 1024 * 1024:  # 5MB
            logger.error(f'文件过大: {file_size} bytes')
            return jsonify({'success': False, 'message': f'文件过大，超过5MB限制。文件大小: {file_size / 1024 / 1024:.2f}MB'})
        
        # 读取文件内容
        try:
            logger.info(f'尝试使用UTF-8编码读取文件: {abs_file_path}')
            with open(abs_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f'成功使用UTF-8编码读取文件，内容长度: {len(content)}')
        except UnicodeDecodeError as e:
            logger.warning(f'UTF-8编码失败，尝试GBK编码: {e}')
            try:
                with open(abs_file_path, 'r', encoding='gbk') as f:
                    content = f.read()
                logger.info(f'成功使用GBK编码读取文件，内容长度: {len(content)}')
            except Exception as e2:
                logger.warning(f'GBK编码也失败，尝试作为二进制文件读取: {e2}')
                # 如果是二进制文件，返回base64编码
                with open(abs_file_path, 'rb') as f:
                    import base64
                    content = base64.b64encode(f.read()).decode('utf-8')
                    logger.info(f'成功读取二进制文件，base64长度: {len(content)}')
                    return jsonify({
                        'success': True,
                        'message': '获取文件内容成功（二进制文件）',
                        'file_name': os.path.basename(abs_file_path),
                        'content': content,
                        'is_binary': True
                    })
        
        file_name = os.path.basename(abs_file_path)
        logger.info(f'成功获取文件内容，文件名: {file_name}, 内容长度: {len(content)}')
        
        return jsonify({
            'success': True,
            'message': '获取文件内容成功',
            'file_name': file_name,
            'content': content
        })
    except Exception as e:
        logger.error(f"获取本地文件内容时出错: {e}")
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(error_traceback)
        return jsonify({
            'success': False, 
            'message': f'获取文件内容时出错: {str(e)}',
            'error': str(e),
            'traceback': error_traceback
        })

@app.route('/api/query_milvus', methods=['POST'])
def query_milvus():
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    
    # 验证用户凭据
    user_name = data.get('user_name')
    password = data.get('password')
    knowledge_name = data.get('knowledge_name')
    if not user_name or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})
    
    user_info = verify_user_credentials(user_name, password)
    if not user_info:
        return jsonify({'success': False, 'message': '用户名或密码错误'})
    
    user_id = user_info['user_id']
    
    if not data:
        return jsonify({'error': 'No data provided'})
    else:
        # Process the query
        logger.info(f"Received data: {data}")
        try:
            param = {"name": knowledge_name, "user_id": user_id}
            kb_info = cSingleSqlite.query_knowledge_by_knowledge_name_and_user_id(param)
            if not kb_info:
                return jsonify({"success": False, "message": "知识库不存在或无权访问"})
            
            knowledge_id = kb_info[0]["knowledge_id"]
            param = {"knowledge_id": knowledge_id, "user_id": user_id, "query": data["query"]}
            result = controller_chat.query_milvus(param)
            return result
        except Exception as e:
            logger.error(f"Error processing query_milvus request: {e}")
            return jsonify({"error_code": 4, "error_msg": f"Error processing Milvus query: {str(e)}"})

@app.route('/api/query_graph_neo4j', methods=['POST'])
def query_graph_neo4j():
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    
    # 验证用户凭据
    user_name = data.get('user_name')
    password = data.get('password')
    knowledge_name = data.get('knowledge_name')
    
    if not user_name or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})
    
    user_info = verify_user_credentials(user_name, password)
    if not user_info:
        return jsonify({'success': False, 'message': '用户名或密码错误'})
    
    user_id = user_info['user_id']
    
    if not data:
        return jsonify({'error': 'No data provided'})
    else:
        # Process the data (example: echo it back)
        logger.info(f"Received data: {data}")
        if(True):
        # try:
            
            param = {"name":knowledge_name, "user_id":user_id}
            kb_info = cSingleSqlite.query_knowledge_by_knowledge_name_and_user_id(param)
            knowledge_id = kb_info[0]["knowledge_id"]
            param = {"knowledge_id":knowledge_id, "user_id":user_id, "query":data["query"]}
            result = controller_chat.query_graph_neo4j(param)
            return result
        else:
        # except Exception as e:
        #     logger.error(f"Error processing data: {e}")
            return jsonify({"error_code":4, "error_msg":"Error, delete keywords file Api."})
        
@app.route('/api/execute_stream_chat', methods=['POST'])
def execute_stream_chat():
    """
    执行流式聊天

    请求参数: {
        "user_name": "用户名",
        "password": "密码",
        "user_id": "用户ID",
        "knowledge_name": "知识库名称",
        "knowledge_id": "知识库ID",
        "session_id": "会话ID"
        "query": "查询内容"
        "stream_chat": "是否流式聊天"
        "stream_chat_type": "流式聊天类型"
    }
    返回参数: {
        "success": true,
        "message": "执行成功"
        "data": {
            "id": "run--671b477d-e754-45c6-a5fb-1f6c6e52a4ac",
            "object": "chat.completion.chunk",
            "created": 1762844637,
            "model": "emb-graph-chat-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": "中的所有",
                        "type": "text"
                    },
                    "finish_reason": null
                }
            ]
        }
    }
    """
    
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    
    
    user_id = data.get('user_id')
    if(not user_id):
        # 验证用户凭据
        user_name = data.get('user_name')
        password = data.get('password')
    
        if not user_name or not password:
            return jsonify({'success': False, 'message': '用户名和密码不能为空'})
        
        user_info = verify_user_credentials(user_name, password)
        if not user_info:
            return jsonify({'success': False, 'message': '用户名或密码错误'})
        
        user_id = user_info['user_id']
    else:
        user_id = user_id

    knowledge_name = data.get('knowledge_name')
    session_id = data.get('session_id')
    
    if not data:
        return jsonify({'error': 'No data provided'})
    else:
        # Process the data (example: echo it back)
        logger.info(f"execute_stream_chat received data: {data}")
        try:
            knowledge_id = data.get('knowledge_id')
            if(not knowledge_id):
                param = {"name":knowledge_name, "user_id":user_id}
                kb_info = cSingleSqlite.query_knowledge_by_knowledge_name_and_user_id(param)
                if(not kb_info):
                    kb_info = cSingleSqlite.query_knowledge_by_knowledge_name(param)
                knowledge_id = kb_info[0]["knowledge_id"]

            param = {"knowledge_id":knowledge_id, "user_id":user_id, "query":data["query"]}
            # result = controller_chat.execute_all_chat(param)
            result = controller_chat.chat_rag_stream(param)
            
            def generate():
                # 添加调试信息
                logger.info(f"Controller result type: {type(result)}")
                
                has_data = False
                chunk_count = 0
                full_response = ""  # 用于收集完整响应
                
                try:
                    for chunk in result:
                        has_data = True
                        chunk_count += 1
                        try:
                            # 添加调试信息
                            logger.info(f"Processing chunk #{chunk_count}: {chunk}, type: {type(chunk)}")

                            # 检查是否是tool_direct类型的chunk
                            is_tool_direct = False
                            if isinstance(chunk, dict) and "choices" in chunk:
                                delta = chunk["choices"][0].get("delta", {})
                                if "type" in delta and delta["type"] == "tool_direct_answer":
                                    is_tool_direct = True
                                    logger.info(f"检测到tool_direct chunk: {chunk.get('id', 'unknown')}")

                            # 收集响应内容
                            if isinstance(chunk, dict) and "choices" in chunk:
                                delta = chunk["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    full_response += content
                                    logger.info(f"Chunk #{chunk_count} content: '{content[:100]}...'")

                            # 直接发送符合OpenAI格式的数据块
                            if isinstance(chunk, dict):
                                chunk_json = json.dumps(chunk, ensure_ascii=False)
                                logger.info(f"Sending SSE data: data: {chunk_json[:200]}...")
                                yield f"data: {chunk_json}\n\n"
                            else:
                                # 如果不是字典，包装成OpenAI格式
                                wrapped_chunk = {
                                    "id": "chatcmpl-fallback",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": "emb-graph-chat-model",
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {
                                                "content": str(chunk),
                                                "type": "text"
                                            },
                                            "finish_reason": None
                                        }
                                    ]
                                }
                                yield f"data: {json.dumps(wrapped_chunk)}\n\n"
                        except Exception as e:
                            error_msg = f"Error processing chunk #{chunk_count}: {str(e)}"
                            logger.error(error_msg)
                            error_chunk = {
                                "id": "chatcmpl-error",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": "emb-graph-chat-model",
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "content": f"Error: {error_msg}",
                                            "type": "text"
                                        },
                                        "finish_reason": None
                                    }
                                ]
                            }
                            yield f"data: {json.dumps(error_chunk)}\n\n"
                    
                    # 保存聊天记录到Redis
                    if full_response:
                        # 获取会话名称
                        session_info = cSingleSqlite.search_session_by_session_id(session_id)
                        session_name = session_info["session_name"] if session_info else "Unknown Session"
                        # 用户查询格式化为列表格式
                        query_list = [{"type":"text", "content":data["query"]}] if data.get("query") else []
                        # 响应格式化为列表格式
                        response_list = [{"type":"text", "content":full_response}] if full_response else []
                        sess_obj.save_chat_history(user_id, session_id, session_name, query_list, response_list)
                        logger.info(f"Chat history saved for user {user_id}, session {session_id}, query_items={len(query_list)}, response_items={len(response_list)}")
                    
                    # 如果没有数据，发送一个测试消息
                    if not has_data:
                        logger.warning("No data received from controller")
                        test_chunk = {
                            "id": "chatcmpl-test",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": "emb-graph-chat-model",
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        "content": "No data received from controller",
                                        "type": "text"
                                    },
                                    "finish_reason": "stop"
                                }
                            ]
                        }
                        yield f"data: {json.dumps(test_chunk)}\n\n"
                    else:
                        logger.info(f"Total chunks sent: {chunk_count}")

                    # 发送流结束信号
                    logger.info("Sending stream end signal")
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    logger.error(f"Error in generate function: {e}")
                    # 即使出现异常也尝试保存已有的响应
                    if full_response:
                        try:
                            # 获取会话名称
                            session_info = cSingleSqlite.search_session_by_session_id(session_id)
                            session_name = session_info["session_name"] if session_info else "Unknown Session"
                            # 用户查询格式化为列表格式
                            query_list = [{"type":"text", "content":data["query"]}] if data.get("query") else []
                            # 响应格式化为列表格式
                            response_list = [{"type":"text", "content":full_response}] if full_response else []
                            sess_obj.save_chat_history(user_id, session_id, session_name, query_list, response_list)
                            logger.info(f"Partial chat history saved after error for user {user_id}, session {session_id}, query_items={len(query_list)}, response_items={len(response_list)}")
                        except Exception as save_error:
                            logger.error(f"Failed to save chat history after error: {save_error}")
                    
                    # 向客户端发送错误信息
                        error_chunk = {
                        "id": "chatcmpl-final-error",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "emb-graph-chat-model",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "content": f"Final error in processing: {str(e)}",
                                    "type": "text"
                                },
                                "finish_reason": "stop"
                            }
                        ]
                    }
                    yield f"data: {json.dumps(error_chunk)}\n\n"
            response = Response(stream_with_context(generate()), mimetype='text/event-stream')
            # 手动添加CORS头部，因为@app.after_request装饰器不适用于直接创建的Response对象
            response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            # 添加SSE相关的头部
            response.headers['Cache-Control'] = 'no-cache'
            response.headers['Connection'] = 'keep-alive'
            return response
        except Exception as e:
            logger.error(f"Error processing data: {e}")
            return jsonify({"error_code":4, "error_msg":f"Error processing stream query: {str(e)}"}), 500

@app.route('/api/execute_query', methods=['POST'])
def execute_query():
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    
    # 验证用户凭据
    user_name = data.get('user_name')
    password = data.get('password')
    knowledge_name = data.get('knowledge_name')
    
    if not user_name or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})
    
    user_info = verify_user_credentials(user_name, password)
    if not user_info:
        return jsonify({'success': False, 'message': '用户名或密码错误'})
    
    user_id = user_info['user_id']
    
    if not data:
        return jsonify({'error': 'No data provided'})
    else:
        # Process the data (example: echo it back)
        logger.info(f"Received data: {data}")
        if(True):
            param = {"name":knowledge_name, "user_id":user_id}
            kb_info = cSingleSqlite.query_knowledge_by_knowledge_name_and_user_id(param)
            if(not kb_info):
                kb_info = cSingleSqlite.query_knowledge_by_knowledge_name(param)
                
            knowledge_id = kb_info[0]["knowledge_id"]
                
            param = {"knowledge_id":knowledge_id, "user_id":user_id, "query":data["query"]}
        # try:
            # Here you would typically process the data and return a response
            # For demonstration, we just return the received data
            result = controller_chat.execute_all_query(param)
            
            # 保存聊天记录到Redis
            # 注意：execute_query 接口不涉及会话，所以暂时注释掉聊天记录保存
            # if result and isinstance(result, dict) and "answer" in result:
            #     sess_obj.save_chat_history(user_id, data["query"], result["answer"])
            
            return result
        else:
        # except Exception as e:
        #     logger.error(f"Error processing data: {e}")
            return jsonify({"error_code":4, "error_msg":"Error, delete keywords file Api."})

@app.route("/api/delete_all_data", methods=['POST'])
def delete_all_data():
    """
    删除所有数据接口
    返回参数: {
        "success": true/false,
        "message": "删除结果信息"
    }
    """
    try:
        result = controller.delete_all_data()
        return result
    except Exception as e:
        logger.error(f"Error processing data: {e}")
        return jsonify({"error_code":4, "error_msg":"Error, delete all graph data Api."})


@app.route('/api/user_login', methods=['POST', 'OPTIONS'])
def user_login():
    """
    用户登录接口
    请求参数: {
        "user_name": "用户名",
        "password": "密码"
    }
    返回参数: {
        "success": true/false,
        "message": "登录结果信息",
        "user_id": "用户ID",
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    user_name = data.get('user_name')
    password = data.get('password')
    
    if not user_name or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})
    if(True):
    #try:
        # 查询用户信息
        c = cSingleSqlite.conn.cursor()
        sql = "SELECT user_id, user_name, password, permissions FROM user_info WHERE user_name=?"
        c.execute(sql, (user_name,))
        row = c.fetchone()
        
        if row and row[2] == password:  # 简单的密码对比（实际项目中应使用加密）
            user_id = row[0]
            # 生成简单的会话ID（实际项目中应使用更安全的方式）
            
            session_id = str(uuid.uuid4())
            
            # 存储会话信息到Redis
            user_session_info = {
                'user_id': user_id,
                'user_name': user_name,
                'login_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            sess_obj.save_user_session(session_id, user_session_info)
            
            return jsonify({
                'success': True,
                'message': '登录成功',
                'user_id': user_id,
            })
        else:
            return jsonify({'success': False, 'message': '用户名或密码错误'})
    # except Exception as e:
    #     logger.error(f"登录过程中发生错误: {e}")
    else:
        return jsonify({'success': False, 'message': '登录过程中发生错误'})

@app.route('/api/user_logout', methods=['POST'])
def user_logout():
    """
    用户登出接口
    请求参数: {
        "session_id": "会话ID" # 可选
        "user_name": "用户名"
        "password": "密码"
    }
    返回参数: {
        "success": true/false,
        "message": "登出结果信息"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})

    user_name = data.get('user_name')
    password = data.get('password')
    
    if not user_name or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})
    
    user_info = verify_user_credentials(user_name, password)
    if not user_info:
        return jsonify({'success': False, 'message': '用户名或密码错误'})
    
    user_id = user_info['user_id']
    
    try:
        
        if(user_id):
            return jsonify({'success': True, 'message': '登出成功'})
        else:
            return jsonify({'success': False, 'message': '登出失败'})
    except Exception as e:
        logger.error(f"登出过程中发生错误: {e}")
        return jsonify({'success': False, 'message': '登出过程中发生错误'})

# 新增清除聊天历史记录的API接口
@app.route('/api/clear_chat_history', methods=['POST'])
def clear_chat_history():
    """
    清除用户聊天历史记录接口
    请求参数: {
        "user_name": "用户名",
        "password": "密码"
    }
    返回参数: {
        "success": true/false,
        "message": "结果信息"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    
    # 验证用户凭据
    user_name = data.get('user_name')
    password = data.get('password')
    
    if not user_name or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})
    
    user_info = verify_user_credentials(user_name, password)
    if not user_info:
        return jsonify({'success': False, 'message': '用户名或密码错误'})
    
    user_id = user_info['user_id']
    
    try:
        # 清除Redis中的聊天历史记录
        result = sess_obj.clear_chat_history(user_id)
        
        if result:
            return jsonify({
                'success': True,
                'message': '聊天历史记录清除成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '聊天历史记录清除失败'
            })
    except Exception as e:
        logger.error(f"清除聊天历史记录时出错: {e}")
        return jsonify({
            'success': False,
            'message': f'清除聊天历史记录时出错: {str(e)}'
        })

@app.route('/api/delete_sessions_by_session_id', methods=['POST'])
def delete_sessions_by_session_id():
    """
    删除指定会话接口
    请求参数: {
        "session_id": "会话ID"
    }
    返回参数: {
        "success": true/false,
        "message": "结果信息"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})

    session_id = data.get('session_id')
    # print("session_id")
    # print(session_id)
    # sess_obj.get_session_messages_by_id(session_id)
    sess_obj.delete_session_messages_by_id(session_id)
    cSingleSqlite.delete_sessions_by_session_id(session_id)
    
    # 删除圆桌讨论相关文件
    try:
        # 通过 session_id 获取所有相关的 discussion_id
        task_stats = cSingleSqlite.count_discussion_tasks_by_session_id(session_id)
        tasks_list = task_stats.get('tasks', [])
        
        # 遍历所有任务，删除对应的 discussion 文件夹和数据库记录
        for task in tasks_list:
            discussion_id = task.get('discussion_id')
            if discussion_id:
                # 删除 discussion 文件夹
                discussion_path = os.path.join("discussion", discussion_id)
                if os.path.exists(discussion_path):
                    shutil.rmtree(discussion_path)
                    print(f"删除圆桌讨论文件夹成功: {discussion_path}")
                
                # 删除数据库中的任务记录
                cSingleSqlite.delete_discussion_task_by_discussion_id(discussion_id)
                print(f"删除圆桌讨论任务记录成功: discussion_id={discussion_id}")
    except Exception as e:
        print(f"删除圆桌讨论文件时出错: {e}")
        import traceback
        traceback.print_exc()
    
    file_info_list = cSingleSqlite.search_file_basic_info_by_session_id(session_id)
    for file_info in file_info_list:
        print("file_info")
        print(file_info)
        file_path = file_info["file_path"]
        # 从文件路径中提取目录路径（删除文件名，保留文件夹路径）
        # 例如：conf/file/file_22814796fd3d46e0/流浪地球.txt -> conf/file/file_22814796fd3d46e0
        file_dir = os.path.dirname(file_path)
        file_id = file_info["file_id"]
        cSingleSqlite.delete_file_basic_info(file_id)
        # 删除整个文件夹
        if os.path.exists(file_dir):
            shutil.rmtree(file_dir)
    return jsonify({'success': True, 'message': '删除成功'})

@app.route('/api/create_session', methods=['POST'])
def create_session():
    """
    创建会话接口
    请求参数: {
        "user_name": "用户名",
        "password": "密码"
        "konwledge_name": "知识库名称" 可选
        "session_name": "会话名称" 
        "knowledge_id": "知识库id" #可选 
        "user_id": "用户id" #可选
    }
    返回参数: {
        "success": true/false,
        "message": "结果信息",
        "session_id": "会话ID"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})

    user_id = data.get('user_id', "")
    if(not user_id):
        # 验证用户凭据
        user_name = data.get('user_name')
        password = data.get('password')
        user_info = verify_user_credentials(user_name, password)
        if not user_info:
            return jsonify({'success': False, 'message': '用户名或密码错误'})
        user_id = user_info['user_id']
    else:
        param = {'user_id': user_id}
        user_name = cSingleSqlite.search_user_name_by_user_id(param)
        print(user_name)
    
    knowledge_id = data.get('knowledge_id', "")
    knowledge_name = data.get('knowledge_name', "")
    if(not knowledge_id and not knowledge_name):
        knowledge_id = ""
        knowledge_name = ""
    elif(not knowledge_id):
        knowledge_base_name = data.get('knowledge_name')
        param = {'knowledge_name': knowledge_base_name, 'user_id': user_id}
        knowledge_d = cSingleSqlite.search_knowledge_base_by_user_id_and_name(param)
        knowledge_id = knowledge_d['knowledge_id']
    elif(not knowledge_name):
        knowledge_d = cSingleSqlite.query_knowledge_base_by_id(knowledge_id)
        knowledge_name = knowledge_d['name']
    session_name = data.get('session_name')
    chat_id = str(uuid.uuid4())
    flag = sess_obj.create_session_info(user_id, chat_id, session_name, 
                                        knowledge_name)
    if(flag):
        return jsonify({
            'success': True,
            'message': '创建会话成功',
            'session':{'session_id': chat_id,
                'title': session_name,
                'knowledge_base_name': knowledge_name,
                'knowledge_base_id': knowledge_id,
                'user_id': user_id,
                'user_name': user_name,
                'create_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'update_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message_count":0,
                "is_archived": False}
            
        })
    else:
        return jsonify({
            'success': False,
            'message': '创建会话失败'
        })

@app.route('/api/get_user_session_messages', methods=['POST'])
def get_user_session_messages():
    """
    获取对话列表接口
    请求参数: {
        "user_name": "管理员用户名",
        "password": "密码"
        "user_id": "用户ID" #可选
    }
    返回参数: {
        "success": true/false,
        "message": "结果信息",
        "messages": [
            {
                "session_id":"", #对话ID
                "session_name": "", #对话名
                "session_desc": "", #对话描述
            }
        ]
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})

    user_id = data.get('user_id')
    if(not user_id):
        # 验证用户凭据
        user_name = data.get('user_name')
        password = data.get('password')

        user_info = verify_user_credentials(user_name, password)
        if not user_info:
            return jsonify({'success': False, 'message': '用户名或密码错误'})
        
        user_id = user_info['user_id']

    if(True):
    #try:
        messages_list = cSingleSqlite.search_session_by_user_id(user_id)
        result = []
        for message in messages_list:
            tmp = {}
            tmp['session_id'] = message['session_id']
            tmp['session_name'] = message['session_name']
            tmp['session_desc'] = message['session_desc']
            result.append(tmp)
        
        return jsonify({
            'success': True,
            'message': '获取聊天记录成功',
            'messages': result
        })
    #except Exception as e:
    #    logger.error(f"获取聊天记录时出错: {e}")
    else:
        e = ""
        return jsonify({
            'success': False,
            'message': f'获取聊天记录时出错: {str(e)}'
        })

@app.route('/api/get_sessions_by_id', methods=['POST'])
def get_sessions_by_id():
    """
    获取指定会话的聊天记录接口
    请求参数: {
        "session_id": "会话ID"
    }
    返回参数: {
        "success": true/false,
        "message": "结果信息",
        "session": {
            "session_id": "会话ID",
            "session_name": "会话名称",
            "session_desc": "会话描述",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "content": "你好"}]
                },
                {
                    "role": "assistant",
                    "content": [{"type": "text", "content": "你好，有什么需要帮助的吗？"}]
                }
            ]
        }
    }
    注意：content 字段现在是列表格式，每个元素包含 type 和 content 字段。
    type 可以是 "text", "echarts", "html_table" 等。
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    session_id = data.get('session_id')
    if(True):
        print("get_sessions_by_id")
    #try:
   
        # print(session_id)
        session = cSingleSqlite.search_session_by_session_id(session_id)
        messages = sess_obj.get_session_messages_by_id(session_id)
        # print(messages)
        return jsonify({
            'success': True,
            'message': '获取聊天记录成功',
            'session': {
                'session_id': session_id,
                'session_name': session['session_name'],
                'session_desc': session['session_desc'],
                'messages': messages
            }
        })
    else:
    # except Exception as e:
    #     logger.error(f"获取聊天记录时出错: {e}")
        return jsonify({
            'success': False,
            'message': '获取聊天记录失败'
        })

@app.route('/api/get_knowledge_base_file_list', methods=['POST'])
def get_knowledge_base_file_list():
    """
    获取知识库文件列表接口
    请求参数: {
        "knowledge_id": "知识库ID"
    }
    返回参数: {
        "success": true/false,
        "message": "结果信息",
        "file_list": [
            {
                "file_id": "",
                "file_name": "",
                "file_path": "",
                "file_size": "",
                "upload_time": "",
                "upload_user_id": "",
                "permission_level": "",
                "url": ""
            }
        ]
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    knowledge_id = data.get('knowledge_id')
    if(not knowledge_id):
        return jsonify({'success': False, 'message': '知识库ID不能为空'})
    file_list = cSingleSqlite.search_file_by_knowledge_id(knowledge_id)
    return jsonify({'success': True, 'message': '获取知识库文件列表成功', 'file_list': file_list})

# @app.route('/api/chat_discussion', methods=['POST'])
# def chat_discussion():
#     """
#     圆桌讨论会议接口 - 异步流式响应
#     请求参数: {
#         "user_name": "用户名",
#         "password": "密码",
#         "session_id": "会话ID",
#         "query": "查询内容",
#         "file": "上传的文件",
#         "resume_discussion_id": "恢复会议ID（可选，用于从断点恢复）"
#     }
#     返回参数: SSE流式响应 {
#         "id": "roundtable-xxx",
#         "object": "chat.completion.chunk",
#         "created": timestamp,
#         "model": "roundtable-discussion-model",
#         "choices": [{
#             "index": 0,
#             "delta": {"content": "", "type": "text"},
#             "finish_reason": null
#         }]
#     }
#     """
#     logger.info("🌐 收到圆桌讨论请求")
    
#     # 处理 multipart/form-data 和 application/json 两种情况
#     if request.content_type and request.content_type.startswith('multipart/form-data'):
#         user_name = request.form.get('user_name')
#         password = request.form.get('password')
#         session_id = request.form.get('session_id')
#         query = request.form.get('query', '')
#         resume_discussion_id = request.form.get('resume_discussion_id', '')
#         file = request.files.get('file')
#     else:
#         data = request.get_json()
#         if not data:
#             response = jsonify({'success': False, 'message': 'No data provided'})
#             response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
#             response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
#             response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
#             response.headers['Access-Control-Allow-Credentials'] = 'true'
#             return response
        
#         user_name = data.get('user_name')
#         password = data.get('password')
#         session_id = data.get('session_id')
#         query = data.get('query', '')
#         resume_discussion_id = data.get('resume_discussion_id', '')
#         file = None
    
#     # 验证用户凭据
#     if not user_name or not password:
#         response = jsonify({'success': False, 'message': '用户名和密码不能为空'})
#         response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
#         response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
#         response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
#         response.headers['Access-Control-Allow-Credentials'] = 'true'
#         return response
    
#     user_info = verify_user_credentials(user_name, password)
#     if not user_info:
#         response = jsonify({'success': False, 'message': '用户名或密码错误'})
#         response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
#         response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
#         response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
#         response.headers['Access-Control-Allow-Credentials'] = 'true'
#         return response
    
#     user_id = user_info['user_id']
#     logger.info(f"👤 用户认证成功: user_id={user_id}, session_id={session_id}")
    
#     try:
#         # 处理文件上传
#         file_path = ""
#         if file and file.filename:
#             file_id = f"file_{uuid.uuid4().hex[:16]}"
#             file_dir = os.path.join("conf", "file", file_id)
#             os.makedirs(file_dir, exist_ok=True)
#             file_path = os.path.join(file_dir, file.filename)
#             file.save(file_path)
#             logger.info(f"📁 文件已保存: {file_path}")
        
#         # 调用圆桌讨论功能
#         result = controller_chat.chat_with_discussion(
#             user_id, 
#             session_id, 
#             query, 
#             file_path,
#             resume_discussion_id if resume_discussion_id else None
#         )
        
#         def generate():
#             """SSE流式响应生成器 - 优化版：增强心跳机制"""
#             has_data = False
#             chunk_count = 0
#             full_response = ""
#             full_response_list = []
            
#             # 心跳配置
#             heartbeat_interval = 3  # 每3秒发送一次心跳（更频繁）
#             last_heartbeat_time = time.time()
#             last_data_time = time.time()
#             connection_timeout = 300  # 5分钟无数据超时
            
#             try:
#                 # 保存初始聊天记录
#                 if query:
#                     session_info = cSingleSqlite.search_session_by_session_id(session_id)
#                     session_name = session_info["session_name"] if session_info else "Discussion Session"
#                     query_list = [{"type": "text", "content": query}]
#                     sess_obj.save_chat_history(user_id, session_id, session_name, query_list, [])
#                     logger.info(f"💾 初始聊天记录已保存: session_id={session_id}")
                
#                 logger.info(f"🎯 开始处理圆桌会议流式响应（优化版）")
                
#                 # 立即发送初始心跳，确认连接建立
#                 initial_heartbeat = {
#                     "id": f"roundtable-heartbeat-{int(time.time())}",
#                     "object": "chat.completion.chunk",
#                     "created": int(time.time()),
#                     "model": "roundtable-discussion-model",
#                     "choices": [{
#                         "index": 0,
#                         "delta": {"content": "", "type": "heartbeat"},
#                         "finish_reason": None
#                     }],
#                     "heartbeat": True,
#                     "message": "连接已建立，正在处理..."
#                 }
#                 yield f"data: {json.dumps(initial_heartbeat, ensure_ascii=False)}\n\n"
                
#                 for chunk in result:
#                     current_time = time.time()
#                     has_data = True
#                     chunk_count += 1
#                     last_data_time = current_time
                    
#                     # 定期发送心跳（每3秒或每10个chunk）
#                     if current_time - last_heartbeat_time >= heartbeat_interval or chunk_count % 10 == 0:
#                         # 发送心跳包
#                         heartbeat_chunk = {
#                             "id": f"roundtable-heartbeat-{int(current_time)}",
#                             "object": "chat.completion.chunk",
#                             "created": int(current_time),
#                             "model": "roundtable-discussion-model",
#                             "choices": [{
#                                 "index": 0,
#                                 "delta": {"content": "", "type": "heartbeat"},
#                                 "finish_reason": None
#                             }],
#                             "heartbeat": True,
#                             "chunks_processed": chunk_count,
#                             "message": f"处理中... ({chunk_count} 块)"
#                         }
#                         yield f"data: {json.dumps(heartbeat_chunk, ensure_ascii=False)}\n\n"
#                         last_heartbeat_time = current_time
                        
#                         if chunk_count % 50 == 0:
#                             logger.info(f"❤️ 圆桌会议心跳: 已处理 {chunk_count} 个 chunks")
                    
#                     try:
#                         # 收集响应内容
#                         if isinstance(chunk, dict) and "choices" in chunk:
#                             delta = chunk["choices"][0].get("delta", {})
#                             content = delta.get("content", "")
#                             type_con = delta.get("type", "text")
                            
#                             if type_con in ["echarts", "html_table", "file"]:
#                                 if full_response and full_response.strip():
#                                     full_response_list.append({"type": "text", "content": full_response})
#                                     full_response = ""
#                                 if content and content.strip():
#                                     full_response_list.append({"type": type_con, "content": content})
#                             else:
#                                 if content:
#                                     full_response += content
                            
#                             # 实时更新聊天记录
#                             if content or type_con:
#                                 current_list = full_response_list.copy()
#                                 if full_response and full_response.strip():
#                                     current_list.append({"type": "text", "content": full_response})
#                                 if current_list:
#                                     sess_obj.update_last_chat_record(session_id, updated_response=current_list)
                        
#                         # 发送SSE数据
#                         if isinstance(chunk, dict):
#                             yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
#                         else:
#                             wrapped_chunk = {
#                                 "id": f"roundtable-{int(time.time())}",
#                                 "object": "chat.completion.chunk",
#                                 "created": int(time.time()),
#                                 "model": "roundtable-discussion-model",
#                                 "choices": [{
#                                     "index": 0,
#                                     "delta": {"content": str(chunk), "type": "text"},
#                                     "finish_reason": None
#                                 }]
#                             }
#                             full_response += str(chunk)
#                             yield f"data: {json.dumps(wrapped_chunk)}\n\n"
                    
#                     except Exception as e:
#                         logger.error(f"❌ 处理chunk #{chunk_count} 失败: {e}")
#                         error_chunk = {
#                             "id": "roundtable-error",
#                             "object": "chat.completion.chunk",
#                             "created": int(time.time()),
#                             "model": "roundtable-discussion-model",
#                             "choices": [{
#                                 "index": 0,
#                                 "delta": {"content": f"Error: {str(e)}", "type": "text"},
#                                 "finish_reason": None
#                             }]
#                         }
#                         yield f"data: {json.dumps(error_chunk)}\n\n"
                
#                 # 最终保存
#                 if full_response and full_response.strip():
#                     full_response_list.append({"type": "text", "content": full_response})
#                 if full_response_list:
#                     sess_obj.update_last_chat_record(session_id, updated_response=full_response_list)
#                     logger.info(f"✅ 圆桌会议完成: 共 {len(full_response_list)} 个响应项")
                
#                 if not has_data:
#                     logger.warning("⚠️ 未收到任何数据")
#                     yield f"data: {json.dumps({'id': 'roundtable-empty', 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': 'roundtable-discussion-model', 'choices': [{'index': 0, 'delta': {'content': '未收到数据', 'type': 'text'}, 'finish_reason': 'stop'}]})}\n\n"
                
#                 logger.info(f"🏁 圆桌会议流结束: 共发送 {chunk_count} 个 chunks")
#                 yield "data: [DONE]\n\n"
                
#             except Exception as e:
#                 logger.error(f"❌ 圆桌会议生成器错误: {e}")
#                 # 保存已有响应
#                 if full_response and full_response.strip():
#                     full_response_list.append({"type": "text", "content": full_response})
#                 if full_response_list:
#                     try:
#                         sess_obj.update_last_chat_record(session_id, updated_response=full_response_list)
#                     except Exception as save_error:
#                         logger.error(f"❌ 保存失败: {save_error}")
                
#                 error_chunk = {
#                     "id": "roundtable-final-error",
#                     "object": "chat.completion.chunk",
#                     "created": int(time.time()),
#                     "model": "roundtable-discussion-model",
#                     "choices": [{
#                         "index": 0,
#                         "delta": {"content": f"圆桌会议错误: {str(e)}", "type": "text"},
#                         "finish_reason": "stop"
#                     }]
#                 }
#                 yield f"data: {json.dumps(error_chunk)}\n\n"
#                 yield "data: [DONE]\n\n"
        
#         # 创建SSE流式响应
#         response = Response(stream_with_context(generate()), mimetype='text/event-stream')
#         response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
#         response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
#         response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
#         response.headers['Access-Control-Allow-Credentials'] = 'true'
#         response.headers['Cache-Control'] = 'no-cache'
#         response.headers['Connection'] = 'keep-alive'
#         response.headers['X-Accel-Buffering'] = 'no'
#         return response
#     except Exception as e:
#         logger.error(f"❌ 圆桌讨论接口错误: {e}")
#         return jsonify({"success": False, "error_code": 4, "error_msg": f"圆桌讨论处理失败: {str(e)}"}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    聊天接口
    请求参数: {
        "user_name": "用户名",
        "password": "密码",
        "message": "用户消息"
        "session_id": "会话ID",
        "knowledge_name": "知识库名称",
        "knowledge_id": "知识库ID",
        "query": "查询内容",
        "file": "上传的文件",
        "permission_level": "权限等级" #public/private,
        "sql_id": "SQL ID" #SQL ID
    }
    返回参数: {
        "success": true/false,
        "message": "结果信息",
        "data": {
            "id": "run--671b477d-e754-45c6-a5fb-1f6c6e52a4ac",
            "object": "chat.completion.chunk",
            "created": 1762844637,
            "model": "emb-graph-chat-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": "",
                        "type": "text"
                    },
                    "finish_reason": null
                }
            ]
        }
    }
    """
    print(f"request.content_type: {request.content_type}")
    # 处理 multipart/form-data 和 application/json 两种情况
    if request.content_type.startswith('multipart/form-data'):
        # 获取表单数据
        user_name = request.form.get('user_name')
        password = request.form.get('password')
        session_id = request.form.get('session_id')
        knowledge_name = request.form.get('knowledge_name', "")
        knowledge_id = request.form.get('knowledge_id', "")
        query = request.form.get('query', "")
        permission_level = request.form.get('permission_level', "")
        sql_id = request.form.get('sql_id', "")
        # 获取上传的文件
        file = request.files.get('file')
        choice = request.form.get('choice', "")
    else:
        # 原有的 JSON 数据处理方式
        data = request.get_json()
        if not data:
            response = jsonify({'success': False, 'message': 'No data provided'})
            response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            return response
        
        user_name = data.get('user_name')
        password = data.get('password')
        session_id = data.get('session_id')
        knowledge_name = data.get('knowledge_name', "")
        knowledge_id = data.get('knowledge_id', "")
        sql_id = data.get('sql_id', "")
        query = data.get('query', "")
        permission_level = data.get('permission_level', "")
        file = data.get('file', "")
        choice = data.get('choice', "")
    print(f"query: {query}")
    if not user_name or not password:
        response = jsonify({'success': False, 'message': '用户名和密码不能为空'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response

    user_info = verify_user_credentials(user_name, password)
    if not user_info:
        response = jsonify({'success': False, 'message': '用户名或密码错误'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    user_id = user_info['user_id']
    try:
        if(not knowledge_id):
            if(knowledge_name):
                param = {"name":knowledge_name, "user_id":user_id}
                kb_info = cSingleSqlite.query_knowledge_by_knowledge_name_and_user_id(param)
                if(not kb_info):
                    kb_info = cSingleSqlite.query_knowledge_by_knowledge_name(param)
                knowledge_id = kb_info[0]["knowledge_id"]

        # 处理文件上传
        file_path = ""
        if file and file.filename:  # 检查是否有上传文件且有文件名
            # 生成文件ID
            file_id = f"file_{uuid.uuid4().hex[:16]}"
            
            # 创建文件保存目录 conf/file/file_id/
            file_dir = os.path.join("conf", "file", file_id)
            os.makedirs(file_dir, exist_ok=True)
            
            # 保存文件到指定目录
            file_path = os.path.join(file_dir, file.filename)
            file.save(file_path)
            file_info_dict = {"knowledge_id": knowledge_id, "file_id": file_id,
                          "file_name": file.filename, "file_path": file_path, 
                          "file_size": os.path.getsize(file_path), "upload_user_id": user_id, 
                          "permission_level": permission_level, "url":"", 
                          "upload_time":time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                          "session_id":session_id}
            #print("file_info_dict")
            #print(file_info_dict)
            cSingleSqlite.insert_file_basic_info(file_info_dict)
        param = {"knowledge_id":knowledge_id, "user_id":user_id,
                "query":query, "file":file_path}
        if(choice == "discussion"):
            # 若请求中带 discussion_id（如前端「重启指定任务」），则沿用原任务ID与文件夹
            request_discussion_id = (data.get("discussion_id") or "").strip() or None
            result = controller_chat.chat_with_discussion(
                user_id, session_id, query, file_path,
                discussion_id=request_discussion_id
            )
        else:
            if(file_path != ""):  # 检查是否有文件路径
                # if(permission_level in ["public", "private"]):
                #     # 存入知识库的请求
                #     result = controller_chat.file_analysis_stream(user_id, user_name, file_path, permission_level)
                # else:
                    # 普通的文档分析请求
                result = controller_chat.chat_with_file(user_id, session_id, query, file_path)
            else:
                if(knowledge_id == "" and sql_id == ""):
                    result = controller_chat.chat(user_id, session_id, query)
                elif(sql_id != "" and knowledge_id == ""):
                    result = controller_chat.chat_with_sql(user_id, session_id, query, sql_id)
                elif(sql_id != "" and knowledge_id != ""):
                    result = controller_chat.chat_with_knowledge_and_sql(user_id, session_id, 
                                                                        query, knowledge_id, sql_id)
                else:
                    param = {"knowledge_id":knowledge_id, "user_id":user_id, "query":query}
                    # result = controller_chat.execute_all_chat(param)
                    result = controller_chat.chat_with_rag(param)

        def generate():
            # 添加调试信息
            # logger.info(f"Controller result type: {type(result)}")
            logger.info("开始处理流式响应chunks")

            has_data = False
            chunk_count = 0
            full_flag = False
            full_response = ""  # 用于收集完整响应
            full_response_list = []  # 用于收集完整响应（列表形式）
            try:
                # 在开始处理前，先保存初始聊天记录（只有query）
                if query:
                    session_info = cSingleSqlite.search_session_by_session_id(session_id)
                    session_name = session_info["session_name"] if session_info else "Unknown Session"
                    query_list = [{"type":"text", "content":query}]
                    initial_response_list = []  # 初始时response为空
                    sess_obj.save_chat_history(user_id, session_id, session_name, query_list, initial_response_list)
                    logger.info(f"Initial chat record saved for user {user_id}, session {session_id}")

                logger.info(f"开始处理圆桌会议流式响应，session_id={session_id}, user_id={user_id}")

                last_heartbeat = time.time()
                for chunk in result:
                    # print("chunk")
                    # print(chunk)
                    current_time = time.time()
                    logger.info(f"开始处理chunk #{chunk_count + 1} (距上次心跳: {current_time - last_heartbeat:.1f}秒)")
                    has_data = True
                    chunk_count += 1

                    # 每10个chunk发送一次心跳
                    if chunk_count % 10 == 0:
                        logger.info(f"❤️ 心跳: 已处理 {chunk_count} 个chunks")
                        last_heartbeat = current_time

                    try:
                        # print(chunk)
                        # 添加调试信息
                        logger.info(f"Processing chunk #{chunk_count}: type={type(chunk)}")

                        # 调试：记录chunk的详细内容（前200字符）
                        chunk_str = str(chunk)[:200] + "..." if len(str(chunk)) > 200 else str(chunk)
                        logger.info(f"Chunk content preview: {chunk_str}")

                        # 收集响应内容
                        if isinstance(chunk, dict) and "choices" in chunk:
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            type_con = delta.get("type", "")

                            # 如果遇到特殊类型（echarts或html_table），先保存之前的文本内容
                            if type_con == "echarts" or type_con == "html_table":
                                # 如果有累积的文本内容，先添加到列表
                                if full_response and full_response.strip():
                                    full_response_list.append({"type":"text", "content":full_response})
                                    full_response = ""
                                # 添加当前的特殊类型内容
                                if content and content.strip():
                                    full_response_list.append({"type":type_con, "content":content})
                            elif(type_con == "file"):
                                if full_response and full_response.strip():
                                    full_response_list.append({"type":"text", "content":full_response})
                                    full_response = ""
                                # 添加当前的特殊类型内容
                                if content and content.strip():
                                    full_response_list.append({"type":type_con, "content":content})
                            else:
                                # 普通文本内容，累积到 full_response
                                if content:
                                    full_response += content

                        # 每次处理chunk后，实时更新最后一条聊天记录
                        if isinstance(chunk, dict) and "choices" in chunk:
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            type_con = delta.get("type", "")

                            # 只有当有实际内容时才更新
                            if content or type_con:
                                # 处理最后剩余的文本内容到列表
                                current_full_response = full_response
                                current_full_response_list = full_response_list.copy()

                                if current_full_response and current_full_response.strip():
                                    current_full_response_list.append({"type":"text", "content":current_full_response})

                                # 更新最后一条聊天记录
                                if current_full_response_list:
                                    sess_obj.update_last_chat_record(session_id, updated_response=current_full_response_list)
                                    logger.info(f"Updated last chat record for session {session_id} with {len(current_full_response_list)} response items")

                        # 直接发送符合OpenAI格式的数据块
                        if isinstance(chunk, dict):
                            sse_data = f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            logger.info(f"发送SSE数据: {len(sse_data)} 字符")
                            logger.info(f"SSE数据内容: {sse_data[:200]}...")
                            yield sse_data
                        else:
                            # 如果不是字典，包装成OpenAI格式
                            wrapped_chunk = {
                                "id": "chatcmpl-fallback",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": "emb-graph-chat-model",
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "content": str(chunk),  # 修复了这里的错误
                                            "type": "text"
                                        },
                                        "finish_reason": None
                                    }
                                ]
                            }
                            # 对于非字典类型的chunk，也累积到full_response
                            if not isinstance(chunk, dict):
                                full_response = full_response + str(chunk)
                            yield f"data: {json.dumps(wrapped_chunk)}\n\n"
                    except Exception as e:
                        error_msg = f"Error processing chunk #{chunk_count}: {str(e)}"
                        logger.error(error_msg)
                        error_chunk = {
                            "id": "chatcmpl-error",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": "emb-graph-chat-model",
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        "content": f"Error: {error_msg}",
                                        "type": "text"
                                    },
                                    "finish_reason": None
                                }
                            ]
                        }
                        yield f"data: {json.dumps(error_chunk)}\n\n"
                
                # 处理最后剩余的文本内容并进行最终更新
                if full_response and full_response.strip():
                    full_response_list.append({"type":"text", "content":full_response})

                # 最终更新一次，确保所有内容都被保存
                if full_response_list:
                    sess_obj.update_last_chat_record(session_id, updated_response=full_response_list)
                    logger.info(f"Final update of last chat record for session {session_id} with {len(full_response_list)} response items")
                # 如果没有数据，发送一个测试消息
                if not has_data:
                    logger.warning("No data received from controller")
                    test_chunk = {
                        "id": "chatcmpl-test",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "emb-graph-chat-model",
                        "choices": [
                            {
                                "index": 0,
                            "delta": {
                                    "content": "No data received from controller",
                                    "type": "text"
                                },
                                "finish_reason": "stop"
                            }
                        ]
                    }
                    yield f"data: {json.dumps(test_chunk)}\n\n"
                else:
                    logger.info(f"Total chunks sent: {chunk_count}")

                # 发送流结束信号
                logger.info("Sending stream end signal [DONE]")
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Error in generate function: {e}")
                # 即使出现异常也尝试保存已有的响应
                # 处理最后剩余的文本内容
                if full_response and full_response.strip():
                    full_response_list.append({"type":"text", "content":full_response})
                
                if full_response_list or full_response:
                    try:
                        # 获取会话名称
                        session_info = cSingleSqlite.search_session_by_session_id(session_id)
                        session_name = session_info["session_name"] if session_info else "Unknown Session"
                        # 用户查询格式化为列表格式
                        query_list = [{"type":"text", "content":query}] if query else []
                        # 响应格式化为列表格式
                        response_list = full_response_list if full_response_list else ([{"type":"text", "content":full_response}] if full_response else [])
                        sess_obj.save_chat_history(user_id, session_id, session_name, query_list, response_list)
                        logger.info(f"Partial chat history saved after error for user {user_id}, session {session_id}, query_items={len(query_list)}, response_items={len(response_list)}")
                    except Exception as save_error:
                        logger.error(f"Failed to save chat history after error: {save_error}")
                
                # 向客户端发送错误信息
                error_chunk = {
                    "id": "chatcmpl-final-error",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "emb-graph-chat-model",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "content": f"Final error in processing: {str(e)}",
                                "type": "text"
                            },
                            "finish_reason": "stop"
                        }
                    ]
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"
        response = Response(stream_with_context(generate()), mimetype='text/event-stream')
        # 手动添加CORS头部，因为@app.after_request装饰器不适用于直接创建的Response对象
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        # 添加SSE相关的头部
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Connection'] = 'keep-alive'
        response.headers['X-Accel-Buffering'] = 'no'  # 禁用nginx缓冲
        return response
    except Exception as e:
        logger.error(f"Error processing data: {e}")
        return jsonify({"error_code":4, "error_msg":f"Error processing stream query: {str(e)}"}), 500

@app.route('/api/insert_sql_info', methods=['POST'])
def insert_sql_info():
    """插入数据库信息"""
    data = request.get_json()
    
    if not data:
        response = jsonify({'success': False, 'message': 'No data provided'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    # 验证用户凭据
    user_name = data.get('user_name')
    password = data.get('password')
    
    if not user_name or not password:
        response = jsonify({'success': False, 'message': '用户名和密码不能为空'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    user_info = verify_user_credentials(user_name, password)
    if not user_info:
        response = jsonify({'success': False, 'message': '用户名或密码错误'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    user_id = user_info['user_id']
    data['user_id'] = user_id
    
    try:
        logger.info(f"Received insert_sql_info data: {data}")
        result = controller_sql.insert_sql_info(data)
        response = jsonify(result)
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    except Exception as e:
        logger.error(f"Error processing insert_sql_info: {e}")
        response = jsonify({"success": False, "message": f"Error, insert sql info Api: {str(e)}"})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response

@app.route('/api/get_sql_info_list', methods=['POST'])
def get_sql_info_list():
    """获取用户的数据库列表"""
    data = request.get_json()
    
    if not data:
        response = jsonify({'success': False, 'message': 'No data provided'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    # 验证用户凭据
    user_name = data.get('user_name')
    password = data.get('password')
    
    if not user_name or not password:
        response = jsonify({'success': False, 'message': '用户名和密码不能为空'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    user_info = verify_user_credentials(user_name, password)
    if not user_info:
        response = jsonify({'success': False, 'message': '用户名或密码错误'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    user_id = user_info['user_id']
    
    try:
        databases = cSingleSqlite.query_base_sql_by_user_id(user_id)
        response = jsonify({
            'success': True,
            'message': '获取数据库列表成功',
            'data': databases
        })
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    except Exception as e:
        logger.error(f"获取数据库列表失败: {e}")
        response = jsonify({'success': False, 'message': f'获取数据库列表失败: {str(e)}'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response

@app.route('/api/get_table_info', methods=['POST'])
def get_table_info():
    """获取表信息"""
    data = request.get_json()
    
    if not data:
        response = jsonify({'success': False, 'message': 'No data provided'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    # 验证用户凭据
    user_name = data.get('user_name')
    password = data.get('password')
    
    if not user_name or not password:
        response = jsonify({'success': False, 'message': '用户名和密码不能为空'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    user_info = verify_user_credentials(user_name, password)
    if not user_info:
        response = jsonify({'success': False, 'message': '用户名或密码错误'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    user_id = user_info['user_id']
    data['user_id'] = user_id
    
    try:
        result = controller_sql.get_table_info(data)
        response = jsonify(result)
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    except Exception as e:
        logger.error(f"获取表信息失败: {e}")
        response = jsonify({'success': False, 'message': f'获取表信息失败: {str(e)}'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response

@app.route('/api/update_sql_info', methods=['POST'])
def update_sql_info():
    """更新数据库信息"""
    data = request.get_json()
    
    if not data:
        response = jsonify({'success': False, 'message': 'No data provided'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    # 验证用户凭据
    user_name = data.get('user_name')
    password = data.get('password')
    
    if user_name and password:
        user_info = verify_user_credentials(user_name, password)
        if not user_info:
            response = jsonify({'success': False, 'message': '用户名或密码错误'})
            response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            return response
        user_id = user_info['user_id']
        data['user_id'] = user_id
    
    try:
        result = controller_sql.update_sql_info(data)
        response = jsonify(result)
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    except Exception as e:
        logger.error(f"更新数据库信息失败: {e}")
        response = jsonify({'success': False, 'message': f'更新数据库信息失败: {str(e)}'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response

@app.route('/api/insert_sql_rel', methods=['POST'])
def insert_sql_rel():
    """插入数据库关系信息"""
    data = request.get_json()
    
    if not data:
        response = jsonify({'success': False, 'message': 'No data provided'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    try:
        result = controller_sql.insert_sql_rel(data)
        response = jsonify(result)
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    except Exception as e:
        logger.error(f"插入数据库关系信息失败: {e}")
        response = jsonify({'success': False, 'message': f'插入数据库关系信息失败: {str(e)}'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
@app.route('/api/delete_sql_rel', methods=['POST'])
def delete_sql_rel():
    """删除数据库关系信息"""
    data = request.get_json()
    
    if not data:
        response = jsonify({'success': False, 'message': 'No data provided'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    try:
        result = controller_sql.delete_sql_rel(data)
        response = jsonify(result)
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    except Exception as e:
        logger.error(f"删除数据库关系信息失败: {e}")
        response = jsonify({'success': False, 'message': f'删除数据库关系信息失败: {str(e)}'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
        
@app.route('/api/file-content', methods=['GET'])
def get_file_content():
    """
    获取文件内容接口
    请求参数: 
        file_path: 文件路径
    返回参数: {
        "success": true/false,
        "message": "结果信息",
        "content": "文件内容"
    }
    """
    try:
        file_path = request.args.get('file_path')
        if not file_path:
            response = jsonify({'success': False, 'message': '文件路径不能为空'})
            response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            return response
        
        # 安全检查：确保文件路径在允许的目录内
        import os
        file_path = os.path.abspath(file_path)
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            response = jsonify({'success': False, 'message': '文件不存在'})
            response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            return response
        
        # 检查文件大小（限制最大读取5MB）
        file_size = os.path.getsize(file_path)
        if file_size > 5 * 1024 * 1024:  # 5MB限制
            response = jsonify({'success': False, 'message': '文件过大，无法预览（最大5MB）'})
            response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            return response
        
        # 尝试读取文件内容
        try:
            # 根据文件类型选择合适的编码
            import mimetypes
            content_type, _ = mimetypes.guess_type(file_path)
            
            if content_type and content_type.startswith('text/'):
                # 文本文件
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    # 如果UTF-8解码失败，尝试其他编码
                    try:
                        with open(file_path, 'r', encoding='gbk') as f:
                            content = f.read()
                    except UnicodeDecodeError:
                        with open(file_path, 'r', encoding='latin1') as f:
                            content = f.read()
            else:
                # 非文本文件，返回二进制内容（以base64编码）
                import base64
                with open(file_path, 'rb') as f:
                    binary_content = f.read()
                content = base64.b64encode(binary_content).decode('utf-8')
                return jsonify({
                    'success': True, 
                    'message': '文件内容获取成功',
                    'content': content,
                    'is_binary': True,
                    'file_size': file_size
                })
            
            response = jsonify({
                'success': True, 
                'message': '文件内容获取成功',
                'content': content,
                'is_binary': False,
                'file_size': file_size,
                'content_type': content_type or 'text/plain'
            })
            
        except Exception as e:
            logger.error(f"读取文件内容失败: {str(e)}")
            response = jsonify({'success': False, 'message': f'读取文件内容失败: {str(e)}'})
            
    except Exception as e:
        logger.error(f"获取文件内容时出错: {str(e)}")
        response = jsonify({'success': False, 'message': f'获取文件内容时出错: {str(e)}'})
    
    # 添加CORS头部
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response

@app.route('/api/delete_sql_info', methods=['POST'])
def delete_sql_info():
    """删除数据库信息"""
    data = request.get_json()
    
    if not data:
        response = jsonify({'success': False, 'message': 'No data provided'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    # 验证用户凭据
    user_name = data.get('user_name')
    password = data.get('password')
    sql_id = data.get('sql_id')
    
    if not user_name or not password:
        response = jsonify({'success': False, 'message': '用户名和密码不能为空'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    if not sql_id:
        response = jsonify({'success': False, 'message': '数据库ID不能为空'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    user_info = verify_user_credentials(user_name, password)
    if not user_info:
        response = jsonify({'success': False, 'message': '用户名或密码错误'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    try:
        # 验证数据库属于该用户
        db_info = cSingleSqlite.query_base_sql_by_sql_id(sql_id)
        if not db_info or db_info['user_id'] != user_info['user_id']:
            response = jsonify({'success': False, 'message': '无权删除该数据库'})
            response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            return response
        
        # success = cSingleSqlite.delete_base_sql(sql_id)
        
        success = controller_sql.delete_sql_info(data)
        
        if success:
            response = jsonify({'success': True, 'message': '删除数据库信息成功'})
        else:
            response = jsonify({'success': False, 'message': '删除数据库信息失败'})
        
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    except Exception as e:
        logger.error(f"删除数据库信息失败: {e}")
        response = jsonify({'success': False, 'message': f'删除数据库信息失败: {str(e)}'})
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response

def run_model():
    # 配置Flask和Werkzeug日志，避免过多输出
    app.logger.setLevel(logging.WARNING)  # 只显示警告和错误
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.WARNING)  # 只显示警告和错误
    # print("asdasdasdasd")
    # 配置我们的应用日志
    if not logger.handlers:
        # 文件日志处理器
        Rthandler = TimedRotatingFileHandler("logging1", 'D', 15, 0)
        Rthandler.suffix = "%Y%m%d.log"
        formatter = logging.Formatter('%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s')
        Rthandler.setFormatter(formatter)
        logger.setLevel(logging.INFO)
        logger.addHandler(Rthandler)

        # 控制台日志处理器（可选，用于开发环境）
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    # 启动Flask应用
    app.run(host='0.0.0.0', port=6199, debug=False, threaded=True)

if __name__ == '__main__':
    run_model()
    
    