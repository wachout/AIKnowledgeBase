# -*- coding:utf-8 _*-


import os
import json
import base64
# import mammoth

 # 使用urllib下载文件
import urllib.request
import urllib.error

# from Files.read_doc import cSingleDoc
# from Files.mineru_pdf import cSinglePdf

from Utils import utils

class CControl():
    
    def __init__(self):
        self.file_path = "conf/tmp/"
        if not os.path.exists(self.file_path):
            os.makedirs(self.file_path)
    
    def save_file(self, file_path, content):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return file_path
    
    def delete_file(self, file_path, file_name):
        file_path = os.path.join(file_path, file_name)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    
    def read_url(self, _url):
        file_extension = os.path.splitext(_url)[1].lower()
        if file_extension in [".doc", ".docx", ".pdf", ".xls", ".xlsx"]:
            api = "/api/read_file_to_base64"
            param = {"url": _url}
            content = utils.request(param, api)
            _json = json.loads(content)
            result_str = _json["result"]
        
            if result_str.startswith("b'") and result_str.endswith("'") and len(result_str) > 4:
                base64_data = result_str[2:-1]  # 去掉引号
                query = base64.b64decode(base64_data)
                query = query.decode('utf-8')
            else:
                query = ""
            
            content_str = _json["content"]
            if content_str.startswith("b'") and content_str.endswith("'") and len(content_str) > 4:
                base64_data = content_str[2:-1]  # 去掉引号
                content = base64.b64decode(base64_data)
                content = content.decode('utf-8')
            else:
                content = ""
                
            return query, content
        else:
            return None, None
        
    def read_stream_file(self, file_path):
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension in [".doc", ".docx", ".pdf", ".xls", ".xlsx"]:
            
            # 读取文件内容
            file_content = None
            # file_name = "unknown"
            
            file_name = os.path.basename(file_path)
            
            # 如果是文件对象，则读取其内容
            if hasattr(file_path, 'read'):
                file_content = file_path.read()
            elif isinstance(file_path, str) and os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    file_content = f.read()
            else:
                # 文件不存在，返回None, None
                return None, None

            # 对读取的二进制文件进行base64编码
            base64_content = base64.b64encode(file_content).decode('utf-8')

            # 构造包含base64编码数据的请求体
            param = {
                'file_name': file_name,
                'file_content_base64': base64_content,
                'file_extension': file_extension
            }

            api = "/api/read_base64_file_to_base64"
            # param = {"data": data}
            content = utils.request(param, api)
            # print(content)
            _json = json.loads(content)
            result_str = _json["result"]
        
            if result_str.startswith("b'") and result_str.endswith("'") and len(result_str) > 4:
                base64_data = result_str[2:-1]
                query = base64.b64decode(base64_data)
                query = query.decode('utf-8')
            else:
                query = ""
            
            content_str = _json["content"]
            if content_str.startswith("b'") and content_str.endswith("'") and len(content_str) > 4:
                base64_data = content_str[2:-1]  # 去掉引号
                content = base64.b64decode(base64_data)
                content = content.decode('utf-8')
            else:
                content = ""
                
            return query, content
        else:
            return None, None
    
    def read_pdf_basic(self, file_path):
        """
        初级PDF解析（使用本地库）
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            tuple: (query, content) 其中query通常为空字符串，content是提取的文本
        """
        try:
            # 尝试使用 PyMuPDF (fitz)
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(file_path)
                text_parts = []
                for page in doc:
                    text_parts.append(page.get_text())
                doc.close()
                content = '\n'.join(text_parts)
                return "", content
            except ImportError:
                pass
            
            # 尝试使用 PyPDF2
            try:
                import PyPDF2
                with open(file_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    text_parts = []
                    for page in pdf_reader.pages:
                        text_parts.append(page.extract_text())
                    content = '\n'.join(text_parts)
                    return "", content
            except ImportError:
                pass
            
            # 如果都没有安装，返回错误
            raise Exception("PDF解析库未安装。请安装 PyMuPDF 或 PyPDF2: pip install PyMuPDF 或 pip install PyPDF2")
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"初级PDF解析失败: {e}")
            return None, None
    
    def read_txt(self, file):
        with open(file, "r", encoding='utf-8') as f:
            content = f.read()
            return content
        return None
    
    def down_file(self, url, file_name):
        """
        下载文件功能
        :param url: 文件下载地址
        :param file_name: 包含路径的完整文件名
        :return: 下载结果信息
        """
        try:
            # 确保文件路径存在
            file_dir = os.path.dirname(file_name)
            if file_dir and not os.path.exists(file_dir):
                os.makedirs(file_dir)
            
            # 下载文件
            urllib.request.urlretrieve(url, file_name)
            
            # 检查文件是否成功下载
            if os.path.exists(file_name):
                file_size = os.path.getsize(file_name)
                return {
                    "success": True,
                    "message": "文件下载成功",
                    "file_path": file_name,
                    "file_size": file_size
                }
            else:
                return {
                    "success": False,
                    "message": "文件下载失败，文件未创建"
                }
        except urllib.error.URLError as e:
            return {
                "success": False,
                "message": f"URL错误: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"文件下载失败: {str(e)}"
            }

    
    