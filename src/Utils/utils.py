import os
import shutil
import json
import requests
import secrets
import string
import numpy as np

URL = "http://192.168.35.125:"
# URL = "http://192.168.35.125:"
FILE_PORT = "6393"

def request(param, api):
    url = URL + FILE_PORT + api
    payload = json.dumps(param)
    headers = {'Content-Type': 'application/json'}
    response = requests.request("POST", url, headers=headers, data=payload)
    return response.text

def generate_secure_string(length = 8):
    letters = string.ascii_letters  # 包含大小写字母（a-z, A-Z）
    return ''.join(secrets.choice(letters) for _ in range(length))

def remove_path(output_path):
    if(os.path.exists(output_path)):
        if(os.path.isdir(output_path)):
            shutil.rmtree(output_path)
        else:
            os.remove(output_path)
        return True
    else:
        return False

def cos_sim(vector_a, vector_b):
    vector_a = np.mat(vector_a)
    vector_b = np.mat(vector_b)
    num = float(vector_a * vector_b.T)
    denom = np.linalg.norm(vector_a) * np.linalg.norm(vector_b)
    cos = num / denom
    sim = 0.5 + 0.5 * cos
    return sim




