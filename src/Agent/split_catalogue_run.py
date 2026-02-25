import os

import asyncio

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain.embeddings import XinferenceEmbeddings
from langgraph.graph import StateGraph, START, END

from Agent.ArticleSplitCatalogue.split_catalogue import (
    GraphState,
    split_node,
)

load_dotenv()

llm = ChatOpenAI(
    temperature=0.6,
    model="deepseek-reasoner",
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",
)
# Using a multilingual model better suited for Chinese text
# embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
# embeddings = XinferenceEmbeddings(server_url="http://192.168.35.125:9997", model_uid="m3e-large")

# 1. Define the workflow
workflow = StateGraph(GraphState)
workflow.add_node("split", split_node)
workflow.add_edge(START, "split")
workflow.add_edge("split", END)
app = workflow.compile()

async def run(document_text, toc_data):
    print("\n--- Running Split and Catalogue ---")
    inputs = {
        "document_text": document_text,
        "toc_data": toc_data,
    }

    final_state = app.invoke(inputs)

    print("\n--- Workflow Complete. Final Chunks: ---")
    for i, chunk in enumerate(final_state['chunks']):
        print(f"--- Chunk {i+1} ---")
        print(chunk.page_content)
    print("\n-----------------------------------------")
    print(f"Total chunks created: {len(final_state['chunks'])}")
    return final_state

def run_sync(document_text, toc_data):
    return asyncio.run(run(document_text, toc_data))

