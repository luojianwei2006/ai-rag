#!/bin/bash
# 客服管理平台 - 后端启动脚本（服务器专用）
# 用法: chmod +x server-startup.sh && ./server-startup.sh

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
LOG_FILE="$BACKEND_DIR/server.log"

echo "=========================================="
echo "🚀 客服管理平台后端启动脚本"
echo "=========================================="

# 1. 进入后端目录
cd "$BACKEND_DIR"

# 2. 创建/激活虚拟环境
if [ -f ".venv/bin/activate" ]; then
    echo "✅ 使用虚拟环境 (.venv)"
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    echo "✅ 使用虚拟环境 (venv)"
    source venv/bin/activate
else
    echo "📦 创建虚拟环境..."
    python3 -m venv .venv
    source .venv/bin/activate
fi

# 3. 安装依赖
echo "📦 检查并安装依赖..."
pip install -r requirements.txt --quiet 2>/dev/null || pip install -r requirements.txt
echo "✅ 依赖就绪"

# 4. 杀死旧进程
if lsof -i :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    OLD_PID=$(lsof -i :8000 -sTCP:LISTEN -t)
    echo "🔄 关闭旧进程 (PID: $OLD_PID)..."
    kill $OLD_PID 2>/dev/null || true
    sleep 2
fi

# 5. 启动后端
echo "🔧 启动后端服务..."
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > "$LOG_FILE" 2>&1 &
BACKEND_PID=$!
echo "   进程 PID: $BACKEND_PID"

# 6. 等待启动
echo "⏳ 等待启动..."
for i in $(seq 1 10); do
    if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
        echo "✅ 后端启动成功: http://localhost:8000"
        echo "   API文档:     http://localhost:8000/docs"
        echo "   健康检查:    http://localhost:8000/health"
        echo ""
        echo "📋 查看日志: tail -f $LOG_FILE"
        exit 0
    fi
    sleep 1
done

# 超时
echo "❌ 启动超时，请检查日志: tail -f $LOG_FILE"
exit 1
