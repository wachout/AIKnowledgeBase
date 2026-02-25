# -*- coding:utf-8 -*-

import sys

# 配置Python标准日志，避免absl相关问题
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("flask_grpc.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

from Servers import run_server

def run():
    run_server.run_model()

if __name__ == "__main__":
    run()