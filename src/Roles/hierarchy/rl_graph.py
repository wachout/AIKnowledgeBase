"""
强化学习有向图
管理智能体节点和边的拓扑结构，支持奖励传播和策略更新
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any
import numpy as np

from .types import (
    AgentNode, Edge, EdgeType, LayerType, AgentState, Policy,
    Experience, AgentAction
)

logger = logging.getLogger(__name__)


class RLGraph:
    """
    强化学习有向图
    管理多层智能体的图结构，支持奖励传播和信息流动
    """
    
    def __init__(self):
        self.nodes: Dict[str, AgentNode] = {}
        self.edges: List[Edge] = []
        self._adjacency_list: Dict[str, List[str]] = {}  # 邻接表
        self._reverse_adjacency: Dict[str, List[str]] = {}  # 反向邻接表（用于反向传播）
        self._edge_index: Dict[Tuple[str, str], Edge] = {}  # 边索引
        
    def add_node(self, node: AgentNode) -> bool:
        """添加节点"""
        if node.node_id in self.nodes:
            logger.warning(f"节点已存在: {node.node_id}")
            return False
        
        self.nodes[node.node_id] = node
        self._adjacency_list[node.node_id] = []
        self._reverse_adjacency[node.node_id] = []
        logger.info(f"添加节点: {node.node_id}, 层级: {node.layer}, 类型: {node.agent_type}")
        return True
    
    def remove_node(self, node_id: str) -> bool:
        """移除节点"""
        if node_id not in self.nodes:
            return False
        
        # 移除相关的边
        self.edges = [e for e in self.edges if e.source != node_id and e.target != node_id]
        
        # 更新邻接表
        del self._adjacency_list[node_id]
        del self._reverse_adjacency[node_id]
        
        for adj_list in self._adjacency_list.values():
            if node_id in adj_list:
                adj_list.remove(node_id)
        
        for adj_list in self._reverse_adjacency.values():
            if node_id in adj_list:
                adj_list.remove(node_id)
        
        # 更新边索引
        self._edge_index = {k: v for k, v in self._edge_index.items() 
                           if k[0] != node_id and k[1] != node_id}
        
        del self.nodes[node_id]
        return True
    
    def add_edge(self, edge: Edge) -> bool:
        """添加边"""
        if edge.source not in self.nodes or edge.target not in self.nodes:
            logger.error(f"边的端点不存在: {edge.source} -> {edge.target}")
            return False
        
        edge_key = (edge.source, edge.target)
        if edge_key in self._edge_index:
            logger.warning(f"边已存在: {edge.source} -> {edge.target}")
            return False
        
        self.edges.append(edge)
        self._adjacency_list[edge.source].append(edge.target)
        self._reverse_adjacency[edge.target].append(edge.source)
        self._edge_index[edge_key] = edge
        
        # 更新节点的边引用
        self.nodes[edge.source].outgoing_edges.append(edge.edge_id)
        self.nodes[edge.target].incoming_edges.append(edge.edge_id)
        
        logger.debug(f"添加边: {edge.source} -> {edge.target}, 类型: {edge.edge_type.value}")
        return True
    
    def remove_edge(self, source: str, target: str) -> bool:
        """移除边"""
        edge_key = (source, target)
        if edge_key not in self._edge_index:
            return False
        
        edge = self._edge_index[edge_key]
        self.edges.remove(edge)
        self._adjacency_list[source].remove(target)
        self._reverse_adjacency[target].remove(source)
        del self._edge_index[edge_key]
        
        # 更新节点的边引用
        if edge.edge_id in self.nodes[source].outgoing_edges:
            self.nodes[source].outgoing_edges.remove(edge.edge_id)
        if edge.edge_id in self.nodes[target].incoming_edges:
            self.nodes[target].incoming_edges.remove(edge.edge_id)
        
        return True
    
    def get_edge(self, source: str, target: str) -> Optional[Edge]:
        """获取边"""
        return self._edge_index.get((source, target))
    
    def get_neighbors(self, node_id: str) -> List[str]:
        """获取节点的邻居（出边指向的节点）"""
        return self._adjacency_list.get(node_id, [])
    
    def get_predecessors(self, node_id: str) -> List[str]:
        """获取节点的前驱（入边来源的节点）"""
        return self._reverse_adjacency.get(node_id, [])
    
    def get_layer_nodes(self, layer: int) -> List[AgentNode]:
        """获取某层的所有节点"""
        return [node for node in self.nodes.values() if node.layer == layer]
    
    def get_subgraph(self, layer: int) -> 'RLGraph':
        """获取某层的子图"""
        subgraph = RLGraph()
        
        # 添加该层的节点
        layer_node_ids = set()
        for node in self.get_layer_nodes(layer):
            subgraph.add_node(node)
            layer_node_ids.add(node.node_id)
        
        # 添加该层节点之间的边
        for edge in self.edges:
            if edge.source in layer_node_ids and edge.target in layer_node_ids:
                subgraph.add_edge(edge)
        
        return subgraph
    
    def get_adjacency_matrix(self) -> Tuple[np.ndarray, List[str]]:
        """
        获取邻接矩阵
        返回: (邻接矩阵, 节点ID列表)
        """
        node_ids = list(self.nodes.keys())
        n = len(node_ids)
        node_index = {nid: i for i, nid in enumerate(node_ids)}
        
        matrix = np.zeros((n, n))
        for edge in self.edges:
            if edge.is_active:
                i = node_index[edge.source]
                j = node_index[edge.target]
                matrix[i, j] = edge.weight
        
        return matrix, node_ids
    
    def propagate_reward(self, reward: float, source_node: str, 
                        discount: float = 0.9, 
                        edge_types: Optional[Set[EdgeType]] = None) -> Dict[str, float]:
        """
        奖励反向传播
        从源节点向前驱节点传播奖励
        
        Args:
            reward: 初始奖励值
            source_node: 奖励来源节点
            discount: 折扣因子
            edge_types: 允许传播的边类型
        
        Returns:
            各节点分配的奖励
        """
        if edge_types is None:
            edge_types = {EdgeType.REWARD, EdgeType.TASK_FLOW, EdgeType.FEEDBACK}
        
        rewards = {source_node: reward}
        visited = {source_node}
        queue = [(source_node, reward)]
        
        while queue:
            current_node, current_reward = queue.pop(0)
            
            # 获取前驱节点
            for pred_id in self.get_predecessors(current_node):
                if pred_id in visited:
                    continue
                
                # 检查边类型
                edge = self.get_edge(pred_id, current_node)
                if edge and edge.edge_type in edge_types and edge.is_active:
                    # 计算传播的奖励
                    propagated_reward = current_reward * discount * edge.weight
                    
                    if pred_id in rewards:
                        rewards[pred_id] += propagated_reward
                    else:
                        rewards[pred_id] = propagated_reward
                    
                    visited.add(pred_id)
                    queue.append((pred_id, propagated_reward))
        
        logger.info(f"奖励传播完成: 从 {source_node} 传播到 {len(rewards)} 个节点")
        return rewards
    
    def forward_pass(self, source_node: str, 
                    message: Dict[str, Any],
                    edge_types: Optional[Set[EdgeType]] = None) -> Dict[str, Dict[str, Any]]:
        """
        前向传递（信息流动）
        从源节点向后继节点传递消息
        
        Args:
            source_node: 消息来源节点
            message: 要传递的消息
            edge_types: 允许传递的边类型
        
        Returns:
            各节点接收的消息
        """
        if edge_types is None:
            edge_types = {EdgeType.TASK_FLOW, EdgeType.COORDINATION}
        
        messages = {source_node: message}
        visited = {source_node}
        queue = [source_node]
        
        while queue:
            current_node = queue.pop(0)
            current_message = messages[current_node]
            
            for neighbor_id in self.get_neighbors(current_node):
                edge = self.get_edge(current_node, neighbor_id)
                if edge and edge.edge_type in edge_types and edge.is_active:
                    if neighbor_id not in visited:
                        # 传递消息（可以在这里加入消息转换逻辑）
                        messages[neighbor_id] = {
                            "from": current_node,
                            "original": current_message,
                            "via_edge": edge.edge_id
                        }
                        visited.add(neighbor_id)
                        queue.append(neighbor_id)
        
        return messages
    
    def update_edge_weights(self, updates: Dict[Tuple[str, str], float]):
        """批量更新边权重"""
        for edge_key, new_weight in updates.items():
            if edge_key in self._edge_index:
                self._edge_index[edge_key].weight = new_weight
    
    def get_critical_path(self, start_node: str, end_node: str) -> List[str]:
        """
        获取关键路径（最长路径）
        使用拓扑排序 + 动态规划
        """
        # BFS找到所有可达路径
        paths = []
        queue = [(start_node, [start_node])]
        
        while queue:
            current, path = queue.pop(0)
            
            if current == end_node:
                paths.append(path)
                continue
            
            for neighbor in self.get_neighbors(current):
                if neighbor not in path:  # 避免环
                    queue.append((neighbor, path + [neighbor]))
        
        if not paths:
            return []
        
        # 返回最长路径
        return max(paths, key=len)
    
    def detect_cycles(self) -> List[List[str]]:
        """检测图中的环"""
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in self.get_neighbors(node):
                if neighbor not in visited:
                    dfs(neighbor, path + [neighbor])
                elif neighbor in rec_stack:
                    # 找到环
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
            
            rec_stack.remove(node)
        
        for node_id in self.nodes:
            if node_id not in visited:
                dfs(node_id, [node_id])
        
        return cycles
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取图的统计信息"""
        layer_counts = {}
        for node in self.nodes.values():
            layer_counts[node.layer] = layer_counts.get(node.layer, 0) + 1
        
        edge_type_counts = {}
        for edge in self.edges:
            edge_type_counts[edge.edge_type.value] = edge_type_counts.get(edge.edge_type.value, 0) + 1
        
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "nodes_per_layer": layer_counts,
            "edges_per_type": edge_type_counts,
            "average_degree": sum(len(adj) for adj in self._adjacency_list.values()) / max(len(self.nodes), 1),
            "has_cycles": len(self.detect_cycles()) > 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "nodes": {
                nid: {
                    "node_id": node.node_id,
                    "agent_type": node.agent_type,
                    "layer": node.layer,
                    "value_estimate": node.value_estimate
                }
                for nid, node in self.nodes.items()
            },
            "edges": [
                {
                    "edge_id": edge.edge_id,
                    "source": edge.source,
                    "target": edge.target,
                    "edge_type": edge.edge_type.value,
                    "weight": edge.weight,
                    "is_active": edge.is_active
                }
                for edge in self.edges
            ],
            "statistics": self.get_statistics()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RLGraph':
        """从字典反序列化"""
        graph = cls()
        
        # 恢复节点
        for nid, node_data in data.get("nodes", {}).items():
            node = AgentNode(
                node_id=node_data["node_id"],
                agent_type=node_data["agent_type"],
                layer=node_data["layer"],
                state=AgentState(agent_id=node_data["node_id"]),
                policy=Policy(),
                value_estimate=node_data.get("value_estimate", 0.0)
            )
            graph.add_node(node)
        
        # 恢复边
        for edge_data in data.get("edges", []):
            edge = Edge(
                edge_id=edge_data["edge_id"],
                source=edge_data["source"],
                target=edge_data["target"],
                edge_type=EdgeType(edge_data["edge_type"]),
                weight=edge_data.get("weight", 1.0),
                is_active=edge_data.get("is_active", True)
            )
            graph.add_edge(edge)
        
        return graph


class GraphBuilder:
    """图构建器 - 辅助创建标准拓扑结构"""
    
    @staticmethod
    def build_hierarchical_graph(
        decision_agents: List[str],
        implementation_groups: List[List[str]],
        validation_agents: List[str]
    ) -> RLGraph:
        """
        构建层次化图结构
        
        Args:
            decision_agents: 决策层智能体ID列表
            implementation_groups: 实施层智能体组（每组一个列表）
            validation_agents: 检验层智能体ID列表
        """
        graph = RLGraph()
        
        # 添加决策层节点
        for agent_id in decision_agents:
            node = AgentNode(
                node_id=agent_id,
                agent_type="decision",
                layer=1,
                state=AgentState(agent_id=agent_id),
                policy=Policy(layer=1)
            )
            graph.add_node(node)
        
        # 决策层内部全连接
        for i, agent1 in enumerate(decision_agents):
            for j, agent2 in enumerate(decision_agents):
                if i != j:
                    graph.add_edge(Edge(
                        source=agent1,
                        target=agent2,
                        edge_type=EdgeType.COORDINATION,
                        weight=1.0
                    ))
        
        # 添加实施层节点
        impl_agents = []
        for group_idx, group in enumerate(implementation_groups):
            for agent_id in group:
                node = AgentNode(
                    node_id=agent_id,
                    agent_type="implementation",
                    layer=2,
                    state=AgentState(agent_id=agent_id),
                    policy=Policy(layer=2)
                )
                graph.add_node(node)
                impl_agents.append(agent_id)
            
            # 组内全连接
            for i, agent1 in enumerate(group):
                for j, agent2 in enumerate(group):
                    if i != j:
                        graph.add_edge(Edge(
                            source=agent1,
                            target=agent2,
                            edge_type=EdgeType.COORDINATION,
                            weight=1.0
                        ))
        
        # 决策层 -> 实施层（任务流）
        for dec_agent in decision_agents:
            for impl_agent in impl_agents:
                graph.add_edge(Edge(
                    source=dec_agent,
                    target=impl_agent,
                    edge_type=EdgeType.TASK_FLOW,
                    weight=1.0
                ))
        
        # 添加检验层节点
        for agent_id in validation_agents:
            node = AgentNode(
                node_id=agent_id,
                agent_type="validation",
                layer=3,
                state=AgentState(agent_id=agent_id),
                policy=Policy(layer=3)
            )
            graph.add_node(node)
        
        # 检验层内部全连接
        for i, agent1 in enumerate(validation_agents):
            for j, agent2 in enumerate(validation_agents):
                if i != j:
                    graph.add_edge(Edge(
                        source=agent1,
                        target=agent2,
                        edge_type=EdgeType.COORDINATION,
                        weight=1.0
                    ))
        
        # 实施层 -> 检验层（结果上报）
        for impl_agent in impl_agents:
            for val_agent in validation_agents:
                graph.add_edge(Edge(
                    source=impl_agent,
                    target=val_agent,
                    edge_type=EdgeType.TASK_FLOW,
                    weight=1.0
                ))
        
        # 检验层 -> 决策层（反馈）
        for val_agent in validation_agents:
            for dec_agent in decision_agents:
                graph.add_edge(Edge(
                    source=val_agent,
                    target=dec_agent,
                    edge_type=EdgeType.FEEDBACK,
                    weight=1.0
                ))
        
        # 检验层 -> 实施层（反馈）
        for val_agent in validation_agents:
            for impl_agent in impl_agents:
                graph.add_edge(Edge(
                    source=val_agent,
                    target=impl_agent,
                    edge_type=EdgeType.FEEDBACK,
                    weight=0.5
                ))
        
        logger.info(f"构建层次化图完成: {graph.get_statistics()}")
        return graph
