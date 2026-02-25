# -*- coding:utf-8 -*-


class Graph:
    def __init__(self):
        self.nodes = set()
        self.edges = {}

    def add_node(self, value):
        self.nodes.add(value)
        self.edges[value] = []

    def add_edge(self, from_node, to_node, weight, description):
        self.edges[from_node].append({"node": to_node, "weight": weight, "description": description})
        self.edges[to_node].append({"node": from_node, "weight": weight, "description": description})

    def bfs(self, start_node, end_node):
        queue = [[start_node]]
        visited = {start_node}

        while queue:
            path = queue.pop(0)
            node = path[-1]

            if node == end_node:
                return path

            for neighbor_info in self.edges.get(node, []):
                neighbor = neighbor_info["node"]
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_path = list(path)
                    new_path.append(neighbor)
                    queue.append(new_path)

        return None

    def find_paths_for_nodes(self, nodes_to_visit):
        nodes_to_visit = set(nodes_to_visit)
        paths = []

        while nodes_to_visit:
            start_node = nodes_to_visit.pop()
            current_path = [start_node]
            
            while True:
                last_node_in_path = current_path[-1]
                nearest_neighbor = None
                shortest_distance = float('inf')

                # Find the nearest neighbor from the remaining nodes to visit
                for neighbor in nodes_to_visit:
                    path_to_neighbor = self.dijkstra(last_node_in_path, neighbor)
                    if path_to_neighbor:
                        # Calculate path length
                        distance = 0
                        for i in range(len(path_to_neighbor) - 1):
                            for edge in self.edges[path_to_neighbor[i]]:
                                if edge['node'] == path_to_neighbor[i+1]:
                                    distance += edge['weight']
                                    break
                        
                        if distance < shortest_distance:
                            shortest_distance = distance
                            nearest_neighbor = path_to_neighbor

                if nearest_neighbor:
                    # Extend the current path with the path to the nearest neighbor
                    current_path.extend(nearest_neighbor[1:])
                    # Remove the visited nodes from the set
                    for node in nearest_neighbor[1:]:
                        if node in nodes_to_visit:
                            nodes_to_visit.remove(node)
                else:
                    # No more reachable nodes from the current path
                    break
            
            paths.append(current_path)
            
        return paths

    def find_optimal_path_for_nodes(self, nodes_to_visit):
        import itertools

        nodes_to_visit = list(nodes_to_visit)
        best_path = None
        min_distance = float('inf')

        for permutation in itertools.permutations(nodes_to_visit):
            current_path = []
            current_distance = 0
            possible = True

            for i in range(len(permutation) - 1):
                path_segment = self.dijkstra(permutation[i], permutation[i+1])
                if not path_segment:
                    possible = False
                    break
                
                for step in path_segment:
                    current_distance += step['weight']
                
                current_path.extend(path_segment)

            if possible and current_distance < min_distance:
                min_distance = current_distance
                best_path = current_path
        
        return best_path

    def dijkstra(self, start_node, end_node):
        distances = {node: float('inf') for node in self.nodes}
        distances[start_node] = 0
        priority_queue = [(0, start_node)]
        previous_nodes = {node: None for node in self.nodes}

        while priority_queue:
            priority_queue.sort()
            current_distance, current_node = priority_queue.pop(0)

            if current_distance > distances[current_node]:
                continue

            if current_node == end_node:
                path = []
                while current_node is not None:
                    path.insert(0, current_node)
                    current_node = previous_nodes[current_node]
                
                detailed_path = []
                for i in range(len(path) - 1):
                    node1 = path[i]
                    node2 = path[i+1]
                    for edge in self.edges[node1]:
                        if edge['node'] == node2:
                            detailed_path.append({
                                "from": node1,
                                "to": node2,
                                "weight": edge['weight'],
                                "description": edge['description']
                            })
                            break
                return detailed_path

            for neighbor_info in self.edges.get(current_node, []):
                neighbor = neighbor_info["node"]
                weight = neighbor_info["weight"]
                distance = current_distance + weight

                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    previous_nodes[neighbor] = current_node
                    priority_queue.append((distance, neighbor))

        return None
    

def main():
    g = Graph()

    g.add_node("A")
    g.add_node("B")
    g.add_node("C")
    g.add_node("D")
    g.add_node("E")
    g.add_node("F")

    g.add_edge("A", "B", 1, "A to B")
    g.add_edge("A", "C", 4, "A to C")
    g.add_edge("B", "D", 2, "B to D")
    g.add_edge("C", "E", 5, "C to E")
    g.add_edge("D", "E", 1, "D to E")
    g.add_edge("D", "F", 3, "D to F")
    g.add_edge("E", "F", 1, "E to F")

    print("Shortest path from A to F (Dijkstra):")
    for step in g.dijkstra("A", "F"):
        print(f"  {step['from']} -> {step['to']} (weight: {step['weight']}, desc: {step['description']})")

    nodes_to_visit = ["A", "D", "F"]
    print(f"\nOptimal path for nodes {nodes_to_visit}:")
    optimal_path = g.find_optimal_path_for_nodes(nodes_to_visit)
    if optimal_path:
        for step in optimal_path:
            print(f"  {step['from']} -> {step['to']} (weight: {step['weight']}, desc: {step['description']})")

# if __name__ == "__main__":
#     main()
    