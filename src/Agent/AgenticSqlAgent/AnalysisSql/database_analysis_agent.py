# -*- coding:utf-8 -*-
"""
数据库信息拆解智能体
基于哲学、认知科学的视角，对数据库描述文本进行分类分析，并支持分词去重和向量存储
"""

import json
import re
import jieba
from typing import Dict, Any, List, Optional
from collections import Counter
from langchain_community.chat_models.tongyi import ChatTongyi
from Control.control_milvus import CControl
from Config.llm_config import get_chat_tongyi
from Config.embedding_config import get_embeddings


class DatabaseAnalysisAgent:
    """数据库信息拆解智能体：基于事物规则和第一性原理对文本进行分类，并支持分词去重和向量存储"""

    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, streaming=False, enable_thinking=False)

        # 初始化向量化和存储相关组件
        self.embedding = get_embeddings()
        self.milvus_control = CControl()

    def analyze_database_descriptions(self, des_list: List[List[str]], sql_id: str = None) -> Dict[str, Any]:
        """
        分析数据库描述文本，进行分类、分词去重和向量存储

        Args:
            des_list: 描述列表，格式为:
                [["table_id", "title", "content"], ["table_id", "title", "content"], ...]
                每个元素是一个包含三个元素的列表：[表格ID, 表格标题, 文本内容]
            sql_id: 数据库ID，用于milvus分区

        Returns:
            分类分析结果，包含:
            - success: 是否成功
            - classified_tables: 分类后的表信息
            - analysis_summary: 分析总结
            - total_tables: 表总数
            - vectors_saved: 保存的向量数量
            - error: 错误信息（如果有）
        """
        try:
            if not des_list:
                return {
                    "success": False,
                    "error": "输入的描述列表为空"
                }

            # 构建系统提示词
            system_prompt = """你现在是一个触及语言学、哲学和认知科学的学者，针对人类已经设定好的事物规则以及第一性原理：我们如何"切分世界"。

## 核心理论基础

### 第一性原理：世界的本质分类
1. **物质世界**：实体存在的物理基础
2. **信息世界**：实体属性的描述和记录
3. **时间世界**：实体变化的时间维度
4. **空间世界**：实体存在的空间维度

### 事物分类体系
1. **大类别**（Category）：
   - 物质实体：人、物、组织、场所等
   - 信息实体：数据、记录、文档等
   - 时间实体：事件、时期、阶段等
   - 空间实体：位置、区域、坐标等

2. **小类别**（Subcategory）：
   - 在大类别基础上进一步细分
   - 如：物质实体 → 人（学生、员工、客户）

3. **本源实体**（Primary Entity）：
   - 最基本的实体单位
   - 如：学生、订单、产品等

4. **属性**（Attributes）：
   - 实体的描述性特征
   - 如：姓名、年龄、颜色、状态等

5. **指标**（Metrics）：
   - 可度量的数值特征
   - 如：数量、金额、分数、比率等

6. **时间维度**（Time Dimensions）：
   - 时间相关的特征
   - 如：创建时间、修改时间、生效日期等

7. **空间维度**（Spatial Dimensions）：
   - 空间相关的特征
   - 如：地址、坐标、区域、位置等

## 分析任务
根据输入的多个段落文本描述，从哲学和认知科学的角度，**整体分析**这些文本中描述的实体和属性。请将这些文本段落作为一个整体进行综合分析，识别其中共同的实体类别、属性、指标等。

## 输出要求
返回JSON格式的分类结果。"""

            # 构建用户提示词 - 将所有文本段落合并在一起分析
            user_prompt = """请分析以下多个数据库表描述文本段落，**将这些文本作为一个整体进行综合分析**，从哲学和认知科学的视角进行分类：

## 输入文本段落（共 {total_count} 个段落）：

""".format(total_count=len(des_list))

            # 将所有文本段落合并展示
            all_texts = []
            for i, item in enumerate(des_list, 1):
                if isinstance(item, list) and len(item) >= 3:
                    table_id = item[0] if item[0] else ""
                    title = item[1] if item[1] else ""
                    content = item[2] if item[2] else ""
                    user_prompt += f"\n### 段落 {i} (table_id: {table_id}): {title}\n{content}\n"
                    all_texts.append({"index": i, "table_id": table_id, "title": title, "content": content})
                elif isinstance(item, dict):
                    # 兼容字典格式
                    title = item.get("title", "")
                    content = item.get("content", "")
                    table_id = item.get("table_id", "")
                    user_prompt += f"\n### 段落 {i}"
                    if table_id:
                        user_prompt += f" (table_id: {table_id})"
                    user_prompt += f": {title}\n{content}\n"
                    all_texts.append({"index": i, "title": title, "content": content, "table_id": table_id})

            user_prompt += """

## 分析要求

请将以上所有文本段落**作为一个整体进行综合分析**，识别这些文本中共同描述的：

1. **大类别**：这些文本整体描述的主要事物类型（物质实体、信息实体、时间实体、空间实体等）
2. **小类别**：在大类别基础上的细分
3. **本源实体**：这些文本中共同提到的核心实体
4. **属性**：这些文本中共同描述的实体属性特征
5. **指标**：这些文本中共同提到的可度量数值特征
6. **时间维度**：这些文本中共同涉及的时间相关特征
7. **空间维度**：这些文本中共同涉及的空间相关特征

## 输出JSON格式：
{{
    "success": true,
    "classified_tables": [
        {{
            "title": "段落标题",
            "content": "段落内容",
            "classification": {{
                "big_category": "大类别",
                "small_category": "小类别",
                "primary_entities": ["本源实体1", "本源实体2"],
                "attributes": ["属性1", "属性2"],
                "metrics": ["指标1", "指标2"],
                "time_dimensions": ["时间维度1", "时间维度2"],
                "spatial_dimensions": ["空间维度1", "空间维度2"]
            }},
            "confidence": 0.8,
            "analysis_reason": "分类理由说明"
        }}
    ],
    "analysis_summary": "整体分析总结（综合所有文本段落的分析结果）",
    "total_tables": {total_count},
    "category_distribution": {{
        "物质实体": 数量,
        "信息实体": 数量,
        "时间实体": 数量,
        "空间实体": 数量
    }}
}}

**重要提示**：
- 请将多个文本段落作为一个整体进行分析，识别共同的实体、属性、指标等
- 每个段落都应该有对应的分类结果
- 请确保返回有效的JSON格式（注意转义大括号）""".format(total_count=len(des_list))

            # 调用LLM进行分析
            response = self.llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ])

            content = response.content.strip()

            # 提取JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)

                # LLM分析成功后，进行分词去重和向量存储
                try:
                    vectors_saved = self._process_tables_and_save_vectors(des_list, result.get("classified_tables", []), sql_id)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"分词去重和向量存储失败: {e}")
                    vectors_saved = 0

                return {
                    "success": True,
                    "classified_tables": result.get("classified_tables", []),
                    "analysis_summary": result.get("analysis_summary", ""),
                    "total_tables": result.get("total_tables", 0),
                    "category_distribution": result.get("category_distribution", {}),
                    "vectors_saved": vectors_saved,
                    "raw_response": result
                }
            else:
                return {
                    "success": False,
                    "error": "无法解析大模型返回的JSON",
                    "raw_response": content
                }

        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON解析失败: {e}",
                "raw_response": content if 'content' in locals() else ""
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"数据库描述分析失败: {str(e)}"
            }

    def _process_tables_and_save_vectors(self, des_list: List[List[str]], classified_tables: List[Dict], sql_id: str) -> int:
        """
        为每个表格进行分词去重和向量存储

        Args:
            des_list: 原始描述列表，格式为[["table_id", "title", "content"], ...]
            classified_tables: LLM分类结果

        Returns:
            保存的向量数量
        """
        vectors_saved = 0

        # 创建table_id到classified_table的映射
        classified_map = {}
        for classified_table in classified_tables:
            # 从classified_table中提取table_id（可能在title中包含）
            title = classified_table.get("title", "")
            # 假设title格式为"段落 X (table_id: XXX): 标题"
            table_id_match = re.search(r'table_id:\s*([^)]+)', title)
            if table_id_match:
                table_id = table_id_match.group(1).strip()
                classified_map[table_id] = classified_table

        # 为每个表格单独处理
        for item in des_list:
            if isinstance(item, list) and len(item) >= 3:
                table_id = item[0]
                title = item[1]
                content = item[2]

                # 获取对应的分类结果
                classified_table = classified_map.get(table_id, {})

                try:
                    # 提取该表格的词汇
                    words = self._extract_words_for_table(title, content, classified_table, table_id)

                    # 生成向量并保存
                    self._save_table_vector(words, table_id, sql_id)

                    vectors_saved += 1

                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"处理表格 {table_id} 失败: {e}")
                    continue

        return vectors_saved

    def _extract_words_for_table(self, title: str, content: str, classified_table: Dict, table_id: str) -> List[str]:
        """
        为单个表格提取词汇，保持原始顺序并添加table_id标识

        Args:
            title: 表格标题
            content: 表格内容
            classified_table: 该表格的分类结果
            table_id: 表格ID

        Returns:
            带table_id标识的词汇列表，保持在table_title中的排列顺序
        """
        tagged_words = []

        # 从table_title中提取词汇，保持原始顺序
        title_words = list(jieba.cut(title))

        # 为每个词加上table_id标识，保持顺序
        for word in title_words:
            word = word.strip()
            if word and len(word) >= 2 and not all(c in ' \t\n\r\f\v' for c in word):
                # 在词后面加上table_id标识
                tagged_word = f"{word}_table_{table_id}"
                tagged_words.append(tagged_word)

        # 从content中提取词汇（可选，用于丰富词汇）
        content_words = list(jieba.cut(content))
        for word in content_words[:5]:  # 只取前5个词，避免内容过长
            word = word.strip()
            if word and len(word) >= 2 and not all(c in ' \t\n\r\f\v' for c in word):
                tagged_word = f"{word}_table_{table_id}"
                if tagged_word not in tagged_words:  # 避免重复
                    tagged_words.append(tagged_word)

        # 从LLM分类结果中提取重要词汇
        classification = classified_table.get("classification", {})
        important_words = []

        entities = classification.get("primary_entities", [])
        attributes = classification.get("attributes", [])
        metrics = classification.get("metrics", [])

        important_words.extend(entities[:2])  # 限制数量
        important_words.extend(attributes[:2])
        important_words.extend(metrics[:1])

        for word in important_words:
            word = word.strip()
            if word and len(word) >= 2:
                tagged_word = f"{word}_table_{table_id}"
                if tagged_word not in tagged_words:  # 避免重复
                    tagged_words.append(tagged_word)

        return tagged_words

    def _save_table_vector(self, words: List[str], table_id: str, sql_id: str):
        """
        将单个表格的分词结果保存到milvus向量库

        Args:
            words: 词汇列表（已按table_title顺序排列并加table_id标识）
            table_id: 表格ID
            sql_id: 数据库ID，用于milvus分区
        """
        try:
            # 将所有词合并成一个文本作为data
            combined_text = " ".join(words)

            # 使用words中的词汇组成title（这些词已在table_title中的组合排列，加上table_id）
            # 取前几个词作为title，避免title过长
            title_words = words[:5] if len(words) > 5 else words
            title = " ".join(title_words)

            # 生成向量
            embedding_vector = self.embedding.embed_query(combined_text)

            # 准备数据
            param = {
                "knowledge_partition": sql_id,  # 使用sql_id作为partition，同一数据库的表格在同一个partition
                "knowledge_collection": "database_table_analysis",  # 使用固定集合名
                "data": combined_text,
                "title": title,  # 使用从table_title拆解的词加上table_id组成的title
                "permission_level": "public",
                "doc_id": table_id,
            }

            # 设置索引参数
            index_params = {
                "metric_type": "COSINE",
                "index_type": "HNSW",
                "params": {"M": 16, "efConstruction": 256}
            }

            # 保存到milvus（如果启用）
            from Config.milvus_config import is_milvus_enabled
            if is_milvus_enabled():
                self.milvus_control.add_text(param, self.embedding, index_params)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"保存表格 {table_id} 到milvus失败: {e}")
            # 不抛出异常，继续执行
