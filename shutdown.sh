#!/bin/bash
# 关闭客服平台前后端服务

echo "正在关闭客服平台服务..."

# 关闭后端 uvicorn 服务
echo "查找后端服务..."
UVICORN_PID=$(ps aux | grep "uvicorn.*main:app" | grep -v grep | awk '{print $2}')
if [ -n "$UVICORN_PID" ]; then
    echo "关闭后端服务 PID: $UVICORN_PID"
    kill $UVICORN_PID 2>/dev/null
    sleep 1
    if ps -p $UVICORN_PID > /dev/null 2>&1; then
        kill -9 $UVICORN_PID 2>/dev/null
    fi
    echo "后端服务已关闭"
else
    echo "后端服务未运行"
fi

# 关闭前端 Vite 服务
echo "查找前端服务..."
VITE_PID=$(ps aux | grep "vite" | grep -v grep | grep -v "vitejs" | awk '{print $2}')
if [ -n "$VITE_PID" ]; then
    echo "关闭前端服务 PID: $VITE_PID"
    kill $VITE_PID 2>/dev/null
    sleep 1
    if ps -p $VITE_PID > /dev/null 2>&1; then
        kill -9 $VITE_PID 2>/dev/null
    fi
    echo "前端服务已关闭"
else
    echo "前端服务未运行"
fi

# 检查 5173 和 8000 端口是否还被占用
echo ""
echo "检查端口占用情况..."
PORT_5173=$(lsof -ti:5173 2>/dev/null)
PORT_8000=$(lsof -ti:8000 2>/dev/null)

if [ -n "$PORT_5173" ]; then
    echo "端口 5173 仍被占用，强制终止进程: $PORT_5173"
    kill -9 $PORT_5173 2>/dev/null
fi

if [ -n "$PORT_8000" ]; then
    echo "端口 8000 仍被占用，强制终止进程: $PORT_8000"
    kill -9 $PORT_8000 2>/dev/null
fi

echo ""
echo "所有服务已关闭"
