# -*- coding:utf-8 _*-

import os


class CControl():
    
    
    def __init__(self):
        pass
    
    def split_data(self, param):
        file = param["file"]
        
        if("metric_type" in param.keys()):
            metric_type = param["metric_type"]
        else:
            metric_type = "IP"
            param["metric_type"] = metric_type
        if("index_type" in param.keys()):
            index_type = param["index_type"]
        else:
            index_type = "HNSW"
            param["index_type"] = index_type
            
        index_params = {
            "index_type": index_type,
            "metric_type": metric_type,
            "params": {}
        }
        # if(os.path.isdir(file)):
        #     _f_list = os.listdir(file)
        #     for _f in _f_list:
        #         if("DS_Store" in _f):
        #             continue
        #         _f_path = os.path.join(file, _f)
        #         _md_f = self.file_obj.read_docx(_f_path)
        #
        #         _read_file = self.file_obj.read_file(_md_f)
        #         _graph = agent_split_run.workflow_run(_read_file)
        # else:
        #     _md_f = self.file_obj.read_docx(file)
        #
        #     _read_file = self.file_obj.read_file(_md_f)
        #     _graph = agent_split_run.workflow_run(_read_file)
        #     pass
        
    # def read_file(self, param):
    #     file = param["file"]
    #     if(os.path.isdir(file)):
    #         _f_list = os.listdir(file)
    #         for _f in _f_list:
    #             if("DS_Store" in _f):
    #                 continue
    #             _f_path = os.path.join(file, _f)
    #             _md_f = self.file_obj.read_docx(_f_path)
    #             _read_file = self.file_obj.read_file(_md_f)
    #     else:
    #         _md_f = self.file_obj.read_docx(file)
    #         _read_file = self.file_obj.read_file(_md_f)
        
        
        