#!/bin/bash

# 客服管理平台启动脚本

echo "🚀 启动客服管理平台..."

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 启动后端
echo "📦 启动后端服务..."
cd "$SCRIPT_DIR/backend"

# 检查虚拟环境
if [ -d ".venv" ]; then
    echo "✅ 使用虚拟环境"
    source .venv/bin/activate
else
    echo "⚠️ 虚拟环境不存在，使用系统 Python3"
fi

# 启动后端服务（不等待依赖安装）
echo "🔧 启动 uvicorn..."
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
BACKEND_PID=$!
echo "  后端 PID: $BACKEND_PID"

echo "⏳ 等待后端启动..."
sleep 3

# 检查后端是否启动成功
if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo "✅ 后端服务已启动: http://localhost:8000"
else
    echo "⚠️ 后端服务可能启动失败，请检查 server.log"
fi

# 启动前端
echo "🎨 启动前端服务..."
cd "$SCRIPT_DIR/frontend"

# 检查 node_modules
if [ ! -d "node_modules" ]; then
    echo "📥 安装前端依赖（首次需要较长时间）..."
    npm install
fi

# 启动前端开发服务器
echo "🔧 启动 Vite..."
nohup npm run dev > frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  前端 PID: $FRONTEND_PID"

echo "⏳ 等待前端启动..."
sleep 3

# 检查前端端口
if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1 || lsof -Pi :5174 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "✅ 前端服务已启动"
else
    echo "⚠️ 前端服务可能启动失败，请检查 frontend.log"
fi

echo ""
echo "=========================================="
echo "🎉 客服管理平台启动完成！"
echo ""
echo "📍 访问地址:"
echo "   - 前端: http://localhost:5173"
echo "   - 后端: http://localhost:8000"
echo "   - API文档: http://localhost:8000/docs"
echo ""
echo "📋 常用命令:"
echo "   - 查看日志: tail -f backend/server.log"
echo "   - 关闭服务: ./shutdown.sh"
echo "=========================================="
