"""
文件分析运行模块

此模块提供文件分析功能的异步流式接口，支持：
- 文件路径输入
- 直接文本内容输入
- 异步流式返回OpenAI格式的自然语言分析结果
- 同步包装函数

使用示例：

# 流式分析文件 - 返回自然语言文本
for chunk in run_file_analysis_sync_stream("path/to/file.pdf"):
    content = chunk["choices"][0]["delta"]["content"]
    print(content)  # 直接输出自然语言文本，如"📄 文件信息：文件名：test.pdf"
    print(f"Chunk ID: {chunk['id']}, Model: {chunk['model']}")

# 异步分析
result = await run_file_analysis_async({"file_path": "test.txt", "content": "内容"})

# 同步分析
result = file_analysis_run("path/to/file.md")
"""

import re
import asyncio
import json
import time
import uuid
import threading
import queue
import logging
from typing import Union, Dict, Any, AsyncGenerator

from .FileAnalyseAgent import run_file_analysis, FileAnalysisResult

logger = logging.getLogger(__name__)


def _split_long_text(content: str, max_length: int = 50000) -> list[str]:
    """
    智能切分长文本，尽量保持语义完整性。
    
    Args:
        content: 要切分的文本内容
        max_length: 每个块的最大长度（字符数）
    
    Returns:
        切分后的文本块列表
    """
    if len(content) <= max_length:
        return [content]
    
    chunks = []
    # 首先尝试按段落切分
    paragraphs = re.split(r'\n\s*\n', content)
    current_chunk = ""
    
    for para in paragraphs:
        # 如果当前块加上新段落不超过限制，则合并
        if len(current_chunk) + len(para) + 2 <= max_length:
            current_chunk += para + "\n\n"
        else:
            # 保存当前块
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            # 如果单个段落就超过限制，需要进一步切分
            if len(para) > max_length:
                # 按句子切分
                sentences = re.split(r'(?<=[.!?。！？])\s+', para)
                temp_chunk = ""
                for sent in sentences:
                    if len(temp_chunk) + len(sent) + 1 <= max_length:
                        temp_chunk += sent + " "
                    else:
                        if temp_chunk:
                            chunks.append(temp_chunk.strip())
                        # 如果单个句子也超过限制，强制切分
                        if len(sent) > max_length:
                            # 按字符切分，但尽量在空格处断开
                            words = sent.split()
                            temp_word_chunk = ""
                            for word in words:
                                if len(temp_word_chunk) + len(word) + 1 <= max_length:
                                    temp_word_chunk += word + " "
                                else:
                                    if temp_word_chunk:
                                        chunks.append(temp_word_chunk.strip())
                                    temp_word_chunk = word + " "
                            if temp_word_chunk:
                                temp_chunk = temp_word_chunk
                        else:
                            temp_chunk = sent + " "
                if temp_chunk:
                    current_chunk = temp_chunk
            else:
                current_chunk = para + "\n\n"
    
    # 添加最后一个块
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks if chunks else [content[:max_length]]


async def run_file_analysis_streaming(input_data: Union[str, Dict[str, Any]]) -> AsyncGenerator[Dict[str, Any], None]:
    """
    异步流式执行文件分析，返回OpenAI格式的自然语言流式响应。
    
    支持长文本智能切分：如果文本过长，会自动切分为多个块分别分析，然后合并结果。

    Args:
        input_data: 文件路径字符串或包含内容的字典，可以包含 query 参数用于针对性分析

    Yields:
        OpenAI格式的流式响应块，其中content字段包含格式化的自然语言文本：
        {
            'id': 'file-analysis-xxxxx',
            'object': 'file.analysis.chunk',
            'created': 1234567890,
            'model': 'file-analysis-model',
            'choices': [{'index': 0, 'delta': {'content': '📄 文件信息：文件名：test.pdf...'}, 'finish_reason': None}]
        }
    """
    # 生成统一的ID和基础信息
    _id = f"file-analysis-{uuid.uuid4().hex}"
    created = int(time.time())
    model = "file-analysis-model"

    try:
        # 添加调试日志
        logger.info(f"📊 开始文件分析，input_data类型: {type(input_data)}")
        
        # 提取文本内容和查询
        content = ""
        query = ""
        file_path = "unknown_file"
        
        if isinstance(input_data, dict):
            content = input_data.get('content', '')
            query = input_data.get('query', '')
            file_path = input_data.get('file_path', 'unknown_file')
            logger.info(f"📊 输入数据包含: file_path={file_path}, "
                       f"content长度={len(str(content))}, "
                       f"query={query}")
        elif isinstance(input_data, str):
            file_path = input_data
        
        # 先发送一个开始chunk，让调用者知道已经开始处理
        start_chunk = {
            "id": _id,
            "object": "file.analysis.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "content": "📄 开始分析文件...\n",
                    "type": "text"
                },
                "finish_reason": None
            }]
        }
        yield start_chunk
        
        # 如果输入是文件路径，需要先读取内容
        if isinstance(input_data, str):
            loop = asyncio.get_event_loop()
            # 读取文件内容
            from .FileAnalyseAgent import read_file_content
            content = await loop.run_in_executor(None, read_file_content, input_data)
            file_path = input_data
        
        # 检查文本长度，如果过长则切分
        MAX_CHUNK_LENGTH = 50000  # 每个块的最大长度
        text_chunks = []
        
        if isinstance(content, str) and len(content) > MAX_CHUNK_LENGTH:
            logger.warning(f"⚠️ 文本内容过长（{len(content)} 字符），将智能切分为多个块进行分析")
            text_chunks = _split_long_text(content, MAX_CHUNK_LENGTH)
            logger.info(f"📊 文本已切分为 {len(text_chunks)} 个部分")
            
            # 发送切分提示
            chunk_notice = f"\n⚠️ 注意：文本内容较长（{len(content)} 字符），已智能切分为 {len(text_chunks)} 个部分进行分析。\n\n"
            notice_chunk = {
                "id": _id,
                "object": "file.analysis.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {
                        "content": chunk_notice,
                        "type": "text"
                    },
                    "finish_reason": None
                }]
            }
            yield notice_chunk
        else:
            # 文本长度在限制内，直接使用
            text_chunks = [content] if content else []
        
        # 对每个文本块进行分析，并立即流式返回结果
        loop = asyncio.get_event_loop()
        total_chunks = len(text_chunks)
        
        for i, chunk_content in enumerate(text_chunks):
            if not chunk_content:
                continue
                
            chunk_num = i + 1
            
            # 如果有多个块，发送进度提示
            if total_chunks > 1:
                progress_notice = f"\n## 📄 第 {chunk_num}/{total_chunks} 部分分析（{len(chunk_content)} 字符）\n\n"
                progress_chunk = {
                    "id": _id,
                    "object": "file.analysis.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": progress_notice,
                            "type": "text"
                        },
                        "finish_reason": None
                    }]
                }
                yield progress_chunk
            
            # 构建当前块的输入数据
            chunk_input_data = {
                "file_path": file_path,
                "content": chunk_content,
                "query": query
            }
            
            # 执行文件分析（在线程池中执行，避免阻塞）
            result = await loop.run_in_executor(None, run_file_analysis, chunk_input_data)
            
            # 检查分析结果
            if not result.get("success", False):
                error_msg = result.get('error', '未知错误')
                logger.error(f"❌ 第 {chunk_num} 部分分析失败: {error_msg}")
                # 继续处理其他块，但记录错误
                error_text = f"⚠️ 第 {chunk_num} 部分分析失败: {error_msg}\n\n"
                error_chunk = {
                    "id": _id,
                    "object": "file.analysis.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": error_text,
                            "type": "text"
                        },
                        "finish_reason": None
                    }]
                }
                yield error_chunk
                continue
            
            # 获取当前块的分析结果
            chunk_analysis = result.get("result", "")
            
            if not chunk_analysis:
                logger.warning(f"⚠️ 第 {chunk_num} 部分分析完成但未返回结果")
                continue
            
            # 如果有多个块，添加块标题
            if total_chunks > 1:
                section_header = f"### 📋 第 {chunk_num} 部分分析结果\n\n"
                header_chunk = {
                    "id": _id,
                    "object": "file.analysis.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": section_header,
                            "type": "text"
                        },
                        "finish_reason": None
                    }]
                }
                yield header_chunk
            
            # 立即流式返回当前块的分析结果
            # 按段落分割（保留段落结构）
            paragraphs = re.split(r'\n\s*\n', chunk_analysis.strip())
            
            if not paragraphs or not any(p.strip() for p in paragraphs):
                # 如果没有段落，尝试按行分割
                paragraphs = [line for line in chunk_analysis.split('\n') if line.strip()]

            for paragraph in paragraphs:
                if paragraph.strip():  # 跳过空段落
                    # 如果段落太长，进一步分割
                    if len(paragraph) > 300:
                        # 按句子分割
                        sentences = re.split(r'(?<=[.!?。！？])\s+', paragraph)
                        for sentence in sentences:
                            if sentence.strip():
                                chunk = {
                                    "id": _id,
                                    "object": "file.analysis.chunk",
                                    "created": created,
                                    "model": model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {
                                                "content": sentence.strip() + " ",
                                                "type": "text"
                                            },
                                            "finish_reason": None,
                                        }
                                    ]
                                }
                                yield chunk
                                await asyncio.sleep(0.02)  # 小延迟模拟流式效果
                    else:
                        # 直接输出整个段落
                        chunk = {
                            "id": _id,
                            "object": "file.analysis.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        "content": paragraph.strip() + "\n\n",
                                        "type": "text"
                                    },
                                    "finish_reason": None
                                }
                            ]
                        }
                        yield chunk
                        await asyncio.sleep(0.05)  # 段落间稍长延迟
            
            # 如果有多个块，在块之间添加分隔符
            if total_chunks > 1 and chunk_num < total_chunks:
                separator = "\n---\n\n"
                separator_chunk = {
                    "id": _id,
                    "object": "file.analysis.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": separator,
                            "type": "text"
                        },
                        "finish_reason": None
                    }]
                }
                yield separator_chunk
        
        # 如果有多块分析，添加总结
        if total_chunks > 1:
            summary_text = "\n## 📝 分析总结\n\n以上是对文件各部分的详细分析，已全部完成。\n\n"
            summary_chunk = {
                "id": _id,
                "object": "file.analysis.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {
                        "content": summary_text,
                        "type": "text"
                    },
                    "finish_reason": None
                }]
            }
            yield summary_chunk

        # 发送完成标记
        complete_chunk = {
            "id": _id,
            "object": "file.analysis.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }
            ]
        }
        yield complete_chunk

    except Exception as e:
        error_text = f"❌ 文件分析过程中发生错误: {str(e)}"
        logger.error(error_text, exc_info=True)

        error_chunk = {
            "id": _id,
            "object": "file.analysis.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": error_text,
                        "type": "text"
                    },
                    "finish_reason": "stop"
                }
            ]
        }
        yield error_chunk


def run_file_analysis_sync_stream(input_data: Union[str, Dict[str, Any]]):
    """
    同步流式文件分析函数，返回符合OpenAI格式的流式响应。

    Args:
        input_data: 文件路径字符串或包含内容的字典，可以包含 query 参数用于针对性分析

    Yields:
        OpenAI格式的流式响应块
    """
    logger.info(f"📊 开始同步流式文件分析，input_data类型: {type(input_data)}")
    if isinstance(input_data, dict):
        logger.info(f"📊 输入数据详情: file_path={input_data.get('file_path', 'N/A')}, "
                   f"content长度={len(str(input_data.get('content', '')))}, "
                   f"query={input_data.get('query', 'N/A')}")
    
    # 使用队列在线程间传递数据
    q = queue.Queue()
    error_occurred = False
    first_chunk_received = False
    
    # 定义在独立线程中运行的异步函数
    def run_async_in_thread():
        nonlocal error_occurred, first_chunk_received
        async def async_part():
            try:
                logger.info("📊 异步线程开始执行文件分析")
                chunk_count = 0
                async for chunk in run_file_analysis_streaming(input_data):
                    chunk_count += 1
                    if chunk_count == 1:
                        first_chunk_received = True
                        logger.info(f"📊 收到第一个chunk，ID: {chunk.get('id', 'N/A')}")
                    q.put(chunk)
                logger.info(f"📊 异步线程完成，共发送 {chunk_count} 个chunks，发送结束信号")
                q.put(None)  # 发送结束信号
            except Exception as e:
                logger.error(f"❌ 异步线程执行失败: {e}", exc_info=True)
                error_occurred = True
                q.put(e)
        
        # 在新事件循环中运行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(async_part())
        except Exception as e:
            logger.error(f"❌ 事件循环执行失败: {e}", exc_info=True)
            error_occurred = True
            q.put(e)
        finally:
            try:
                loop.close()
            except:
                pass
    
    # 启动线程
    t = threading.Thread(target=run_async_in_thread)
    t.daemon = True  # 设置为守护线程
    t.start()
    logger.info("📊 已启动异步线程，等待第一个chunk...")
    
    # 从队列中获取结果并yield
    timeout_count = 0
    max_timeout = 300  # 最大等待时间300秒（5分钟）
    chunk_count = 0
    
    while True:
        try:
            # 使用较小的超时时间以避免阻塞
            item = q.get(timeout=1)
            timeout_count = 0  # 重置超时计数
            
            if item is None:  # 结束信号
                logger.info(f"📊 收到结束信号，共处理了 {chunk_count} 个chunks")
                break
            if isinstance(item, Exception):
                # 返回错误chunk
                logger.error(f"❌ 收到异常: {item}")
                error_chunk = {
                    "id": f"file-analysis-error-{uuid.uuid4().hex[:16]}",
                    "object": "file.analysis.chunk",
                    "created": int(time.time()),
                    "model": "file-analysis-model",
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": f"❌ 文件分析过程中发生错误: {str(item)}",
                            "type": "text"
                        },
                        "finish_reason": "stop"
                    }]
                }
                yield error_chunk
                break
            
            chunk_count += 1
            if chunk_count == 1:
                logger.info(f"📊 收到第一个chunk并yield，ID: {item.get('id', 'N/A')}")
            yield item
        except queue.Empty:
            timeout_count += 1
            # 如果等待第一个chunk超过5秒，记录警告
            if not first_chunk_received and timeout_count > 5:
                logger.warning(f"⚠️ 等待第一个chunk已超过 {timeout_count} 秒，线程状态: {'alive' if t.is_alive() else 'dead'}")
            
            # 检查线程是否还活着
            if not t.is_alive():
                logger.warning("⚠️ 异步线程已结束，但未收到结束信号")
                if error_occurred:
                    # 如果发生错误但队列为空，生成错误响应
                    error_chunk = {
                        "id": f"file-analysis-error-{uuid.uuid4().hex[:16]}",
                        "object": "file.analysis.chunk",
                        "created": int(time.time()),
                        "model": "file-analysis-model",
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "content": "❌ 文件分析线程异常结束",
                                "type": "text"
                            },
                            "finish_reason": "stop"
                        }]
                    }
                    yield error_chunk
                elif not first_chunk_received:
                    # 如果从未收到任何chunk，可能是启动失败
                    error_chunk = {
                        "id": f"file-analysis-error-{uuid.uuid4().hex[:16]}",
                        "object": "file.analysis.chunk",
                        "created": int(time.time()),
                        "model": "file-analysis-model",
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "content": "❌ 文件分析线程启动失败，未收到任何数据",
                                "type": "text"
                            },
                            "finish_reason": "stop"
                        }]
                    }
                    yield error_chunk
                break
            # 如果超时时间过长，也退出
            if timeout_count > max_timeout:
                logger.error(f"❌ 等待超时（{max_timeout}秒），共收到 {chunk_count} 个chunks")
                error_chunk = {
                    "id": f"file-analysis-error-{uuid.uuid4().hex[:16]}",
                    "object": "file.analysis.chunk",
                    "created": int(time.time()),
                    "model": "file-analysis-model",
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": f"❌ 文件分析超时（超过{max_timeout}秒）",
                            "type": "text"
                        },
                        "finish_reason": "stop"
                    }]
                }
                yield error_chunk
                break
            continue
    
    # 等待线程完成
    t.join(timeout=5)  # 设置较短的超时时间
    logger.info("📊 同步流式文件分析完成")


def file_analysis_run(input_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    同步执行文件分析的便捷函数。

    Args:
        input_data: 文件路径字符串或包含内容的字典

    Returns:
        包含分析结果的字典
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # 运行异步文件分析
    result = loop.run_until_complete(run_file_analysis_async(input_data))

    return result


async def run_file_analysis_async(input_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    异步执行文件分析。

    Args:
        input_data: 文件路径字符串或包含内容的字典

    Returns:
        包含完整分析结果的字典
    """
    # 收集所有流式输出
    chunks = []
    async for chunk in run_file_analysis_streaming(input_data):
        chunks.append(chunk)

    # 解析最后一个有效结果
    if not chunks:
        return {
            "success": False,
            "error": "No analysis results generated",
            "chunks": []
        }

    try:
        # 尝试解析最后一个chunk来获取最终状态
        last_chunk = json.loads(chunks[-1])

        if last_chunk.get("type") == "complete":
            return {
                "success": True,
                "file_path": last_chunk.get("file_path", "unknown"),
                "chunks": chunks
            }
        elif last_chunk.get("type") == "error":
            return {
                "success": False,
                "error": last_chunk.get("message", "Unknown error"),
                "chunks": chunks
            }
        else:
            return {
                "success": True,
                "chunks": chunks
            }

    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "Failed to parse analysis results",
            "chunks": chunks
        }