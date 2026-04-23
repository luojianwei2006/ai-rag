#!/bin/bash
# 一键启动脚本

echo "🚀 启动客服管理平台..."
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 检查 sqlite3 版本（ChromaDB 要求 >= 3.35.0）
echo "🔍 检查 sqlite3 版本..."
SQLITE_VER=$(python3 -c "import sqlite3; print(sqlite3.sqlite_version)" 2>/dev/null)
SQLITE_MAJOR=$(echo "$SQLITE_VER" | cut -d. -f1)
SQLITE_MINOR=$(echo "$SQLITE_VER" | cut -d. -f2)

if [ "$SQLITE_MAJOR" -lt 3 ] || ([ "$SQLITE_MAJOR" -eq 3 ] && [ "$SQLITE_MINOR" -lt 35 ]); then
    echo "  ❌ sqlite3 版本 $SQLITE_VER 过低，ChromaDB 要求 >= 3.35.0"
    echo ""
    echo "  请先升级 sqlite3："
    echo "  ---- CentOS / Ubuntu 通用 ----"
    echo "  cd /tmp"
    echo "  wget https://www.sqlite.org/2024/sqlite-autoconf-3450000.tar.gz"
    echo "  tar xzf sqlite-autoconf-3450000.tar.gz"
    echo "  cd sqlite-autoconf-3450000"
    echo "  ./configure --prefix=/usr/local/sqlite3 --enable-fts5"
    echo "  make -j\$(nproc) && make install"
    echo ""
    echo "  export LD_LIBRARY_PATH=/usr/local/sqlite3/lib:\$LD_LIBRARY_PATH"
    echo "  export CFLAGS=\"-I/usr/local/sqlite3/include\""
    echo "  export LDFLAGS=\"-L/usr/local/sqlite3/lib\""
    echo ""
    echo "  # 然后重建虚拟环境："
    echo "  rm -rf backend/.venv"
    echo ""
    exit 1
fi
echo "  ✅ sqlite3 $SQLITE_VER（满足要求）"

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
