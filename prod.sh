#!/bin/bash
# 生产模式启动脚本：构建前端 + 启动后端（单进程服务前后端）
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "📦 构建前端..."
cd "$ROOT/frontend"
npm install --legacy-peer-deps 2>/dev/null || true
npx vite build --mode production
cd "$ROOT"

echo "🚀 启动服务..."
cd "$ROOT/backend"
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
