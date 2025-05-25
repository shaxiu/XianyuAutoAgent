#!/bin/bash

echo "启动闲鱼AutoAgent管理后台"
echo "========================="

# 获取当前目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 检查环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3 命令"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "错误: 未找到 npm 命令"
    exit 1
fi

# 创建日志目录
mkdir -p logs

# 安装后端API依赖
echo "安装后端API依赖..."
cd "$SCRIPT_DIR/admin/api"
pip install -r requirements.txt

# 安装前端依赖
echo "安装前端依赖..."
cd "$SCRIPT_DIR/admin_frontend"
npm install

# 启动后端API (后台运行)
echo "启动后端API服务..."
cd "$SCRIPT_DIR/admin"
python3 start_admin.py > "$SCRIPT_DIR/logs/api.log" 2>&1 &
API_PID=$!
echo "API服务已启动 (PID: $API_PID)"

# 启动前端服务 (后台运行)
echo "启动前端服务..."
cd "$SCRIPT_DIR/admin_frontend"
npm run dev > "$SCRIPT_DIR/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "前端服务已启动 (PID: $FRONTEND_PID)"

echo ""
echo "管理后台已启动!"
echo "API服务: http://localhost:8000"
echo "前端界面: http://localhost:3000"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 捕获中断信号
trap 'echo "正在停止服务..."; kill $API_PID $FRONTEND_PID 2>/dev/null; echo "服务已停止"; exit 0' INT

# 保持脚本运行
while true; do
    sleep 1
done 