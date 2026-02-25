from py2neo import Graph, Node, Relationship
from Config.neo4j_config import get_neo4j_connection_params, is_neo4j_enabled
import logging

logger = logging.getLogger(__name__)

class KnowledgeGraph():
    def __init__(self, uri=None, user=None, password=None):
        """
        初始化Neo4j图数据库连接
        
        Args:
            uri: Neo4j URI（可选，默认从.env读取）
            user: 用户名（可选，默认从.env读取）
            password: 密码（可选，默认从.env读取）
        """
        # 检查是否启用Neo4j
        self.enabled = is_neo4j_enabled()
        
        if not self.enabled:
            logger.info("Neo4j已禁用（NEO4J_FLAG=False），跳过连接初始化")
            self.graph = None
            return
        
        # 如果未提供参数，从.env文件读取配置
        if uri is None or user is None or password is None:
            config = get_neo4j_connection_params()
            uri = uri or config["uri"]
            user = user or config["user"]
            password = password or config["password"]
        
        try:
            self.graph = Graph(uri, auth=(user, password))
        except Exception as e:
            logger.error(f"Neo4j连接失败: {e}")
            self.graph = None
            raise
        # self.graph.nodes

    def create_node(self, labels, **properties):
        """
        创建节点
        :param labels: 节点标签
        :param properties: 节点属性
        :return: 创建的节点
        """
        if not self.enabled or self.graph is None:
            logger.debug("Neo4j已禁用，跳过创建节点操作")
            return None
            
        node = Node(labels, **properties)
        self.graph.create(node)
        return node
    
    def create_relationship(self, from_node, rel_type, to_node, **properties):
        """
        创建关系
        :param from_node: 起始节点
        :param to_node: 目标节点
        :param rel_type: 关系类型
        :param properties: 关系属性
        :return: 创建的关系
        """
        if not self.enabled or self.graph is None:
            logger.debug("Neo4j已禁用，跳过创建关系操作")
            return None
            
        relationship = Relationship(from_node, rel_type, to_node, **properties)
        self.graph.create(relationship)
        return relationship
    
    def query(self, cypher_query, parameters=None):
        """
        执行Cypher查询
        :param cypher_query: Cypher查询语句
        :param parameters: 查询参数（可选）
        :return: 查询结果
        """
        if not self.enabled or self.graph is None:
            logger.debug("Neo4j已禁用，跳过查询操作")
            return []
            
        return self.graph.run(cypher_query, parameters).data()    
    
    def delete_node(self, query):
        if not self.enabled or self.graph is None:
            logger.debug("Neo4j已禁用，跳过删除节点操作")
            return False
            
        self.graph.run(query)
        return True
    
    def delete_all(self):
        """
        删除所有图数据
        """
        if not self.enabled or self.graph is None:
            logger.debug("Neo4j已禁用，跳过删除所有图数据操作")
            return False
            
        self.graph.delete_all()
        return True

        
cSingleNeo4j = KnowledgeGraph() 
    

