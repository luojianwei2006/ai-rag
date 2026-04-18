#!/bin/bash
# 一键启动脚本

echo "🚀 启动客服管理平台..."
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 启动后端
echo "📦 启动后端服务..."
cd "$PROJECT_DIR/backend"

if [ ! -d ".venv" ]; then
  echo "  创建Python虚拟环境..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip3 install -r requirements.txt -q 2>/dev/null || echo "  ⚠️ 依赖安装跳过"

echo "  后端启动在 http://localhost:8000"
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
BACKEND_PID=$!

# 等待后端启动
sleep 2

# 启动前端
echo "🎨 启动前端服务..."
cd "$PROJECT_DIR/frontend"

if [ ! -d "node_modules" ]; then
  echo "  安装前端依赖..."
  npm install
fi

echo "  前端启动在 http://localhost:5173"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ 启动完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🔧 管理员后台: http://localhost:5173/admin/login"
echo "     默认账号: admin / admin123"
echo ""
echo "  🏢 商户登录:   http://localhost:5173/login"
echo "  📋 API文档:    http://localhost:8000/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待退出
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT
wait
