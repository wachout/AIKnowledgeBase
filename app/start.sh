#!/bin/bash

# 启动脚本 - 解决 EPERM 错误
# 使用方法: ./start.sh 或 bash start.sh

# 设置绝对路径
APP_DIR="/AIKnowledgeBase/app"

# 切换到应用目录
cd "$APP_DIR" || exit 1

# 检查 node_modules 是否存在
if [ ! -d "node_modules" ]; then
    echo "正在安装依赖..."
    # 使用绝对路径调用 npm
    /usr/local/bin/npm install
fi

# 启动开发服务器
echo "启动开发服务器..."
/usr/local/bin/npm run dev

