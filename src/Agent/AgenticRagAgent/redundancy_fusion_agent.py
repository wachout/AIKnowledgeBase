# -*- coding:utf-8 -*-
"""
文本冗余信息融合智能体（不使用大模型）
解决信息冗余，将检索单元从"段"缩减到"句子"，按逻辑关系构建三层图
"""

import re
from typing import Dict, Any, List, Tuple
from collections import defaultdict
import jieba
from Config.embedding_config import get_embeddings
from Control.control_milvus import CControl as MilvusController
from Config.milvus_config import is_milvus_enabled


class RedundancyFusionAgent:
    """文本冗余信息融合智能体：句子级检索 + 三层图结构"""
    
    def __init__(self):
        self.embedding = get_embeddings()
        self.enabled = is_milvus_enabled()
        if self.enabled:
            self.milvus_control = MilvusController()
        else:
            self.milvus_control = None
        
        # 12种修辞关系（精简版RST）
        self.rhetorical_relations = {
            "因果": ["因为", "由于", "所以", "因此", "导致", "造成", "引起"],
            "条件": ["如果", "假如", "倘若", "只要", "除非", "当"],
            "转折": ["但是", "然而", "不过", "可是", "却", "尽管"],
            "并列": ["并且", "同时", "另外", "此外", "而且", "以及"],
            "递进": ["不仅", "而且", "甚至", "更", "还", "进一步"],
            "举例": ["例如", "比如", "譬如", "如", "像"],
            "对比": ["相比", "相对于", "与...相比", "而", "相反"],
            "总结": ["总之", "综上所述", "总的来说", "概括"],
            "解释": ["即", "也就是说", "换句话说", "换言之"],
            "时间": ["首先", "然后", "接着", "最后", "之后", "之前"],
            "目的": ["为了", "以便", "旨在", "目的是"],
            "让步": ["虽然", "尽管", "即使", "纵然"]
        }
    
    def split_into_sentences(self, text: str) -> List[str]:
        """
        将文本拆分成句子
        
        Args:
            text: 输入文本
            
        Returns:
            句子列表
        """
        # 中文句子分割：。！？；\n
        sentences = re.split(r'[。！？；\n]+', text)
        # 过滤空句子和过短句子
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
        return sentences
    
    def identify_rhetorical_relation(self, sentence: str) -> Tuple[str, float]:
        """
        识别句子的修辞关系
        
        Args:
            sentence: 句子文本
            
        Returns:
            (关系类型, 置信度)
        """
        sentence_lower = sentence.lower()
        max_score = 0
        best_relation = "背景"  # 默认关系
        
        for relation, keywords in self.rhetorical_relations.items():
            score = sum(1 for kw in keywords if kw in sentence_lower)
            if score > max_score:
                max_score = score
                best_relation = relation
        
        confidence = min(max_score / 3.0, 1.0)  # 归一化置信度
        return best_relation, confidence
    
    def extract_entities(self, sentence: str) -> List[str]:
        """
        提取句子中的实体（简单版本，使用jieba分词）
        
        Args:
            sentence: 句子文本
            
        Returns:
            实体列表
        """
        # 使用jieba分词
        words = jieba.cut(sentence)
        # 过滤停用词和标点
        stopwords = {"的", "了", "在", "是", "和", "与", "或", "但", "而", "等", "、", "，", "。"}
        entities = [w for w in words if w.strip() and w not in stopwords and len(w) > 1]
        return entities[:5]  # 最多返回5个实体
    
    def build_three_layer_graph(self, sentences: List[str], 
                                search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        构建三层图结构
        
        Args:
            sentences: 句子列表
            search_results: 搜索结果
            
        Returns:
            三层图结构：
            - sub_sentences: sub句子层（背景、因果、举例等）
            - core_sentences: core句层（核心事实）
            - topic_bridges: Topic层（文档"桥梁"）
        """
        sub_sentences = []  # sub句子层
        core_sentences = []  # core句层
        topic_bridges = []  # Topic层
        
        # 为每个句子分类
        for i, sentence in enumerate(sentences):
            relation, confidence = self.identify_rhetorical_relation(sentence)
            entities = self.extract_entities(sentence)
            
            sentence_info = {
                "sentence": sentence,
                "index": i,
                "relation": relation,
                "confidence": confidence,
                "entities": entities
            }
            
            # 根据修辞关系分类
            if relation in ["背景", "举例", "解释", "时间"]:
                sub_sentences.append(sentence_info)
            elif relation in ["因果", "条件", "目的"]:
                # 这些关系可能包含核心逻辑，但也可能是背景
                if confidence > 0.5:
                    core_sentences.append(sentence_info)
                else:
                    sub_sentences.append(sentence_info)
            else:
                # 其他关系（转折、并列、递进等）通常是核心事实
                core_sentences.append(sentence_info)
        
        # 构建Topic层（文档"桥梁"）
        # 通过实体对齐，找到跨文档的连接
        entity_to_sentences = defaultdict(list)
        for sentence_info in core_sentences + sub_sentences:
            for entity in sentence_info["entities"]:
                entity_to_sentences[entity].append(sentence_info)
        
        # 找出连接多个句子的实体（Topic桥梁）
        for entity, linked_sentences in entity_to_sentences.items():
            if len(linked_sentences) >= 2:  # 至少连接2个句子
                topic_bridges.append({
                    "entity": entity,
                    "linked_sentences": [s["sentence"] for s in linked_sentences[:3]],  # 最多3个句子
                    "sentence_count": len(linked_sentences)
                })
        
        return {
            "sub_sentences": sub_sentences,
            "core_sentences": core_sentences,
            "topic_bridges": topic_bridges,
            "total_sentences": len(sentences)
        }
    
    def fuse_redundant_information(self, search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        融合冗余信息：拆句、找关系、架桥梁
        
        Args:
            search_results: 搜索结果列表
            
        Returns:
            融合后的信息：
            - fused_content: 融合后的核心内容
            - three_layer_graph: 三层图结构
            - entity_triples: 实体-关系-实体三元组
        """
        try:
            # 步骤1: 拆句，把文档切成单句
            all_sentences = []
            sentence_to_source = {}  # 记录句子来源
            
            for result in search_results:
                content = result.get("content", "")
                doc_id = result.get("doc_id", "")
                
                sentences = self.split_into_sentences(content)
                for sentence in sentences:
                    all_sentences.append(sentence)
                    sentence_to_source[sentence] = doc_id
            
            print(f"📝 拆句完成：共 {len(all_sentences)} 个句子")
            
            # 步骤2: 找关系，识别句间12种修辞关系
            # 这一步已经在build_three_layer_graph中完成
            
            # 步骤3: 架桥梁，跨文档实体对齐，生成"实体-关系-实体"三元组
            three_layer_graph = self.build_three_layer_graph(all_sentences, search_results)
            
            # 生成实体-关系-实体三元组
            entity_triples = []
            core_sentences = three_layer_graph["core_sentences"]
            
            for i, sent_info1 in enumerate(core_sentences):
                entities1 = sent_info1["entities"]
                relation1 = sent_info1["relation"]
                
                # 查找与当前句子有共同实体的其他句子
                for j, sent_info2 in enumerate(core_sentences[i+1:], start=i+1):
                    entities2 = sent_info2["entities"]
                    relation2 = sent_info2["relation"]
                    
                    # 找共同实体
                    common_entities = set(entities1) & set(entities2)
                    if common_entities:
                        # 生成三元组
                        for entity in common_entities:
                            # 确定关系类型
                            if relation1 == relation2:
                                relation = relation1
                            else:
                                relation = f"{relation1}-{relation2}"
                            
                            entity_triples.append({
                                "entity1": entities1[0] if entities1 else "",
                                "relation": relation,
                                "entity2": entities2[0] if entities2 else "",
                                "bridge_entity": entity,
                                "sentence1": sent_info1["sentence"],
                                "sentence2": sent_info2["sentence"]
                            })
            
            # 融合核心内容（去重，保留核心事实）
            fused_content_parts = []
            seen_sentences = set()
            
            # 优先使用core句层的句子
            for sent_info in three_layer_graph["core_sentences"]:
                sentence = sent_info["sentence"]
                if sentence not in seen_sentences:
                    fused_content_parts.append(sentence)
                    seen_sentences.add(sentence)
            
            # 补充sub句层的重要背景信息
            for sent_info in three_layer_graph["sub_sentences"][:5]:  # 最多5个背景句
                sentence = sent_info["sentence"]
                if sentence not in seen_sentences:
                    fused_content_parts.append(sentence)
                    seen_sentences.add(sentence)
            
            fused_content = "\n".join(fused_content_parts)
            
            return {
                "success": True,
                "fused_content": fused_content,
                "three_layer_graph": three_layer_graph,
                "entity_triples": entity_triples[:10],  # 最多10个三元组
                "core_sentences": [s["sentence"] for s in three_layer_graph["core_sentences"]],
                "topic_bridges": three_layer_graph["topic_bridges"]
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"信息融合失败: {str(e)}",
                "fused_content": "",
                "three_layer_graph": {},
                "entity_triples": []
            }
