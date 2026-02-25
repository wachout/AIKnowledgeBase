"""
动态 System Prompt 生成器

基于知识库元数据和文件详情，动态生成和组装 System Prompt。
"""

from typing import Dict, Any, List, Optional
from Db.sqlite_db import cSingleSqlite

class DynamicPromptGenerator:
    """动态 System Prompt 生成器"""
    
    def __init__(self):
        pass
    
    def generate_system_prompt(self, query: str, knowledge_id: str, 
                              search_results: List[Dict[str, Any]] = None) -> str:
        """
        生成动态 System Prompt
        
        Args:
            query: 用户查询
            knowledge_id: 知识库ID
            search_results: 搜索结果（可选，用于提取文件元数据）
            
        Returns:
            生成的 System Prompt
        """
        # 1. 获取知识库元数据
        knowledge_metadata = self._get_knowledge_metadata(knowledge_id)
        
        # 2. 获取相关文件的元数据
        file_metadata_list = self._get_file_metadata_from_results(search_results or [])
        
        # 3. 组装 System Prompt
        system_prompt = self._assemble_prompt(query, knowledge_metadata, file_metadata_list)
        
        return system_prompt
    
    def _get_knowledge_metadata(self, knowledge_id: str) -> Dict[str, Any]:
        """获取知识库元数据"""
        try:
            knowledge_info = cSingleSqlite.search_knowledge_base_by_knowledge_id(knowledge_id)
            return {
                "knowledge_id": knowledge_id,
                "name": knowledge_info.get("name", "未知知识库"),
                "description": knowledge_info.get("description", "知识库未描述"),
                "create_time": knowledge_info.get("create_time", ""),
                "file_count": cSingleSqlite.search_file_num_by_knowledge_id(knowledge_id)
            }
        except Exception as e:
            print(f"⚠️ 获取知识库元数据失败: {e}")
            return {
                "knowledge_id": knowledge_id,
                "name": "未知知识库",
                "description": "知识库未描述",
                "file_count": 0
            }
    
    def _get_file_metadata_from_results(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从搜索结果中提取文件元数据"""
        file_metadata_list = []
        seen_file_ids = set()
        
        for result in search_results:
            file_id = result.get("file_id") or result.get("doc_id")
            if file_id and file_id not in seen_file_ids:
                seen_file_ids.add(file_id)
                
                try:
                    file_detail = cSingleSqlite.search_file_detail_info_by_file_id(file_id)
                    if file_detail:
                        file_metadata_list.append({
                            "file_id": file_id,
                            "file_name": file_detail.get("file_name", ""),
                            "recognized_title": file_detail.get("recognized_title", ""),
                            "overview": file_detail.get("overview", ""),
                            "author": file_detail.get("author", ""),
                            "valid_area_province": file_detail.get("valid_area_province", ""),
                            "valid_area_city": file_detail.get("valid_area_city", ""),
                            "tags": file_detail.get("tags", ""),
                            "category": file_detail.get("category", ""),
                            "catalog": file_detail.get("catalog", ""),
                            "valid_start_time": file_detail.get("valid_start_time", ""),
                            "valid_end_time": file_detail.get("valid_end_time", "")
                        })
                except Exception as e:
                    print(f"⚠️ 获取文件 {file_id} 元数据失败: {e}")
        
        return file_metadata_list
    
    def _assemble_prompt(self, query: str, knowledge_metadata: Dict[str, Any], 
                        file_metadata_list: List[Dict[str, Any]]) -> str:
        """组装 System Prompt"""
        
        # 基础角色定义
        base_role = """你是一个专业的智能助手，专门负责回答基于知识库内容的问题。"""
        
        # 知识库上下文
        kb_context = f"""
## 知识库信息
- 知识库名称: {knowledge_metadata.get('name', '未知')}
- 知识库描述: {knowledge_metadata.get('description', '未描述')}
- 文件数量: {knowledge_metadata.get('file_count', 0)} 个文件
"""
        
        # 文件元数据上下文
        file_context = ""
        if file_metadata_list:
            file_context = "\n## 相关文件元数据\n"
            for i, file_meta in enumerate(file_metadata_list[:5], 1):  # 最多显示5个文件
                file_context += f"""
### 文件 {i}: {file_meta.get('file_name', '未知文件名')}
- 识别标题: {file_meta.get('recognized_title', '无')}
- 概述: {file_meta.get('overview', '无概述')}
- 作者: {file_meta.get('author', '未知')}
- 类别: {file_meta.get('category', '未分类')}
- 标签: {file_meta.get('tags', '无标签')}
- 目录: {file_meta.get('catalog', '无目录')}
"""
                if file_meta.get('valid_area_province') or file_meta.get('valid_area_city'):
                    file_context += f"- 有效区域: {file_meta.get('valid_area_province', '')} {file_meta.get('valid_area_city', '')}\n"
                if file_meta.get('valid_start_time') or file_meta.get('valid_end_time'):
                    file_context += f"- 有效时间: {file_meta.get('valid_start_time', '')} 至 {file_meta.get('valid_end_time', '')}\n"
        
        # 用户查询上下文
        query_context = f"""
## 用户查询
{query}
"""
        
        # 回答指导原则
        guidelines = """
## 回答指导原则
1. **准确性优先**: 严格基于提供的知识库内容回答，不要编造信息
2. **上下文理解**: 充分利用文件元数据（类别、标签、目录等）来理解文档的上下文和适用范围
3. **结构化回答**: 如果涉及多个文件或主题，请清晰地组织答案结构
4. **引用来源**: 在回答中适当提及信息来源（文件名称、类别等）
5. **不确定性处理**: 如果信息不足，明确说明并建议用户提供更多信息
6. **元数据利用**: 
   - 利用文件的有效区域信息，判断内容的地理适用性
   - 利用文件的有效时间信息，判断内容的时间适用性
   - 利用文件的类别和标签，更好地理解文档的专业领域
"""
        
        # 组装完整的 System Prompt
        system_prompt = f"""{base_role}

{kb_context}

{file_context}

{query_context}

{guidelines}

请基于以上信息提供准确、全面、有帮助的回答。"""
        
        return system_prompt
