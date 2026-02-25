"""
共识追踪系统 - 层次化共识依赖图
包含共识依赖关系管理、级联强度计算、拓扑排序等功能。
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from .types import ConsensusType

if TYPE_CHECKING:
    from .consensus_point import ConsensusPoint


class DependencyType(Enum):
    """共识依赖类型"""
    PREREQUISITE = "prerequisite"   # 前提依赖：子共识依赖于父共识的建立
    SUPPORTS = "supports"           # 支持关系：子共识支持/强化父共识
    REFINES = "refines"             # 细化关系：子共识是父共识的具体化
    CONTRADICTS = "contradicts"     # 矛盾关系：子共识与父共识存在冲突
    EXTENDS = "extends"             # 扩展关系：子共识扩展父共识的范围
    DERIVES = "derives"             # 派生关系：子共识由父共识推导而来


class ConsensusHierarchyLevel(Enum):
    """
    共识层次级别
    
    层次越低（数值越小），共识越基础、越重要
    """
    FOUNDATIONAL = 1   # 基础层（前提共识）
    STRUCTURAL = 2     # 结构层（框架共识）
    OPERATIONAL = 3    # 操作层（实施共识）
    DETAIL = 4         # 细节层（辅助共识）
    
    @classmethod
    def from_consensus_type(cls, consensus_type: ConsensusType) -> 'ConsensusHierarchyLevel':
        """根据共识类型推断层次级别"""
        mapping = {
            ConsensusType.CORE: cls.FOUNDATIONAL,
            ConsensusType.STRATEGIC: cls.STRUCTURAL,
            ConsensusType.TACTICAL: cls.OPERATIONAL,
            ConsensusType.TECHNICAL: cls.OPERATIONAL,
            ConsensusType.PROCEDURAL: cls.DETAIL,
            ConsensusType.AUXILIARY: cls.DETAIL
        }
        return mapping.get(consensus_type, cls.DETAIL)


@dataclass
class ConsensusDependency:
    """
    共识依赖关系
    
    描述两个共识点之间的依赖关系，用于构建共识依赖图。
    """
    parent_id: str                          # 父共识ID
    child_id: str                           # 子共识ID
    dependency_type: DependencyType         # 依赖类型
    strength: float = 1.0                   # 依赖强度 (0.0-1.0)
    created_at: str = None                  # 创建时间
    evidence: str = ""                      # 依赖关系的证据/说明
    is_inferred: bool = False               # 是否是推断出来的
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def get_impact_factor(self) -> float:
        """
        获取依赖关系的影响因子
        
        不同类型的依赖关系对共识强度传播的影响不同
        """
        impact_factors = {
            DependencyType.PREREQUISITE: 0.9,   # 前提依赖影响最大
            DependencyType.SUPPORTS: 0.7,       # 支持关系影响较大
            DependencyType.REFINES: 0.6,        # 细化关系影响中等
            DependencyType.EXTENDS: 0.5,        # 扩展关系影响中等
            DependencyType.DERIVES: 0.4,        # 派生关系影响较小
            DependencyType.CONTRADICTS: -0.3    # 矛盾关系为负影响
        }
        return impact_factors.get(self.dependency_type, 0.5) * self.strength
    
    def is_positive(self) -> bool:
        """依赖关系是否是正向的"""
        return self.dependency_type != DependencyType.CONTRADICTS
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "parent_id": self.parent_id,
            "child_id": self.child_id,
            "dependency_type": self.dependency_type.value,
            "strength": self.strength,
            "created_at": self.created_at,
            "evidence": self.evidence,
            "is_inferred": self.is_inferred
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConsensusDependency':
        return cls(
            parent_id=data.get("parent_id", ""),
            child_id=data.get("child_id", ""),
            dependency_type=DependencyType(data.get("dependency_type", "supports")),
            strength=data.get("strength", 1.0),
            created_at=data.get("created_at"),
            evidence=data.get("evidence", ""),
            is_inferred=data.get("is_inferred", False)
        )


class ConsensusDependencyGraph:
    """
    共识依赖图
    
    管理共识点之间的依赖关系，支持：
    - 添加/移除依赖关系
    - 计算级联强度
    - 获取拓扑排序的聚合顺序
    - 层次化共识分析
    """
    
    def __init__(self):
        # 依赖关系列表
        self.dependencies: List[ConsensusDependency] = []
        # 邻接表: parent_id -> List[child_id]
        self._adjacency: Dict[str, List[str]] = {}
        # 反向邻接表: child_id -> List[parent_id]
        self._reverse_adjacency: Dict[str, List[str]] = {}
        # 共识ID到层次的映射
        self._hierarchy_levels: Dict[str, ConsensusHierarchyLevel] = {}
        # 缓存的拓扑排序
        self._topo_order_cache: Optional[List[str]] = None
        # 缓存的级联强度
        self._cascading_strength_cache: Dict[str, float] = {}
    
    def add_dependency(self, parent_id: str, child_id: str,
                       dep_type: DependencyType,
                       strength: float = 1.0,
                       evidence: str = "",
                       is_inferred: bool = False) -> bool:
        """
        添加共识依赖关系
        
        Args:
            parent_id: 父共识ID
            child_id: 子共识ID
            dep_type: 依赖类型
            strength: 依赖强度
            evidence: 依赖关系的证据
            is_inferred: 是否是推断出来的
            
        Returns:
            bool: 是否成功添加
        """
        # 检查是否会形成环
        if self._would_create_cycle(parent_id, child_id):
            return False
        
        # 检查是否已存在
        for dep in self.dependencies:
            if dep.parent_id == parent_id and dep.child_id == child_id:
                # 更新已有依赖
                dep.dependency_type = dep_type
                dep.strength = strength
                dep.evidence = evidence
                self._invalidate_caches()
                return True
        
        # 添加新依赖
        dependency = ConsensusDependency(
            parent_id=parent_id,
            child_id=child_id,
            dependency_type=dep_type,
            strength=strength,
            evidence=evidence,
            is_inferred=is_inferred
        )
        self.dependencies.append(dependency)
        
        # 更新邻接表
        if parent_id not in self._adjacency:
            self._adjacency[parent_id] = []
        self._adjacency[parent_id].append(child_id)
        
        if child_id not in self._reverse_adjacency:
            self._reverse_adjacency[child_id] = []
        self._reverse_adjacency[child_id].append(parent_id)
        
        self._invalidate_caches()
        return True
    
    def remove_dependency(self, parent_id: str, child_id: str) -> bool:
        """移除依赖关系"""
        for i, dep in enumerate(self.dependencies):
            if dep.parent_id == parent_id and dep.child_id == child_id:
                self.dependencies.pop(i)
                
                # 更新邻接表
                if parent_id in self._adjacency:
                    self._adjacency[parent_id] = [
                        cid for cid in self._adjacency[parent_id] if cid != child_id
                    ]
                if child_id in self._reverse_adjacency:
                    self._reverse_adjacency[child_id] = [
                        pid for pid in self._reverse_adjacency[child_id] if pid != parent_id
                    ]
                
                self._invalidate_caches()
                return True
        return False
    
    def _would_create_cycle(self, parent_id: str, child_id: str) -> bool:
        """检查添加依赖是否会形成环"""
        if parent_id == child_id:
            return True
        
        # BFS检查从 child_id 是否能到达 parent_id
        visited = set()
        queue = [child_id]
        
        while queue:
            current = queue.pop(0)
            if current == parent_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            
            for neighbor in self._adjacency.get(current, []):
                if neighbor not in visited:
                    queue.append(neighbor)
        
        return False
    
    def _invalidate_caches(self) -> None:
        """使缓存失效"""
        self._topo_order_cache = None
        self._cascading_strength_cache.clear()
    
    def set_hierarchy_level(self, consensus_id: str, 
                            level: ConsensusHierarchyLevel) -> None:
        """设置共识的层次级别"""
        self._hierarchy_levels[consensus_id] = level
    
    def get_hierarchy_level(self, consensus_id: str) -> ConsensusHierarchyLevel:
        """
        获取共识的层次级别
        
        如果未明确设置，根据依赖关系推断
        """
        if consensus_id in self._hierarchy_levels:
            return self._hierarchy_levels[consensus_id]
        
        # 根据依赖关系推断
        parents = self._reverse_adjacency.get(consensus_id, [])
        if not parents:
            # 没有父共识，认为是基础层
            return ConsensusHierarchyLevel.FOUNDATIONAL
        
        # 有父共识，层次比父共识低一级
        parent_levels = [
            self.get_hierarchy_level(pid).value for pid in parents
        ]
        max_parent_level = max(parent_levels)
        
        # 层次不超过 DETAIL
        return ConsensusHierarchyLevel(
            min(max_parent_level + 1, ConsensusHierarchyLevel.DETAIL.value)
        )
    
    def get_parents(self, consensus_id: str) -> List[str]:
        """获取共识的所有父共识ID"""
        return self._reverse_adjacency.get(consensus_id, [])
    
    def get_children(self, consensus_id: str) -> List[str]:
        """获取共识的所有子共识ID"""
        return self._adjacency.get(consensus_id, [])
    
    def get_ancestors(self, consensus_id: str) -> List[str]:
        """获取共识的所有祖先共识ID"""
        ancestors = []
        visited = set()
        queue = self.get_parents(consensus_id)
        
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            ancestors.append(current)
            queue.extend(self.get_parents(current))
        
        return ancestors
    
    def get_descendants(self, consensus_id: str) -> List[str]:
        """获取共识的所有后代共识ID"""
        descendants = []
        visited = set()
        queue = self.get_children(consensus_id)
        
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            descendants.append(current)
            queue.extend(self.get_children(current))
        
        return descendants
    
    def calculate_cascading_strength(self, consensus_id: str,
                                      consensus_strengths: Dict[str, float]) -> float:
        """
        计算级联强度
        
        考虑依赖的父共识强度对当前共识的影响。
        如果父共识强度较低，子共识的有效强度也会降低。
        
        Args:
            consensus_id: 共识ID
            consensus_strengths: 共识ID到原始强度的映射
            
        Returns:
            float: 级联强度因子 (0.0 - 1.0+)
        """
        # 检查缓存
        if consensus_id in self._cascading_strength_cache:
            return self._cascading_strength_cache[consensus_id]
        
        base_strength = consensus_strengths.get(consensus_id, 0.5)
        
        # 获取父共识
        parent_ids = self.get_parents(consensus_id)
        if not parent_ids:
            # 没有父共识，返回1.0
            self._cascading_strength_cache[consensus_id] = 1.0
            return 1.0
        
        # 计算父共识的影响
        parent_impacts = []
        for parent_id in parent_ids:
            # 获取依赖关系
            dep = self._get_dependency(parent_id, consensus_id)
            if dep is None:
                continue
            
            # 父共识的强度
            parent_strength = consensus_strengths.get(parent_id, 0.5)
            
            # 依赖关系的影响因子
            impact = dep.get_impact_factor()
            
            if dep.is_positive():
                # 正向依赖：父共识强度越高，加成越多
                parent_impacts.append(parent_strength * impact)
            else:
                # 矛盾关系：父共识强度越高，惩罚越多
                parent_impacts.append(-parent_strength * abs(impact))
        
        if not parent_impacts:
            cascading_factor = 1.0
        else:
            # 加权平均
            avg_impact = sum(parent_impacts) / len(parent_impacts)
            # 转换为因子 (0.5 - 1.5)
            cascading_factor = 1.0 + avg_impact * 0.5
            cascading_factor = max(0.3, min(1.5, cascading_factor))
        
        self._cascading_strength_cache[consensus_id] = cascading_factor
        return cascading_factor
    
    def _get_dependency(self, parent_id: str, child_id: str) -> Optional[ConsensusDependency]:
        """获取两个共识之间的依赖关系"""
        for dep in self.dependencies:
            if dep.parent_id == parent_id and dep.child_id == child_id:
                return dep
        return None
    
    def get_aggregation_order(self) -> List[str]:
        """
        获取拓扑排序的聚合顺序
        
        确保父共识在子共识之前被处理，以便正确计算级联强度。
        
        Returns:
            List[str]: 按拓扑顺序排列的共识ID列表
        """
        if self._topo_order_cache is not None:
            return self._topo_order_cache
        
        # 收集所有共识ID
        all_ids = set()
        for dep in self.dependencies:
            all_ids.add(dep.parent_id)
            all_ids.add(dep.child_id)
        
        if not all_ids:
            return []
        
        # 计算入度
        in_degree = {cid: 0 for cid in all_ids}
        for dep in self.dependencies:
            in_degree[dep.child_id] += 1
        
        # 拓扑排序 (Kahn算法)
        queue = [cid for cid in all_ids if in_degree[cid] == 0]
        result = []
        
        while queue:
            current = queue.pop(0)
            result.append(current)
            
            for child_id in self._adjacency.get(current, []):
                in_degree[child_id] -= 1
                if in_degree[child_id] == 0:
                    queue.append(child_id)
        
        # 检查是否有环
        if len(result) != len(all_ids):
            # 有环，返回空列表
            return []
        
        self._topo_order_cache = result
        return result
    
    def calculate_partial_consensus_contribution(self,
                                                  consensus_id: str,
                                                  total_participants: int,
                                                  supporter_count: int) -> float:
        """
        计算部分共识对整体的贡献度
        
        考虑：
        - 支持者占比
        - 层次级别
        - 依赖关系数量
        
        Args:
            consensus_id: 共识ID
            total_participants: 总参与者数
            supporter_count: 支持者数
            
        Returns:
            float: 贡献度 (0.0 - 1.0)
        """
        if total_participants <= 0:
            return 0.0
        
        # 支持者占比
        support_ratio = supporter_count / total_participants
        
        # 层次权重
        level = self.get_hierarchy_level(consensus_id)
        level_weights = {
            ConsensusHierarchyLevel.FOUNDATIONAL: 1.0,
            ConsensusHierarchyLevel.STRUCTURAL: 0.8,
            ConsensusHierarchyLevel.OPERATIONAL: 0.6,
            ConsensusHierarchyLevel.DETAIL: 0.4
        }
        level_weight = level_weights.get(level, 0.5)
        
        # 依赖关系数量加成
        children_count = len(self.get_children(consensus_id))
        dependency_bonus = min(0.2, children_count * 0.05)
        
        contribution = support_ratio * level_weight + dependency_bonus
        return min(1.0, contribution)
    
    def get_hierarchy_summary(self) -> Dict[str, List[str]]:
        """获取各层次的共识ID列表"""
        summary = {
            "foundational": [],
            "structural": [],
            "operational": [],
            "detail": []
        }
        
        all_ids = set()
        for dep in self.dependencies:
            all_ids.add(dep.parent_id)
            all_ids.add(dep.child_id)
        
        for cid in all_ids:
            level = self.get_hierarchy_level(cid)
            if level == ConsensusHierarchyLevel.FOUNDATIONAL:
                summary["foundational"].append(cid)
            elif level == ConsensusHierarchyLevel.STRUCTURAL:
                summary["structural"].append(cid)
            elif level == ConsensusHierarchyLevel.OPERATIONAL:
                summary["operational"].append(cid)
            else:
                summary["detail"].append(cid)
        
        return summary
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "dependencies": [dep.to_dict() for dep in self.dependencies],
            "hierarchy_levels": {
                k: v.value for k, v in self._hierarchy_levels.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConsensusDependencyGraph':
        """反序列化"""
        graph = cls()
        
        for dep_data in data.get("dependencies", []):
            dep = ConsensusDependency.from_dict(dep_data)
            graph.dependencies.append(dep)
            
            # 重建邻接表
            if dep.parent_id not in graph._adjacency:
                graph._adjacency[dep.parent_id] = []
            graph._adjacency[dep.parent_id].append(dep.child_id)
            
            if dep.child_id not in graph._reverse_adjacency:
                graph._reverse_adjacency[dep.child_id] = []
            graph._reverse_adjacency[dep.child_id].append(dep.parent_id)
        
        for cid, level_value in data.get("hierarchy_levels", {}).items():
            graph._hierarchy_levels[cid] = ConsensusHierarchyLevel(level_value)
        
        return graph
