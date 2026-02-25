import os
import argparse
import asyncio
import json
import requests
import networkx as nx
import numpy as np
import shutil
import sys
from typing import Dict, Any, List

from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.llm.ollama import ollama_model_complete, ollama_embed
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.utils import EmbeddingFunc, setup_logger

from Config.embedding_config import get_embeddings

# 1. API Configuration - 从.env文件读取
from Config.embedding_config import get_embedding_config, get_vector_length
from Config.llm_config import get_llm_config

# 获取embedding配置
embedding_config = get_embedding_config()
EMBEDDING_API_KEY = embedding_config.api_key
EMBEDDING_BASE_URL = embedding_config.base_url
EMBEDDING_MODEL = embedding_config.model_name

# 获取LLM配置（如果需要）
llm_config = get_llm_config()
API_KEY = llm_config.api_key
BASE_URL = llm_config.base_url
CHAT_MODEL = llm_config.model_name

# 保留其他配置（如果需要）
DEEPSEEK_API_KEY = "sk-f932e5d2da4a4190aedb38d9e20cc6ed"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_CHAT_MODEL = "deepseek-reasoner"
WORKING_DIR = "lightrag_data"

# GRAPH_FILE_PATH = os.path.join(WORKING_DIR, "graph_chunk_entity_relation.graphml")
# OUTPUT_JSON_PATH = os.path.join(WORKING_DIR, "output_graph.json")

GRAPH_FILE_PATH = "graph_chunk_entity_relation.graphml"
OUTPUT_JSON_PATH = "output_graph.json"

# 2. Custom Model Handlers
async def qwen_llm_func(prompt: str, system_prompt: str = None, **kwargs) -> str:
    # 使用Ollama的qwen3:32b模型
    model_to_use = kwargs.pop('model', CHAT_MODEL)
    kwargs.pop('context', None)
    return await openai_complete_if_cache(
        prompt=prompt,
        model=model_to_use,
        api_key=API_KEY,  # Ollama不需要真实的API key
        base_url=BASE_URL,  # Ollama OpenAI兼容接口地址
        system_prompt=system_prompt, **kwargs
    )
    
    # headers = {
    #     "Content-Type": "application/json",
    # }
    # payload = {
    #     "model": "qwen3:32b",
    #     "messages": [
    #         {"role": "system", "content": system_prompt},
    #         {"role": "user", "content": prompt}
    #     ]
    # }
    # # 发送请求
    # response = requests.post(BASE_URL, headers=headers, data=json.dumps(payload))
    #
    # # 解析响应
    # if response.status_code == 200:
    #     result = response.json()
    #     return result
    # else:
    #     return {}
    
async def embedding(texts) -> np.ndarray:
    embed_text = []
    embeddings_model = get_embeddings()
    for text in texts:
        data = embeddings_model.embed_query(text)
        embed_text.append(data)
    return embed_text

async def qwen_embedding_func(texts: list[str], **kwargs) -> list[list[float]]:
    response_array = await openai_embed(
        texts=texts, model=EMBEDDING_MODEL, api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_BASE_URL, **kwargs
    )
    # response_array = await embedding(texts)
    
    if isinstance(response_array, np.ndarray):
        return response_array.tolist()
    elif(isinstance(response_array, list)):
        return response_array
    elif hasattr(response_array, 'data'):
        return [item.embedding for item in response_array.data]
    raise TypeError(f"Unexpected response type from embedding function: {type(response_array)}")

def notify_completion(file_path: str):
    """
    Prints a user-friendly completion message.
    """
    if file_path and os.path.exists(file_path):
        message = f"\n✅ 图谱抽取已成功完成！\n"
        message += f"   - 结果已保存到文件: {file_path}"
        print(message, file=sys.stderr)
    else:
        print("\n❌ 抽取失败或文件未保存。", file=sys.stderr)
        
async def initialize_rag(save_path):
    # 从配置获取向量维度
    dim = get_vector_length()
    print("Initializing LightRAG...", file=sys.stderr)
    print(f"Saving to directory: {save_path}", file=sys.stderr)
    rag = LightRAG(
        enable_llm_cache=True,  # 启用LLM响应缓存
        enable_llm_cache_for_entity_extract=True,  # 实体提取缓存
        working_dir=save_path,
        # llm_model_func=qwen_llm_func,
        embedding_func=EmbeddingFunc(func=qwen_embedding_func, 
                                     embedding_dim=dim,
                                     max_token_size=8192
                                     ),
        llm_model_func=ollama_model_complete,
        llm_model_name="qwen3:32b",
        # llm_model_name="qwen3:8b",
        llm_model_kwargs={"host": "http://192.168.35.125:11434"},
        # embedding_func=ollama_embed,
        graph_storage="NetworkXStorage",
        addon_params={"language": "Simplified Chinese"}
    )
    # IMPORTANT: Both initialization calls are required!
    await rag.initialize_storages()  # Initialize storage backends
    await initialize_pipeline_status()  # Initialize processing pipeline
    return rag

async def run_async(text_segments, save_path) -> str:
    """
    Main execution block to demonstrate the new workflow.
    """
    setup_logger("lightrag", level="INFO")
    print("--- Starting Graph Extraction Process ---", file=sys.stderr)
    # try:
    if(True):
        try:
            rag = await initialize_rag(save_path)
            await rag.ainsert(text_segments)
        except:
            if(rag):
                await rag.finalize_storages()
                return ""

        print(f"Processing {len(text_segments)} text segment(s)...", file=sys.stderr)
        
        graph_file_path = os.path.join(save_path, GRAPH_FILE_PATH)
        print(f"Reading persisted graph from {graph_file_path}...", file=sys.stderr)
        if not os.path.exists(graph_file_path):
            raise FileNotFoundError(f"LightRAG did not create the expected graph file at {graph_file_path}")
            return ""

        graph = nx.read_graphml(graph_file_path)
        
        # Relabel nodes to use entity names as IDs
        id_to_name_mapping = {node_id: data.get('id', node_id) for node_id, data in graph.nodes(data=True)}
        relabelled_graph = nx.relabel_nodes(graph, id_to_name_mapping, copy=True)
        graph_json_data = nx.node_link_data(relabelled_graph)
    
        # Save the final JSON to a file
        output_json_path = os.path.join(save_path, OUTPUT_JSON_PATH)
        
        print(f"Saving extracted graph to {output_json_path}...", file=sys.stderr)
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(graph_json_data, f, ensure_ascii=False, indent=4)
    
        # Verify that the file was created
        if not os.path.exists(output_json_path):
            raise IOError(f"Failed to save the output JSON file to {output_json_path}")
            return ""

        abs_path = os.path.abspath(output_json_path)
        print(f"File saved successfully to {abs_path}", file=sys.stderr)
        
        # 3. Call the notification function
        notify_completion(abs_path)

        # 4. Demonstrate using the returned path to read the data
        print(f"\n--- Reading data from returned path: {abs_path} ---", file=sys.stderr)
        with open(abs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(json.dumps(data, ensure_ascii=False, indent=4))
        
        await rag.finalize_storages()
        await rag.aclear_cache()
        success_file_path = os.path.join(save_path, "success.txt")
        _f = open(success_file_path, "w")
        _f.write("success")
        _f.close()
        return save_path
    else:
    # except Exception as e:
    #     print(f"\nAn error occurred during the process: {e}", file=sys.stderr)
        return ""
    
def run(md_path, chunk_core):
    current_path = os.getcwd()
    save_path = os.path.join(current_path, WORKING_DIR, chunk_core)
    
    # md_file = os.path.join(save_path, md_path)
    with open(md_path, 'r', encoding='utf-8') as f:
        _txt = f.read()

    result = asyncio.run(run_async(_txt, save_path))
    return result

#if __name__ == "__main__":
#    print("Starting LightRAG Graph Extraction...")
#    # Example text segments for testing
#
#    parser = argparse.ArgumentParser(description='Process some integers.')
#    parser.add_argument('md_file', type=str, help='The first parameter')
#    parser.add_argument('partition_core', type=str, help='The second parameter')
#    args = parser.parse_args()
#
#    current_path = os.getcwd()
#    chunk_core = args.partition_core
#    
#    save_path = os.path.join(current_path, WORKING_DIR, chunk_core)
#
#    file_path = os.path.join(save_path, args.md_file)
#    with open(file_path, 'r', encoding='utf-8') as f:
#        content = f.read()
#
#    result = asyncio.run(run_async(content, save_path))
#    if result:
#        print(f"Graph extraction completed successfully. Data saved in: {result}")
#    else:
#        print("Graph extraction failed.")   

    


