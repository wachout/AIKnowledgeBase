# -*- coding:utf-8 _*-

import requests
import json

from Config import config

BASE_URL = config.config.GetSysConfig().get("base_url", "http://192.168.35.125:9997")

class CControl():

    def __init__(self, url, model_name="bge-reranker-large"):
        self.url = url
        self.name = model_name
    
    def result(self, text, document):
        data = {
          "query": text,
          "model": self.name,
          "documents": document
        }
        payload = json.dumps(data)
        headers = {
          'Content-Type': 'application/json'
        }
        
        response = requests.request("POST", BASE_URL, headers=headers, data=payload)

        return response.text
