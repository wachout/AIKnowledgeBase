import os
import json

import networkx as nx

def run_importer(file_path):
    """
    Main function to run the importer.
    """
            
    # files_to_import = "graph_chunk_entity_relation.graphml"
    # file_path = os.path.join(data_directory, files_to_import)
    
    G = nx.read_graphml(file_path)    
    
    # for node_id, data in G.nodes(data=True):
    #     labels = data.get('labels', [])
    #     properties = {k: v for k, v in data.items() if k != 'labels'}
        # db.add_node(node_id, labels=labels, properties=properties)
        # print(f"Node ID: {node_id}, Labels: {labels}, Properties: {properties}")
    
    # for source_id, target_id, data in G.edges(data=True):
    #     rel_type = data.get('type', 'RELATED_TO')
    #     properties = {k: v for k, v in data.items() if k != 'type'}
        # db.add_relationship(source_id, target_id, rel_type, properties=properties)
        # print(f"Relationship: {source_id} -[{rel_type}]-> {target_id}, Properties: {properties}")
    
    return G

def read_graph_json(file_path: str):
    """
    Reads the graph JSON file from the specified directory.
    """
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Graph JSON file not found at {file_path}")
    
    try:
        with open(file_path, 'r') as f:
            # Check if file is empty
            content = f.read()
            if not content:
                print(f"   File {file_path} is empty. Skipping.")
                return
            data = json.loads(content)
            
            return data
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from file {file_path}: {e}")
        return ""
    except Exception as e:
        print(f"Unexpected error reading file {file_path}: {e}")
        return ""
    
    
        
        