import os
import re

from typing import List, TypedDict, Optional
from langchain.docstore.document import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from dotenv import load_dotenv 

load_dotenv()

CATALOGUE_OVERLAP_SIZE=os.getenv("CATALOGUE_SPLIT_SIZE")
CATALOGUE_SPLIT_SIZE=os.getenv("CATALOGUE_OVERLAP_SIZE")

def parse_json_toc(toc_data: dict) -> List[str]:
    """
    Recursively parses a JSON/dict table of contents to extract all headings.
    """
    headings = []
    for key, value in toc_data.items():
        headings.append(key)
        if isinstance(value, dict) and value:
            headings.extend(parse_json_toc(value))
    return headings

def _split_single_text_by_headings(document_text: str, headings: List[str]) -> List[Document]:
    """
    Helper function to split a single text block based on a list of headings.
    """
    if not headings:
        return [Document(page_content=document_text)]
    
    headings.sort(key=len, reverse=True)
    pattern = '|'.join(map(re.escape, headings))
    chunks = re.split(f'({pattern})', document_text)
    
    documents = []
    num_empty_sections = 0
    
    if chunks[0] and chunks[0].strip():
        documents.append(Document(page_content=chunks[0].strip()))
    
    for i in range(1, len(chunks), 2):
        heading = chunks[i]
        text = chunks[i+1] if (i+1) < len(chunks) else ""
        
        if not text.strip():
            num_empty_sections += 1
        
        documents.append(Document(page_content=(heading + text).strip()))
    
    if num_empty_sections > 0:
        print(f"--- Warning: Found {num_empty_sections} heading(s) with no descriptive content following them. ---")

    return [doc for doc in documents if doc.page_content]

def split_text_by_headings(document_text: str, headings: List[str]) -> List[Document]:
    """
    Splits the document text based on a list of headings.
    If the document is long, it's first split into large chunks, then by headings.
    """
    if len(document_text) > 10000:
        print("--- Document is long. First, splitting into large chunks... ---")
        large_chunk_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CATALOGUE_OVERLAP_SIZE,
            chunk_overlap=CATALOGUE_SPLIT_SIZE,
            length_function=len
        )
        large_chunks = large_chunk_splitter.split_text(document_text)
        
        all_final_chunks = []
        print(f"--- Found {len(large_chunks)} large chunks. Now splitting each by headings... ---")
        for i, chunk_text in enumerate(large_chunks):
            # For each large chunk, find which headings from the TOC are actually in it.
            headings_in_chunk = [h for h in headings if h in chunk_text]
            
            # Split the large chunk using only the headings it contains.
            chunks_from_large_block = _split_single_text_by_headings(chunk_text, headings_in_chunk)
            all_final_chunks.extend(chunks_from_large_block)
            
        return all_final_chunks
    else:
        print("--- Document is short, using headings for splitting. ---")
        return _split_single_text_by_headings(document_text, headings)

class GraphState(TypedDict):
    """
    Represents the state of our graph.
    """
    document_text: str
    toc_data: dict
    chunks: List[Document]

def split_node(state: GraphState):
    """
    Node to parse the TOC and split the document text into chunks.
    """
    print("--- Splitting Document ---")
    document_text = state["document_text"]
    toc_data = state["toc_data"]
    
    headings = parse_json_toc(toc_data)
    chunks = split_text_by_headings(document_text, headings)
    return {"chunks": chunks}

