# -*- coding: utf-8 -*-


# import imp


import sys
# imp.reload(sys)
import configparser

class Config(object):

    def __init__(self):
        print("Config init")
        self.ReadSysConfig()


    def ReadFile(self, filename):    
        fr = open(filename, "r")
        content = fr.read()
        return set(content.split("\n"))

    def Get_P2p_Opposites(self):
        return self.p2p_opposites

    def GetSysConfig(self):
        return self.sysConfig

    def ReadSysConfig(self):
        self.sysConfig = {}
        cf = configparser.ConfigParser()
        cf.read("./conf/config.ini")
        conf = cf.sections()
        for item in conf:
            infos = cf.items(item)
            for info in infos:
                self.sysConfig[info[0]] = info[1]

        print("===>",self.sysConfig)

        # 设置智能问数相关配置
        self._set_sql_intelligence_config()

    def _set_sql_intelligence_config(self):
        """设置智能问数相关配置"""
        # ChromaDB 配置
        if "CHROMA_DB_PATH" not in self.sysConfig:
            self.sysConfig["CHROMA_DB_PATH"] = "conf/chroma_db/sql_schema"

        # 向量搜索配置
        if "VECTOR_SEARCH_LIMIT" not in self.sysConfig:
            self.sysConfig["VECTOR_SEARCH_LIMIT"] = "20"

        # 图搜索配置
        if "GRAPH_SEARCH_MAX_DEPTH" not in self.sysConfig:
            self.sysConfig["GRAPH_SEARCH_MAX_DEPTH"] = "3"

        # LangGraph 配置
        if "LANGGRAPH_MAX_ITERATIONS" not in self.sysConfig:
            self.sysConfig["LANGGRAPH_MAX_ITERATIONS"] = "50"

        # 工作流配置
        if "SQL_WORKFLOW_TIMEOUT" not in self.sysConfig:
            self.sysConfig["SQL_WORKFLOW_TIMEOUT"] = "300"  # 5分钟超时

config = Config()

