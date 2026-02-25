"""
多层强化学习智能体系统 - 图操作工具
"""

from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
import json


@dataclass
class GraphPath:
    """图路径"""
    nodes: List[str] = field(default_factory=list)
    edges: List[str] = field(default_factory=list)
    total_weight: float = 0.0


class GraphAnalyzer:
    """
    图分析器
    提供图结构分析功能
    """
    
    def __init__(self, rl_graph=None):
        self.graph = rl_graph
    
    def set_graph(self, rl_graph):
        """设置要分析的图"""
        self.graph = rl_graph
    
    def find_shortest_path(
        self,
        source: str,
        target: str
    ) -> Optional[GraphPath]:
        """
        查找最短路径（Dijkstra算法）
        """
        if not self.graph:
            return None
        
        # 初始化
        distances: Dict[str, float] = {node: float('inf') for node in self.graph.nodes}
        distances[source] = 0
        previous: Dict[str, Optional[str]] = {node: None for node in self.graph.nodes}
        unvisited: Set[str] = set(self.graph.nodes.keys())
        
        while unvisited:
            # 找最小距离节点
            current = min(unvisited, key=lambda n: distances[n])
            
            if distances[current] == float('inf'):
                break
            
            if current == target:
                break
            
            unvisited.remove(current)
            
            # 更新邻居
            neighbors = self.graph.get_neighbors(current)
            for neighbor_id in neighbors:
                if neighbor_id in unvisited:
                    edge = self.graph.get_edge(current, neighbor_id)
                    if edge:
                        new_dist = distances[current] + (1.0 / edge.weight if edge.weight > 0 else 1.0)
                        if new_dist < distances[neighbor_id]:
                            distances[neighbor_id] = new_dist
                            previous[neighbor_id] = current
        
        # 构建路径
        if distances[target] == float('inf'):
            return None
        
        path = GraphPath()
        current = target
        while current:
            path.nodes.insert(0, current)
            current = previous[current]
        
        path.total_weight = distances[target]
        return path
    
    def find_all_paths(
        self,
        source: str,
        target: str,
        max_depth: int = 10
    ) -> List[GraphPath]:
        """查找所有路径（DFS）"""
        if not self.graph:
            return []
        
        paths = []
        visited: Set[str] = set()
        current_path: List[str] = []
        
        def dfs(node: str, depth: int):
            if depth > max_depth:
                return
            
            visited.add(node)
            current_path.append(node)
            
            if node == target:
                paths.append(GraphPath(nodes=current_path.copy()))
            else:
                for neighbor_id in self.graph.get_neighbors(node):
                    if neighbor_id not in visited:
                        dfs(neighbor_id, depth + 1)
            
            current_path.pop()
            visited.remove(node)
        
        dfs(source, 0)
        return paths
    
    def compute_centrality(self) -> Dict[str, float]:
        """计算节点中心性（度中心性）"""
        if not self.graph:
            return {}
        
        centrality = {}
        total_nodes = len(self.graph.nodes)
        
        for node_id, node in self.graph.nodes.items():
            # 度中心性 = (入度 + 出度) / (2 * (n-1))
            in_degree = len(node.incoming_edges)
            out_degree = len(node.outgoing_edges)
            
            if total_nodes > 1:
                centrality[node_id] = (in_degree + out_degree) / (2 * (total_nodes - 1))
            else:
                centrality[node_id] = 0.0
        
        return centrality
    
    def find_cycles(self) -> List[List[str]]:
        """检测环"""
        if not self.graph:
            return []
        
        cycles = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []
        
        def dfs(node: str):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor_id in self.graph.get_neighbors(node):
                if neighbor_id not in visited:
                    dfs(neighbor_id)
                elif neighbor_id in rec_stack:
                    # 找到环
                    cycle_start = path.index(neighbor_id)
                    cycles.append(path[cycle_start:] + [neighbor_id])
            
            path.pop()
            rec_stack.remove(node)
        
        for node_id in self.graph.nodes:
            if node_id not in visited:
                dfs(node_id)
        
        return cycles
    
    def get_layer_statistics(self) -> Dict[int, Dict[str, Any]]:
        """获取各层统计"""
        if not self.graph:
            return {}
        
        stats = {}
        
        for layer in [1, 2, 3]:
            layer_nodes = [
                n for n in self.graph.nodes.values()
                if n.layer == layer
            ]
            
            if layer_nodes:
                stats[layer] = {
                    "node_count": len(layer_nodes),
                    "avg_value_estimate": sum(n.value_estimate for n in layer_nodes) / len(layer_nodes),
                    "total_edges": sum(len(n.incoming_edges) + len(n.outgoing_edges) for n in layer_nodes)
                }
        
        return stats


class GraphVisualizer:
    """
    图可视化器
    生成图的可视化表示
    """
    
    def __init__(self, rl_graph=None):
        self.graph = rl_graph
    
    def set_graph(self, rl_graph):
        """设置要可视化的图"""
        self.graph = rl_graph
    
    def to_mermaid(self) -> str:
        """生成Mermaid图表语法"""
        if not self.graph:
            return "graph TB\n    A[Empty Graph]"
        
        lines = ["graph TB"]
        
        # 按层分组
        for layer in [1, 2, 3]:
            layer_name = {1: "决策层", 2: "实施层", 3: "检验层"}.get(layer, f"层{layer}")
            lines.append(f"    subgraph {layer_name}")
            
            for node_id, node in self.graph.nodes.items():
                if node.layer == layer:
                    lines.append(f"        {node_id}[{node.agent_type}]")
            
            lines.append("    end")
        
        # 添加边
        for edge in self.graph.edges:
            lines.append(f"    {edge.source} --> {edge.target}")
        
        return "\n".join(lines)
    
    def to_ascii(self) -> str:
        """生成ASCII图表"""
        if not self.graph:
            return "Empty Graph"
        
        lines = []
        
        for layer in [1, 2, 3]:
            layer_name = {1: "决策层", 2: "实施层", 3: "检验层"}.get(layer, f"层{layer}")
            lines.append(f"=== {layer_name} ===")
            
            layer_nodes = [n for n in self.graph.nodes.values() if n.layer == layer]
            for node in layer_nodes:
                lines.append(f"  [{node.node_id}] {node.agent_type}")
                lines.append(f"    入边: {len(node.incoming_edges)}, 出边: {len(node.outgoing_edges)}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def to_json(self) -> str:
        """导出为JSON"""
        if not self.graph:
            return "{}"
        
        data = {
            "nodes": [
                {
                    "id": n.node_id,
                    "type": n.agent_type,
                    "layer": n.layer,
                    "value": n.value_estimate
                }
                for n in self.graph.nodes.values()
            ],
            "edges": [
                {
                    "id": e.edge_id,
                    "source": e.source,
                    "target": e.target,
                    "type": e.edge_type.value,
                    "weight": e.weight
                }
                for e in self.graph.edges
            ]
        }
        
        return json.dumps(data, indent=2, ensure_ascii=False)
