#!/bin/bash
# Docker 容器启动脚本：同时运行 Nginx + Uvicorn
# 正确处理 SIGTERM 信号，支持优雅退出

set -e

echo "🚀 Starting Customer Service Platform..."

# 启动 Uvicorn（后台）
uvicorn main:app --host 127.0.0.1 --port 8000 &
UVICORN_PID=$!

# 启动 Nginx（后台，非 daemon 模式在另一个方式处理）
nginx -g "daemon off;" &
NGINX_PID=$!

echo "✅ Uvicorn PID: $UVICORN_PID"
echo "✅ Nginx PID: $NGINX_PID"
echo "🎉 Platform is ready at http://0.0.0.0:80"

# 信号处理函数
cleanup() {
    echo "🛑 Received signal, shutting down gracefully..."
    # 先停 Nginx
    kill -TERM $NGINX_PID 2>/dev/null || true
    # 再停 Uvicorn
    kill -TERM $UVICORN_PID 2>/dev/null || true
    wait $NGINX_PID 2>/dev/null || true
    wait $UVICORN_PID 2>/dev/null || true
    echo "✅ All processes stopped."
    exit 0
}

# 注册信号处理
trap cleanup SIGTERM SIGINT SIGQUIT

# 等待任意进程退出（如果任一进程异常退出，整个容器退出）
wait -n $UVICORN_PID $NGINX_PID 2>/dev/null

# 如果到了这里，说明有进程退出了，执行清理
echo "⚠️ One process exited, shutting down..."
cleanup
