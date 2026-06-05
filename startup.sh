#!/bin/bash

# 客服管理平台启动脚本（服务器部署版）
# 说明：前端已通过本地构建上传到 nginx，此脚本只启动后端

echo "🚀 启动客服管理平台后端..."

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 启动后端
echo "📦 启动后端服务..."
cd "$SCRIPT_DIR/backend"

# 检查虚拟环境，不存在则创建
if [ -f ".venv/bin/activate" ]; then
    echo "✅ 使用虚拟环境"
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    echo "✅ 使用虚拟环境 (venv)"
    source venv/bin/activate
else
    echo "📥 创建虚拟环境..."
    python3 -m venv .venv
    source .venv/bin/activate
    echo "📥 安装依赖..."
    pip install -r requirements.txt --quiet
    echo "✅ 依赖安装完成"
fi

# 启动后端服务
echo "🔧 启动 uvicorn..."
pkill -f "uvicorn main:app" 2>/dev/null || true
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
    echo "   查看日志: tail -f backend/server.log"
fi

# 提示：前端是 nginx 托管的，不需要在此启动
echo ""
echo "=========================================="
echo "🎉 客服管理平台启动完成！"
echo ""
echo "📍 访问地址:"
echo "   - 前端: http://$(curl -s http://checkip.amazonaws.com 2>/dev/null || echo 'your-server-ip')"
echo "   - 后端: http://localhost:8000"
echo "   - API文档: http://localhost:8000/docs"
echo ""
echo "📋 常用命令:"
echo "   - 查看日志: tail -f backend/server.log"
echo "   - 关闭服务: ./shutdown.sh"
echo "=========================================="
