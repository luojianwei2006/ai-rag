#!/bin/bash
# 生产模式启动脚本：构建前端 + 启动后端（单进程服务前后端）
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "📦 构建前端..."
cd "$ROOT/frontend"
npm install --legacy-peer-deps 2>/dev/null || true
npx vite build --mode production

echo "🐍 准备 Python 环境..."
cd "$ROOT/backend"
if [ ! -d ".venv" ]; then
    echo "   创建虚拟环境..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

echo "🚀 启动服务 (http://0.0.0.0:8000)..."
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
