# -*- coding:utf-8 _*-


'''
Created on 2024年9月5日

@author: 
'''

# import torch
# from csv import excel
# EMBEDDING_DEVICE = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"

VECTOR_STORE_EMB_DB_PATH = './StoreEmb'

VECTOR_STORE_GRAPH_DB_PATH = './StoreGraph'

VECTOR_STORE_DB_DB_PATH = "./StoreMilvus"

VECTOR_MODEL_PATH = "./Weight"

# VECTOR_MODEL_NAME = "bge-large-zh-v1.5"

FILE_PATH = "./conf/file"

SQLITE_PATH = "./conf/splite"

MODEL_SOURCE = ["xinference", "qwen", "ollama"]

OLLAMA_MODEL = ["modelscope.cn/Qwen/Qwen2.5-32B-Instruct-GGUF:latest","deepseek-r1:32b"]

QWEN_EMBEDDING = ["text-embedding-v3",
"text-embedding-v2",
"text-embedding-v1"]

QWEN_RERANKER = ["gte-rerank"]

PROMPT_PAHT = "./conf/tmp"


