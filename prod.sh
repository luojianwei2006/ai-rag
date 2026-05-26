#!/bin/bash
# 生产模式启动脚本：构建前端 + 启动后端（单进程服务前后端）
set -e

cd "$(dirname "$0")"

echo "📦 构建前端..."
cd frontend
npm run build
cd ..

echo "🚀 启动服务..."
cd backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
