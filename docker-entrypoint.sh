#!/bin/bash
# Docker 容器启动脚本：同时运行 Nginx + Uvicorn

set -e

echo "Starting Customer Service Platform..."

# 启动后端
uvicorn main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

# 启动 Nginx
nginx -g "daemon off;" &
NGINX_PID=$!

echo "Uvicorn PID: $UVICORN_PID"
echo "Nginx PID: $NGINX_PID"
echo "Platform is ready!"

# 等待任一进程退出
wait -n $UVICORN_PID $NGINX_PID 2>/dev/null

# 一个退出则全部退出
kill $UVICORN_PID $NGINX_PID 2>/dev/null
