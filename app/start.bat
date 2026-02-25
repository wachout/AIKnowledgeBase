@echo off
REM Windows 启动脚本

cd /d "%~dp0"

if not exist "node_modules" (
    echo 正在安装依赖...
    call npm install
)

echo 启动开发服务器...
call npm run dev

